"""
Pharma Radar — FDA News

Recupera le FDA Press Announcements e le trasforma
in News Items standardizzati per Pharma Radar.

Architettura:

FDA Press Announcements
        ↓
FDA News
        ↓
FDA Matcher
        ↓
FDA Catalyst
        ↓
FDA Score
        ↓
Trading Intelligence

IMPORTANTE:
Questo modulo NON decide se una news riguarda una
società della watchlist.

Il recupero deve essere sufficientemente ampio da
permettere al matcher di identificare successivamente
azienda/programmi rilevanti.
"""

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================
# FDA URLS
# ============================================

FDA_BASE_URL = "https://www.fda.gov"

FDA_DRUGS_URL = (
    "https://www.fda.gov/drugs/news-events-human-drugs/"
    "drug-safety-and-availability"
)

FDA_NEWS_URL = (
    "https://www.fda.gov/news-events/"
    "press-announcements"
)

# Alias mantenuto per compatibilità.
FDA_PRESS_ANNOUNCEMENTS_URL = FDA_NEWS_URL


# ============================================
# CONFIGURATION
# ============================================

DEFAULT_MAX_NEWS = 50
DEFAULT_MAX_PAGES = 5


# ============================================
# HTTP
# ============================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================
# KEYWORDS
# ============================================

CATEGORY_KEYWORDS = {
    "APPROVAL": [
        "approves",
        "approved",
        "approval",
        "approves new",
        "grants accelerated approval",
        "accelerated approval",
        "full approval",
        "traditional approval",
    ],
    "REJECTION": [
        "rejects",
        "rejected",
        "rejection",
        "complete response letter",
        "crl",
        "refuses approval",
        "not approved",
    ],
    "SAFETY": [
        "safety",
        "warning",
        "recall",
        "adverse events",
        "risk",
        "safety communication",
        "boxed warning",
        "withdraw",
        "withdrawal",
    ],
    "CLINICAL": [
        "clinical trial",
        "clinical study",
        "clinical results",
        "trial results",
        "efficacy",
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
        "new indication",
        "indication",
        "labeling",
        "label",
    ],
}


# ============================================
# PRIORITY
# ============================================

PRIORITY_BY_CATEGORY = {
    "APPROVAL": "EXTREME",
    "REJECTION": "EXTREME",
    "SAFETY": "EXTREME",
    "CLINICAL": "HIGH",
    "LABEL": "HIGH",
}


# ============================================
# TEXT NORMALIZATION
# ============================================

def normalize_text(text):
    """
    Normalizza un testo per classificazione e
    deduplicazione.
    """

    if text is None:
        return ""

    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================
# DATE NORMALIZATION
# ============================================

def normalize_date(value):
    """
    Normalizza una data in formato ISO.

    Supporta:
    - datetime
    - ISO string
    - date FDA comuni
    - None
    """

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.isoformat()

    text = normalize_text(value)

    if not text:
        return None

    # ISO già presente
    try:
        parsed = datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.isoformat()

    except ValueError:
        pass

    # Formati tipici FDA
    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(
                text,
                fmt,
            )

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

            return parsed.isoformat()

        except ValueError:
            continue

    return text


# ============================================
# URL NORMALIZATION
# ============================================

def normalize_url(url):
    """
    Converte URL relativi FDA in URL assoluti.
    """

    if not url:
        return ""

    url = str(url).strip()

    return urljoin(
        FDA_BASE_URL,
        url,
    )


# ============================================
# URL VALIDATION
# ============================================

def is_fda_press_announcement_url(url):
    """
    Verifica che l'URL appartenga al dominio FDA.

    Accetta anche eventuali URL FDA aggiuntivi
    perché il feed può utilizzare strutture diverse
    nel tempo.
    """

    if not url:
        return False

    url = normalize_url(url)

    return url.startswith(
        "https://www.fda.gov/"
    )


# ============================================
# TITLE VALIDATION
# ============================================

def is_valid_news_title(title):
    """
    Verifica che il titolo sia plausibilmente
    una FDA News Item.
    """

    title = normalize_text(title)

    if not title:
        return False

    if len(title) < 8:
        return False

    return True


# ============================================
# ITEM ID
# ============================================

def get_item_id(
    title,
    url,
):
    """
    Genera un identificatore stabile per la news.
    """

    raw = (
        normalize_text(title)
        + "|"
        + normalize_url(url)
    )

    return hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================
# CLASSIFICATION
# ============================================

def classify_fda_news(
    title,
    summary="",
):
    """
    Classifica una FDA news in una o più categorie.

    La classificazione è informativa:
    NON determina la rilevanza per la watchlist.
    """

    text = (
        normalize_text(title)
        + " "
        + normalize_text(summary)
    ).lower()

    categories = []

    for category, keywords in (
        CATEGORY_KEYWORDS.items()
    ):
        for keyword in keywords:
            if keyword.lower() in text:
                categories.append(
                    category
                )
                break

    return categories


# ============================================
# PRIORITY
# ============================================

def calculate_priority(
    categories,
):
    """
    Determina la priorità della news sulla base
    della categoria FDA.

    Una news senza categoria rimane LOW ma
    NON viene scartata.
    """

    categories = {
        str(category).upper()
        for category in (
            categories or []
        )
    }

    priority_order = {
        "EXTREME": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    selected = "LOW"

    for category in categories:
        priority = PRIORITY_BY_CATEGORY.get(
            category,
            "LOW",
        )

        if (
            priority_order.get(
                priority,
                1,
            )
            > priority_order.get(
                selected,
                1,
            )
        ):
            selected = priority

    return selected


# ============================================
# BUILD NEWS ITEM
# ============================================

def build_fda_news_item(
    title,
    summary="",
    published_at=None,
    url=None,
    **extra,
):
    """
    Costruisce una News Item standardizzata.

    I campi extra vengono conservati per permettere
    al matcher di utilizzare informazioni aggiuntive
    quando disponibili.
    """

    title = normalize_text(
        title
    )

    summary = normalize_text(
        summary
    )

    url = normalize_url(
        url
    )

    published_at = normalize_date(
        published_at
    )

    categories = classify_fda_news(
        title,
        summary,
    )

    item = {
        "id": get_item_id(
            title,
            url,
        ),
        "source": "FDA",
        "title": title,
        "summary": summary,
        "published_at": published_at,
        "url": url,
        "categories": categories,
        "priority": calculate_priority(
            categories
        ),
    }

    # Conserva i campi estesi quando presenti.
    for key, value in extra.items():

        if value is None:
            continue

        if isinstance(
            value,
            str,
        ):
            value = normalize_text(
                value
            )

        if value:
            item[key] = value

    return item


# ============================================
# HTML HELPERS
# ============================================

def _extract_text(element):
    """
    Estrae testo pulito da un elemento BeautifulSoup.
    """

    if element is None:
        return ""

    return normalize_text(
        element.get_text(
            " ",
            strip=True,
        )
    )


def _extract_link(element):
    """
    Estrae un URL da un elemento.
    """

    if element is None:
        return ""

    href = element.get(
        "href"
    )

    if not href:
        return ""

    return normalize_url(
        href
    )


def _extract_date(element):
    """
    Cerca una data all'interno di un elemento.
    """

    if element is None:
        return None

    # <time datetime="...">
    time_element = element.find(
        "time"
    )

    if time_element:

        value = (
            time_element.get(
                "datetime"
            )
            or time_element.get_text(
                " ",
                strip=True,
            )
        )

        if value:
            return normalize_date(
                value
            )

    # Attributi comuni
    for attribute in (
        "datetime",
        "data-date",
        "date",
    ):

        value = element.get(
            attribute
        )

        if value:
            return normalize_date(
                value
            )

    # Testo dell'elemento
    text = _extract_text(
        element
    )

    if not text:
        return None

    date_patterns = [
        r"\b[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\b",
        r"\b[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            text,
        )

        if match:
            return normalize_date(
                match.group(0)
            )

    return None


# ============================================
# ARTICLE EXTRACTION
# ============================================

def _extract_article_fields(
    article,
):
    """
    Estrae titolo, summary, data e testo esteso
    da un elemento article.
    """

    if article is None:
        return None

    title = ""

    # Preferenza per heading
    for selector in (
        "h1",
        "h2",
        "h3",
        ".field--name-title",
        ".usa-card__heading",
    ):

        heading = article.select_one(
            selector
        )

        if heading:
            title = _extract_text(
                heading
            )

            if title:
                break

    link = None

    # Cerca il link principale
    for anchor in article.select(
        "a[href]"
    ):

        href = _extract_link(
            anchor
        )

        if (
            "/news-events/press-announcements/"
            in href
        ):
            link = href
            break

    if not link:

        first_link = article.find(
            "a",
            href=True,
        )

        if first_link:
            link = _extract_link(
                first_link
            )

    summary = ""

    for selector in (
        ".field--name-body",
        ".field--name-field-teaser",
        ".usa-card__description",
        "p",
    ):

        node = article.select_one(
            selector
        )

        if node:
            summary = _extract_text(
                node
            )

            if summary:
                break

    published_at = _extract_date(
        article
    )

    full_text = _extract_text(
        article
    )

    if not title:
        return None

    return {
        "title": title,
        "summary": summary,
        "published_at": published_at,
        "url": link,
        "content": full_text,
    }


# ============================================
# DIRECT LINK EXTRACTION
# ============================================

def _extract_direct_links(
    soup,
):
    """
    Estrae direttamente i link FDA Press
    Announcements dalla pagina.

    Questo è un fallback importante perché la
    struttura HTML della FDA può cambiare.
    """

    results = []

    for anchor in soup.select(
        "a[href]"
    ):

        href = _extract_link(
            anchor
        )

        if (
            "/news-events/press-announcements/"
            not in href
        ):
            continue

        title = _extract_text(
            anchor
        )

        if not is_valid_news_title(
            title
        ):
            continue

        results.append({
            "title": title,
            "summary": "",
            "published_at": None,
            "url": href,
            "content": title,
        })

    return results


# ============================================
# PARSE FDA PAGE
# ============================================

def parse_fda_page(
    html,
):
    """
    Analizza una pagina FDA e restituisce
    News Items grezze.

    Supporta:
    - article
    - card
    - link diretti alle Press Announcements
    """

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    # ----------------------------------------
    # ARTICLE BLOCKS
    # ----------------------------------------

    for article in soup.select(
        "article"
    ):

        fields = _extract_article_fields(
            article
        )

        if not fields:
            continue

        url = normalize_url(
            fields.get(
                "url"
            )
        )

        if not is_fda_press_announcement_url(
            url
        ):
            continue

        results.append(
            fields
        )

    # ----------------------------------------
    # DIRECT LINKS
    # ----------------------------------------

    results.extend(
        _extract_direct_links(
            soup
        )
    )

    # ----------------------------------------
    # DEDUPLICATION
    # ----------------------------------------

    deduplicated = []
    seen = set()

    for item in results:

        url = normalize_url(
            item.get(
                "url"
            )
        )

        title = normalize_text(
            item.get(
                "title"
            )
        )

        key = (
            url
            or title
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)

        item["url"] = url

        deduplicated.append(
            item
        )

    return deduplicated


# ============================================
# FETCH SINGLE PAGE
# ============================================

def fetch_fda_page(
    page=0,
    timeout=30,
):
    """
    Recupera una singola pagina FDA.

    page=0:
        pagina principale

    page>0:
        paginazione FDA.
    """

    page = int(page)

    if page <= 0:
        url = FDA_NEWS_URL
    else:
        url = (
            FDA_NEWS_URL
            + "?page="
            + str(page)
        )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=timeout,
    )

    response.raise_for_status()

    return response.text


# ============================================
# GET FDA NEWS
# ============================================

def get_fda_news(
    max_news=DEFAULT_MAX_NEWS,
    max_pages=DEFAULT_MAX_PAGES,
):
    """
    Recupera le FDA Press Announcements.

    IMPORTANTE:

    Questa funzione NON applica un filtro catalyst
    aggressivo.

    Recupera invece una base ampia di news e lascia
    al matcher Pharma Radar il compito di determinare
    quali riguardano la watchlist.

    Questo evita di perdere una news rilevante
    solamente perché il titolo non contiene una
    keyword prevista.
    """

    try:
        max_news = int(
            max_news
        )
    except (
        TypeError,
        ValueError,
    ):
        max_news = DEFAULT_MAX_NEWS

    try:
        max_pages = int(
            max_pages
        )
    except (
        TypeError,
        ValueError,
    ):
        max_pages = DEFAULT_MAX_PAGES

    if max_news <= 0:
        return []

    if max_pages <= 0:
        max_pages = 1

    results = []
    seen = set()

    for page in range(
        max_pages
    ):

        try:
            html = fetch_fda_page(
                page=page
            )

        except Exception:
            # Una pagina non disponibile non deve
            # cancellare le news già recuperate.
            continue

        parsed = parse_fda_page(
            html
        )

        if not parsed:
            # Se una pagina successiva è vuota,
            # possiamo interrompere la paginazione.
            if page > 0:
                break

            continue

        for raw_item in parsed:

            title = normalize_text(
                raw_item.get(
                    "title"
                )
            )

            url = normalize_url(
                raw_item.get(
                    "url"
                )
            )

            if not is_valid_news_title(
                title
            ):
                continue

            if (
                url
                and not is_fda_press_announcement_url(
                    url
                )
            ):
                continue

            item = build_fda_news_item(
                title=title,
                summary=raw_item.get(
                    "summary",
                    "",
                ),
                published_at=raw_item.get(
                    "published_at"
                ),
                url=url,
                content=raw_item.get(
                    "content",
                    "",
                ),
            )

            item_id = item.get(
                "id"
            )

            if item_id in seen:
                continue

            seen.add(
                item_id
            )

            results.append(
                item
            )

            if len(results) >= max_news:
                return results

    return results


# ============================================
# GET FDA CATALYST NEWS
# ============================================

def get_fda_catalyst_news(
    max_items=DEFAULT_MAX_NEWS,
):
    """
    Recupera le FDA news disponibili.

    NOTA ARCHITETTURALE:

    Il nome storico della funzione viene mantenuto
    per compatibilità con il resto del progetto.

    Non elimina le news non classificate come catalyst:
    la rilevanza per la watchlist viene determinata
    dal matcher.
    """

    return get_fda_news(
        max_news=max_items
    )


# ============================================
# FILTER FDA CATALYSTS
# ============================================

def filter_fda_catalysts(
    news_items,
):
    """
    Filtra le news classificate come potenziali
    catalyst.

    Questo filtro viene applicato DOPO il recupero.

    Le news non catalyst restano disponibili al
    livello feed e possono essere utilizzate in
    future evoluzioni del Radar.
    """

    if not news_items:
        return []

    results = []

    for item in news_items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        categories = item.get(
            "categories",
            [],
        )

        if not isinstance(
            categories,
            list,
        ):
            categories = list(
                categories or []
            )

        normalized_categories = {
            str(category).upper()
            for category in categories
        }

        if normalized_categories:
            results.append(
                item
            )

    return results


# ============================================
# SORT
# ============================================

def sort_fda_news(
    news_items,
):
    """
    Ordina le news per priorità e data.
    """

    if not news_items:
        return []

    priority_order = {
        "EXTREME": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    def sort_key(item):

        priority = priority_order.get(
            str(
                item.get(
                    "priority",
                    "LOW",
                )
            ).upper(),
            1,
        )

        published = item.get(
            "published_at"
        ) or ""

        return (
            priority,
            published,
        )

    return sorted(
        news_items,
        key=sort_key,
        reverse=True,
    )


# ============================================
# DEDUPLICATION
# ============================================

def deduplicate_fda_news(
    news_items,
):
    """
    Elimina duplicati per ID o URL.
    """

    if not news_items:
        return []

    results = []
    seen = set()

    for item in news_items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        item_id = item.get(
            "id"
        )

        url = normalize_url(
            item.get(
                "url"
            )
        )

        key = (
            item_id
            or url
            or item.get(
                "title",
                "",
            )
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(
            key
        )

        results.append(
            item
        )

    return results


# ============================================
# SOURCES
# ============================================

def get_fda_sources():
    """
    Restituisce le sorgenti FDA utilizzate.
    """

    return [
        FDA_NEWS_URL,
        FDA_DRUGS_URL,
    ]


# ============================================
# PUBLIC API
# ============================================

__all__ = [
    "FDA_BASE_URL",
    "FDA_DRUGS_URL",
    "FDA_NEWS_URL",
    "FDA_PRESS_ANNOUNCEMENTS_URL",
    "DEFAULT_MAX_NEWS",
    "DEFAULT_MAX_PAGES",
    "normalize_text",
    "normalize_date",
    "normalize_url",
    "is_fda_press_announcement_url",
    "is_valid_news_title",
    "get_item_id",
    "classify_fda_news",
    "calculate_priority",
    "build_fda_news_item",
    "parse_fda_page",
    "fetch_fda_page",
    "get_fda_news",
    "get_fda_catalyst_news",
    "filter_fda_catalysts",
    "sort_fda_news",
    "deduplicate_fda_news",
    "get_fda_sources",
]