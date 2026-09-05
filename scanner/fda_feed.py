"""Pharma Radar — FDA Feed."""

from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime
from html import unescape
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

FDA_NEWS_URL = "https://www.fda.gov/news-events/fda-newsroom/press-announcements"
FDA_PRESS_ANNOUNCEMENTS_URL = FDA_NEWS_URL
FDA_NEWSROOM_URL = "https://www.fda.gov/news-events/fda-newsroom"
FDA_DRUGS_URL = "https://www.fda.gov/drugs/news-events-human-drugs/drug-safety-and-availability"
FDA_WHATS_NEW_URL = "https://www.fda.gov/drugs/news-events-human-drugs/whats-new-related-drugs"
FDA_NOTABLE_APPROVALS_URL = "https://www.fda.gov/drugs/news-events-human-drugs/notable-approvals-drugs"
FDA_NOVEL_APPROVALS_2026_URL = "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2026"
FDA_ONCOLOGY_APPROVALS_URL = "https://www.fda.gov/drugs/resources-information-approved-drugs/oncology-cancerhematologic-malignancies-approval-notifications"

DEFAULT_MAX_NEWS = 50
DEFAULT_MAX_PAGES = 5
REQUEST_TIMEOUT = 20
FETCH_RETRIES = 3
RETRY_DELAY_SECONDS = 1
USER_AGENT = "Mozilla/5.0 (compatible; PharmaRadar/1.0; +https://github.com/)"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
})

CATEGORY_KEYWORDS = {
    "APPROVAL": ["approved", "approval", "approves", "authorizes", "authorized", "authorization", "cleared", "clearance"],
    "REJECTION": ["rejected", "rejection", "not approved", "complete response letter", "crl", "refused", "refusal", "denied", "denial"],
    "SAFETY": ["safety", "warning", "recall", "adverse event", "adverse events", "risk", "boxed warning", "contamination", "death", "deaths"],
    "CLINICAL": ["clinical trial", "clinical study", "clinical results", "trial results", "efficacy", "endpoint", "phase 1", "phase 2", "phase 3", "phase i", "phase ii", "phase iii"],
    "LABEL": ["label expansion", "expanded indication", "expanded use", "indication", "labeling", "label"],
}
CATEGORY_PRIORITY = ["APPROVAL", "REJECTION", "SAFETY", "CLINICAL", "LABEL"]
PRIORITY_BY_CATEGORY = {"APPROVAL": "EXTREME", "REJECTION": "EXTREME", "SAFETY": "EXTREME", "CLINICAL": "HIGH", "LABEL": "HIGH"}


def normalize_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unescape(str(value))).strip()


def normalize_url(url, base_url=FDA_NEWS_URL) -> str:
    if not url:
        return ""
    return urljoin(base_url, unescape(str(url)).strip())


def is_fda_press_announcement_url(url) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(str(url))
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower().rstrip("/")
    if host not in {"www.fda.gov", "fda.gov"}:
        return False
    return path.startswith("/news-events/fda-newsroom/press-announcements/")


def is_valid_news_title(title) -> bool:
    title = normalize_text(title)
    if not title or len(title) < 4 or len(title) > 500:
        return False
    return title.lower() not in {"home", "news", "search", "menu", "main menu", "skip to main content", "contact fda", "about fda", "resources", "subscribe"}


def get_item_id(item) -> str:
    if not isinstance(item, dict):
        item = {"value": str(item)}
    raw = "|".join([normalize_text(item.get("title", "")), normalize_text(item.get("url", "")), normalize_text(item.get("published_at", ""))])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_date(value):
    if not value:
        return None
    text = normalize_text(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).isoformat()
        except ValueError:
            continue
    return text


def normalize_date(value):
    return _parse_date(value)


def _extract_date(container):
    if container is None:
        return None
    time_tag = container.find("time")
    if time_tag is not None:
        value = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        if value:
            return _parse_date(value)
    for attr in ("datetime", "date", "data", "published", "published_at"):
        value = container.get(attr)
        if value:
            return _parse_date(value)
    text = normalize_text(container.get_text(" ", strip=True))
    patterns = [r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b", r"\b\d{1,2}/\d{1,2}/\d{4}\b", r"\b\d{4}-\d{2}-\d{2}\b"]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _parse_date(match.group(0))
    return None


def extract_link(article, base_url=FDA_NEWS_URL) -> str:
    if article is None:
        return ""
    if isinstance(article, str):
        return normalize_url(article, base_url)
    link = article if getattr(article, "name", None) == "a" else article.find("a", href=True)
    return normalize_url(link.get("href"), base_url) if link is not None and link.get("href") else ""


def extract_title(article) -> str:
    if article is None:
        return ""
    heading = article.find(["h1", "h2", "h3", "h4", "h5"])
    if heading is not None:
        title = normalize_text(heading.get_text(" ", strip=True))
        if is_valid_news_title(title):
            return title
    link = article.find("a", href=True)
    if link is not None:
        title = normalize_text(link.get_text(" ", strip=True))
        if is_valid_news_title(title):
            return title
    return ""


def _extract_summary(container, title="") -> str:
    if container is None:
        return ""
    for paragraph in container.find_all("p"):
        text = normalize_text(paragraph.get_text(" ", strip=True))
        if text and text != title:
            return text[:2000]
    return ""


def extract_summary(article) -> str:
    return _extract_summary(article, extract_title(article))


def extract_date(article):
    return _extract_date(article)


def classify_fda_text(text):
    normalized = normalize_text(text).lower()
    return [category for category, keywords in CATEGORY_KEYWORDS.items() if any(k.lower() in normalized for k in keywords)]


def get_fda_priority(categories):
    normalized = {str(x).upper() for x in (categories or [])}
    for category in CATEGORY_PRIORITY:
        if category in normalized:
            return PRIORITY_BY_CATEGORY[category]
    return "LOW"


def calculate_priority(categories):
    return get_fda_priority(categories)


def build_fda_news_item(title, url, published_at=None, summary="", source="FDA"):
    title = normalize_text(title)
    url = normalize_url(url)
    summary = normalize_text(summary)
    categories = classify_fda_text(f"{title} {summary}")
    item = {"source": source, "title": title, "summary": summary, "url": url, "published_at": _parse_date(published_at), "categories": categories, "priority": get_fda_priority(categories)}
    item["item_id"] = get_item_id(item)
    return item


def _candidate_containers(soup):
    containers = []
    for selector in ("article", ".views-row", ".node", "li"):
        containers.extend(soup.select(selector))
    return containers or soup.find_all(["h2", "h3", "h4"])


def _parse_container(container, base_url=FDA_NEWS_URL):
    title = extract_title(container)
    if not is_valid_news_title(title):
        return None
    url = extract_link(container, base_url)
    if not url:
        return None
    return build_fda_news_item(title, url, _extract_date(container), _extract_summary(container, title))


def _parse_anchor_fallback(soup, base_url=FDA_NEWS_URL):
    results = []
    for link in soup.find_all("a", href=True):
        title = normalize_text(link.get_text(" ", strip=True))
        href = normalize_url(link.get("href"), base_url)
        if is_valid_news_title(title) and href and not href.startswith("#"):
            results.append(build_fda_news_item(title, href))
    return results


def parse_fda_page(html_content, base_url=FDA_NEWS_URL, max_items=DEFAULT_MAX_NEWS):
    if not html_content:
        return []
    try:
        max_items = int(max_items)
    except (TypeError, ValueError):
        max_items = DEFAULT_MAX_NEWS
    if max_items <= 0:
        return []
    soup = BeautifulSoup(str(html_content), "html.parser")
    results = []
    for container in _candidate_containers(soup):
        item = _parse_container(container, base_url)
        if item is not None:
            results.append(item)
        if len(results) >= max_items:
            break
    if len(results) < max_items:
        results.extend(_parse_anchor_fallback(soup, base_url))
    return deduplicate_fda_news(results)[:max_items]


def _fetch_html(url, params=None):
    last_error = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            response = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
            status = response.status_code
            final_url = str(response.url)
            content = response.text or ""
            print(f"FDA FETCH attempt={attempt}/{FETCH_RETRIES} status={status} bytes={len(content)} url={final_url}", flush=True)
            response.raise_for_status()
            if content.strip():
                return content
            last_error = requests.RequestException(f"Empty FDA response for {final_url} (HTTP {status})")
        except requests.RequestException as exc:
            last_error = exc
            print(f"FDA FETCH ERROR attempt={attempt}/{FETCH_RETRIES}: {type(exc).__name__}: {exc}", flush=True)
        if attempt < FETCH_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS * attempt)
    raise last_error or requests.RequestException(f"Unable to fetch {url}")


def _filter_press_announcement_items(items):
    return [item for item in items if is_fda_press_announcement_url(item.get("url"))]


def _fetch_press_announcements(max_news=DEFAULT_MAX_NEWS, max_pages=DEFAULT_MAX_PAGES):
    try:
        max_news = int(max_news)
        max_pages = max(1, int(max_pages))
    except (TypeError, ValueError):
        max_news, max_pages = DEFAULT_MAX_NEWS, DEFAULT_MAX_PAGES
    if max_news <= 0:
        return []
    results = []
    for page in range(max_pages):
        if len(results) >= max_news:
            break
        try:
            html = _fetch_html(FDA_PRESS_ANNOUNCEMENTS_URL, {"page": page})
        except requests.RequestException:
            continue
        parsed = _filter_press_announcement_items(parse_fda_page(html, FDA_PRESS_ANNOUNCEMENTS_URL, max_news))
        results.extend(parsed)
        print(f"FDA PRESS PAGE page={page} parsed={len(parsed)} cumulative={len(results)}", flush=True)
        if not parsed:
            break
    results = deduplicate_fda_news(results)[:max_news]
    if results:
        return results
    try:
        html = _fetch_html(FDA_NEWSROOM_URL)
    except requests.RequestException:
        return []
    parsed = parse_fda_page(html, FDA_NEWSROOM_URL, max_news * 2)
    filtered = _filter_press_announcement_items(parsed)
    print(f"FDA NEWSROOM FALLBACK parsed={len(parsed)} press={len(filtered)}", flush=True)
    return deduplicate_fda_news(filtered)[:max_news]


def _fetch_source_items(url, max_items=DEFAULT_MAX_NEWS):
    try:
        return parse_fda_page(_fetch_html(url), url, max_items)
    except requests.RequestException:
        return []


def _fetch_novel_approvals_2026(max_items=DEFAULT_MAX_NEWS):
    try:
        soup = BeautifulSoup(_fetch_html(FDA_NOVEL_APPROVALS_2026_URL), "html.parser")
    except requests.RequestException:
        return []
    results = []
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        texts = [normalize_text(c.get_text(" ", strip=True)) for c in cells]
        title = texts[0]
        if not is_valid_news_title(title):
            continue
        link = row.find("a", href=True)
        url = normalize_url(link.get("href"), FDA_NOVEL_APPROVALS_2026_URL) if link else FDA_NOVEL_APPROVALS_2026_URL
        results.append(build_fda_news_item(title, url, texts[-1] if len(texts) >= 3 else None, " | ".join(x for x in texts[1:] if x)))
        if len(results) >= max_items:
            break
    return deduplicate_fda_news(results)


def deduplicate_fda_news(news_items):
    unique, seen_ids, seen_urls, seen_titles = [], set(), set(), set()
    for item in news_items or []:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        normalized["title"] = normalize_text(normalized.get("title", ""))
        normalized["url"] = normalize_url(normalized.get("url", ""))
        normalized["summary"] = normalize_text(normalized.get("summary", ""))
        if not is_valid_news_title(normalized["title"]):
            continue
        normalized["item_id"] = normalized.get("item_id") or get_item_id(normalized)
        url_key, title_key = normalized["url"].lower(), normalized["title"].lower()
        if normalized["item_id"] in seen_ids or (url_key and url_key in seen_urls) or title_key in seen_titles:
            continue
        seen_ids.add(normalized["item_id"])
        if url_key:
            seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(normalized)
    return unique


def _sort_key(item):
    value = item.get("published_at")
    if value:
        try:
            return (1, datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None))
        except ValueError:
            pass
    rank = {"EXTREME": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
    return (0, rank.get(str(item.get("priority", "LOW")).upper(), 0))


def sort_fda_news(news_items):
    return sorted(news_items or [], key=_sort_key, reverse=True)


def get_fda_news(max_news=DEFAULT_MAX_NEWS, max_pages=DEFAULT_MAX_PAGES, max_items=None):
    if max_items is not None:
        max_news = max_items
    return sort_fda_news(_fetch_press_announcements(max_news=max_news, max_pages=max_pages))[:max_news]
