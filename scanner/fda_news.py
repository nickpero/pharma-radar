"""
Pharma Radar — FDA News Feed

Acquisisce le FDA Press Announcements, classifica
le notizie come potenziali catalyst e prepara gli
oggetti utilizzati dal resto del Radar.

Questo modulo NON effettua raccomandazioni
di acquisto o vendita.
"""

import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


FDA_BASE_URL = "https://www.fda.gov"

# URL corretto della pagina FDA Newsroom / Press Announcements.
# È la stessa sorgente utilizzata dal feed FDA live funzionante.
FDA_NEWS_URL = (
    "https://www.fda.gov/news-events/fda-newsroom/"
    "press-announcements"
)

FDA_PRESS_ANNOUNCEMENTS_URL = FDA_NEWS_URL

FDA_DRUGS_URL = (
    "https://www.fda.gov/drugs/news-events-human-drugs/"
    "drug-safety-and-availability"
)

DEFAULT_MAX_NEWS = 50
DEFAULT_MAX_PAGES = 5
REQUEST_TIMEOUT = 20


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PharmaRadar/1.0; "
        "+https://www.fda.gov/)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================================
# FDA CLASSIFICATION
# ============================================================================

CATEGORY_KEYWORDS = {
    "APPROVAL": [
        "fda approves",
        "fda approved",
        "fda grants approval",
        "receives fda approval",
        "fda authorizes",
        "grants accelerated approval",
    ],
    "REJECTION": [
        "fda rejects",
        "fda rejected",
        "rejection",
        "complete response letter",
        "complete response",
        "crl",
        "refuses approval",
        "not approved",
        "application was rejected",
        "application rejected",
    ],
    "SAFETY": [
        "safety",
        "safety warning",
        "boxed warning",
        "recall",
        "adverse events",
        "adverse event",
        "risk",
        "warning",
        "withdrawn",
        "withdrawal",
    ],
    "CLINICAL": [
        "clinical trial",
        "clinical study",
        "clinical results",
        "trial results",
        "study results",
        "efficacy",
        "phase 1",
        "phase 2",
        "phase 3",
        "phase iii",
        "phase ii",
        "phase i",
        "endpoint",
        "primary endpoint",
    ],
    "LABEL": [
        "label expansion",
        "expanded indication",
        "new indication",
        "additional indication",
        "indication",
        "labeling",
        "label update",
    ],
}


CATEGORY_PRIORITY = [
    "APPROVAL",
    "REJECTION",
    "SAFETY",
    "CLINICAL",
    "LABEL",
]


PRIORITY_MAP = {
    "APPROVAL": "EXTREME",
    "REJECTION": "EXTREME",
    "SAFETY": "EXTREME",
    "CLINICAL": "HIGH",
    "LABEL": "HIGH",
}


# ============================================================================
# NORMALIZATION
# ============================================================================

def normalize_text(value):
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def normalize_date(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    text = str(value).strip()

    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )

        return parsed.isoformat()

    except ValueError:
        pass

    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]

    for date_format in formats:

        try:
            parsed = datetime.strptime(
                text,
                date_format,
            )

            return parsed.isoformat()

        except ValueError:
            continue

    return text


def normalize_url(url):
    if not url:
        return None

    url = str(url).strip()

    if not url:
        return None

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return urljoin(
            FDA_BASE_URL,
            url,
        )

    if url.startswith("http://"):
        return (
            "https://"
            + url[len("http://"):]
        )

    if url.startswith("https://"):
        return url

    return urljoin(
        FDA_BASE_URL + "/",
        url,
    )


# ============================================================================
# URL VALIDATION
# ============================================================================

def is_fda_press_announcement_url(url):
    normalized = normalize_url(url)

    if not normalized:
        return False

    parsed = urlparse(normalized)

    if parsed.scheme != "https":
        return False

    if parsed.netloc.lower() not in {
        "www.fda.gov",
        "fda.gov",
    }:
        return False

    return True


# ============================================================================
# TITLE VALIDATION
# ============================================================================

def is_valid_news_title(title):
    if not title:
        return False

    normalized = normalize_text(title)

    if len(normalized) < 8:
        return False

    blocked_titles = {
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
        "menu",
        "search",
        "home",
    }

    if normalized in blocked_titles:
        return False

    navigation_prefixes = (
        "skip to ",
        "menu",
        "search",
        "sign in",
        "subscribe",
    )

    if any(
        normalized.startswith(prefix)
        for prefix in navigation_prefixes
    ):
        return False

    return True


# ============================================================================
# ITEM ID
# ============================================================================

def get_item_id(item):
    if not isinstance(item, dict):
        raise TypeError(
            "item must be a dictionary"
        )

    source = (
        item.get("url")
        or item.get("title")
        or item.get("summary")
        or ""
    )

    return hashlib.sha256(
        str(source).encode("utf-8")
    ).hexdigest()


# ============================================================================
# CLASSIFICATION
# ============================================================================

def classify_fda_news(
    title="",
    summary="",
):
    text = normalize_text(
        f"{title or ''} {summary or ''}"
    )

    categories = []

    if not text:
        return categories

    for category, keywords in CATEGORY_KEYWORDS.items():

        for keyword in keywords:

            if normalize_text(keyword) in text:
                categories.append(category)
                break

    return categories


def classify_fda_text(
    title="",
    summary="",
):
    """
    Compatibility wrapper per il vecchio nome
    utilizzato dai test e dal codice precedente.
    """

    return classify_fda_news(
        title,
        summary,
    )


# ============================================================================
# PRIORITY
# ============================================================================

def calculate_priority(categories):
    if not categories:
        return "LOW"

    normalized = {
        str(category).upper()
        for category in categories
    }

    for category in CATEGORY_PRIORITY:

        if category in normalized:
            return PRIORITY_MAP.get(
                category,
                "LOW",
            )

    return "LOW"


def get_fda_priority(categories):
    """
    Compatibility wrapper per il vecchio API.
    """

    return calculate_priority(
        categories
    )


# ============================================================================
# NEWS ITEM
# ============================================================================

def build_fda_news_item(
    title="",
    summary="",
    url=None,
    published_at=None,
    source="FDA",
    **extra,
):
    categories = classify_fda_news(
        title,
        summary,
    )

    item = {
        "id": None,
        "source": source or "FDA",
        "title": str(title or "").strip(),
        "summary": str(summary or "").strip(),
        "url": normalize_url(url),
        "published_at": normalize_date(
            published_at
        ),
        "categories": categories,
        "priority": get_fda_priority(
            categories
        ),
    }

    for key, value in extra.items():

        if value is not None:
            item[key] = value

    item["id"] = get_item_id(
        item
    )

    return item


# ============================================================================
# HTML HELPERS
# ============================================================================

def _extract_text(node):
    if node is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        node.get_text(
            " ",
            strip=True,
        ),
    ).strip()


def _extract_link(node):
    if node is None:
        return None

    if node.name == "a":

        href = node.get("href")

        if href:
            return normalize_url(
                href
            )

    link = node.find(
        "a",
        href=True,
    )

    if link:

        return normalize_url(
            link.get("href")
        )

    return None


def _extract_date(node):
    if node is None:
        return None

    time_node = node.find(
        "time"
    )

    if time_node:

        value = time_node.get(
            "datetime"
        )

        if value:
            return normalize_date(
                value
            )

        text = _extract_text(
            time_node
        )

        if text:
            return normalize_date(
                text
            )

    for attribute in (
        "datetime",
        "data-date",
        "data-published",
        "data-publish-date",
    ):

        value = node.get(
            attribute
        )

        if value:
            return normalize_date(
                value
            )

    text = _extract_text(
        node
    )

    date_patterns = [
        r"\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\.?\s+\d{1,2},\s+\d{4}\b",
    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return normalize_date(
                match.group(0)
            )

    return None


def _extract_article_fields(article):
    title = ""
    summary = ""
    url = None
    published_at = None

    title_node = (
        article.find("h1")
        or article.find("h2")
        or article.find("h3")
        or article.find("h4")
    )

    if title_node:

        title = _extract_text(
            title_node
        )

    url = _extract_link(
        article
    )

    summary_candidates = [
        article.find(
            "div",
            class_=re.compile(
                "summary",
                re.I,
            ),
        ),
        article.find(
            "div",
            class_=re.compile(
                "description",
                re.I,
            ),
        ),
        article.find(
            "div",
            class_=re.compile(
                "teaser",
                re.I,
            ),
        ),
        article.find("p"),
    ]

    for candidate in summary_candidates:

        text = _extract_text(
            candidate
        )

        if text and text != title:

            summary = text
            break

    published_at = _extract_date(
        article
    )

    content = _extract_text(
        article
    )

    return {
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": published_at,
        "content": content,
        "description": summary,
    }


def _extract_direct_links(soup):
    results = []

    for link in soup.find_all(
        "a",
        href=True,
    ):

        href = normalize_url(
            link.get("href")
        )

        if not href:
            continue

        parsed = urlparse(
            href
        )

        path = parsed.path.lower()

        if (
            "/news-events/"
            not in path
        ):
            continue

        if (
            "press-announcement"
            not in path
        ):
            continue

        title = _extract_text(
            link
        )

        if not is_valid_news_title(
            title
        ):
            continue

        results.append(
            {
                "title": title,
                "summary": "",
                "url": href,
                "published_at": None,
                "content": title,
                "description": "",
            }
        )

    return results


# ============================================================================
# PAGE PARSER
# ============================================================================

def parse_fda_page(
    html,
    base_url=FDA_NEWS_URL,
):
    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    # ------------------------------------------------------------------------
    # ARTICLE PARSER
    # ------------------------------------------------------------------------

    for article in soup.find_all(
        "article"
    ):

        fields = _extract_article_fields(
            article
        )

        title = fields.get(
            "title",
            "",
        )

        url = fields.get(
            "url"
        )

        if not is_valid_news_title(
            title
        ):
            continue

        if url and not is_fda_press_announcement_url(
            url
        ):
            continue

        if not url:
            continue

        results.append(
            fields
        )

    # ------------------------------------------------------------------------
    # DIRECT LINK FALLBACK
    # ------------------------------------------------------------------------

    results.extend(
        _extract_direct_links(
            soup
        )
    )

    # ------------------------------------------------------------------------
    # DEDUPLICATION
    # ------------------------------------------------------------------------

    unique = []

    seen = set()

    for item in results:

        title = normalize_text(
            item.get("title")
        )

        url = normalize_url(
            item.get("url")
        )

        key = (
            url
            or title
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(
            key
        )

        item["url"] = url

        unique.append(
            item
        )

    return unique


# ============================================================================
# HTTP FETCH
# ============================================================================

def fetch_fda_page(
    page=0,
):
    try:
        page = int(page)

    except (
        ValueError,
        TypeError,
    ):
        page = 0

    if page <= 0:

        url = FDA_NEWS_URL

    else:

        url = (
            f"{FDA_NEWS_URL}"
            f"?page={page}"
        )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.text


# ============================================================================
# NEWS FEED
# ============================================================================

def get_fda_news(
    max_news=DEFAULT_MAX_NEWS,
    max_pages=DEFAULT_MAX_PAGES,
):
    try:
        max_news = int(
            max_news
        )

    except (
        ValueError,
        TypeError,
    ):
        max_news = DEFAULT_MAX_NEWS

    try:
        max_pages = int(
            max_pages
        )

    except (
        ValueError,
        TypeError,
    ):
        max_pages = DEFAULT_MAX_PAGES

    if max_news <= 0:
        return []

    if max_pages <= 0:
        max_pages = 1

    news = []

    seen = set()

    for page in range(
        max_pages
    ):

        try:
            html = fetch_fda_page(
                page
            )

        except Exception:
            # Manteniamo la compatibilità con il comportamento
            # precedente, ma non interrompiamo le pagine successive.
            continue

        parsed_items = parse_fda_page(
            html,
            base_url=FDA_NEWS_URL,
        )

        if not parsed_items:

            if page > 0:
                break

            continue

        for raw_item in parsed_items:

            title = raw_item.get(
                "title",
                "",
            )

            summary = raw_item.get(
                "summary",
                "",
            )

            url = raw_item.get(
                "url"
            )

            published_at = raw_item.get(
                "published_at"
            )

            if not is_valid_news_title(
                title
            ):
                continue

            key = (
                normalize_url(url)
                or normalize_text(title)
            )

            if not key:
                continue

            if key in seen:
                continue

            seen.add(
                key
            )

            item = build_fda_news_item(
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
                source="FDA",
                content=raw_item.get(
                    "content",
                    "",
                ),
                description=raw_item.get(
                    "description",
                    "",
                ),
            )

            news.append(
                item
            )

            if len(news) >= max_news:

                return news[
                    :max_news
                ]

    return news[
        :max_news
    ]


# ============================================================================
# FDA CATALYST NEWS
# ============================================================================

def get_fda_catalyst_news(
    max_items=DEFAULT_MAX_NEWS,
):
    return get_fda_news(
        max_news=max_items,
        max_pages=DEFAULT_MAX_PAGES,
    )


# ============================================================================
# CATALYST FILTER
# ============================================================================

def filter_fda_catalysts(
    news_items,
):
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

        if categories:

            results.append(
                item
            )

    return results


# ============================================================================
# SORT
# ============================================================================

def sort_fda_news(
    news_items,
):
    priority = {
        "EXTREME": 4,
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    return sorted(
        news_items or [],
        key=lambda item: (
            priority.get(
                str(
                    item.get(
                        "priority",
                        "LOW",
                    )
                ).upper(),
                0,
            ),
            str(
                item.get(
                    "published_at"
                )
                or ""
            ),
        ),
        reverse=True,
    )


# ============================================================================
# DEDUPLICATION
# ============================================================================

def deduplicate_fda_news(
    news_items,
):
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

        key = (
            item.get("id")
            or normalize_url(
                item.get("url")
            )
            or normalize_text(
                item.get("title")
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


# ============================================================================
# FDA SOURCES
# ============================================================================

def get_fda_sources():
    """
    Restituisce le sorgenti FDA utilizzate dal Radar.

    Mantiene il contratto storico atteso dai test.
    """

    return {
        "drug_approvals": FDA_DRUGS_URL,
        "press_announcements": FDA_NEWS_URL,
    }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "FDA_BASE_URL",
    "FDA_DRUGS_URL",
    "FDA_NEWS_URL",
    "FDA_PRESS_ANNOUNCEMENTS_URL",
    "DEFAULT_MAX_NEWS",
    "DEFAULT_MAX_PAGES",
    "CATEGORY_KEYWORDS",
    "CATEGORY_PRIORITY",
    "PRIORITY_MAP",
    "normalize_text",
    "normalize_date",
    "normalize_url",
    "is_fda_press_announcement_url",
    "is_valid_news_title",
    "get_item_id",
    "classify_fda_news",
    "classify_fda_text",
    "calculate_priority",
    "get_fda_priority",
    "build_fda_news_item",
    "_extract_text",
    "_extract_link",
    "_extract_date",
    "_extract_article_fields",
    "_extract_direct_links",
    "parse_fda_page",
    "fetch_fda_page",
    "get_fda_news",
    "get_fda_catalyst_news",
    "filter_fda_catalysts",
    "sort_fda_news",
    "deduplicate_fda_news",
    "get_fda_sources",
]