"""
Pharma Radar — FDA Feed

Layer di acquisizione e normalizzazione delle FDA News.

Responsabilità:
- recuperare le FDA Press Announcements;
- estrarre titolo, URL, data e summary;
- normalizzare i testi;
- classificare gli articoli in modo compatibile con il Radar;
- deduplicare gli elementi;
- fornire le API legacy utilizzate dai test e dal pipeline.

IMPORTANTE
---------
parse_fda_page()
    È un parser GENERICO di HTML. Non deve imporre che gli URL
    appartengano alle Press Announcements, perché viene utilizzato
    anche dai test unitari con HTML sintetico.

get_fda_news()
    È invece il feed LIVE ufficiale utilizzato dal Radar e restituisce
    esclusivamente URL riconducibili alle FDA Press Announcements.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from html import unescape
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

FDA_NEWS_URL = (
    "https://www.fda.gov/news-events/"
    "fda-newsroom/press-announcements"
)

FDA_PRESS_ANNOUNCEMENTS_URL = FDA_NEWS_URL

FDA_DRUGS_URL = (
    "https://www.fda.gov/drugs/"
    "news-events-human-drugs/drug-safety-and-availability"
)

FDA_WHATS_NEW_URL = (
    "https://www.fda.gov/drugs/"
    "news-events-human-drugs/whats-new-related-drugs"
)

FDA_NOTABLE_APPROVALS_URL = (
    "https://www.fda.gov/drugs/"
    "news-events-human-drugs/notable-approvals-drugs"
)

FDA_NOVEL_APPROVALS_2026_URL = (
    "https://www.fda.gov/drugs/"
    "novel-drug-approvals-fda/novel-drug-approvals-2026"
)

FDA_ONCOLOGY_APPROVALS_URL = (
    "https://www.fda.gov/drugs/"
    "resources-information-approved-drugs/"
    "oncology-cancerhematologic-malignancies-approval-notifications"
)

DEFAULT_MAX_NEWS = 50
DEFAULT_MAX_PAGES = 5
REQUEST_TIMEOUT = 20

USER_AGENT = (
    "Mozilla/5.0 (compatible; PharmaRadar/1.0; "
    "+https://github.com/)"
)


# ---------------------------------------------------------------------------
# HTTP SESSION
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
)


# ---------------------------------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "APPROVAL": [
        "approved",
        "approval",
        "approves",
        "authorizes",
        "authorized",
        "authorization",
        "cleared",
        "clearance",
    ],
    "REJECTION": [
        "rejected",
        "rejection",
        "not approved",
        "complete response letter",
        "crl",
        "refused",
        "refusal",
        "denied",
        "denial",
    ],
    "SAFETY": [
        "safety",
        "warning",
        "recall",
        "adverse event",
        "adverse events",
        "risk",
        "boxed warning",
        "contamination",
        "death",
        "deaths",
    ],
    "CLINICAL": [
        "clinical trial",
        "clinical study",
        "clinical results",
        "trial results",
        "efficacy",
        "endpoint",
        "phase 1",
        "phase 2",
        "phase 3",
        "phase i",
        "phase ii",
        "phase iii",
    ],
    "LABEL": [
        "label expansion",
        "expanded indication",
        "expanded use",
        "indication",
        "labeling",
        "label",
    ],
}

CATEGORY_PRIORITY = [
    "APPROVAL",
    "REJECTION",
    "SAFETY",
    "CLINICAL",
    "LABEL",
]

PRIORITY_BY_CATEGORY = {
    "APPROVAL": "EXTREME",
    "REJECTION": "EXTREME",
    "SAFETY": "EXTREME",
    "CLINICAL": "HIGH",
    "LABEL": "HIGH",
}


# ---------------------------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------------------------

def normalize_text(value) -> str:
    """Normalizza un valore testuale."""
    if value is None:
        return ""

    text = unescape(str(value))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_url(url, base_url=FDA_NEWS_URL) -> str:
    """Converte URL relativi in assoluti."""
    if not url:
        return ""

    url = unescape(str(url)).strip()
    if not url:
        return ""

    return urljoin(base_url, url)


# ---------------------------------------------------------------------------
# URL VALIDATION
# ---------------------------------------------------------------------------

def is_fda_press_announcement_url(url) -> bool:
    """Verifica se un URL appartiene a una FDA Press Announcement."""
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

    return "/news-events/press-announcements/" in path


# ---------------------------------------------------------------------------
# TITLE VALIDATION
# ---------------------------------------------------------------------------

def is_valid_news_title(title) -> bool:
    """Filtra titoli vuoti o chiaramente appartenenti alla navigazione."""
    title = normalize_text(title)

    if not title or len(title) < 4 or len(title) > 500:
        return False

    invalid_titles = {
        "home",
        "news",
        "search",
        "menu",
        "main menu",
        "skip to main content",
        "contact fda",
        "about fda",
        "resources",
        "subscribe",
    }

    return title.lower() not in invalid_titles


# ---------------------------------------------------------------------------
# ITEM ID
# ---------------------------------------------------------------------------

def get_item_id(item) -> str:
    """Restituisce un identificativo stabile SHA-256."""
    if not isinstance(item, dict):
        item = {"value": str(item)}

    raw = "|".join(
        [
            normalize_text(item.get("title", "")),
            normalize_text(item.get("url", "")),
            normalize_text(item.get("published_at", "")),
        ]
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# DATE PARSING
# ---------------------------------------------------------------------------

def _parse_date(value):
    """Converte una data FDA in ISO 8601 quando possibile."""
    if not value:
        return None

    text = normalize_text(value)

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.isoformat()
    except ValueError:
        pass

    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.isoformat()
        except ValueError:
            continue

    return text


def normalize_date(value):
    """
    API pubblica/legacy per la normalizzazione delle date FDA.

    Mantiene lo stesso comportamento del parser interno:
    - None/vuoto -> None
    - data ISO -> ISO
    - data testuale FDA -> ISO
    - formato sconosciuto -> testo normalizzato
    """
    return _parse_date(value)


def _extract_date(container):
    """Cerca una data in <time>, attributi comuni o testo."""
    if container is None:
        return None

    time_tag = container.find("time")

    if time_tag is not None:
        datetime_value = time_tag.get("datetime")
        if datetime_value:
            return _parse_date(datetime_value)

        text = normalize_text(time_tag.get_text(" ", strip=True))
        if text:
            return _parse_date(text)

    for attr in ("datetime", "date", "data", "published", "published_at"):
        value = container.get(attr)
        if value:
            return _parse_date(value)

    text = normalize_text(container.get_text(" ", strip=True))

    patterns = [
        r"\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _parse_date(match.group(0))

    return None


# ---------------------------------------------------------------------------
# LINK / TEXT EXTRACTION
# ---------------------------------------------------------------------------

def extract_link(article, base_url=FDA_NEWS_URL) -> str:
    """Estrae il primo href utile da un elemento BeautifulSoup."""
    if article is None:
        return ""

    if isinstance(article, str):
        return normalize_url(article, base_url)

    if getattr(article, "name", None) == "a":
        link = article
    else:
        link = article.find("a", href=True)

    if link is None:
        return ""

    href = link.get("href")
    if not href:
        return ""

    return normalize_url(href, base_url)


def extract_title(article) -> str:
    """Estrae il titolo da un contenitore HTML."""
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

    paragraphs = container.find_all("p")
    for paragraph in paragraphs:
        text = normalize_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        if title and text == title:
            continue
        return text[:2000]

    return ""


def extract_summary(article) -> str:
    """API pubblica/legacy per l'estrazione del summary."""
    return _extract_summary(article, extract_title(article))


def extract_date(article):
    """API pubblica/legacy per l'estrazione della data."""
    return _extract_date(article)


# ---------------------------------------------------------------------------
# CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_fda_text(text):
    """Classifica il testo FDA in una o più categorie."""
    normalized = normalize_text(text).lower()
    categories = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in normalized for keyword in keywords):
            categories.append(category)

    return categories


def get_fda_priority(categories):
    """Restituisce la priorità più alta associata alle categorie."""
    normalized = {str(category).upper() for category in (categories or [])}

    if "APPROVAL" in normalized:
        return "EXTREME"
    if "REJECTION" in normalized:
        return "EXTREME"
    if "SAFETY" in normalized:
        return "EXTREME"
    if "CLINICAL" in normalized:
        return "HIGH"
    if "LABEL" in normalized:
        return "HIGH"

    return "LOW"


def calculate_priority(categories):
    """Alias legacy."""
    return get_fda_priority(categories)


# ---------------------------------------------------------------------------
# ITEM BUILDER
# ---------------------------------------------------------------------------

def build_fda_news_item(
    title,
    url,
    published_at=None,
    summary="",
    source="FDA",
):
    """Costruisce un item standardizzato del feed FDA."""
    title = normalize_text(title)
    url = normalize_url(url)
    summary = normalize_text(summary)

    categories = classify_fda_text(" ".join([title, summary]))

    item = {
        "source": source,
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": _parse_date(published_at),
        "categories": categories,
        "priority": get_fda_priority(categories),
    }

    item["item_id"] = get_item_id(item)
    return item


# ---------------------------------------------------------------------------
# GENERIC HTML PARSER
# ---------------------------------------------------------------------------

def _candidate_containers(soup):
    """Restituisce contenitori plausibili per articoli FDA."""
    containers = []

    for selector in ["article", ".views-row", ".node", "li"]:
        try:
            containers.extend(soup.select(selector))
        except Exception:
            continue

    if not containers:
        containers.extend(soup.find_all(["h2", "h3", "h4"]))

    return containers


def _parse_container(container, base_url=FDA_NEWS_URL):
    title = extract_title(container)
    if not is_valid_news_title(title):
        return None

    url = extract_link(container, base_url=base_url)
    if not url:
        return None

    return build_fda_news_item(
        title=title,
        url=url,
        published_at=_extract_date(container),
        summary=_extract_summary(container, title=title),
    )


def _parse_anchor_fallback(soup, base_url=FDA_NEWS_URL):
    results = []

    for link in soup.find_all("a", href=True):
        title = normalize_text(link.get_text(" ", strip=True))
        if not is_valid_news_title(title):
            continue

        href = normalize_url(link.get("href"), base_url)
        if not href or href.startswith("#"):
            continue

        results.append(build_fda_news_item(title=title, url=href))

    return results


def parse_fda_page(
    html_content,
    base_url=FDA_NEWS_URL,
    max_items=DEFAULT_MAX_NEWS,
):
    """
    Parser GENERICO della pagina HTML FDA.

    Non verifica is_fda_press_announcement_url(): questa funzione è usata
    anche dai test unitari con HTML sintetico.
    """
    if not html_content:
        return []

    if not isinstance(html_content, str):
        html_content = str(html_content)

    try:
        max_items = int(max_items)
    except (TypeError, ValueError):
        max_items = DEFAULT_MAX_NEWS

    if max_items <= 0:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    results = []

    for container in _candidate_containers(soup):
        item = _parse_container(container, base_url=base_url)
        if item is not None:
            results.append(item)
        if len(results) >= max_items:
            break

    if len(results) < max_items:
        results.extend(_parse_anchor_fallback(soup, base_url=base_url))

    return deduplicate_fda_news(results)[:max_items]


# ---------------------------------------------------------------------------
# HTTP FETCH
# ---------------------------------------------------------------------------

def _fetch_html(url, params=None):
    response = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# PRESS ANNOUNCEMENTS FETCH
# ---------------------------------------------------------------------------

def _fetch_press_announcements(
    max_news=DEFAULT_MAX_NEWS,
    max_pages=DEFAULT_MAX_PAGES,
):
    """Recupera esclusivamente le FDA Press Announcements."""
    results = []

    try:
        max_news = int(max_news)
    except (TypeError, ValueError):
        max_news = DEFAULT_MAX_NEWS

    try:
        max_pages = int(max_pages)
    except (TypeError, ValueError):
        max_pages = DEFAULT_MAX_PAGES

    if max_news <= 0:
        return []
    if max_pages <= 0:
        max_pages = 1

    for page in range(max_pages):
        if len(results) >= max_news:
            break

        try:
            html_content = _fetch_html(
                FDA_PRESS_ANNOUNCEMENTS_URL,
                params={"page": page},
            )
        except requests.RequestException:
            continue

        parsed = parse_fda_page(
            html_content,
            base_url=FDA_PRESS_ANNOUNCEMENTS_URL,
            max_items=max_news,
        )

        parsed = [
            item
            for item in parsed
            if is_fda_press_announcement_url(item.get("url"))
        ]

        results.extend(parsed)

        if not parsed:
            break

    return deduplicate_fda_news(results)[:max_news]


# ---------------------------------------------------------------------------
# GENERIC SOURCE FETCH
# ---------------------------------------------------------------------------

def _fetch_source_items(url, max_items=DEFAULT_MAX_NEWS):
    try:
        html_content = _fetch_html(url)
    except requests.RequestException:
        return []

    return parse_fda_page(
        html_content,
        base_url=url,
        max_items=max_items,
    )


# ---------------------------------------------------------------------------
# NOVEL APPROVALS TABLE
# ---------------------------------------------------------------------------

def _fetch_novel_approvals_2026(max_items=DEFAULT_MAX_NEWS):
    try:
        html_content = _fetch_html(FDA_NOVEL_APPROVALS_2026_URL)
    except requests.RequestException:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    results = []

    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        texts = [
            normalize_text(cell.get_text(" ", strip=True))
            for cell in cells
        ]

        title = texts[0]
        if not is_valid_news_title(title):
            continue

        link = row.find("a", href=True)
        if link is not None:
            url = normalize_url(
                link.get("href"),
                FDA_NOVEL_APPROVALS_2026_URL,
            )
        else:
            url = FDA_NOVEL_APPROVALS_2026_URL

        date_value = texts[-1] if len(texts) >= 3 else None
        summary = " | ".join(value for value in texts[1:] if value)

        results.append(
            build_fda_news_item(
                title=title,
                url=url,
                published_at=date_value,
                summary=summary,
                source="FDA",
            )
        )

        if len(results) >= max_items:
            break

    return deduplicate_fda_news(results)


# ---------------------------------------------------------------------------
# DEDUPLICATION / SORTING
# ---------------------------------------------------------------------------

def deduplicate_fda_news(news_items):
    """Deduplica per URL, item_id e titolo."""
    if not news_items:
        return []

    unique = []
    seen_ids = set()
    seen_urls = set()
    seen_titles = set()

    for item in news_items:
        if not isinstance(item, dict):
            continue

        normalized = dict(item)
        normalized["title"] = normalize_text(normalized.get("title", ""))
        normalized["url"] = normalize_url(normalized.get("url", ""))
        normalized["summary"] = normalize_text(normalized.get("summary", ""))

        if not is_valid_news_title(normalized["title"]):
            continue

        item_id = normalized.get("item_id") or get_item_id(normalized)
        normalized["item_id"] = item_id

        url_key = normalized["url"].lower()
        title_key = normalized["title"].lower()

        if item_id in seen_ids:
            continue
        if url_key and url_key in seen_urls:
            continue
        if title_key in seen_titles:
            continue

        seen_ids.add(item_id)
        if url_key:
            seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(normalized)

    return unique


def _sort_key(item):
    value = item.get("published_at")
    if value:
        try:
            return (
                1,
                datetime.fromisoformat(
                    str(value).replace("Z", "+00:00")
                ).replace(tzinfo=None),
            )
        except ValueError:
            pass

    priority_rank = {
        "EXTREME": 3,
        "HIGH": 2,
        "MEDIUM": 1,
        "LOW": 0,
    }
    return (0, priority_rank.get(str(item.get("priority", "LOW")).upper(), 0))


def sort_fda_news(news_items):
    """Ordina per data quando presente; altrimenti per priorità."""
    return sorted(
        news_items or [],
        key=_sort_key,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# LIVE MAIN FEED
# ---------------------------------------------------------------------------

def get_fda_news(
    max_news=DEFAULT_MAX_NEWS,
    max_pages=DEFAULT_MAX_PAGES,
    max_items=None,
):
    """
    Recupera il feed LIVE FDA.

    max_items è accettato come alias legacy di max_news.
    Il feed principale contiene esclusivamente FDA Press Announcements.
    """
    if max_items is not None:
        max_news = max_items

    try:
        max_news = int(max_news)
    except (TypeError, ValueError):
        max_news = DEFAULT_MAX_NEWS

    if max_news <= 0:
        return []

    news = _fetch_press_announcements(
        max_news=max_news,
        max_pages=max_pages,
    )

    news = [
        item
        for item in news
        if is_fda_press_announcement_url(item.get("url"))
    ]

    return sort_fda_news(deduplicate_fda_news(news))[:max_news]


# ---------------------------------------------------------------------------
# COMPATIBILITY API
# ---------------------------------------------------------------------------

def get_fda_catalyst_news(max_items=DEFAULT_MAX_NEWS):
    """API utilizzata dal trial_scanner."""
    news = get_fda_news(max_news=max_items)
    return filter_fda_catalysts(news)


def filter_fda_catalysts(news_items):
    """Filtra le news potenzialmente rilevanti per Catalyst Engine."""
    if not news_items:
        return []

    relevant = []

    for item in news_items:
        categories = {
            str(category).upper()
            for category in item.get("categories", [])
        }
        priority = str(item.get("priority", "LOW")).upper()

        if categories.intersection(
            {"APPROVAL", "REJECTION", "SAFETY", "CLINICAL", "LABEL"}
        ):
            relevant.append(item)
            continue

        if priority in {"EXTREME", "HIGH"}:
            relevant.append(item)

    return relevant


def get_fda_sources():
    """Restituisce le fonti FDA disponibili."""
    return {
        "press_announcements": FDA_PRESS_ANNOUNCEMENTS_URL,
        "drug_safety": FDA_DRUGS_URL,
        "whats_new": FDA_WHATS_NEW_URL,
        "notable_approvals": FDA_NOTABLE_APPROVALS_URL,
        "novel_approvals_2026": FDA_NOVEL_APPROVALS_2026_URL,
        "oncology_approvals": FDA_ONCOLOGY_APPROVALS_URL,
    }


def deduplicate_news(news_items):
    """Alias legacy."""
    return deduplicate_fda_news(news_items)


def sort_news(news_items):
    """Alias legacy."""
    return sort_fda_news(news_items)


__all__ = [
    "FDA_NEWS_URL",
    "FDA_PRESS_ANNOUNCEMENTS_URL",
    "FDA_DRUGS_URL",
    "FDA_WHATS_NEW_URL",
    "FDA_NOTABLE_APPROVALS_URL",
    "FDA_NOVEL_APPROVALS_2026_URL",
    "FDA_ONCOLOGY_APPROVALS_URL",
    "DEFAULT_MAX_NEWS",
    "DEFAULT_MAX_PAGES",
    "REQUEST_TIMEOUT",
    "normalize_text",
    "normalize_url",
    "normalize_date",
    "is_fda_press_announcement_url",
    "is_valid_news_title",
    "get_item_id",
    "extract_title",
    "extract_link",
    "extract_summary",
    "extract_date",
    "classify_fda_text",
    "get_fda_priority",
    "calculate_priority",
    "build_fda_news_item",
    "parse_fda_page",
    "deduplicate_fda_news",
    "sort_fda_news",
    "get_fda_news",
    "get_fda_catalyst_news",
    "filter_fda_catalysts",
    "get_fda_sources",
    "deduplicate_news",
    "sort_news",
]
