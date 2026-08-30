"""
Pharma Radar — FDA Feed

Recupera le comunicazioni pubbliche FDA e le
trasforma in News Item standardizzati.

Responsabilità:
- recuperare le news FDA;
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
# PARSE DATE
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
    # TEXT SEARCH
    # ----------------------------------------

    text = element.get_text(
        " ",
        strip=True,
    )

    # Regex volutamente semplice e bilanciata.
    #
    # Esempio:
    # August 30, 2026

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

            title = normalize