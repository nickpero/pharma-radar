"""
Pharma Radar — FDA News Feed

Recupera le comunicazioni pubbliche della FDA
utilizzabili come possibili catalyst Pharma.

Il modulo:
- scarica la pagina ufficiale FDA;
- estrae le Press Announcements;
- normalizza titolo, data e URL;
- classifica le news;
- assegna una priorità preliminare;
- prepara dati strutturati per i successivi
  motori Catalyst, Score e Trading Intelligence.

IMPORTANTE:
Questo modulo NON decide se una notizia è
tradabile e NON produce raccomandazioni
di acquisto o vendita.
"""


import re
from html.parser import HTMLParser
from urllib.parse import urljoin

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
    ),
    "Accept": (
        "text/html,"
        "application/xhtml+xml"
    ),
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
# HTML PARSER
# ============================================

class FDAAnnouncementParser(HTMLParser):
    """
    Parser HTML leggero per la pagina FDA
    Press Announcements.

    Non dipende da BeautifulSoup o da altre
    librerie esterne.
    """

    def __init__(self):

        super().__init__()

        self.announcements = []

        self.current_link = None
        self.current_text = []

        self.current_date = None

        self.in_heading = False
        self.in_date = False

    # ----------------------------------------
    # START TAG
    # ----------------------------------------

    def handle_starttag(self, tag, attrs):

        attributes = dict(
            attrs
        )

        # ------------------------------------
        # Heading / link
        # ------------------------------------

        if tag.lower() in {
            "h2",
            "h3",
            "h4",
        }:

            self.in_heading = True
            self.current_text = []

            href = attributes.get(
                "href"
            )

            if href:

                self.current_link = href

        # ------------------------------------
        # Link
        # ------------------------------------

        elif tag.lower() == "a":

            href = attributes.get(
                "href"
            )

            if href:

                self.current_link = href

                self.current_text = []

        # ------------------------------------
        # Time / date
        # ------------------------------------

        elif tag.lower() == "time":

            self.in_date = True

            self.current_date = (
                attributes.get(
                    "datetime"
                )
            )

    # ----------------------------------------
    # DATA
    # ----------------------------------------

    def handle_data(self, data):

        if self.in_heading:

            self.current_text.append(
                data
            )

        if self.in_date:

            text = normalize_text(
                data
            )

            if text:

                self.current_date = (
                    self.current_date
                    or text
                )

    # ----------------------------------------
    # END TAG
    # ----------------------------------------

    def handle_endtag(self, tag):

        tag = tag.lower()

        # ------------------------------------
        # Heading completed
        # ------------------------------------

        if tag in {
            "h2",
            "h3",
            "h4",
        }:

            title = normalize_text(
                " ".join(
                    self.current_text
                )
            )

            if (
                title
                and self.current_link
            ):

                self.announcements.append({
                    "title": title,
                    "url": self.current_link,
                    "published_at": (
                        self.current_date
                    ),
                })

            self.in_heading = False
            self.current_text = []

        # ------------------------------------
        # Link completed
        # ------------------------------------

        elif tag == "a":

            if (
                self.current_text
                and self.current_link
            ):

                title = normalize_text(
                    " ".join(
                        self.current_text
                    )
                )

                # Only keep likely FDA
                # announcement links.
                if (
                    title
                    and self.current_link
                ):

                    self.announcements.append({
                        "title": title,
                        "url": self.current_link,
                        "published_at": (
                            self.current_date
                        ),
                    })

            self.current_text = []

        # ------------------------------------
        # Date completed
        # ------------------------------------

        elif tag == "time":

            self.in_date = False


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
# NORMALIZE URL
# ============================================

def normalize_url(url):
    """
    Converte un URL FDA relativo in assoluto.
    """

    if not url:

        return None

    url = str(
        url
    ).strip()

    return urljoin(
        FDA_NEWS_URL,
        url
    )


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

    Questa è una classificazione preliminare.
    Lo scoring finale avverrà nel Trading
    Intelligence layer.
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
# PARSE PRESS ANNOUNCEMENTS
# ============================================

def parse_fda_press_announcements(
    html,
    max_items=DEFAULT_MAX_NEWS
):
    """
    Estrae le Press Announcements dalla
    pagina HTML FDA.

    Restituisce una lista di news standardizzate.
    """

    if not html:

        return []

    parser = FDAAnnouncementParser()

    parser.feed(
        html
    )

    results = []

    seen = set()

    for announcement in (
        parser.announcements
    ):

        title = normalize_text(
            announcement.get(
                "title",
                ""
            )
        )

        if not title:
            continue

        url = normalize_url(
            announcement.get(
                "url"
            )
        )

        published_at = (
            announcement.get(
                "published_at"
            )
        )

        key = (
            title.lower(),
            url or ""
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        item = build_fda_news_item(
            title=title,
            summary="",
            url=url,
            published_at=published_at,
        )

        results.append(
            item
        )

        if (
            max_items is not None
            and len(results) >= max_items
        ):

            break

    return results


# ============================================
# FETCH PRESS ANNOUNCEMENTS
# ============================================

def fetch_fda_press_announcements(
    max_items=DEFAULT_MAX_NEWS
):
    """
    Scarica e interpreta le ultime Press
    Announcements pubblicate dalla FDA.
    """

    html = fetch_url(
        FDA_NEWS_URL
    )

    return parse_fda_press_announcements(
        html,
        max_items=max_items
    )


# ============================================
# FILTER CATALYST NEWS
# ============================================

def filter_fda_catalysts(news_items):
    """
    Restituisce soltanto le comunicazioni
    FDA con potenziale rilevanza.
    """

    catalysts = []

    for item in (
        news_items or []
    ):

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
# DEDUPLICATE NEWS
# ============================================

def deduplicate_fda_news(
    news_items
):
    """
    Elimina eventuali duplicati.

    La deduplicazione usa titolo + URL.
    """

    if not news_items:

        return []

    results = []

    seen = set()

    for item in news_items:

        title = normalize_text(
            item.get(
                "title",
                ""
            )
        ).lower()

        url = normalize_url(
            item.get(
                "url"
            )
        )

        key = (
            title,
            url or ""
        )

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