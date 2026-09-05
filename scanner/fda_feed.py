"""
Pharma Radar — FDA Feed Engine

Raccoglie, normalizza e deduplica le notizie FDA.

NON effettua raccomandazioni di acquisto o vendita.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================
# FDA SOURCES
# ============================================

FDA_NEWS_URL = (
    "https://www.fda.gov/news-events/fda-newsroom/"
    "press-announcements"
)

FDA_PRESS_ANNOUNCEMENTS_URL = FDA_NEWS_URL

FDA_DRUGS_URL = (
    "https://www.fda.gov/drugs/news-events-human-drugs/"
    "drug-safety-and-availability"
)

FDA_WHATS_NEW_URL = (
    "https://www.fda.gov/drugs/news-events-human-drugs/"
    "whats-new-related-drugs"
)

FDA_NOTABLE_APPROVALS_URL = (
    "https://www.fda.gov/drugs/news-events-human-drugs/"
    "notable-approvals-drugs"
)

FDA_NOVEL_APPROVALS_2026_URL = (
    "https://www.fda.gov/drugs/novel-drug-approvals-fda/"
    "novel-drug-approvals-2026"
)

FDA_ONCOLOGY_APPROVALS_URL = (
    "https://www.fda.gov/drugs/resources-information-approved-drugs/"
    "oncology-cancerhematologic-malignancies-approval-notifications"
)


# ============================================
# CONFIG
# ============================================

DEFAULT_MAX_NEWS = 50
DEFAULT_MAX_PAGES = 5
REQUEST_TIMEOUT = 20

USER_AGENT = (
    "Mozilla/5.0 (compatible; PharmaRadar/1.0; "
    "+https://github.com/)"
)


# ============================================
# CLASSIFICATION
# ============================================

CATEGORY_KEYWORDS = {
    "APPROVAL": [
        "approved",
        "approval",
        "approves",
        "approving",
        "grants approval",
        "granted approval",
        "accelerated approval",
        "full approval",
        "fda approval",
        "new drug approval",
    ],
    "REJECTION": [
        "rejected",
        "rejection",
        "refuses approval",
        "refused approval",
        "complete response letter",
        "crl",
        "not approved",
        "declined approval",
    ],
    "SAFETY": [
        "safety warning",
        "safety communication",
        "boxed warning",
        "recall",
        "serious adverse",
        "adverse event",
        "safety concern",
        "risk",
        "withdrawn",
        "withdrawal",
        "label warning",
    ],
    "CLINICAL": [
        "clinical trial",
        "clinical study",
        "clinical results",
        "trial results",
        "phase 1",
        "phase 2",
        "phase 3",
        "efficacy",
        "primary endpoint",
        "topline",
        "clinical benefit",
    ],
    "LABEL": [
        "label expansion",
        "expanded indication",
        "new indication",
        "additional indication",
        "indication expanded",
        "label update",
        "labeling update",
    ],
}

PRIORITY_SCORE = {
    "APPROVAL": 5,
    "REJECTION": 5,
    "SAFETY": 5,
    "CLINICAL": 4,
    "LABEL": 4,
}

CATEGORY_PRIORITY = [
    "APPROVAL",
    "REJECTION",
    "SAFETY",
    "CLINICAL",
    "LABEL",
]


# ============================================
# HTTP
# ============================================

def _get_session():
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    return session


def _fetch_html(url):
    response = _get_session().get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.text


# ============================================
# TEXT
# ============================================

def normalize_text(value):
    if value is None:
        return ""

    text = str(value)

    text = text.replace(
        "\u00a0",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _clean_text(value):
    return normalize_text(value)


# ============================================
# URL
# ============================================

def _normalize_url(url):
    if not url:
        return None

    url = str(url).strip()

    if not url:
        return None

    url = url.split(
        "#",
        1,
    )[0]

    return url


def is_fda_url(url):
    """
    True se l'URL appartiene a FDA.gov.
    """

    if not url:
        return False

    try:
        hostname = urlparse(
            str(url)
        ).netloc.lower()
    except Exception:
        return False

    return (
        hostname == "fda.gov"
        or hostname.endswith(".fda.gov")
    )


def is_fda_press_announcement_url(url):
    """
    True se l'URL appartiene alla sezione
    FDA Press Announcements.
    """

    if not url:
        return False

    normalized = _normalize_url(
        url
    )

    if not normalized:
        return False

    if not is_fda_url(
        normalized
    ):
        return False

    parsed = urlparse(
        normalized
    )

    path = parsed.path.rstrip(
        "/"
    ).lower()

    expected_path = (
        "/news-events/fda-newsroom/"
        "press-announcements"
    )

    return (
        path == expected_path
        or path.startswith(
            expected_path + "/"
        )
    )


# ============================================
# DATE
# ============================================

def normalize_date(value):

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    text = normalize_text(value)

    if not text:
        return None

    iso_candidate = text.replace(
        "Z",
        "+00:00",
    )

    try:
        parsed = datetime.fromisoformat(
            iso_candidate
        )

        return parsed.isoformat()

    except ValueError:
        pass

    patterns = [
        (
            r"\b("
            r"January|February|March|April|May|June|July|August|"
            r"September|October|November|December"
            r")\s+"
            r"(\d{1,2}),\s+(\d{4})\b",
            "%B %d, %Y",
        ),
        (
            r"\b("
            r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
            r")\.?\s+"
            r"(\d{1,2}),\s+(\d{4})\b",
            "%b %d, %Y",
        ),
        (
            r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
            "%m/%d/%Y",
        ),
    ]

    for pattern, date_format in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        candidate = match.group(0).replace(
            ".",
            "",
        )

        try:
            return datetime.strptime(
                candidate,
                date_format,
            ).isoformat()

        except ValueError:
            continue

    return None


def _extract_date(text):
    return normalize_date(text)


# ============================================
# ITEM ID
# ============================================

def get_item_id(item):

    if not isinstance(
        item,
        dict,
    ):
        return None

    url = _normalize_url(
        item.get("url")
    )

    if url:

        identity = url.lower()

    else:

        title = normalize_text(
            item.get(
                "title",
                "",
            )
        )

        if not title:
            return None

        identity = re.sub(
            r"[^a-z0-9]+",
            " ",
            title.lower(),
        ).strip()

        if not identity:
            return None

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


# ============================================
# HTML EXTRACTION
# ============================================

def extract_title(element):

    if element is None:
        return ""

    if isinstance(
        element,
        str,
    ):
        return normalize_text(element)

    for selector in (
        "h1",
        "h2",
        "h3",
        ".field--name-title",
        ".node__title",
        ".title",
    ):

        found = element.select_one(
            selector
        )

        if found:

            text = normalize_text(
                found.get_text(
                    " ",
                    strip=True,
                )
            )

            if text:
                return text

    return normalize_text(
        element.get_text(
            " ",
            strip=True,
        )
    )


def extract_link(
    element,
    base_url=FDA_NEWS_URL,
):

    if element is None:
        return None

    href = None

    if hasattr(
        element,
        "get",
    ):

        href = element.get(
            "href"
        )

        if not href:

            anchor = element.find(
                "a",
                href=True,
            )

            if anchor is not None:

                href = anchor.get(
                    "href"
                )

    if not href:
        return None

    href = str(
        href
    ).strip()

    if not href:
        return None

    href = urljoin(
        base_url,
        href,
    )

    return _normalize_url(
        href
    )


def extract_summary(element):

    if element is None:
        return ""

    if isinstance(
        element,
        str,
    ):
        return normalize_text(element)

    for selector in (
        ".field--name-body",
        ".field--name-field-body",
        ".field--name-field-summary",
        ".summary",
        ".description",
        ".teaser",
        "p",
    ):

        found = element.select_one(
            selector
        )

        if found:

            text = normalize_text(
                found.get_text(
                    " ",
                    strip=True,
                )
            )

            if text:
                return text

    return normalize_text(
        element.get_text(
            " ",
            strip=True,
        )
    )


def extract_date(element):

    if element is None:
        return None

    if isinstance(
        element,
        str,
    ):
        return normalize_date(
            element
        )

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

    time_element = element.find(
        "time"
    )

    if time_element:

        for attribute in (
            "datetime",
            "data-date",
        ):

            value = time_element.get(
                attribute
            )

            if value:

                normalized = normalize_date(
                    value
                )

                if normalized:
                    return normalized

        text = normalize_text(
            time_element.get_text(
                " ",
                strip=True,
            )
        )

        normalized = normalize_date(
            text
        )

        if normalized:
            return normalized

    text = normalize_text(
        element.get_text(
            " ",
            strip=True,
        )
    )

    return normalize_date(
        text
    )


# ============================================
# ARCHIVE
# ============================================

def _is_archive_artifact(
    title,
    url,
):

    title_clean = normalize_text(
        title
    ).lower()

    url_clean = str(
        url or ""
    ).lower()

    if title_clean in {
        "2018-2020",
        "2019-2020",
        "2020",
        "archive",
    }:
        return True

    if "wayback.archive" in url_clean:
        return True

    if "archive-it.org" in url_clean:
        return True

    if "/archive/" in url_clean:
        return True

    return False


# ============================================
# CLASSIFICATION
# ============================================

def classify_fda_text(
    title="",
    summary="",
):

    text = (
        f"{title} {summary}"
    ).lower()

    categories = set()

    for category, keywords in CATEGORY_KEYWORDS.items():

        for keyword in keywords:

            if keyword.lower() in text:

                categories.add(
                    category
                )

                break

    return sorted(
        categories,
        key=lambda value: (
            CATEGORY_PRIORITY.index(
                value
            )
            if value in CATEGORY_PRIORITY
            else 999
        ),
    )


def get_fda_priority(categories):

    if not categories:
        return "LOW"

    normalized = {
        str(category).upper()
        for category in categories
    }

    if "APPROVAL" in normalized:
        return "EXTREME"

    if "REJECTION" in normalized:
        return "EXTREME"

    if "SAFETY" in normalized:
        return "EXTREME"

    if "CLINICAL" in normalized:
        return "HIGH"

    if "LABEL" in normalized:
        return "HIGH"

    return "LOW"


def calculate_priority(
    categories,
    title="",
    summary="",
):

    combined_categories = {
        str(category).upper()
        for category in (
            categories or []
        )
    }

    combined_categories.update(
        classify_fda_text(
            title=title,
            summary=summary,
        )
    )

    if not combined_categories:
        return "LOW"

    score = max(
        PRIORITY_SCORE.get(
            category,
            0,
        )
        for category in combined_categories
    )

    if score >= 5:
        return "EXTREME"

    if score >= 4:
        return "HIGH"

    if score >= 2:
        return "MEDIUM"

    return "LOW"


# ============================================
# NEWS ITEM
# ============================================

def build_fda_news_item(
    title,
    url,
    summary="",
    published_at=None,
    source="FDA",
):

    title = normalize_text(
        title
    )

    summary = normalize_text(
        summary
    )

    url = _normalize_url(
        url
    )

    if published_at:
        published_at = normalize_date(
            published_at
        )

    categories = classify_fda_text(
        title=title,
        summary=summary,
    )

    priority = calculate_priority(
        categories=categories,
        title=title,
        summary=summary,
    )

    return {
        "source": source,
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": published_at,
        "categories": categories,
        "priority": priority,
    }


# ============================================
# ARTICLE CONTENT
# ============================================

def _extract_article_content(html):

    if not html:
        return ""

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
            "header",
            "form",
        ]
    ):
        tag.decompose()

    candidates = []

    selectors = [
        "main",
        "article",
        ".field--name-body",
        ".field--name-field-body",
        ".node__content",
        ".content",
        "#main-content",
    ]

    for selector in selectors:

        for element in soup.select(
            selector
        ):

            text = normalize_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(text) >= 100:
                candidates.append(
                    text
                )

    if not candidates:

        body = soup.find(
            "body"
        )

        if body:

            text = normalize_text(
                body.get_text(
                    " ",
                    strip=True,
                )
            )

            if text:
                candidates.append(
                    text
                )

    if not candidates:
        return ""

    return max(
        candidates,
        key=len,
    )[:20000]


def _enrich_article_item(
    item,
    session=None,
):

    url = item.get(
        "url"
    )

    if not url:
        return item

    if not is_fda_url(
        url
    ):
        return item

    try:

        if session is None:
            session = _get_session()

        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        content = _extract_article_content(
            response.text
        )

        if content:

            existing_summary = normalize_text(
                item.get(
                    "summary",
                    "",
                )
            )

            if existing_summary:

                combined = (
                    f"{existing_summary} "
                    f"{content}"
                )

            else:

                combined = content

            item["summary"] = combined[
                :20000
            ]

            item["categories"] = classify_fda_text(
                title=item.get(
                    "title",
                    "",
                ),
                summary=item[
                    "summary"
                ],
            )

            item["priority"] = calculate_priority(
                categories=item[
                    "categories"
                ],
                title=item.get(
                    "title",
                    "",
                ),
                summary=item[
                    "summary"
                ],
            )

    except Exception:
        pass

    return item


# ============================================
# ARTICLE PARSER
# ============================================

def _parse_article(
    article,
    base_url,
    source,
):

    title = extract_title(
        article
    )

    if not title:
        return None

    url = extract_link(
        article,
        base_url=base_url,
    )

    if not url:
        return None

    summary = extract_summary(
        article
    )

    published_at = extract_date(
        article
    )

    return build_fda_news_item(
        title=title,
        url=url,
        summary=summary,
        published_at=published_at,
        source=source,
    )


def parse_fda_page(
    html,
    base_url=FDA_NEWS_URL,
    source="FDA",
    max_items=None,
):

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    articles = soup.find_all(
        "article"
    )

    for article in articles:

        item = _parse_article(
            article=article,
            base_url=base_url,
            source=source,
        )

        if item is None:
            continue

        if _is_archive_artifact(
            item.get("title"),
            item.get("url"),
        ):
            continue

        results.append(item)

        if max_items is not None:

            if len(results) >= int(
                max_items
            ):
                break

    if not articles:

        for anchor in soup.find_all(
            "a",
            href=True,
        ):

            title = normalize_text(
                anchor.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(title) < 10:
                continue

            url = extract_link(
                anchor,
                base_url=base_url,
            )

            if not url:
                continue

            if not is_fda_url(
                url
            ):
                continue

            if _is_archive_artifact(
                title,
                url,
            ):
                continue

            item = build_fda_news_item(
                title=title,
                url=url,
                summary="",
                published_at=None,
                source=source,
            )

            results.append(item)

            if max_items is not None:

                if len(results) >= int(
                    max_items
                ):
                    break

    return deduplicate_fda_news(
        results
    )


# ============================================
# LINK EXTRACTION
# ============================================

def _extract_links(
    html,
    base_url,
    source,
):

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        title = normalize_text(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        if len(title) < 10:
            continue

        url = extract_link(
            anchor,
            base_url=base_url,
        )

        if not url:
            continue

        if not is_fda_url(
            url
        ):
            continue

        if _is_archive_artifact(
            title,
            url,
        ):
            continue

        results.append(
            build_fda_news_item(
                title=title,
                url=url,
                summary="",
                published_at=None,
                source=source,
            )
        )

    return deduplicate_fda_news(
        results
    )


# ============================================
# PRESS ANNOUNCEMENTS
# ============================================

def _fetch_press_announcements(
    max_items=50,
    max_pages=DEFAULT_MAX_PAGES,
):

    results = []

    session = _get_session()

    for page in range(
        max_pages
    ):

        if len(results) >= max_items:
            break

        if page == 0:

            url = (
                FDA_PRESS_ANNOUNCEMENTS_URL
            )

        else:

            url = (
                f"{FDA_PRESS_ANNOUNCEMENTS_URL}"
                f"?page={page}"
            )

        try:

            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

        except Exception:
            continue

        page_items = parse_fda_page(
            html=response.text,
            base_url=url,
            source="FDA_PRESS",
            max_items=max_items - len(results),
        )

        for item in page_items:

            if _is_archive_artifact(
                item.get("title"),
                item.get("url"),
            ):
                continue

            results.append(item)

            if len(results) >= max_items:
                break

    return results


# ============================================
# GENERIC SOURCE
# ============================================

def _fetch_source_items(
    url,
    source,
    max_items=50,
):

    try:

        html = _fetch_html(
            url
        )

    except Exception:
        return []

    items = parse_fda_page(
        html=html,
        base_url=url,
        source=source,
        max_items=max_items,
    )

    return items[:max_items]


# ============================================
# NOVEL APPROVALS
# ============================================

def _fetch_novel_approvals_2026(
    max_items=50,
):

    try:

        html = _fetch_html(
            FDA_NOVEL_APPROVALS_2026_URL
        )

    except Exception:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    results = []

    for table in soup.find_all(
        "table"
    ):

        for row in table.find_all(
            "tr"
        ):

            cells = row.find_all(
                [
                    "td",
                    "th",
                ]
            )

            if len(cells) < 4:
                continue

            values = [
                normalize_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in cells
            ]

            number = values[0]
            drug_name = values[1]
            active_ingredient = values[2]
            approval_date = values[3]

            if not number.isdigit():
                continue

            if not drug_name:
                continue

            if drug_name.lower() in {
                "drug name",
                "active ingredient",
            }:
                continue

            indication = (
                values[4]
                if len(values) >= 5
                else ""
            )

            title = (
                "FDA Novel Drug Approval: "
                f"{drug_name} "
                f"({active_ingredient})"
            )

            summary = (
                f"FDA approval date: "
                f"{approval_date}. "
                f"Active ingredient: "
                f"{active_ingredient}. "
                f"FDA-approved use: "
                f"{indication}"
            )

            results.append(
                build_fda_news_item(
                    title=title,
                    url=FDA_NOVEL_APPROVALS_2026_URL,
                    summary=summary,
                    published_at=approval_date,
                    source="FDA_NOVEL_APPROVALS",
                )
            )

            if len(results) >= max_items:
                return results

    return results


# ============================================
# DEDUPLICATION
# ============================================

def deduplicate_fda_news(
    news_items
):

    if not news_items:
        return []

    results = []

    seen_ids = set()

    for item in news_items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        title = normalize_text(
            item.get(
                "title",
                "",
            )
        )

        url = _normalize_url(
            item.get("url")
        )

        if not title:
            continue

        if _is_archive_artifact(
            title,
            url,
        ):
            continue

        item_id = get_item_id(
            {
                "title": title,
                "url": url,
            }
        )

        if (
            item_id
            and item_id in seen_ids
        ):
            continue

        normalized_title = re.sub(
            r"[^a-z0-9]+",
            " ",
            title.lower(),
        ).strip()

        title_id = None

        if normalized_title:

            title_id = hashlib.sha256(
                normalized_title.encode(
                    "utf-8"
                )
            ).hexdigest()

            if title_id in seen_ids:
                continue

        if item_id:
            seen_ids.add(
                item_id
            )

        if title_id:
            seen_ids.add(
                title_id
            )

        results.append(item)

    return results


# ============================================
# SORT
# ============================================

def sort_fda_news(
    news_items
):

    priority = {
        "EXTREME": 5,
        "HIGH": 4,
        "MEDIUM": 3,
        "LOW": 2,
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
                1,
            ),
            str(
                item.get(
                    "published_at",
                    "",
                )
            ),
        ),
        reverse=True,
    )


# ============================================
# MAIN FDA NEWS
# ============================================

def get_fda_news(
    max_news=DEFAULT_MAX_NEWS,
    max_pages=DEFAULT_MAX_PAGES,
):

    try:

        max_news = int(
            max_news
        )

    except (
        TypeError,
        ValueError,
    ):

        max_news = DEFAULT_MAX_NEWS

    if max_news <= 0:
        return []

    try:

        max_pages = int(
            max_pages
        )

    except (
        TypeError,
        ValueError,
    ):

        max_pages = DEFAULT_MAX_PAGES

    if max_pages <= 0:
        max_pages = DEFAULT_MAX_PAGES

    all_items = []

    all_items.extend(
        _fetch_press_announcements(
            max_items=max_news,
            max_pages=max_pages,
        )
    )

    all_items.extend(
        _fetch_source_items(
            url=FDA_WHATS_NEW_URL,
            source="FDA_WHATS_NEW",
            max_items=max_news,
        )
    )

    all_items.extend(
        _fetch_source_items(
            url=FDA_NOTABLE_APPROVALS_URL,
            source="FDA_NOTABLE_APPROVALS",
            max_items=max_news,
        )
    )

    all_items.extend(
        _fetch_novel_approvals_2026(
            max_items=max_news,
        )
    )

    all_items.extend(
        _fetch_source_items(
            url=FDA_ONCOLOGY_APPROVALS_URL,
            source="FDA_ONCOLOGY_APPROVALS",
            max_items=max_news,
        )
    )

    all_items = deduplicate_fda_news(
        all_items
    )

    all_items = sort_fda_news(
        all_items
    )

    session = _get_session()

    enriched = []

    for item in all_items[:max_news]:

        enriched.append(
            _enrich_article_item(
                item,
                session=session,
            )
        )

    return enriched[:max_news]


# ============================================
# COMPATIBILITY API
# ============================================

def get_fda_catalyst_news(
    max_items=DEFAULT_MAX_NEWS,
):

    news = get_fda_news(
        max_news=max_items,
    )

    return filter_fda_catalysts(
        news
    )


def filter_fda_catalysts(
    news_items
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

        priority = str(
            item.get(
                "priority",
                "LOW",
            )
        ).upper()

        if (
            categories
            or priority in {
                "EXTREME",
                "HIGH",
            }
        ):

            results.append(item)

    return results


def get_fda_sources():

    return {
        "press_announcements": (
            FDA_PRESS_ANNOUNCEMENTS_URL
        ),
        "drugs": FDA_DRUGS_URL,
        "whats_new": FDA_WHATS_NEW_URL,
        "notable_approvals": (
            FDA_NOTABLE_APPROVALS_URL
        ),
        "novel_approvals_2026": (
            FDA_NOVEL_APPROVALS_2026_URL
        ),
        "oncology_approvals": (
            FDA_ONCOLOGY_APPROVALS_URL
        ),
    }


# ============================================
# EXPORTS
# ============================================

__all__ = [
    "FDA_NEWS_URL",
    "FDA_PRESS_ANNOUNCEMENTS_URL",
    "FDA_DRUGS_URL",
    "FDA_WHATS_NEW_URL",
    "FDA_NOTABLE_APPROVALS_URL",
    "FDA_NOVEL_APPROVALS_2026_URL",
    "FDA_ONCOLOGY_APPROVALS_URL",
    "DEFAULT_MAX_NEWS",
    "DEFAULT_MAX_PAGES",
    "normalize_text",
    "normalize_date",
    "get_item_id",
    "extract_title",
    "extract_link",
    "extract_summary",
    "extract_date",
    "parse_fda_page",
    "classify_fda_text",
    "get_fda_priority",
    "calculate_priority",
    "build_fda_news_item",
    "get_fda_news",
    "get_fda_catalyst_news",
    "filter_fda_catalysts",
    "sort_fda_news",
    "deduplicate_fda_news",
    "get_fda_sources",
    "is_fda_url",
    "is_fda_press_announcement_url",
]