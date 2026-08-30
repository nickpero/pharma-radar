"""
Pharma Radar — FDA News Feed

Recupera comunicazioni pubbliche FDA tramite
feed RSS ufficiali e le trasforma in oggetti
strutturati utilizzabili dal Pharma Radar.

Pipeline:

FDA RSS
    ↓
News Item
    ↓
Keyword Classification
    ↓
FDA Priority
    ↓
FDA Catalyst

Questo modulo NON decide se una notizia è
tradabile.
"""

import re
import requests
import xml.etree.ElementTree as ET


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
    "news-events/fda-newsroom/press-announcements"
)

# FDA official RSS feed for press releases.
#
# FDA publishes official RSS feeds for agency
# news and announcements.
FDA_PRESS_RSS_URL = (
    "https://www.fda.gov/about-fda/"
    "contact-fda/subscribe-podcasts-and-news-feeds"
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
        "approving",
    ],

    "REJECTION": [
        "complete response letter",
        "rejected",
        "rejects",
        "refuses",
        "refusal",
        "not approved",
        "cannot approve",
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
        "serious adverse",
    ],

    "CLINICAL": [
        "clinical trial",
        "clinical study",
        "phase 1",
        "phase 2",
        "phase 3",
        "primary endpoint",
        "secondary endpoint",
        "endpoint",
        "efficacy",
        "clinical results",
    ],

    "LABEL": [
        "label",
        "labeling",
        "indication",
        "expanded indication",
        "expands indication",
        "new indication",
        "label expansion",
    ],
}


# ============================================
# HTTP GET
# ============================================

def fetch_url(url):
    """
    Scarica una pagina o un feed FDA.
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
    Normalizza il testo.
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

def classify_fda_text(
    title,
    summary=""
):
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
    """

    categories = {
        str(category).upper()
        for category in (
            categories or []
        )
    }

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
    Restituisce soltanto le comunicazioni FDA
    con potenziale rilevanza.
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
# XML HELPERS
# ============================================

def _strip_namespace(tag):
    """
    Rimuove il namespace XML dal tag.
    """

    if "}" in tag:

        return tag.split(
            "}",
            1
        )[1]

    return tag


def _find_text(element, names):
    """
    Cerca il primo elemento XML corrispondente
    ai nomi forniti.
    """

    names = {
        str(name).lower()
        for name in names
    }

    for child in element.iter():

        tag = _strip_namespace(
            child.tag
        ).lower()

        if tag in names:

            return normalize_text(
                child.text
            )

    return ""


# ============================================
# PARSE RSS
# ============================================

def parse_fda_rss(xml_text):
    """
    Converte un feed RSS/XML FDA in una lista
    di News Items.

    Supporta RSS standard e namespace XML.
    """

    if not xml_text:
        return []

    root = ET.fromstring(
        xml_text
    )

    items = []

    for element in root.iter():

        tag = _strip_namespace(
            element.tag
        ).lower()

        if tag not in {
            "item",
            "entry",
        }:

            continue

        title = _find_text(
            element,
            {
                "title",
            }
        )

        summary = _find_text(
            element,
            {
                "description",
                "summary",
                "content",
            }
        )

        published_at = _find_text(
            element,
            {
                "pubdate",
                "published",
                "updated",
                "date",
            }
        )

        url = None

        # ------------------------------------
        # RSS <link>
        # ------------------------------------

        for child in element:

            tag_name = _strip_namespace(
                child.tag
            ).lower()

            if tag_name == "link":

                if child.text:

                    url = (
                        child.text.strip()
                    )

                elif child.attrib.get(
                    "href"
                ):

                    url = (
                        child.attrib[
                            "href"
                        ]
                    )

                if url:
                    break

        if not title:
            continue

        items.append(
            build_fda_news_item(
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
            )
        )

    return items


# ============================================
# FETCH FDA RSS
# ============================================

def fetch_fda_rss(
    rss_url=None
):
    """
    Scarica e interpreta un feed RSS FDA.

    Nota:
    l'URL RSS può essere fornito dal feed
    ufficiale FDA configurato nel progetto.
    """

    if rss_url is None:

        raise ValueError(
            "rss_url must be provided"
        )

    xml_text = fetch_url(
        rss_url
    )

    return parse_fda_rss(
        xml_text
    )


# ============================================
# GET FDA NEWS
# ============================================

def get_fda_news(
    rss_url=None
):
    """
    Recupera le news FDA dal feed RSS
    configurato.

    Restituisce sempre una lista.
    """

    if rss_url is None:

        return []

    try:

        return fetch_fda_rss(
            rss_url
        )

    except (
        requests.RequestException,
        ET.ParseError,
        ValueError,
    ):

        return []


# ============================================
# GET FDA CATALYST NEWS
# ============================================

def get_fda_catalyst_news(
    rss_url=None
):
    """
    Recupera soltanto le news FDA
    considerate potenziali catalyst.
    """

    news = get_fda_news(
        rss_url
    )

    return filter_fda_catalysts(
        news
    )


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
        "press_rss": FDA_PRESS_RSS_URL,
    }