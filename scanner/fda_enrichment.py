"""Pharma Radar — FDA article enrichment."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re

import requests
from bs4 import BeautifulSoup

from scanner.fda_feed import get_fda_news, is_fda_press_announcement_url, normalize_text, normalize_date

FDA_HOSTS = {"www.fda.gov", "fda.gov"}
FDA_ALLOWED_PREFIXES = (
    "/news-events/press-announcements/",
    "/news-events/fda-newsroom/press-announcements/",
    "/drugs/resources-information-approved-drugs/",
)
ARTICLE_TIMEOUT = 12
MAX_ENRICH_ITEMS = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PharmaRadar/1.0; +https://www.fda.gov/)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _valid_fda_url(url: str) -> bool:
    try:
        parsed = urlparse(url or "")
    except Exception:
        return False
    if parsed.scheme != "https" or parsed.netloc.lower() not in FDA_HOSTS:
        return False
    path = (parsed.path or "").lower()
    return is_fda_press_announcement_url(url) or any(path.startswith(prefix) for prefix in FDA_ALLOWED_PREFIXES[2:])


def _extract_article_text(html: str, title: str = "") -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        node.decompose()
    candidates = []
    for selector in ("main", "article", ".field--name-body", ".field--name-field-body", ".usa-prose", "[role='main']"):
        candidates.extend(soup.select(selector))
    if not candidates:
        candidates = [soup.body or soup]
    best = max(candidates, key=lambda node: len(normalize_text(node.get_text(" ", strip=True))))
    text = normalize_text(best.get_text(" ", strip=True))
    normalized_title = normalize_text(title)
    if normalized_title and text.startswith(normalized_title):
        text = text[len(normalized_title):].strip(" -:")
    return text[:12000]


def _extract_article_published_at(html: str):
    """Extract the article's own publication timestamp when the RSS item lacks one."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")

    selectors = (
        ("meta", {"property": "article:published_time"}),
        ("meta", {"name": "article:published_time"}),
        ("meta", {"name": "date"}),
        ("meta", {"name": "dcterms.date"}),
        ("meta", {"name": "DC.date"}),
        ("meta", {"name": "publishdate"}),
        ("meta", {"name": "published"}),
    )
    for tag_name, attrs in selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get("content"):
            value = normalize_date(tag.get("content"))
            if value:
                return value

    for tag in soup.find_all("time"):
        value = tag.get("datetime") or tag.get_text(" ", strip=True)
        if value:
            normalized = normalize_date(value)
            if normalized:
                return normalized

    # FDA press announcements expose the release date as visible article text,
    # commonly immediately after "For Immediate Release:". This is the source
    # used when machine-readable metadata is absent.
    article_text = normalize_text(soup.get_text(" ", strip=True))
    patterns = (
        r"For Immediate Release:\s*((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})",
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, article_text, re.IGNORECASE)
        if match:
            normalized = normalize_date(match.group(1))
            if normalized:
                return normalized

    return None


def enrich_fda_news_item(news_item: dict) -> dict:
    """Fetch and attach official FDA article body text and publication time."""
    if not isinstance(news_item, dict):
        return news_item
    enriched = dict(news_item)
    url = enriched.get("url", "")
    if not _valid_fda_url(url):
        return enriched
    try:
        response = requests.get(url, headers=HEADERS, timeout=ARTICLE_TIMEOUT)
        response.raise_for_status()
        html = response.text
        content = _extract_article_text(html, enriched.get("title", ""))
        if not enriched.get("published_at"):
            published_at = _extract_article_published_at(html)
            if published_at:
                enriched["published_at"] = published_at
                enriched["event_timestamp"] = published_at
    except requests.RequestException as exc:
        print(f"FDA ENRICH ERROR url={url} error={type(exc).__name__}: {exc}", flush=True)
        return enriched
    if not content:
        return enriched
    enriched["content"] = content
    enriched["article_text"] = content
    enriched["body"] = content
    enriched["text"] = " ".join(part for part in (enriched.get("title", ""), enriched.get("summary", ""), content) if part)
    return enriched


def enrich_fda_news(news_items, max_items=MAX_ENRICH_ITEMS):
    """Enrich the newest official FDA items in parallel."""
    items = list(news_items or [])
    try:
        limit = max(0, int(max_items))
    except (TypeError, ValueError):
        limit = MAX_ENRICH_ITEMS
    targets, remainder = items[:limit], items[limit:]
    enriched = [None] * len(targets)
    if targets:
        with ThreadPoolExecutor(max_workers=min(8, len(targets))) as executor:
            futures = {executor.submit(enrich_fda_news_item, item): i for i, item in enumerate(targets)}
            for future in as_completed(futures):
                i = futures[future]
                try:
                    enriched[i] = future.result()
                except Exception as exc:
                    print(f"FDA ENRICH UNEXPECTED ERROR index={i}: {type(exc).__name__}: {exc}", flush=True)
                    enriched[i] = targets[i]
    return [item for item in enriched + remainder if item is not None]


def get_enriched_fda_news(max_news=50, max_pages=5, max_enrich=MAX_ENRICH_ITEMS):
    """Fetch the FDA feed and enrich its newest article bodies."""
    return enrich_fda_news(get_fda_news(max_news=max_news, max_pages=max_pages), max_items=max_enrich)
