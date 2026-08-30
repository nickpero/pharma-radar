"""
Pharma Radar — FDA News Feed

Recupera le comunicazioni pubbliche della FDA
utilizzabili come possibili catalyst Pharma.

Questo modulo NON decide se una notizia è
tradabile: fornisce dati strutturati al
motore di classificazione.
"""

import re
import requests


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


# ============================================
# HTTP SETTINGS
# ============================================

REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "PharmaRadar/1.0 "
        "(research monitoring tool)"
    )
}


# ============================================
# KEYWORDS
# ============================================

FDA_CATALYST_KEYWORDS = {

    "APPROVAL": [
        "approves",
        "approved",
        "approval",
    ],

    "REJECTION": [
        "complete response letter",
        "rejected",
        "rejects",
        "refuses",
        "refusal",
    ],

    "SAFETY": [
        "safety",
        "safety concern",
        "safety signal",
        "adverse event",
        "warning",
        "recall",
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
    ],

    "LABEL": [
        "label",
        "labeling",
        "indication",
        "expanded indication",
    ],
}


# ============================================
# HTTP GET
# ============================================

def fetch_url(url):
    """
    Scarica una pagina FDA.
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
    Normalizza il testo per la classificazione.
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
# CLASSIFY FDA TEXT
# ============================================

def classify_fda_text(title, summary=""):
    """
    Classifica una comunicazione FDA
    in base alle parole chiave.
    """

    title = normalize_text(
        title
    )

    summary = normalize_text(
        summary
    )

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
    Determina la priorità iniziale della
    comunicazione FDA.

    Questa è una classificazione preliminare.
    Lo scoring finale avverrà nel Trading
    Intelligence layer.
    """

    categories = set(
        categories or []
    )

    if categories.intersection({
        "APPROVAL",
        "REJECTION",
        "SAFETY",
    }):
        return "EXTREME"

    if categories.intersection({
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
    Costruisce un oggetto news standardizzato.
    """

    title = normalize_text(
        title
    )

    summary = normalize_text(
        summary
    )

    categories = classify_fda_text(
        title,
        summary
    )

    priority = get_fda_priority(
        categories
    )

    return {
        "source": "FDA",
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": published_at,
        "categories": categories,
        "priority": priority,
    }


# ============================================
# FILTER CATALYST NEWS
# ============================================

def filter_fda_catalysts(news_items):
    """
    Restituisce soltanto le comunicazioni
    FDA con potenziale rilevanza.
    """

    catalysts = []

    for item in news_items:

        if item.get(
            "priority"
        ) in {
            "EXTREME",
            "HIGH",
        }:

            catalysts.append(
                item
            )

    return catalysts


# ============================================
# PUBLIC API
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