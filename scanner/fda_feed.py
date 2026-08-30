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
from urllib.parse import urljoin, urlparse

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

def fetch_fda_page(url=FDA_NEWS_URL):
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
# NORMALIZE
# ============================================

def normalize_text(text):
    """
    Normalizza il testo.
    """

    if text is None:
        return ""

    text = str(text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================
# ITEM ID
# ============================================

def get_item_id(item):
    """
    Genera un identificatore stabile.
    """

    url = normalize_text(
        item.get("url")
    )

    if url:
        value = url
    else:
        value = (
            f"{item.get('title', '')}|"
            f"{item.get('published_at', '')}"
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
    """

    if not value:
        return None

    value = normalize_text(value)

    # ----------------------------------------
    # ISO
    # ----------------------------------------

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        return parsed.isoformat()

    except ValueError:
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

    time_element = element.find("time")

    if time_element:

        datetime_value = time_element.get(
            "datetime"
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
    # TEXT
    # ----------------------------------------

    text = element.get_text(
        " ",
        strip=True,
    )

    # ----------------------------------------
    # MONTH DATE
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
    Estrae il link della comunicazione.
    """

    if element is None:
        return None

    link = element.find(
        "a",
        href=True,
    )

    if not link:
        return None

    href = normalize_text(
        link.get("href")
    )

    if not href:
        return None

    return urljoin(
        base_url,
        href,
    )


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
        ".field--name-title",
        ".node-title",
        "h1",
        "h2",
        "h3",
        "h4",
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

    link = element.find("a")

    if link:

        return normalize_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

    return ""


# ============================================
# URL VALIDATION
# ============================================

def is_valid_fda_news_url(
    url,
    base_url=FDA_NEWS_URL,
):
    """
    Determina se un URL può rappresentare
    una vera FDA Press Announcement.

    Scarta:
    - anchor;
    - menu;
    - pagine generiche;
    - URL della pagina indice;
    - URL esterni;
    - link di servizio FDA.
    """

    if not url:
        return False

    normalized = normalize_text(url)

    parsed = urlparse(normalized)

    base = urlparse(base_url)

    # ----------------------------------------
    # SOLO HTTPS
    # ----------------------------------------

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return False

    # ----------------------------------------
    # SOLO FDA
    # ----------------------------------------

    if parsed.netloc.lower() != base.netloc.lower():
        return False

    # ----------------------------------------
    # NO ANCHOR
    # ----------------------------------------

    if parsed.fragment:
        return False

    path = parsed.path.rstrip("/").lower()

    base_path = base.path.rstrip("/").lower()

    # ----------------------------------------
    # NON LA PAGINA INDICE
    # ----------------------------------------

    if path == base_path:
        return False

    # ----------------------------------------
    # SERVIZI / NAVIGAZIONE
    # ----------------------------------------

    blocked_paths = (
        "/about-fda/",
        "/contact-fda",
        "/search",
        "/safety/",
        "/regulatory-information/",
        "/drugs/",
        "/medical-devices/",
        "/food/",
        "/vaccines-blood-biologics/",
        "/radiation-emitting-products/",
        "/tobacco-products/",
        "/animal-veterinary/",
        "/consumer-updates/",
        "/news-events/",
    )

    # Una vera news può essere sotto
    # /news-events/... quindi gestiamo
    # separatamente la struttura.

    if path.startswith(
        "/about-fda/"
    ):
        return False

    if path.startswith(
        "/contact-fda"
    ):
        return False

    if path.startswith(
        "/search"
    ):
        return False

    # ----------------------------------------
    # PRESS ANNOUNCEMENT
    # ----------------------------------------

    valid_prefixes = (
        "/news-events/fda-newsroom/press-announcements/",
        "/news-events/newsroom/press-announcements/",
    )

    if not path.startswith(valid_prefixes):
        return False

    # Deve esserci qualcosa dopo
    # l'ultimo slash.

    slug = path.rsplit(
        "/",
        1,
    )[-1]

    if not slug:
        return False

    return True


# ============================================
# TITLE VALIDATION
# ============================================

def is_valid_news_title(title):
    """
    Elimina titoli palesemente appartenenti
    alla navigazione della pagina.
    """

    title = normalize_text(title)

    if not title:
        return False

    blocked_exact = {
        "press announcements",
        "skip to main content",
        "skip to fda search",
        "skip to footer links",
        "skip to in this section menu",
        "report a product problem",
        "contact fda",
        "fda guidance documents",
        "recalls, market withdrawals and safety alerts",
        "fda news",
        "newsroom",
    }

    if title.lower() in blocked_exact:
        return False

    blocked_prefixes = (
        "skip to ",
    )

    lower_title = title.lower()

    if lower_title.startswith(
        blocked_prefixes
    ):
        return False

    return True


# ============================================
# VALID NEWS CONTAINER
# ============================================

def is_valid_news_container(
    container,
    base_url=FDA_NEWS_URL,
):
    """
    Determina se un container HTML contiene
    una vera Press Announcement.
    """

    if container is None:
        return False

    title = extract_title(
        container
    )

    if not is_valid_news_title(
        title
    ):
        return False

    url = extract_link(
        container,
        base_url,
    )

    if not is_valid_fda_news_url(
        url,
        base_url,
    ):
        return False

    return True


# ============================================
# FIND NEWS CONTAINERS
# ============================================

def find_news_containers(soup):
    """
    Individua esclusivamente i container
    delle vere FDA Press Announcements.

    IMPORTANTE:
    non utilizza più `li` come fallback,
    perché la pagina FDA contiene moltissimi
    elementi di navigazione <li>.
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

    seen = set()

    for selector in selectors:

        for container in soup.select(
            selector
        ):

            identity = id(container)

            if identity in seen:
                continue

            seen.add(identity)

            if not is_valid_news_container(
                container
            ):
                continue

            containers.append(
                container
            )

    return containers


# ============================================
# PARSE PAGE
# ============================================

def parse_fda_page(
    html,
    base_url=FDA_NEWS_URL,
    max_items=MAX_ITEMS,
):
    """
    Converte HTML FDA in News Items.
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

        if not is_valid_news_title(
            title
        ):
            continue

        if not is_valid_fda_news_url(
            url,
            base_url,
        ):
            continue

        item = build_fda_news_item(
            title=title,
            summary=summary,
            url=url,
            published_at=published_at,
        )

        item["id"] = get_item_id(
            item
        )

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
    Recupera le vere comunicazioni pubbliche FDA.
    """

    html = fetch_fda_page(
        FDA_NEWS_URL
    )

    return parse_fda_page(
        html,
        base_url=FDA_NEWS_URL,
        max_items=max_items,
    )


# ============================================
# GET FDA CATALYST NEWS
# ============================================

def get_fda_catalyst_news(
    max_items=MAX_ITEMS,
):
    """
    Recupera soltanto le news FDA
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
    "get_item_id",
    "normalize_date",
    "extract_date",
    "extract_summary",
    "extract_link",
    "extract_title",
    "is_valid_fda_news_url",
    "is_valid_news_title",
    "is_valid_news_container",
    "find_news_containers",
    "parse_fda_page",
    "get_fda_news",
    "get_fda_catalyst_news",
    "sort_fda_news",
]