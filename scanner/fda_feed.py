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
from urllib.parse import urljoin

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
# NORMALIZE
# ============================================

def normalize_text(text):
    """
    Normalizza il testo.
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
# ITEM ID
# ============================================

def get_item_id(item):
    """
    Genera un identificatore stabile.

    L'URL viene utilizzato come chiave primaria
    quando disponibile.
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

    time_element = element.find(
        "time"
    )

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

            normalized = normalize_date(
                time_text
            )

            if normalized:
                return normalized

    # ----------------------------------------
    # COMMON DATE ATTRIBUTES
    # ----------------------------------------

    for attribute in (
        "datetime",
        "data-date",
        "content",
    ):

        value = element.get(
            attribute
        )

        if value:

            normalized = normalize_date(
                value
            )

            if normalized:
                return normalized

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
        ".field--name-field-summary",
        ".field--name-body",
        ".summary",
        ".description",
        ".field--type-text-with-summary",
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
    Estrae il link della comunicazione FDA.
    """

    if element is None:
        return None

    links = element.find_all(
        "a",
        href=True,
    )

    # ----------------------------------------
    # Prefer official FDA news URLs
    # ----------------------------------------

    for link in links:

        href = normalize_text(
            link.get("href")
        )

        if not href:
            continue

        absolute_url = urljoin(
            base_url,
            href,
        )

        if is_valid_news_url(
            absolute_url
        ):

            return absolute_url

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

    for link in element.find_all(
        "a"
    ):

        title = normalize_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        if title:
            return title

    return ""


# ============================================
# VALID TITLE
# ============================================

def is_valid_news_title(title):
    """
    Verifica che il titolo non sia un elemento
    di navigazione della pagina FDA.
    """

    if not title:
        return False

    normalized = normalize_text(
        title
    ).lower()

    invalid_titles = {
        "press announcements",
        "skip to main content",
        "skip to fda search",
        "skip to in this section menu",
        "skip to footer links",
        "report a product problem",
        "contact fda",
        "fda guidance documents",
        "recalls, market withdrawals and safety alerts",
        "home",
        "search",
        "menu",
    }

    if normalized in invalid_titles:
        return False

    invalid_prefixes = (
        "skip to ",
        "report a ",
        "contact ",
    )

    if normalized.startswith(
        invalid_prefixes
    ):
        return False

    return True


# ============================================
# VALID NEWS URL
# ============================================

def is_valid_news_url(url):
    """
    Verifica che l'URL sia una vera pagina
    di comunicazione FDA.

    Esclude:
    - anchor;
    - pagina indice;
    - menu;
    - link generici FDA.
    """

    if not url:
        return False

    normalized = normalize_text(
        url
    ).lower()

    if "fda.gov" not in normalized:
        return False

    # ----------------------------------------
    # NO ANCHORS
    # ----------------------------------------

    if "#" in normalized:
        return False

    # ----------------------------------------
    # FDA NEWS PATH
    # ----------------------------------------

    if "/news-events/" not in normalized:
        return False

    # ----------------------------------------
    # EXCLUDED INDEX PAGES
    # ----------------------------------------

    excluded_paths = {
        "/news-events/fda-newsroom/press-announcements",
        "/news-events/fda-newsroom/press-announcements/",
        "/news-events/newsroom/press-announcements",
        "/news-events/newsroom/press-announcements/",
        "/news-events/fda-newsroom",
        "/news-events/fda-newsroom/",
        "/news-events/newsroom",
        "/news-events/newsroom/",
    }

    path = normalized.split(
        "fda.gov",
        1
    )[-1]

    if path in excluded_paths:
        return False

    # ----------------------------------------
    # PRESS ANNOUNCEMENT ARTICLE
    # ----------------------------------------

    if (
        "/news-events/press-releases/"
        in normalized
    ):
        return True

    if (
        "/news-events/fda-newsroom/"
        in normalized
    ):
        return True

    if (
        "/news-events/newsroom/"
        in normalized
    ):
        return True

    return False


# ============================================
# CONTAINER QUALITY
# ============================================

def is_news_container(element):
    """
    Verifica se un elemento contiene
    caratteristiche compatibili con una vera news.
    """

    if element is None:
        return False

    title = extract_title(
        element
    )

    if not is_valid_news_title(
        title
    ):
        return False

    url = extract_link(
        element
    )

    if not is_valid_news_url(
        url
    ):
        return False

    return True


# ============================================
# FIND NEWS CONTAINERS
# ============================================

def find_news_containers(soup):
    """
    Individua i contenitori delle vere FDA News.

    NON utilizza genericamente tutti gli <li>,
    perché la pagina FDA contiene numerosi elementi
    di navigazione.
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

    # ----------------------------------------
    # STANDARD CONTAINERS
    # ----------------------------------------

    for selector in selectors:

        found = soup.select(
            selector
        )

        if found:
            containers.extend(
                found
            )

    # ----------------------------------------
    # FALLBACK:
    # FIND LINKS TO REAL NEWS
    # ----------------------------------------

    if not containers:

        for link in soup.find_all(
            "a",
            href=True,
        ):

            href = normalize_text(
                link.get("href")
            )

            absolute_url = urljoin(
                FDA_NEWS_URL,
                href,
            )

            if not is_valid_news_url(
                absolute_url
            ):
                continue

            parent = link

            # Risale pochi livelli per trovare
            # il contenitore della notizia.

            for _ in range(5):

                if parent.parent is None:
                    break

                parent = parent.parent

                if parent.name in {
                    "article",
                    "div",
                    "li",
                }:

                    containers.append(
                        parent
                    )

                    break

    # ----------------------------------------
    # REMOVE DUPLICATES
    # ----------------------------------------

    unique = []

    seen = set()

    for container in containers:

        identity = id(
            container
        )

        if identity in seen:
            continue

        seen.add(
            identity
        )

        # ------------------------------------
        # QUALITY FILTER
        # ------------------------------------

        if not is_news_container(
            container
        ):
            continue

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

        if not is_valid_news_title(
            title
        ):
            continue

        url = extract_link(
            container,
            base_url,
        )

        if not is_valid_news_url(
            url
        ):
            continue

        summary = extract_summary(
            container
        )

        published_at = extract_date(
            container
        )

        # ------------------------------------
        # BUILD NEWS ITEM
        # ------------------------------------

        item = build_fda_news_item(
            title=title,
            summary=summary,
            url=url,
            published_at=published_at,
        )

        item["id"] = get_item_id(
            item
        )

        # ------------------------------------
        # DUPLICATE FILTER
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
    Recupera le comunicazioni pubbliche FDA.
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
    "is_valid_news_title",
    "is_valid_news_url",
    "is_news_container",
    "find_news_containers",
    "parse_fda_page",
    "get_fda_news",
    "get_fda_catalyst_news",
    "sort_fda_news",
]