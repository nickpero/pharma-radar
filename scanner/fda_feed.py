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
# URL
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    url = normalize_text(url)

    if not url:
        return ""

    return urljoin(
        FDA_BASE_URL,
        url,
    )


def is_fda_press_announcement_url(
    url: str,
) -> bool:

    normalized = normalize_url(url)

    if not normalized:
        return False

    if not normalized.startswith(
        FDA_BASE_URL
    ):
        return False

    remainder = normalized[
        len(FDA_BASE_URL):
    ]

    if remainder and not remainder.startswith(
        "/"
    ):
        return False

    return True


# ---------------------------------------------------------------------------
# TITLE VALIDATION
# ---------------------------------------------------------------------------

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


def is_valid_news_title(
    title: str,
) -> bool:

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

    if any(
        lowered.startswith(term)
        for term in navigation_terms
    ):
        return False

    if len(title) < 10:
        return False

    return True


# ---------------------------------------------------------------------------
# ITEM ID
# ---------------------------------------------------------------------------

def get_item_id(
    item: Any,
) -> str:

    if isinstance(item, dict):

        url = normalize_url(
            item.get("url", "")
        )

        title = normalize_text(
            item.get("title", "")
        )

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
        identity = normalize_text(
            item
        ).lower()

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# SORT
# ---------------------------------------------------------------------------

def sort_fda_news(
    news: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    priority_rank = {
        "EXTREME": 4,
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    def sort_key(
        item: dict[str, Any],
    ) -> int:

        priority = normalize_text(
            item.get("priority", "")
        ).upper()

        return priority_rank.get(
            priority,
            0,
        )

    return sorted(
        news,
        key=sort_key,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# HTML EXTRACTION
# ---------------------------------------------------------------------------

def extract_title(
    node: Tag,
) -> str:

    heading = node.find(
        [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        ]
    )

    if heading:

        return normalize_text(
            heading.get_text(
                " ",
                strip=True,
            )
        )

    title_meta = node.find(
        "meta",
        attrs={
            "property": "og:title"
        },
    )

    if (
        title_meta
        and title_meta.get("content")
    ):

        return normalize_text(
            title_meta["content"]
        )

    return ""


def extract_link(
    node: Tag,
) -> str:

    link = node.find(
        "a",
        href=True,
    )

    if not link:
        return ""

    href = normalize_text(
        link.get("href", "")
    )

    return normalize_url(href)


def extract_summary(
    node: Tag,
) -> str:

    selectors = (
        "p",
        ".field--name-body",
        ".field--name-field-summary",
        ".field--name-field-dek",
        ".summary",
        ".description",
    )

    for selector in selectors:

        element = node.select_one(
            selector
        )

        if element:

            text = normalize_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if text:
                return text

    return ""


def extract_date(
    node: Tag,
) -> str:

    time_element = node.find(
        "time"
    )

    if time_element:

        datetime_value = (
            time_element.get(
                "datetime"
            )
        )

        if datetime_value:

            return normalize_date(
                datetime_value
            )

        text = normalize_text(
            time_element.get_text(
                " ",
                strip=True,
            )
        )

        if text:
            return normalize_date(text)

    selectors = (
        ".date",
        ".datetime",
        ".field--name-field-date",
        ".field--name-field-display-date",
    )

    for selector in selectors:

        element = node.select_one(
            selector
        )

        if element:

            text = normalize_text(
                element.get_text(
                    " ",
                    strip=True,
                )
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

    if not is_fda_press_announcement_url(
        url
    ):
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
# LINK-BASED FALLBACK
# ---------------------------------------------------------------------------

def build_fda_news_item_from_link(
    link: Tag,
    *,
    source: str = "FDA",
) -> dict[str, Any] | None:
    """
    Build an FDA news item directly from an announcement link.

    The live FDA page currently exposes announcement entries through links
    that may not be wrapped in <article>. This fallback makes the feed
    resilient to that page structure while preserving the article parser
    used by the unit tests.
    """

    href = normalize_url(
        link.get("href", "")
    )

    if not is_fda_press_announcement_url(
        href
    ):
        return None

    # Prefer the visible anchor text.
    title = normalize_text(
        link.get_text(
            " ",
            strip=True,
        )
    )

    if not is_valid_news_title(title):
        return None

    # Find the closest useful container.
    container: Tag | None = None

    for parent in link.parents:

        if not isinstance(parent, Tag):
            continue

        if parent.name in (
            "li",
            "article",
            "div",
            "section",
        ):
            container = parent
            break

    published_at = ""

    summary = ""

    if container is not None:

        published_at = extract_date(
            container
        )

        summary = extract_summary(
            container
        )

    # Some FDA pages place the date in the
    # same textual block as the announcement.
    if not published_at and container:

        text = normalize_text(
            container.get_text(
                " ",
                strip=True,
            )
        )

        date_match = re.search(
            r"\b("
            r"January|February|March|April|May|June|"
            r"July|August|September|October|November|December"
            r")\s+"
            r"\d{1,2},\s+\d{4}\b",
            text,
        )

        if date_match:

            published_at = normalize_date(
                date_match.group(0)
            )

    return {
        "source": source,
        "title": title,
        "summary": summary,
        "url": href,
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

    results: list[
        dict[str, Any]
    ] = []

    seen_urls: set[str] = set()

    seen_ids: set[str] = set()

    # =======================================================================
    # 1. PRIMARY PARSER
    # =======================================================================

    candidates: list[Tag] = []

    for article in soup.find_all(
        "article"
    ):

        candidates.append(article)

    if not candidates:

        selectors = (
            ".node--type-press-announcement",
            ".views-row",
            ".news-item",
            ".press-announcement",
        )

        for selector in selectors:

            found = soup.select(
                selector
            )

            if found:

                candidates.extend(
                    element
                    for element in found
                    if isinstance(
                        element,
                        Tag,
                    )
                )

            if candidates:
                break

    for candidate in candidates:

        item = build_fda_news_item(
            candidate
        )

        if item is None:
            continue

        canonical_url = normalize_url(
            item.get("url", "")
        ).lower()

        if not canonical_url:
            continue

        item_id = get_item_id(
            item
        )

        if canonical_url in seen_urls:
            continue

        if item_id in seen_ids:
            continue

        seen_urls.add(
            canonical_url
        )

        seen_ids.add(
            item_id
        )

        results.append(item)

    # =======================================================================
    # 2. LIVE FDA LINK FALLBACK
    # =======================================================================

    # If the article/container parser did not find anything, inspect every
    # FDA announcement link directly.
    #
    # This is intentionally a fallback so the existing unit-test behavior
    # remains unchanged.
    # =======================================================================

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = normalize_url(
            link.get("href", "")
        )

        # For live FDA pages, prioritize actual press-announcement paths.
        if "/news-events/press-announcements/" not in href:
            continue

        item = build_fda_news_item_from_link(
            link
        )

        if item is None:
            continue

        canonical_url = normalize_url(
            item.get("url", "")
        ).lower()

        if not canonical_url:
            continue

        item_id = get_item_id(
            item
        )

        if canonical_url in seen_urls:
            continue

        if item_id in seen_ids:
            continue

        seen_urls.add(
            canonical_url
        )

        seen_ids.add(
            item_id
        )

        results.append(item)

        if len(results) >= max_items:
            break

    # =======================================================================
    # 3. FINAL SORT + LIMIT
    # =======================================================================

    results = sort_fda_news(
        results
    )

    return results[:max_items]


# ---------------------------------------------------------------------------
# LIVE FDA FEED
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
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
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

    return get_fda_news(
        max_items=max_items,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# BACKWARD COMPATIBILITY
# ---------------------------------------------------------------------------

fetch_fda_news = get_fda_news

fetch_fda_catalyst_news = (
    get_fda_catalyst_news
)


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
            f"{item['priority']} | "
            f"{item['title']} | "
            f"{item['url']}"
        )