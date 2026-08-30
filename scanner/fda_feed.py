"""
Pharma Radar — FDA Feed

Recupera le comunicazioni pubbliche FDA e le
trasforma in News Item standardizzati.

Responsabilità:
- recuperare le news FDA;
- individuare soltanto le vere Press Announcements;
- estrarre titolo, URL, data e testo;
- eliminare duplicati;
- restituire dati compatibili con fda_news.py.

NON effettua:
- scoring;
- matching;
- Trading Intelligence;
- invio Telegram.
"""

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from scanner.fda_news import (
    FDA_NEWS_URL,
    build_fda_news_item,
)


# ============================================
# SETTINGS
# ============================================

REQUEST_TIMEOUT = 30

MAX_ITEMS = 50

HEADERS = {
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
}


# ============================================
# FETCH
# ============================================

def fetch_fda_page(
    url=FDA_NEWS_URL,
):
    """
    Recupera una pagina FDA.
    """

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.text


# ============================================
# NORMALIZE TEXT
# ============================================

def normalize_text(text):
    """
    Normalizza il testo eliminando spazi multipli.
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
# NORMALIZE URL
# ============================================

def normalize_url(
    url,
    base_url=FDA_NEWS_URL,
):
    """
    Normalizza un URL FDA.

    - converte URL relativi in assoluti;
    - elimina fragment (#...);
    - elimina query string;
    - elimina slash finali non necessari;
    - mantiene protocollo e dominio.
    """

    if not url:
        return None

    url = normalize_text(url)

    if not url:
        return None

    absolute_url = urljoin(
        base_url,
        url,
    )

    parsed = urlsplit(
        absolute_url
    )

    path = parsed.path or "/"

    if (
        path != "/"
        and path.endswith("/")
    ):
        path = path.rstrip("/")

    normalized = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            "",
            "",
        )
    )

    return normalized


# ============================================
# FDA PRESS ANNOUNCEMENT URL
# ============================================

def is_press_announcement_url(
    url,
):
    """
    Verifica se un URL appartiene a una vera
    FDA Press Announcement.

    Sono escluse:
    - pagine indice;
    - pagine di navigazione;
    - anchor interni;
    - URL generici /press-announcements.

    Esempi validi:

    /news-events/press-announcements/fda-approves-...
    /news-events/fda-newsroom/press-announcements/fda-...

    Esempi NON validi:

    /news-events/press-announcements
    /news-events/fda-newsroom/press-announcements
    /news-events/fda-newsroom/press-announcements#main-content
    """

    normalized = normalize_url(
        url
    )

    if not normalized:
        return False

    parsed = urlsplit(
        normalized
    )

    path = (
        parsed.path
        or ""
    ).lower().rstrip("/")

    if not path:
        return False

    # Deve appartenere alla sezione FDA
    # Press Announcements.
    if (
        "/press-announcements/"
        not in path
    ):
        return False

    # Deve avere qualcosa dopo
    # /press-announcements/
    suffix = path.split(
        "/press-announcements/",
        1,
    )[1]

    if not suffix:
        return False

    # Evita percorsi strani o pagine di navigazione.
    if suffix in {
        "press-announcements",
        "main-content",
        "search-form",
        "section-nav",
        "footer",
    }:
        return False

    return True


# ============================================
# COMPATIBILITY ALIAS
# ============================================

def is_fda_press_announcement_url(
    url,
):
    """
    Alias pubblico utilizzato dai test e dal
    resto del Pharma Radar.

    Mantiene compatibilità con entrambe le
    denominazioni:
    - is_press_announcement_url
    - is_fda_press_announcement_url
    """

    return is_press_announcement_url(
        url
    )


# ============================================
# ITEM ID
# ============================================

def get_item_id(item):
    """
    Genera un identificatore stabile.

    L'URL normalizzato viene utilizzato come
    chiave primaria quando disponibile.
    """

    if not isinstance(
        item,
        dict,
    ):
        item = {}

    url = normalize_url(
        item.get("url")
    )

    if url:
        value = url

    else:
        title = normalize_text(
            item.get(
                "title",
                "",
            )
        )

        published_at = normalize_text(
            item.get(
                "published_at",
                "",
            )
        )

        value = (
            f"{title}|"
            f"{published_at}"
        )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


# ============================================
# NORMALIZE DATE
# ============================================

def normalize_date(value):
    """
    Normalizza una data FDA in formato ISO.

    Supporta:
    - ISO;
    - date testuali;
    - MM/DD/YYYY;
    - YYYY-MM-DD.
    """

    if not value:
        return None

    value = normalize_text(
        value
    )

    # ----------------------------------------
    # ISO
    # ----------------------------------------

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )

        return parsed.isoformat()

    except (
        ValueError,
        TypeError,
    ):
        pass

    # ----------------------------------------
    # COMMON FORMATS
    # ----------------------------------------

    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
    ]

    for date_format in formats:

        try:

            parsed = datetime.strptime(
                value,
                date_format,
            )

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

            return parsed.isoformat()

        except ValueError:
            continue

    return value


# ============================================
# EXTRACT DATE
# ============================================

def extract_date(element):
    """
    Estrae una data da un elemento HTML.
    """

    if element is None:
        return None

    # ----------------------------------------
    # <time>
    # ----------------------------------------

    time_element = element.find(
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

        time_text = time_element.get_text(
            " ",
            strip=True,
        )

        if time_text:

            return normalize_date(
                time_text
            )

    # ----------------------------------------
    # DATA ATTRIBUTES
    # ----------------------------------------

    for attribute in (
        "datetime",
        "data-date",
        "data-published",
        "data-published-at",
    ):

        value = element.get(
            attribute
        )

        if value:

            result = normalize_date(
                value
            )

            if result:
                return result

    # ----------------------------------------
    # TEXT SEARCH
    # ----------------------------------------

    text = element.get_text(
        " ",
        strip=True,
    )

    # ----------------------------------------
    # MONTH NAME DATE
    # ----------------------------------------

    pattern = (
        r"\b("
        r"January|February|March|April|May|June|"
        r"July|August|September|October|November|December"
        r")\s+"
        r"\d{1,2}"
        r",\s+"
        r"\d{4}"
        r"\b"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if match:

        return normalize_date(
            match.group(0)
        )

    # ----------------------------------------
    # NUMERIC DATE
    # ----------------------------------------

    numeric_pattern = (
        r"\b\d{1,2}/\d{1,2}/\d{4}\b"
    )

    match = re.search(
        numeric_pattern,
        text,
    )

    if match:

        return normalize_date(
            match.group(0)
        )

    # ----------------------------------------
    # ISO DATE IN TEXT
    # ----------------------------------------

    iso_pattern = (
        r"\b\d{4}-\d{2}-\d{2}"
        r"(?:T[0-9:.+\-Z]+)?\b"
    )

    match = re.search(
        iso_pattern,
        text,
    )

    if match:

        return normalize_date(
            match.group(0)
        )

    return None


# ============================================
# EXTRACT SUMMARY
# ============================================

def extract_summary(element):
    """
    Estrae una breve descrizione.
    """

    if element is None:
        return ""

    selectors = [
        ".field--name-body",
        ".field--name-field-summary",
        ".summary",
        ".description",
        ".field--name-field-description",
        "p",
    ]

    for selector in selectors:

        paragraph = element.select_one(
            selector
        )

        if paragraph:

            text = normalize_text(
                paragraph.get_text(
                    " ",
                    strip=True,
                )
            )

            if text:
                return text

    return ""


# ============================================
# EXTRACT LINK
# ============================================

def extract_link(
    element,
    base_url=FDA_NEWS_URL,
):
    """
    Estrae il primo link utile della
    comunicazione.
    """

    if element is None:
        return None

    links = element.find_all(
        "a",
        href=True,
    )

    if not links:
        return None

    # ----------------------------------------
    # PRIORITY 1:
    # FDA Press Announcement URL
    # ----------------------------------------

    for link in links:

        href = normalize_text(
            link.get("href")
        )

        if not href:
            continue

        absolute = normalize_url(
            href,
            base_url,
        )

        if is_press_announcement_url(
            absolute
        ):
            return absolute

    # ----------------------------------------
    # PRIORITY 2:
    # FIRST VALID LINK
    #
    # Necessario per i test unitari generici.
    # Il filtro "vera Press Announcement"
    # viene applicato al feed live.
    # ----------------------------------------

    for link in links:

        href = normalize_text(
            link.get("href")
        )

        if not href:
            continue

        absolute = normalize_url(
            href,
            base_url,
        )

        if absolute:
            return absolute

    return None


# ============================================
# EXTRACT TITLE
# ============================================

def extract_title(element):
    """
    Estrae il titolo della news.
    """

    if element is None:
        return ""

    selectors = [
        "h1",
        "h2",
        "h3",
        "h4",
        ".field--name-title",
        ".node-title",
        ".page-title",
        ".title",
    ]

    for selector in selectors:

        title_element = element.select_one(
            selector
        )

        if title_element:

            title = normalize_text(
                title_element.get_text(
                    " ",
                    strip=True,
                )
            )

            if title:
                return title

    # ----------------------------------------
    # FALLBACK LINK
    # ----------------------------------------

    link = element.find(
        "a"
    )

    if link:

        return normalize_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

    return ""


# ============================================
# FIND NEWS CONTAINERS
# ============================================

def find_news_containers(soup):
    """
    Individua i contenitori delle news FDA.

    La funzione mantiene una strategia
    permissiva per consentire i test HTML
    sintetici.

    Il filtraggio delle vere Press Announcements
    viene effettuato successivamente nel feed live.
    """

    if soup is None:
        return []

    selectors = [
        "article",
        ".node--type-press-release",
        ".node--type-news",
        ".views-row",
        ".news-item",
        ".press-release",
    ]

    containers = []

    for selector in selectors:

        found = soup.select(
            selector
        )

        if found:
            containers.extend(
                found
            )

    # ----------------------------------------
    # FALLBACK
    # ----------------------------------------

    if not containers:

        containers = soup.find_all(
            "li"
        )

    # ----------------------------------------
    # REMOVE DUPLICATE HTML NODES
    # ----------------------------------------

    unique = []

    seen_nodes = set()

    for container in containers:

        identity = id(
            container
        )

        if identity in seen_nodes:
            continue

        seen_nodes.add(
            identity
        )

        unique.append(
            container
        )

    return unique


# ============================================
# PARSE PAGE
# ============================================

def parse_fda_page(
    html,
    base_url=FDA_NEWS_URL,
    max_items=MAX_ITEMS,
    press_announcements_only=False,
):
    """
    Converte HTML FDA in News Items.

    Se press_announcements_only=True vengono
    mantenute esclusivamente le vere Press
    Announcements.

    Il default rimane permissivo per mantenere
    compatibilità con i test unitari.
    """

    if not html:
        return []

    try:

        max_items = int(
            max_items
        )

    except (
        ValueError,
        TypeError,
    ):

        max_items = MAX_ITEMS

    if max_items <= 0:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    containers = find_news_containers(
        soup
    )

    news = []

    seen_ids = set()

    seen_urls = set()

    for container in containers:

        title = extract_title(
            container
        )

        url = extract_link(
            container,
            base_url,
        )

        summary = extract_summary(
            container
        )

        published_at = extract_date(
            container
        )

        # ------------------------------------
        # VALIDATION
        # ------------------------------------

        if not title:
            continue

        if (
            press_announcements_only
            and not is_press_announcement_url(
                url
            )
        ):
            continue

        # ------------------------------------
        # NORMALIZE URL
        # ------------------------------------

        url = normalize_url(
            url,
            base_url,
        )

        # ------------------------------------
        # URL DUPLICATE FILTER
        # ------------------------------------

        if url:

            if url in seen_urls:
                continue

            seen_urls.add(
                url
            )

        # ------------------------------------
        # BUILD ITEM
        # ------------------------------------

        item = build_fda_news_item(
            title=title,
            summary=summary,
            url=url,
            published_at=published_at,
        )

        # ------------------------------------
        # STABLE ID
        # ------------------------------------

        item["id"] = get_item_id(
            item
        )

        # ------------------------------------
        # ID DUPLICATE FILTER
        # ------------------------------------

        if item["id"] in seen_ids:
            continue

        seen_ids.add(
            item["id"]
        )

        news.append(
            item
        )

        if len(news) >= max_items:
            break

    return news


# ============================================
# GET FDA NEWS
# ============================================

def get_fda_news(
    max_items=MAX_ITEMS,
):
    """
    Recupera esclusivamente le vere FDA
    Press Announcements.
    """

    html = fetch_fda_page(
        FDA_NEWS_URL
    )

    return parse_fda_page(
        html,
        base_url=FDA_NEWS_URL,
        max_items=max_items,
        press_announcements_only=True,
    )


# ============================================
# GET FDA CATALYST NEWS
# ============================================

def get_fda_catalyst_news(
    max_items=MAX_ITEMS,
):
    """
    Recupera le Press Announcements FDA
    con priorità HIGH o EXTREME.
    """

    news = get_fda_news(
        max_items=max_items
    )

    return [
        item
        for item in news
        if item.get("priority")
        in {
            "HIGH",
            "EXTREME",
        }
    ]


# ============================================
# SORT NEWS
# ============================================

def sort_fda_news(news_items):
    """
    Ordina le news per priorità e data.
    """

    priority_order = {
        "EXTREME": 3,
        "HIGH": 2,
        "LOW": 1,
    }

    return sorted(
        news_items or [],
        key=lambda item: (
            priority_order.get(
                item.get(
                    "priority",
                    "LOW",
                ),
                0,
            ),
            item.get(
                "published_at"
            ) or "",
        ),
        reverse=True,
    )


# ============================================
# PUBLIC API
# ============================================

__all__ = [
    "fetch_fda_page",
    "normalize_text",
    "normalize_url",
    "get_item_id",
    "normalize_date",
    "extract_date",
    "extract_summary",
    "extract_link",
    "extract_title",
    "find_news_containers",
    "is_press_announcement_url",
    "is_fda_press_announcement_url",
    "parse_fda_page",
    "get_fda_news",
    "get_fda_catalyst_news",
    "sort_fda_news",
]