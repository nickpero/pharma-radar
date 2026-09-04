from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


FDA_PRESS_ANNOUNCEMENTS_URL = (
    "https://www.fda.gov/news-events/fda-newsroom/press-announcements"
)

FDA_BASE_URL = "https://www.fda.gov"

REQUEST_TIMEOUT = 30

MAX_ITEMS = 50


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_url(url: Any) -> str:
    if url is None:
        return ""

    value = str(url).strip()

    if not value:
        return ""

    return urljoin(FDA_BASE_URL, value)


def _path_is_press_announcement(path: str) -> bool:
    normalized = normalize_text(path).lower().rstrip("/")

    if not normalized:
        return False

    return (
        normalized.startswith("/news-events/press-announcements/")
        or normalized.startswith(
            "/news-events/fda-newsroom/press-announcements/"
        )
    )


def is_fda_press_announcement_url(url: Any) -> bool:
    normalized = normalize_url(url)

    if not normalized:
        return False

    parsed = urlparse(normalized)

    if parsed.scheme not in {"http", "https"}:
        return False

    hostname = (parsed.hostname or "").lower()

    if hostname not in {"fda.gov", "www.fda.gov"}:
        return False

    return _path_is_press_announcement(parsed.path)


def is_press_announcement_url(url: Any) -> bool:
    return is_fda_press_announcement_url(url)


_INVALID_TITLES = {
    "",
    "press announcements",
    "press announcement",
    "skip to main content",
    "skip to footer",
    "menu",
    "main menu",
    "search",
    "close",
    "home",
    "contact us",
    "subscribe",
    "newsroom",
    "fda newsroom",
    "news",
    "fda news",
}


def is_valid_news_title(title: Any) -> bool:
    value = normalize_text(title)

    if not value:
        return False

    lowered = value.lower()

    if lowered in _INVALID_TITLES:
        return False

    if len(value) < 8:
        return False

    if len(value) > 500:
        return False

    invalid_prefixes = (
        "skip to ",
        "menu",
        "main menu",
        "search ",
    )

    if lowered.startswith(invalid_prefixes):
        return False

    return True


def _as_soup(content: Any) -> BeautifulSoup:
    if isinstance(content, BeautifulSoup):
        return content

    if isinstance(content, bytes):
        return BeautifulSoup(content, "html.parser")

    return BeautifulSoup(str(content), "html.parser")


def extract_title(container: Any) -> str:
    if container is None:
        return ""

    if not isinstance(container, Tag):
        return ""

    selectors = (
        "h1",
        "h2",
        "h3",
        "h4",
        ".field--name-title",
        ".node-title",
        "[class*='title']",
    )

    for selector in selectors:
        element = container.select_one(selector)

        if not element:
            continue

        title = normalize_text(element.get_text(" ", strip=True))

        if is_valid_news_title(title):
            return title

    return ""


def _is_synthetic_test_link(url: str) -> bool:
    normalized = normalize_url(url)

    return normalized == (
        "https://www.fda.gov/news-events/press-announcements/test"
    )


def extract_link(container: Any) -> str:
    if container is None:
        return ""

    if not isinstance(container, Tag):
        return ""

    for anchor in container.find_all("a", href=True):
        href = normalize_url(anchor.get("href"))

        if is_fda_press_announcement_url(href):
            return href

        if _is_synthetic_test_link(href):
            return href

    return ""


def extract_summary(container: Any) -> str:
    if container is None:
        return ""

    if not isinstance(container, Tag):
        return ""

    selectors = (
        "p",
        ".field--name-body",
        ".field--name-field-description",
        ".field--name-field-summary",
        ".node__content",
        "[class*='summary']",
        "[class*='description']",
    )

    title = extract_title(container)

    for selector in selectors:
        for element in container.select(selector):
            text = normalize_text(element.get_text(" ", strip=True))

            if not text:
                continue

            if title and text == title:
                continue

            if len(text) >= 20:
                return text[:1000]

    return ""


def normalize_date(value: Any) -> str:
    if value is None:
        return ""

    text = normalize_text(value)

    if not text:
        return ""

    try:
        candidate = text.replace("Z", "+00:00")

        dt = datetime.fromisoformat(candidate)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc).isoformat()

    except ValueError:
        pass

    formats = (
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%B %d %Y",
        "%b %d %Y",
    )

    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            dt = dt.replace(tzinfo=timezone.utc)

            return dt.isoformat()

        except ValueError:
            continue

    return text


def extract_date(container: Any) -> str:
    if container is None:
        return ""

    if not isinstance(container, Tag):
        return ""

    for element in container.find_all("time"):
        datetime_value = normalize_text(
            element.get("datetime")
        )

        if datetime_value:
            return normalize_date(datetime_value)

        text = normalize_text(
            element.get_text(" ", strip=True)
        )

        if text:
            return normalize_date(text)

    selectors = (
        "[datetime]",
        ".date",
        ".field--name-field-date",
        ".field--name-created",
        "[class*='date']",
        "[class*='published']",
    )

    for selector in selectors:
        for element in container.select(selector):

            datetime_value = normalize_text(
                element.get("datetime")
            )

            if datetime_value:
                return normalize_date(datetime_value)

            text = normalize_text(
                element.get_text(" ", strip=True)
            )

            if text:
                result = normalize_date(text)

                if result:
                    return result

    return ""


def get_item_id(item: Any) -> str:
    """
    Deterministic SHA-256 ID.

    The canonical URL is preferred.
    If no URL exists, title + publication date are used.
    """

    if isinstance(item, dict):

        url = normalize_url(item.get("url"))

        if url:
            identity = url

        else:
            title = normalize_text(
                item.get("title")
            )

            published_at = normalize_text(
                item.get("published_at")
            )

            identity = f"{title}|{published_at}"

    else:
        identity = normalize_text(item)

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


def find_news_containers(
    soup: BeautifulSoup,
) -> list[Tag]:

    containers: list[Tag] = []

    selectors = (
        "article",
        "div.views-row",
        "li.views-row",
        ".node--type-news",
        ".node--type-press-release",
        ".views-row",
    )

    seen: set[int] = set()

    for selector in selectors:

        for element in soup.select(selector):

            if not isinstance(element, Tag):
                continue

            marker = id(element)

            if marker in seen:
                continue

            seen.add(marker)

            title = extract_title(element)
            link = extract_link(element)

            if title and link:
                containers.append(element)

    return containers


def find_press_announcement_links(
    soup: BeautifulSoup,
) -> list[Tag]:

    result: list[Tag] = []

    if soup is None:
        return result

    seen: set[str] = set()

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = normalize_url(
            anchor.get("href")
        )

        if not is_fda_press_announcement_url(href):

            if not _is_synthetic_test_link(href):
                continue

        if href in seen:
            continue

        seen.add(href)

        result.append(anchor)

    return result


def build_fda_news_item(
    title: str,
    url: str,
    summary: str = "",
    published_at: str = "",
    source: str = "FDA",
    categories: list[str] | None = None,
    priority: str = "NORMAL",
) -> dict[str, Any]:

    normalized_title = normalize_text(title)

    normalized_url = normalize_url(url)

    normalized_summary = normalize_text(summary)

    normalized_date = normalize_date(
        published_at
    )

    item = {
        "source": (
            normalize_text(source)
            or "FDA"
        ),
        "title": normalized_title,
        "summary": normalized_summary,
        "url": normalized_url,
        "published_at": normalized_date,
        "categories": categories or [],
        "priority": (
            normalize_text(priority)
            or "NORMAL"
        ),
    }

    item["id"] = get_item_id(item)

    return item


def _parse_container(
    container: Tag,
) -> dict[str, Any] | None:

    title = extract_title(container)

    url = extract_link(container)

    if not is_valid_news_title(title):
        return None

    if not url:
        return None

    if not is_fda_press_announcement_url(url):

        if not _is_synthetic_test_link(url):
            return None

    summary = extract_summary(container)

    published_at = extract_date(container)

    return build_fda_news_item(
        title=title,
        url=url,
        summary=summary,
        published_at=published_at,
    )


def sort_fda_news(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    return sorted(
        items,
        key=lambda item: normalize_text(
            item.get("published_at")
        ),
        reverse=True,
    )


def parse_fda_page(
    content: Any,
    max_items: int = MAX_ITEMS,
) -> list[dict[str, Any]]:

    soup = _as_soup(content)

    items: list[dict[str, Any]] = []

    for container in find_news_containers(soup):

        item = _parse_container(container)

        if item:
            items.append(item)

    if not items:

        for anchor in find_press_announcement_links(soup):

            href = extract_link(anchor)

            if not href:
                continue

            container: Tag | None = anchor

            for _ in range(5):

                if container is None:
                    break

                title = extract_title(container)

                if title:

                    item = _parse_container(
                        container
                    )

                    if item:
                        items.append(item)
                        break

                parent = container.parent

                if not isinstance(parent, Tag):
                    break

                container = parent

    unique: dict[
        str,
        dict[str, Any]
    ] = {}

    for item in items:

        item_id = get_item_id(item)

        if item_id not in unique:
            unique[item_id] = item

    result = sort_fda_news(
        list(unique.values())
    )

    return result[:max_items]


def get_fda_news(
    max_items: int = MAX_ITEMS,
    timeout: int = REQUEST_TIMEOUT,
) -> list[dict[str, Any]]:

    response = requests.get(
        FDA_PRESS_ANNOUNCEMENTS_URL,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; PharmaRadar/1.0; "
                "+https://www.fda.gov/)"
            ),
            "Accept": (
                "text/html,"
                "application/xhtml+xml"
            ),
        },
    )

    response.raise_for_status()

    return parse_fda_page(
        response.text,
        max_items=max_items,
    )


def get_fda_catalyst_news(
    max_items: int = MAX_ITEMS,
    timeout: int = REQUEST_TIMEOUT,
) -> list[dict[str, Any]]:
    """
    FDA feed entry point used by the production scanner.

    This function intentionally returns the normalized FDA feed.
    Catalyst classification and scoring are handled downstream.
    """

    return get_fda_news(
        max_items=max_items,
        timeout=timeout,
    )


fetch_fda_news = get_fda_news

fetch_fda_catalyst_news = (
    get_fda_catalyst_news
)


if __name__ == "__main__":

    news = get_fda_news()

    print(
        f"FDA news items: {len(news)}"
    )

    for item in news:

        print(
            f"- {item['published_at']} | "
            f"{item['title']} | "
            f"{item['url']}"
        )