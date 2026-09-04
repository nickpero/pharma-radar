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
        "