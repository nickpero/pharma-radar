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
    """
    Normalize arbitrary text into a clean single-line string.
    """
    if value is None:
        return ""

    text = str(value)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_url(url: Any) -> str:
    """
    Normalize an FDA URL.

    Relative URLs are converted into absolute FDA URLs.
    """
    if url is None:
        return ""

    value = str(url).strip()

    if not value:
        return ""

    return urljoin(FDA_BASE_URL, value)


def _path_is_press_announcement(path: str) -> bool:
    """
    Return True when the URL path points to an FDA press announcement.
    """
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
    """
    Validate that a URL belongs to an FDA press announcement.

    This deliberately rejects generic FDA navigation pages.
    """
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
    """
    Backwards-compatible alias.
    """
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
    """
    Reject navigation/menu titles and accept real news headlines.
    """
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
    """
    Convert HTML content into BeautifulSoup.
    """
    if isinstance(content, BeautifulSoup):
        return content

    if isinstance(content, bytes):
        return BeautifulSoup(content, "html.parser")

    return BeautifulSoup(str(content), "html.parser")


def extract_title(container: Any) -> str:
    """
    Extract a news title from a container.
    """
    if container is None:
        return ""

    if isinstance(container, Tag):
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
            element = container.select