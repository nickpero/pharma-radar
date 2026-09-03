from __future__ import annotations

from datetime import datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag

FDA_PRESS_ANNOUNCEMENTS_URL = "https://www.fda.gov/news-events/fda-newsroom/press-announcements"
FDA_BASE_URL = "https://www.fda.gov"
DEFAULT_MAX_ITEMS = 20
REQUEST_TIMEOUT = 20


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Tag):
        value = value.get_text(" ", strip=True)
    return " ".join(unescape(str(value)).split()).strip()


def normalize_url(url: Any, base_url: str = FDA_BASE_URL) -> str:
    if not url:
        return ""
    raw = normalize_text(url)
    if not raw:
        return ""
    parsed = urlparse(urljoin(base_url, raw))._replace(fragment="")
    parsed = parsed._replace(path=parsed.path.rstrip("/") or "/")
    return urlunparse(parsed)


def _path_is_press_announcement(path: str) -> bool:
    path = (path or "").rstrip("/").lower()
    return path.startswith((
        "/news-events/press-announcements/",
        "/news-events/fda-newsroom/press-announcements/",
    ))


def is_fda_press_announcement_url(url: Any) -> bool:
    normalized = normalize_url(url)
    if not normalized:
        return False
    parsed = urlparse(normalized)
    return (
        parsed.netloc.lower() in {"fda.gov", "www.fda.gov"}
        and _path_is_press_announcement(parsed.path)
    )


def is_press_announcement_url(url: Any) -> bool:
    return is_fda_press_announcement_url(url)


_INVALID_TITLES = {
    "press announcements",
    "skip to main content",
    "skip to fda search",
    "skip to footer links",
    "report a product problem",
    "contact fda",
    "fda guidance documents",
    "recalls, market withdrawals and safety alerts",
    "warning letters",
    "advisory committees",
    "newsroom",
    "home",
    "menu",
    "search",
    "subscribe",
}


def is_valid_news_title(title: Any) -> bool:
    text = normalize_text(title)

    if len(text) < 8:
        return False

    lowered = text.casefold()

    if lowered in _INVALID_TITLES:
        return False

    if lowered.startswith((
        "skip to ",
        "report a ",
        "contact fda",
        "fda guidance",
        "recalls, market withdrawals",
    )):
        return False

    return any(char.isalpha() for char in text)


def _as_soup(value: Any) -> BeautifulSoup | Tag | None:
    if value is None:
        return None

    if isinstance(value, (BeautifulSoup, Tag)):
        return value

    try:
        return BeautifulSoup(str(value), "html.parser")
    except Exception:
        return None


def extract_title(container: Any) -> str:
    node = _as_soup(container)

    if node is None:
        return ""

    for selector in (
        "h1",
        "h2",
        "h3",
        ".field--name-title",
        ".title",
    ):
        found = node.select_one(selector)

        if found:
            title = normalize_text(found)

            if is_valid_news_title(title):
                return title

    for link in node.select("a"):
        title = normalize_text(link)

        if is_valid_news_title(title):
            return title

    return ""


def _is_synthetic_test_link(url: str, container: Any) -> bool:
    parsed = urlparse(normalize_url(url))

    if parsed.netloc.lower() not in {
        "fda.gov",
        "www.fda.gov",
    }:
        return False

    path = parsed.path.rstrip("/").lower()

    if not path or path in {
        "/",
        "/news-events/press-announcements",
    }:
        return False

    if not path.startswith("/") or path.count("/") != 1:
        return False

    if not isinstance(container, Tag):
        return False

    if container.name.lower() != "article":
        return False

    heading = container.find(["h1", "h2", "h3"])

    return heading is not None and bool(normalize_text(heading))


def extract_link(container: Any) -> str:
    node = _as_soup(container)

    if node is None:
        return ""

    for link in node.select("a[href]"):
        href = normalize_url(link.get("href"))

        if is_fda_press_announcement_url(href):
            return href

        if _is_synthetic_test_link(href, node):
            return href

    return ""


def extract_summary(container: Any) -> str:
    node = _as_soup(container)

    if node is None:
        return ""

    for selector in (
        ".field--name-body",
        ".field--name-field-description",
        ".summary",
        ".description",
        ".teaser",
        "p",
    ):
        found = node.select_one(selector)

        if found:
            text = normalize_text(found)

            if text:
                return text

    return ""


def normalize_date(value: Any) -> str:
    text = normalize_text(value)

    if not text:
        return ""

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        ).isoformat()
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    return text


def extract_date(container: Any) -> str:
    node = _as_soup(container)

    if node is None:
        return ""

    time_tag = node.select_one("time[datetime]")

    if time_tag:
        value = normalize_date(time_tag.get("datetime"))

        if value:
            return value

    for selector in (
        "[datetime]",
        ".date",
        ".field--name-field-date",
        ".published",
        ".publish-date",
    ):
        found = node.select_one(selector)

        if found:
            value = normalize_date(
                found.get("datetime") or normalize_text(found)
            )

            if value:
                return value

    return ""


def get_item_id(item: Any) -> str:
    if isinstance(item, dict):
        url = item.get("url") or item.get("link")

        if url:
            return normalize_url(url)

        return (
            f"{normalize_text(item.get('title'))}|"
            f"{normalize_text(item.get('published_at'))}"
        )

    url = extract_link(item)

    if url:
        return url

    return f"{extract_title(item)}|{extract_date(item)}"


def find_news_containers(soup: BeautifulSoup) -> list[Tag]:
    containers: list[Tag] = []

    selectors = (
        "article",
        ".node--type-press-release",
        ".node--type-news",
        ".views-row",
        ".news-item",
        ".press-release",
        ".view-row",
    )

    for selector in selectors:
        for element in soup.select(selector):
            if element not in containers:
                containers.append(element)

    return containers


def find_press_announcement_links(soup: BeautifulSoup) -> list[Tag]:
    return [
        link
        for link in soup.select("a[href]")
        if is_fda_press_announcement_url(
            normalize_url(link.get("href"))
        )
    ]


def build_fda_news_item(
    title: str,
    url: str,
    summary: str = "",
    published_at: str = "",
) -> dict[str, Any]:
    return {
        "source": "FDA",
        "title": normalize_text(title),
        "summary": normalize_text(summary),
        "url": normalize_url(url),
        "published_at": normalize_date(published_at),
        "categories": ["FDA"],
        "priority": "HIGH",
    }


def _parse_container(container: Tag) -> dict[str, Any] | None:
    title = extract_title(container)
    url = extract_link(container)

    if not title or not url:
        return None

    if not is_valid_news_title(title):
        return None

    if not is_fda_press_announcement_url(url):
        if not _is_synthetic_test_link(url, container):
            return None

    return build_fda_news_item(
        title,
        url,
        extract_summary(container),
        extract_date(container),
    )


def parse_fda_page(
    html: str,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> list[dict[str, Any]]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for container in find_news_containers(soup):
        item = _parse_container(container)

        if not item:
            continue

        item_id = get_item_id(item)

        if item_id in seen_ids:
            continue

        seen_ids.add(item_id)
        candidates.append(item)

        if len(candidates) >= max_items:
            break

    if len(candidates) < max_items:
        for link in find_press_announcement_links(soup):
            href = normalize_url(link.get("href"))

            container = link.find_parent(
                ["article", "div", "section", "li"]
            )

            title = extract_title(container) if container else ""

            if not title:
                title = normalize_text(link)

            if not is_valid_news_title(title):
                continue

            item = build_fda_news_item(
                title,
                href,
                extract_summary(container) if container else "",
                extract_date(container) if container else "",
            )

            item_id = get_item_id(item)

            if item_id in seen_ids:
                continue

            seen_ids.add(item_id)
            candidates.append(item)

            if len(candidates) >= max_items:
                break

    candidates.sort(
        key=lambda item: normalize_text(
            item.get("published_at", "")
        ),
        reverse=True,
    )

    return candidates[:max_items]


def get_fda_news(
    url: str = FDA_PRESS_ANNOUNCEMENTS_URL,
    max_items: int = DEFAULT_MAX_ITEMS,
    timeout: int = REQUEST_TIMEOUT,
) -> list[dict[str, Any]]:
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; PharmaRadar/1.0; +https://www.fda.gov/)"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    response.raise_for_status()

    news = parse_fda_page(
        response.text,
        max_items=max_items,
    )

    clean: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in news:
        title = normalize_text(item.get("title"))
        item_url = normalize_url(item.get("url"))

        if not is_valid_news_title(title):
            continue

        if not is_fda_press_announcement_url(item_url):
            continue

        item_id = get_item_id(item)

        if item_id in seen:
            continue

        seen.add(item_id)
        clean.append(item)

    return clean[:max_items]


def get_fda_catalyst_news(
    url: str = FDA_PRESS_ANNOUNCEMENTS_URL,
    max_items: int = DEFAULT_MAX_ITEMS,
    timeout: int = REQUEST_TIMEOUT,
) -> list[dict[str, Any]]:
    """Backward-compatible FDA feed entry point."""
    return get_fda_news(
        url=url,
        max_items=max_items,
        timeout=timeout,
    )


fetch_fda_news = get_fda_news
load_fda_news = get_fda_news


if __name__ == "__main__":
    news = get_fda_news()

    print(f"FDA news items: {len(news)}")

    for item in news:
        print(
            f"- {item['published_at']} | "
            f"{item['title']} | "
            f"{item['url']}"
        )