"""
Pharma Radar — FDA Feed

Recupera le comunicazioni pubbliche FDA e le
trasforma in News Item standardizzati.

Responsabilità del modulo:
- recuperare le news FDA;
- estrarre titolo, URL, data e testo;
- eliminare duplicati;
- restituire dati compatibili con fda_news.py.

NON effettua:
- scoring;
- matching con aziende;
- Trading Intelligence;
- invio Telegram.
"""

import re
import hashlib
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
        "PharmaRadar/1.0 "
        "(research monitoring tool)"
    )
}


# ============================================
# FETCH
# ============================================

def fetch_fda_page(
    url=FDA_NEWS_URL,
):
    """
    Recupera una pagina FDA.

    Restituisce l'HTML oppure solleva
    un'eccezione HTTP.
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
    Normalizza testo HTML/plain text.
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
    Genera un identificatore stabile per una news.

    L'URL è la chiave primaria quando disponibile.
    In assenza dell'URL viene utilizzato titolo +
    data.
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
        value.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================
# PARSE DATE
# ============================================

def normalize_date(value):
    """
    Normalizza una data FDA in formato ISO.

    Se la data non è interpretabile, restituisce
    comunque il valore originale normalizzato.
    """

    if not value:
        return None

    value = normalize_text(
        value
    )

    # ----------------------------------------
    # ISO DATE
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
    # COMMON FDA FORMAT
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
    Cerca una data all'interno di un elemento.
    """

    if element is None:
        return None

    # ----------------------------------------
    # <time datetime="...">
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

        text = time_element.get_text(
            " ",
            strip=True,
        )

        if text:
            return normalize_date(
                text
            )

    # ----------------------------------------
    # TEXT
    # ----------------------------------------

    text = element.get_text(
        " ",
        strip=True,
    )

    match = re.search(
        r"""
        (
            January|February|March|April|
            May|June|July|August|
            September|October|November|December
        )
        \s+
        \d{1,2}
        ,
        \s+
        \d{4}
        )
        """,
        text,
        re.IGNORECASE | re.VERBOSE,
    )

    if match:

        return normalize_date(
            match.group(1)
        )

    return None


# ============================================
# EXTRACT SUMMARY
# ============================================

def extract_summary(element):
    """
    Estrae una breve descrizione dalla card FDA.
    """

    if element is None:
        return ""

    # ----------------------------------------
    # COMMON DESCRIPTION TAGS
    # ----------------------------------------

    selectors = [
        "p",
        ".field--name-body",
        ".field--name-field-summary",
        ".summary",
        ".description",
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
        "h1",
        "h2",
        "h3",
        "h4",
        ".field--name-title",
        ".node-title",
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
    # FALLBACK LINK TEXT
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
    Individua i contenitori delle comunicazioni
    FDA.

    La funzione utilizza più strategie per
    tollerare piccole variazioni del markup FDA.
    """

    selectors = [

        "article",

        ".node--type-press-release",

        ".node--type-news",

        ".views-row",

        ".news-item",

        ".press-release",

        "li",
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
    Converte l'HTML FDA in una lista di
    News Item standardizzati.
    """

    if not html:
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

        # ------------------------------------
        # VALIDATION
        # ------------------------------------

        if not title:
            continue

        # Un contenitore senza URL e senza
        # data è meno affidabile, ma può
        # comunque essere utilizzato.

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
    Recupera e analizza le comunicazioni
    pubbliche FDA.
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
# FILTER CATALYST NEWS
# ============================================

def get_fda_catalyst_news(
    max_items=MAX_ITEMS,
):
    """
    Recupera soltanto le news FDA con
    priorità HIGH o EXTREME.
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
    Ordina le news mettendo prima le più
    rilevanti.
    """

    priority_order = {
        "EXTREME": 3,
        "HIGH": 2,
        "LOW": 1,
    }

    return sorted(
        news_items,
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
    "find_news_containers",
    "parse_fda_page",
    "get_fda_news",
    "get_fda_catalyst_news",
    "sort_fda_news",
]