from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


FDA_PRESS_ANNOUNCEMENTS_URL = (
    "https://www.fda.gov/news-events/fda-newsroom/press-announcements"
)

FDA_BASE_URL = "https://www.fda.gov"

DEFAULT_TIMEOUT = 20

FDA_ALLOWED_PATH_PREFIXES = (
    "/news-events/press-announcements/",
    "/news-events/fda-newsroom/press-announcements/",
)

INVALID_TITLES = {
    "",
    "press announcements",
    "skip to main content",
    "skip to footer",
    "menu",
    "search",
    "home",
    "newsroom",
}


# ---------------------------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------------------------

def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_date(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        dt = value

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc).isoformat()

    text = normalize_text(value)

    if not text:
        return ""

    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)

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
        "%Y/%m/%d",
    )

    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue

    return text


# ---------------------------------------------------------------------------
# URL / TITLE VALIDATION
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    url = normalize_text(url)

    if not url:
        return ""

    return urljoin(FDA_BASE_URL, url)


def is_fda_press_announcement_url(url: str) -> bool:
    normalized = normalize_url(url)

    if not normalized:
        return False

    if not normalized.startswith(FDA_BASE_URL):
        return False

    path = normalized[len(FDA_BASE_URL):]

    return any(
        path.startswith(prefix)
        for prefix in FDA_ALLOWED_PATH_PREFIXES
    )


def is_valid_news_title(title: str) -> bool:
    title = normalize_text(title)

    if not title:
        return False

    lowered = title.lower()

    if lowered in INVALID_TITLES:
        return False

    navigation_terms = (
        "skip to ",
        "menu",
        "search",
        "sign in",
        "subscribe",
    )

    if any(lowered.startswith(term) for term in navigation_terms):
        return False

    if len(title) < 10:
        return False

    return True


# ---------------------------------------------------------------------------
# ITEM ID
# ---------------------------------------------------------------------------

def get_item_id(item: Any) -> str:
    """
    Return a deterministic SHA-256 identifier.

    The canonical URL is the primary identity.
    Title/date are used as fallback when URL is unavailable.
    """

    if isinstance(item, dict):
        url = normalize_url(item.get("url", ""))
        title = normalize_text(item.get("title", ""))
        published_at = normalize_date(
            item.get("published_at", "")
        )

        if url:
            identity = url.lower()
        else:
            identity = "|".join(
                (
                    title.lower(),
                    published_at.lower(),
                )
            )
    else:
        identity = normalize_text(item).lower()

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# SORTING
# ---------------------------------------------------------------------------

def sort_fda_news(
    news: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Sort FDA news newest first.

    Items without a valid date are kept after dated items.
    """

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        published_at = normalize_date(
            item.get("published_at", "")
        )

        if not published_at:
            return (0, "")

        return (1, published_at)

    return sorted(
        news,
        key=sort_key,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# HTML EXTRACTION
# ---------------------------------------------------------------------------

def extract_title(node: Tag) -> str:
    heading = node.find(
        ["h1", "h2", "h3", "h4", "h5", "h6"]
    )

    if heading:
        return normalize_text(
            heading.get_text(" ", strip=True)
        )

    title_meta = node.find(
        "meta",
        attrs={"property": "og:title"},
    )

    if title_meta and title_meta.get("content"):
        return normalize_text(
            title_meta["content"]
        )

    return ""


def extract_link(node: Tag) -> str:
    link = node.find("a", href=True)

    if not link:
        return ""

    href = normalize_text(
        link.get("href", "")
    )

    return normalize_url(href)


def extract_summary(node: Tag) -> str:
    for selector in (
        "p",
        ".field--name-body",
        ".field--name-field-summary",
        ".field--name-field-dek",
        ".summary",
        ".description",
    ):
        element = node.select_one(selector)

        if element:
            text = normalize_text(
                element.get_text(" ", strip=True)
            )

            if text:
                return text

    return ""


def extract_date(node: Tag) -> str:
    time_element = node.find("time")

    if time_element:
        datetime_value = time_element.get("datetime")

        if datetime_value:
            return normalize_date(datetime_value)

        text = normalize_text(
            time_element.get_text(" ", strip=True)
        )

        if text:
            return normalize_date(text)

    for selector in (
        ".date",
        ".datetime",
        ".field--name-field-date",
        ".field--name-field-display-date",
    ):
        element = node.select_one(selector)

        if element:
            text = normalize_text(
                element.get_text(" ", strip=True)
            )

            if text:
                return normalize_date(text)

    return ""


# ---------------------------------------------------------------------------
# ITEM BUILDING
# ---------------------------------------------------------------------------

def build_fda_news_item(
    node: Tag,
    *,
    source: str = "FDA",
) -> dict[str, Any] | None:

    title = extract_title(node)
    url = extract_link(node)
    summary = extract_summary(node)
    published_at = extract_date(node)

    if not is_valid_news_title(title):
        return None

    if not is_fda_press_announcement_url(url):
        return None

    return {
        "source": source,
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": published_at,
        "categories": [
            "FDA",
            "PRESS_ANNOUNCEMENT",
        ],
        "priority": "HIGH",
    }


# ---------------------------------------------------------------------------
# PARSER
# ---------------------------------------------------------------------------

def parse_fda_page(
    html: str,
    *,
    max_items: int = 50,
) -> list[dict[str, Any]]:

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates: list[Tag] = []

    for article in soup.find_all("article"):
        candidates.append(article)

    if not candidates:
        selectors = (
            ".node--type-press-announcement",
            ".views-row",
            ".news-item",
            ".press-announcement",
        )

        for selector in selectors:
            found = soup.select(selector)

            if found:
                candidates.extend(
                    element
                    for element in found
                    if isinstance(element, Tag)
                )

            if candidates:
                break

    results: list[dict[str, Any]] = []

    seen_urls: set[str] = set()
    seen_ids: set[str] = set()

    for candidate in candidates:

        item = build_fda_news_item(candidate)

        if item is None:
            continue

        canonical_url = normalize_url(
            item.get("url", "")
        ).lower()

        if not canonical_url:
            continue

        item_id = get_item_id(item)

        # Primary duplicate protection.
        if canonical_url in seen_urls:
            continue

        # Secondary duplicate protection.
        if item_id in seen_ids:
            continue

        seen_urls.add(canonical_url)
        seen_ids.add(item_id)

        results.append(item)

    results = sort_fda_news(results)

    return results[:max_items]


# ---------------------------------------------------------------------------
# LIVE FDA REQUEST
# ---------------------------------------------------------------------------

def get_fda_news(
    *,
    max_items: int = 50,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:

    response = requests.get(
        FDA_PRESS_ANNOUNCEMENTS_URL,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; PharmaRadar/1.0; "
                "+https://www.fda.gov/)"
            )
        },
    )

    response.raise_for_status()

    return parse_fda_page(
        response.text,
        max_items=max_items,
    )


# ---------------------------------------------------------------------------
# FDA CATALYST FEED
# ---------------------------------------------------------------------------

def get_fda_catalyst_news(
    *,
    max_items: int = 50,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    """
    Compatibility entry point used by the FDA catalyst pipeline.
    """

    return get_fda_news(
        max_items=max_items,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# BACKWARD COMPATIBILITY ALIASES
# ---------------------------------------------------------------------------

fetch_fda_news = get_fda_news
fetch_fda_catalyst_news = get_fda_catalyst_news


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    news = get_fda_news()

    print(
        f"FDA items: {len(news)}"
    )

    for item in news:
        print(
            f"{item['published_at']} | "
            f"{item['title']} | "
            f"{item['url']}"
        )