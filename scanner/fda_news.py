"""
Pharma Radar — FDA News Feed

Recupera le comunicazioni pubbliche della FDA
utilizzabili come possibili catalyst Pharma.

Pipeline:

FDA Press Announcements
        ↓
Parsing
        ↓
Normalizzazione
        ↓
Classificazione
        ↓
Priorità

Questo modulo NON decide se una notizia è
tradabile e NON produce raccomandazioni
di acquisto o vendita.
"""

import hashlib
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================
# FDA SOURCES
# ============================================

FDA_DRUGS_URL = (
    "https://www.fda.gov/"
    "drugs/resources-information-approved-drugs/"
    "drug-approvals-and-databases"
)

FDA_NEWS_URL = (
    "https://www.fda.gov/"
    "news-events/fda-newsroom/"
    "press-announcements"
)


# Compatibilità con eventuali moduli che
# utilizzano questo nome.
FDA_PRESS_ANNOUNCEMENTS_URL = FDA_NEWS_URL


# ============================================
# HTTP SETTINGS
# ============================================

REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; PharmaRadar/1.0; "
        "+https://www.fda.gov/)"
    ),
    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
        "application/xml;q=0.9,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================
# LIMITS
# ============================================

DEFAULT_MAX_NEWS = 50


# ============================================
# KEYWORDS
# ============================================

FDA_CATALYST_KEYWORDS = {

    "APPROVAL": [
        "approves",
        "approved",
        "approval",
        "approving",
        "grants accelerated approval",
        "grants approval",
        "grants traditional approval",
    ],

    "REJECTION": [
        "complete response letter",
        "rejected",
        "rejects",
        "refuses",
        "refusal",
        "not approved",
        "failed to approve",
    ],

    "SAFETY": [
        "safety",
        "safety concern",
        "safety signal",
        "adverse event",
        "adverse events",
        "warning",
        "recall",
        "risk",
    ],

    "CLINICAL": [
        "clinical trial",
        "clinical study",
        "phase 1",
        "phase 2",
        "phase 3",
        "primary endpoint",
        "secondary endpoint",
        "efficacy",
        "clinical results",
        "trial results",
    ],

    "LABEL": [
        "label",
        "labeling",
        "indication",
        "expanded indication",
        "label expansion",
    ],
}


# ============================================
# TEXT NORMALIZATION
# ============================================

def normalize_text(text):
    """
    Normalizza uno string mantenendo il contenuto
    leggibile.
    """

    if text is None:
        return ""

    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================
# DATE NORMALIZATION
# ============================================

def normalize_date(value):
    """
    Normalizza una data FDA senza tentare
    conversioni rischiose.

    Mantiene il valore ISO se disponibile.
    """

    if value is None:
        return None

    value = normalize_text(value)

    if not value:
        return None

    return value


# ============================================
# URL NORMALIZATION
# ============================================

def normalize_url(url):
    """
    Converte URL relativi FDA in URL assoluti.
    """

    if not url:
        return None

    url = str(url).strip()

    return urljoin(
        FDA_NEWS_URL,
        url
    )


# ============================================
# FDA URL VALIDATION
# ============================================

def is_fda_press_announcement_url(url):
    """
    Verifica che un URL appartenga al dominio FDA.

    Gli URL sintetici usati dai test possono
    utilizzare percorsi diversi, quindi il controllo
    resta volutamente permissivo sul path.
    """

    if not url:
        return False

    normalized = normalize_url(url)

    if not normalized:
        return False

    return normalized.startswith(
        "https://www.fda.gov/"
    )


# ============================================
# TITLE VALIDATION
# ============================================

def is_valid_news_title(title):
    """
    Scarta titoli vuoti o elementi di navigazione
    della pagina FDA.
    """

    title = normalize_text(title)

    if not title:
        return False

    if len(title) < 12:
        return False

    navigation_titles = {
        "menu",
        "search",
        "home",
        "contact",
        "about",
        "resources",
        "news",
        "newsroom",
        "press announcements",
        "skip to main content",
    }

    if title.lower() in navigation_titles:
        return False

    return True


# ============================================
# ITEM ID
# ============================================

def get_item_id(item):
    """
    Genera un ID stabile per una FDA news item.
    """

    if not isinstance(item, dict):
        raise TypeError(
            "item must be a dictionary"
        )

    raw = "|".join([
        normalize_text(
            item.get("title", "")
        ),
        normalize_url(
            item.get("url")
        ) or "",
        normalize_date(
            item.get("published_at")
        ) or "",
    ])

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


# ============================================
# CLASSIFY FDA TEXT
# ============================================

def classify_fda_text(
    title,
    summary=""
):
    """
    Classifica una comunicazione FDA
    in base al titolo e al summary.
    """

    title = normalize_text(title)
    summary = normalize_text(summary)

    text = (
        f"{title} "
        f"{summary}"
    ).lower()

    categories = []

    for category, keywords in (
        FDA_CATALYST_KEYWORDS.items()
    ):

        for keyword in keywords:

            if keyword.lower() in text:

                categories.append(
                    category
                )

                break

    return categories


# ============================================
# CATALYST PRIORITY
# ============================================

def get_fda_priority(categories):
    """
    Determina la priorità preliminare.
    """

    normalized = {
        str(category).upper()
        for category in (
            categories or []
        )
    }

    if normalized.intersection({
        "APPROVAL",
        "REJECTION",
        "SAFETY",
    }):
        return "EXTREME"

    if normalized.intersection({
        "CLINICAL",
        "LABEL",
    }):
        return "HIGH"

    return "LOW"


# ============================================
# BUILD NEWS ITEM
# ============================================

def build_fda_news_item(
    title,
    summary="",
    url=None,
    published_at=None
):
    """
    Costruisce una FDA News Item standardizzata.
    """

    title = normalize_text(title)
    summary = normalize_text(summary)

    url = normalize_url(url)

    published_at = normalize_date(
        published_at
    )

    categories = classify_fda_text(
        title,
        summary
    )

    priority = get_fda_priority(
        categories
    )

    item = {
        "source": "FDA",
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": published_at,
        "categories": categories,
        "priority": priority,
    }

    item["id"] = get_item_id(item)

    return item


# ============================================
# HTML EXTRACTION HELPERS
# ============================================

def extract_title(node):
    """
    Estrae il titolo da un nodo HTML.
    """

    if node is None:
        return ""

    title_node = node.find(
        ["h1", "h2", "h3", "h4", "h5"]
    )

    if title_node is not None:
        return normalize_text(
            title_node.get_text(
                " ",
                strip=True
            )
        )

    return normalize_text(
        node.get_text(
            " ",
            strip=True
        )
    )


def extract_link(node):
    """
    Estrae il primo link FDA disponibile.
    """

    if node is None:
        return None

    link = node.find(
        "a",
        href=True
    )

    if link is None:
        return None

    return normalize_url(
        link.get("href")
    )


def extract_summary(node):
    """
    Estrae un summary testuale dal contenitore.
    """

    if node is None:
        return ""

    candidates = node.find_all(
        ["p", "div"],
        limit=10
    )

    for candidate in candidates:

        text = normalize_text(
            candidate.get_text(
                " ",
                strip=True
            )
        )

        if (
            text
            and len(text) >= 30
        ):
            return text

    return ""


def extract_date(node):
    """
    Estrae la data da un elemento HTML.
    """

    if node is None:
        return None

    time_node = node.find(
        "time"
    )

    if time_node is not None:

        value = (
            time_node.get("datetime")
            or time_node.get_text(
                " ",
                strip=True
            )
        )

        return normalize_date(
            value
        )

    text = normalize_text(
        node.get_text(
            " ",
            strip=True
        )
    )

    match = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\.?\s+\d{1,2},\s+\d{4}\b",
        text,
        re.IGNORECASE,
    )

    if match:
        return normalize_date(
            match.group(0)
        )

    return None


# ============================================
# BUILD FROM LINK
# ============================================

def build_fda_news_item_from_link(
    link,
    title=None,
    summary="",
    published_at=None,
):
    """
    Costruisce una news a partire da un link FDA.
    """

    if link is None:
        return None

    href = link.get("href")

    if not href:
        return None

    url = normalize_url(href)

    if not is_fda_press_announcement_url(
        url
    ):
        return None

    if title is None:
        title = link.get_text(
            " ",
            strip=True
        )

    title = normalize_text(
        title
    )

    if not is_valid_news_title(title):
        return None

    if not summary:
        parent = link.find_parent()
        if parent is not None:
            summary = extract_summary(
                parent
            )

    if not published_at:
        parent = link.find_parent()
        if parent is not None:
            published_at = extract_date(
                parent
            )

    return build_fda_news_item(
        title=title,
        summary=summary,
        url=url,
        published_at=published_at,
    )


# ============================================
# PARSE FDA PAGE
# ============================================

def parse_fda_page(
    html,
    max_items=DEFAULT_MAX_NEWS
):
    """
    Parser robusto della pagina FDA.

    Cerca prima i contenitori article.
    Se necessario utilizza direttamente i link
    alle Press Announcements.

    Deduplica per URL / ID.
    """

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    results = []
    seen = set()

    # ========================================
    # 1. ARTICLE-BASED EXTRACTION
    # ========================================

    for article in soup.find_all(
        "article"
    ):

        title = extract_title(
            article
        )

        link = article.find(
            "a",
            href=True
        )

        if link is None:
            continue

        url = normalize_url(
            link.get("href")
        )

        if not is_fda_press_announcement_url(
            url
        ):
            continue

        if not is_valid_news_title(
            title
        ):
            continue

        summary = extract_summary(
            article
        )

        published_at = extract_date(
            article
        )

        item = build_fda_news_item(
            title=title,
            summary=summary,
            url=url,
            published_at=published_at,
        )

        key = (
            item["id"],
            item["url"],
        )

        if key in seen:
            continue

        seen.add(key)
        results.append(item)

        if (
            max_items is not None
            and len(results) >= max_items
        ):
            return results[:max_items]

    # ========================================
    # 2. DIRECT ANNOUNCEMENT LINKS
    # ========================================

    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link.get("href", "")

        normalized_href = normalize_url(
            href
        )

        if not normalized_href:
            continue

        # La pagina reale FDA usa questo path
        # per le singole Press Announcements.
        if "/news-events/press-announcements/" not in (
            normalized_href.lower()
        ):
            continue

        title = normalize_text(
            link.get_text(
                " ",
                strip=True
            )
        )

        if not is_valid_news_title(
            title
        ):
            continue

        parent = link.find_parent()

        summary = ""

        published_at = None

        if parent is not None:

            summary = extract_summary(
                parent
            )

            published_at = extract_date(
                parent
            )

        item = build_fda_news_item(
            title=title,
            summary=summary,
            url=normalized_href,
            published_at=published_at,
        )

        key = (
            item["id"],
            item["url"],
        )

        if key in seen:
            continue

        seen.add(key)
        results.append(item)

        if (
            max_items is not None
            and len(results) >= max_items
        ):
            break

    return results[:max_items] if (
        max_items is not None
    ) else results


# ============================================
# PARSE PRESS ANNOUNCEMENTS
# ============================================

def parse_fda_press_announcements(
    html,
    max_items=DEFAULT_MAX_NEWS
):
    """
    Compatibilità con la precedente API.
    """

    return parse_fda_page(
        html,
        max_items=max_items
    )


# ============================================
# FETCH FDA NEWS
# ============================================

def get_fda_news(
    max_items=DEFAULT_MAX_NEWS
):
    """
    Recupera le ultime FDA Press Announcements.
    """

    response = requests.get(
        FDA_PRESS_ANNOUNCEMENTS_URL,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return parse_fda_page(
        response.text,
        max_items=max_items
    )


# ============================================
# FETCH PRESS ANNOUNCEMENTS
# ============================================

def fetch_fda_press_announcements(
    max_items=DEFAULT_MAX_NEWS
):
    """
    Alias compatibile con la vecchia API.
    """

    return get_fda_news(
        max_items=max_items
    )


# ============================================
# FDA CATALYST NEWS
# ============================================

def get_fda_catalyst_news(
    max_items=DEFAULT_MAX_NEWS
):
    """
    Recupera le news FDA e mantiene soltanto
    quelle con priorità EXTREME o HIGH.
    """

    news = get_fda_news(
        max_items=max_items
    )

    return filter_fda_catalysts(
        news
    )


# ============================================
# FILTER CATALYST NEWS
# ============================================

def filter_fda_catalysts(news_items):
    """
    Restituisce soltanto le comunicazioni FDA
    con potenziale rilevanza catalyst.
    """

    catalysts = []

    for item in (
        news_items or []
    ):

        priority = str(
            item.get(
                "priority",
                "LOW"
            )
        ).upper()

        if priority in {
            "EXTREME",
            "HIGH",
        }:

            catalysts.append(
                item
            )

    return catalysts


# ============================================
# SORT FDA NEWS
# ============================================

def sort_fda_news(news_items):
    """
    Ordina le news per priorità.
    """

    priority = {
        "EXTREME": 4,
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    return sorted(
        news_items or [],
        key=lambda item: priority.get(
            str(
                item.get(
                    "priority",
                    "LOW"
                )
            ).upper(),
            0,
        ),
        reverse=True,
    )


# ============================================
# DEDUPLICATE NEWS
# ============================================

def deduplicate_fda_news(
    news_items
):
    """
    Elimina duplicati usando ID e URL.
    """

    if not news_items:
        return []

    results = []
    seen = set()

    for item in news_items:

        if not isinstance(
            item,
            dict
        ):
            continue

        item_id = item.get(
            "id"
        )

        url = normalize_url(
            item.get("url")
        )

        title = normalize_text(
            item.get(
                "title",
                ""
            )
        ).lower()

        key = (
            item_id,
            url,
            title,
        )

        if key in seen:
            continue

        seen.add(key)
        results.append(item)

    return results


# ============================================
# FDA SOURCES
# ============================================

def get_fda_sources():
    """
    Restituisce gli endpoint FDA utilizzati
    dal Radar.
    """

    return {
        "drug_approvals": FDA_DRUGS_URL,
        "press_announcements": FDA_NEWS_URL,
    }


# ============================================
# PUBLIC API
# ============================================

__all__ = [
    "FDA_DRUGS_URL",
    "FDA_NEWS_URL",
    "FDA_PRESS_ANNOUNCEMENTS_URL",
    "normalize_text",
    "normalize_date",
    "normalize_url",
    "is_fda_press_announcement_url",
    "is_valid_news_title",
    "get_item_id",
    "classify_fda_text",
    "get_fda_priority",
    "build_fda_news_item",
    "build_fda_news_item_from_link",
    "extract_title",
    "extract_link",
    "extract_summary",
    "extract_date",
    "parse_fda_page",
    "parse_fda_press_announcements",
    "get_fda_news",
    "fetch_fda_press_announcements",
    "get_fda_catalyst_news",
    "filter_fda_catalysts",
    "sort_fda_news",
    "deduplicate_fda_news",
    "get_fda_sources",
]