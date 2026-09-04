"""
Pharma Radar — FDA News Feed

Acquisisce le FDA Press Announcements, classifica
le notizie come potenziali catalyst e prepara gli
oggetti utilizzati dal resto del Radar.

Questo modulo NON effettua raccomandazioni
di acquisto o vendita.
"""

import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


FDA_BASE_URL = "https://www.fda.gov"
FDA_DRUGS_URL = (
    "https://www.fda.gov/drugs/news-events-human-drugs/"
    "drug-safety-and-availability"
)
FDA_NEWS_URL = "https://www.fda.gov/news-events/press-announcements"
FDA_PRESS_ANNOUNCEMENTS_URL = FDA_NEWS_URL

DEFAULT_MAX_NEWS = 50
DEFAULT_MAX_PAGES = 5

REQUEST_TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PharmaRadar/1.0; "
        "+https://www.fda.gov/)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# FDA catalyst classification
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "APPROVAL": [
        "fda approves",
        "fda approved",
        "approval",
        "approves",
        "approved",
        "accelerated approval",
        "grants accelerated approval",
        "authorizes",
        "authorized",
        "clearance",
        "clears",
    ],
    "REJECTION": [
        "fda rejects",
        "fda rejected",
        "rejection",
        "complete response letter",
        "complete response",
        "crl",
        "refuses approval",
        "not approved",
    ],
    "SAFETY": [
        "safety",
        "safety warning",
        "boxed warning",
        "recall",
        "adverse events",
        "adverse event",
        "risk",
        "warning",
        "withdrawn",
        "withdrawal",
    ],
    "CLINICAL": [
        "clinical trial",
        "clinical study",
        "clinical results",
        "trial results",
        "study results",
        "efficacy",
        "phase 1",
        "phase 2",
        "phase 3",
        "phase iii",
        "phase ii",
        "phase i",
        "endpoint",
        "primary endpoint",
    ],
    "LABEL": [
        "label expansion",
        "expanded indication",
        "new indication",
        "additional indication",
        "indication",
        "labeling",
        "label update",
    ],
}


CATEGORY_PRIORITY = [
    "APPROVAL",
    "REJECTION",
    "SAFETY",
    "CLINICAL",
    "LABEL",
]


PRIORITY_MAP = {
    "APPROVAL": "EXTREME",
    "REJECTION": "EXTREME",
    "SAFETY": "EXTREME",
    "CLINICAL": "HIGH",
    "LABEL": "HIGH",
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def normalize_text(value):
    """
    Normalizza testo per confronti e classificazione.
    """
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def normalize_date(value):
    """
    Normalizza una data in formato ISO quando possibile.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    text = str(value).strip()

    if not text:
        return None

    # ISO già valido
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.isoformat()
    except ValueError:
        pass

    # Formati comuni FDA
    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
    ]

    for date_format in formats:
        try:
            parsed = datetime.strptime(text, date_format)
            return parsed.isoformat()
        except ValueError:
            continue

    return text


def normalize_url(url):
    """
    Converte URL relativi FDA in URL assoluti.
    """
    if not url:
        return None

    url = str(url).strip()

    if not url:
        return None

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return urljoin(FDA_BASE_URL, url)

    if url.startswith("http://"):
        return "https://" + url[len("http://"):]

    if url.startswith("https://"):
        return url

    return urljoin(FDA_BASE_URL + "/", url)


def is_fda_press_announcement_url(url):
    """
    Verifica che l'URL appartenga al sito FDA.
    """
    normalized = normalize_url(url)

    if not normalized:
        return False

    parsed = urlparse(normalized)

    if parsed.scheme != "https":
        return False

    if parsed.netloc.lower() not in {
        "www.fda.gov",
        "fda.gov",
    }:
        return False

    return True


def is_valid_news_title(title):
    """
    Verifica che il titolo sia sufficientemente valido.
    """
    if not title:
        return False

    normalized = normalize_text(title)

    if len(normalized) < 8:
        return False

    return True


def get_item_id(item):
    """
    Genera un identificativo stabile per una notizia.
    """
    if not isinstance(item, dict):
        raise TypeError("item must be a dictionary")

    source = (
        item.get("url")
        or item.get("title")
        or item.get("summary")
        or ""
    )

    return hashlib.sha256(
        str(source).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_fda_news(title="", summary=""):
    """
    Classifica una FDA News in una o più categorie.
    """
    text = normalize_text(
        f"{title or ''} {summary or ''}"
    )

    categories = []

    if not text:
        return categories

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if normalize_text(keyword) in text:
                categories.append(category)
                break

    return categories


def classify_fda_text(title="", summary=""):
    """
    Compatibility wrapper per il vecchio nome della funzione.

    Mantiene compatibilità con i test e con eventuale codice
    precedente che utilizza classify_fda_text().
    """
    return classify_fda_news(title, summary)


def calculate_priority(categories):
    """
    Calcola la priorità massima associata alle categorie.
    """
    if not categories:
        return "LOW"

    normalized = {
        str(category).upper()
        for category in categories
    }

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


# ---------------------------------------------------------------------------
# News object
# ---------------------------------------------------------------------------

def build_fda_news_item(
    title="",
    summary="",
    url=None,
    published_at=None,
    source="FDA",
    **extra,
):
    """
    Costruisce un oggetto FDA News standardizzato.
    """
    categories = classify_fda_news(
        title,
        summary,
    )

    item = {
        "id": None,
        "source": source or "FDA",
        "title": str(title or "").strip(),
        "summary": str(summary or "").strip(),
        "url": normalize_url(url),
        "published_at": normalize_date(published_at),
        "categories": categories,
        "priority": calculate_priority(categories),
    }

    for key, value in extra.items():
        if value is not None:
            item[key] = value

    item["id"] = get_item_id(item)

    return item


# ---------------------------------------------------------------------------
# HTML extraction helpers
# ---------------------------------------------------------------------------

def _extract_text(node):
    """
    Estrae testo pulito da un nodo BeautifulSoup.
    """
    if node is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        node.get_text(" ", strip=True),
    ).strip()


def _extract_link(node):
    """
    Estrae il primo link utile da un nodo.
    """
    if node is None:
        return None

    if node.name == "a":
        href = node.get("href")
        if href:
            return normalize_url(href)

    link = node.find("a", href=True)

    if link:
        return normalize_url(link.get("href"))

    return None


def _extract_date(node):
    """
    Cerca una data in un blocco HTML.
    """
    if node is None:
        return None

    # <time datetime="...">
    time_node = node.find("time")

    if time_node:
        value = time_node.get("datetime")

        if value:
            return normalize_date(value)

        text = _extract_text(time_node)

        if text:
            return normalize_date(text)

    # Attributi comuni
    for attribute in (
        "datetime",
        "data-date",
        "data-published",
        "data-publish-date",
    ):
        value = node.get(attribute)

        if value:
            return normalize_date(value)

    text = _extract_text(node)

    date_patterns = [
        r"\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\.?\s+\d{1,2},\s+\d{4}\b",
    ]

    for pattern in date_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return normalize_date(match.group(0))

    return None


def _extract_article_fields(article):
    """
    Estrae titolo, summary, data, URL e testo da un elemento article.
    """
    title = ""
    summary = ""
    url = None
    published_at = None

    # Titolo
    title_node = (
        article.find("h1")
        or article.find("h2")
        or article.find("h3")
        or article.find("h4")
    )

    if title_node:
        title = _extract_text(title_node)

    # Link
    url = _extract_link(article)

    # Summary / teaser
    summary_candidates = [
        article.find("div", class_=re.compile("summary", re.I)),
        article.find("div", class_=re.compile("description", re.I)),
        article.find("div", class_=re.compile("teaser", re.I)),
        article.find("p"),
    ]

    for candidate in summary_candidates:
        text = _extract_text(candidate)

        if text and text != title:
            summary = text
            break

    published_at = _extract_date(article)

    content = _extract_text(article)

    return {
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": published_at,
        "content": content,
        "description": summary,
    }


def _extract_direct_links(soup):
    """
    Estrae direttamente i link alle FDA Press Announcements.
    """
    results = []

    for link in soup.find_all("a", href=True):
        href = normalize_url(link.get("href"))

        if not href:
            continue

        parsed = urlparse(href)

        path = parsed.path.lower()

        if "/news-events/press-announcements/" not in path:
            continue

        title = _extract_text(link)

        if not is_valid_news_title(title):
            continue

        results.append(
            {
                "title": title,
                "summary": "",
                "url": href,
                "published_at": None,
                "content": title,
                "description": "",
            }
        )

    return results


# ---------------------------------------------------------------------------
# Page parser
# ---------------------------------------------------------------------------

def parse_fda_page(html, base_url=FDA_NEWS_URL):
    """
    Analizza una pagina FDA e restituisce le news individuate.
    """
    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    # Primo metodo: blocchi article
    for article in soup.find_all("article"):
        fields = _extract_article_fields(article)

        title = fields.get("title", "")
        url = fields.get("url")

        if not is_valid_news_title(title):
            continue

        if url and not is_fda_press_announcement_url(url):
            continue

        if not url:
            continue

        results.append(fields)

    # Secondo metodo: link diretti
    results.extend(
        _extract_direct_links(soup)
    )

    # Deduplicazione
    unique = []
    seen = set()

    for item in results:
        title = normalize_text(item.get("title"))
        url = normalize_url(item.get("url"))

        key = url or title

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)

        item["url"] = url

        unique.append(item)

    return unique


# ---------------------------------------------------------------------------
# HTTP feed
# ---------------------------------------------------------------------------

def fetch_fda_page(page=0):
    """
    Scarica una pagina FDA Press Announcements.
    """
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 0

    if page <= 0:
        url = FDA_NEWS_URL
    else:
        url = f"{FDA_NEWS_URL}?page={page}"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.text


def get_fda_news(
    max_news=DEFAULT_MAX_NEWS,
    max_pages=DEFAULT_MAX_PAGES,
):
    """
    Recupera le FDA Press Announcements.

    Cerca su più pagine per evitare di limitarsi
    alle sole notizie presenti nella prima pagina.
    """
    try:
        max_news = int(max_news)
    except (ValueError, TypeError):
        max_news = DEFAULT_MAX_NEWS

    try:
        max_pages = int(max_pages)
    except (ValueError, TypeError):
        max_pages = DEFAULT_MAX_PAGES

    if max_news <= 0:
        return []

    if max_pages <= 0:
        max_pages = 1

    news = []
    seen = set()

    for page in range(max_pages):
        try:
            html = fetch_fda_page(page)
        except Exception:
            # Un errore su una pagina non deve impedire
            # l'elaborazione delle pagine precedenti.
            continue

        parsed_items = parse_fda_page(
            html,
            base_url=FDA_NEWS_URL,
        )

        if not parsed_items:
            # Se una pagina è vuota, non ha senso
            # continuare indefinitamente.
            if page > 0:
                break
            continue

        for raw_item in parsed_items:
            title = raw_item.get("title", "")
            summary = raw_item.get("summary", "")
            url = raw_item.get("url")
            published_at = raw_item.get("published_at")

            if not is_valid_news_title(title):
                continue

            key = normalize_url(url) or normalize_text(title)

            if not key:
                continue

            if key in seen:
                continue

            seen.add(key)

            item = build_fda_news_item(
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
                source="FDA",
                content=raw_item.get("content", ""),
                description=raw_item.get("description", ""),
            )

            news.append(item)

            if len(news) >= max_news:
                return news[:max_news]

    return news[:max_news]


def get_fda_catalyst_news(max_items=DEFAULT_MAX_NEWS):
    """
    Alias pubblico utilizzato dal Trial Scanner.
    """
    return get_fda_news(
        max_news=max_items,
        max_pages=DEFAULT_MAX_PAGES,
    )


# ---------------------------------------------------------------------------
# Filtering and sorting
# ---------------------------------------------------------------------------

def filter_fda_catalysts(news_items):
    """
    Mantiene le news che hanno almeno una categoria
    FDA riconosciuta.
    """
    if not news_items:
        return []

    results = []

    for item in news_items:
        if not isinstance(item, dict):
            continue

        categories = item.get("categories", [])

        if not isinstance(categories, list):
            categories = list(categories or [])

        if categories:
            results.append(item)

    return results


def sort_fda_news(news_items):
    """
    Ordina le FDA news per priorità.
    """
    priority = {
        "EXTREME": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    return sorted(
        news_items or [],
        key=lambda item: (
            priority.get(
                str(item.get("priority", "LOW")).upper(),
                0,
            ),
            str(item.get("published_at") or ""),
        ),
        reverse=True,
    )


def deduplicate_fda_news(news_items):
    """
    Rimuove duplicati per URL o ID.
    """
    if not news_items:
        return []

    results = []
    seen = set()

    for item in news_items:
        if not isinstance(item, dict):
            continue

        key = (
            item.get("id")
            or normalize_url(item.get("url"))
            or normalize_text(item.get("title"))
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        results.append(item)

    return results


def get_fda_sources(news_items):
    """
    Restituisce gli URL delle FDA news.
    """
    if not news_items:
        return []

    sources = []

    for item in news_items:
        if not isinstance(item, dict):
            continue

        url = normalize_url(item.get("url"))

        if url and url not in sources:
            sources.append(url)

    return sources


__all__ = [
    "FDA_BASE_URL",
    "FDA_DRUGS_URL",
    "FDA_NEWS_URL",
    "FDA_PRESS_ANNOUNCEMENTS_URL",
    "DEFAULT_MAX_NEWS",
    "DEFAULT_MAX_PAGES",
    "CATEGORY_KEYWORDS",
    "CATEGORY_PRIORITY",
    "PRIORITY_MAP",
    "normalize_text",
    "normalize_date",
    "normalize_url",
    "is_fda_press_announcement_url",
    "is_valid_news_title",
    "get_item_id",
    "classify_fda_news",
    "classify_fda_text",
    "calculate_priority",
    "build_fda_news_item",
    "_extract_text",
    "_extract_link",
    "_extract_date",
    "_extract_article_fields",
    "_extract_direct_links",
    "parse_fda_page",
    "fetch_fda_page",
    "get_fda_news",
    "get_fda_catalyst_news",
    "filter_fda_catalysts",
    "sort_fda_news",
    "deduplicate_fda_news",
    "get_fda_sources",
]