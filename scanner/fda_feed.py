"""
Pharma Radar — FDA News Engine

Raccoglie notizie e aggiornamenti FDA rilevanti per Pharma Radar.

Fonti principali:
- FDA Press Announcements
- FDA What's New Related to Drugs
- FDA Notable Approvals
- FDA Novel Drug Approvals 2026
- FDA Oncology/Hematologic Approval Notifications

Il modulo:
1. scarica le pagine FDA;
2. individua gli articoli/link rilevanti;
3. estrae titolo, data, URL e contenuto;
4. classifica la notizia;
5. assegna una priorità;
6. elimina duplicati e artefatti di archivio.

NON effettua raccomandazioni di acquisto o vendita.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

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

DEFAULT_MAX_NEWS = 50
DEFAULT_MAX_PAGES = 5
REQUEST_TIMEOUT = 20

USER_AGENT = (
    "Mozilla/5.0 (compatible; PharmaRadar/1.0; "
    "+https://github.com/)"
)


# ============================================================
# CLASSIFICATION KEYWORDS
# ============================================================

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


# ============================================================
# HTTP
# ============================================================

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


# ============================================================
# TEXT HELPERS
# ============================================================

def _clean_text(value):
    if value is None:
        return ""

    text = str(value)

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\u00a0", " ", text)

    return text.strip()


def _normalize_url(url):
    if not url:
        return None

    url = str(url).strip()

    if not url:
        return None

    return url.split("#", 1)[0]


def _is_fda_url(url):
    if not url:
        return False

    try:
        hostname = urlparse(url).netloc.lower()
    except Exception:
        return False

    return (
        hostname == "fda.gov"
        or hostname.endswith(".fda.gov")
    )


def _is_archive_artifact(title, url):
    title_clean = _clean_text(title).lower()
    url_clean = str(url or "").lower()

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


def _extract_date(text):
    if not text:
        return None

    text = _clean_text(text)

    patterns = [
        r"\b("
        r"January|February|March|April|May|June|July|August|"
        r"September|October|November|December"
        r")\s+"
        r"(\d{1,2}),\s+(\d{4})\b",
        r"\b("
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
        r")\.?\s+"
        r"(\d{1,2}),\s+(\d{4})\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = match.group(0)

        for fmt in (
            "%B %d, %Y",
            "%b %d, %Y",
        ):
            try:
                return datetime.strptime(
                    value.replace(".", ""),
                    fmt,
                ).isoformat()
            except ValueError:
                continue

    return None


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_fda_text(title="", summary=""):
    text = (
        f"{title} {summary}"
    ).lower()

    categories = set()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                categories.add(category)
                break

    return sorted(
        categories,
        key=lambda value: CATEGORY_PRIORITY.index(value)
        if value in CATEGORY_PRIORITY
        else 999,
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


def calculate_priority(categories, title="", summary=""):
    combined_categories = set(
        str(category).upper()
        for category in categories or []
    )

    detected = classify_fda_text(
        title=title,
        summary=summary,
    )

    combined_categories.update(detected)

    if not combined_categories:
        return "LOW"

    score = max(
        PRIORITY_SCORE.get(category, 0)
        for category in combined_categories
    )

    if score >= 5:
        return "EXTREME"

    if score >= 4:
        return "HIGH"

    if score >= 2:
        return "MEDIUM"

    return "LOW"


# ============================================================
# NEWS ITEM
# ============================================================

def build_fda_news_item(
    title,
    url,
    summary="",
    published_at=None,
    source="FDA",
):
    title = _clean_text(title)
    summary = _clean_text(summary)
    url = _normalize_url(url)

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


# ============================================================
# ARTICLE CONTENT EXTRACTION
# ============================================================

def _extract_article_content(html):
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

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
        for element in soup.select(selector):
            text = _clean_text(
                element.get_text(" ", strip=True)
            )

            if len(text) >= 100:
                candidates.append(text)

    if not candidates:
        body = soup.find("body")

        if body:
            text = _clean_text(
                body.get_text(" ", strip=True)
            )

            if text:
                candidates.append(text)

    if not candidates:
        return ""

    # Prefer the longest meaningful article body.
    content = max(
        candidates,
        key=len,
    )

    # Avoid absurdly large payloads.
    return content[:20000]


def _enrich_article_item(item, session=None):
    url = item.get("url")

    if not url:
        return item

    if not _is_fda_url(url):
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
            existing_summary = _clean_text(
                item.get("summary", "")
            )

            if existing_summary:
                combined = (
                    f"{existing_summary} {content}"
                )
            else:
                combined = content

            item["summary"] = combined[:20000]

            item["categories"] = classify_fda_text(
                title=item.get("title", ""),
                summary=item["summary"],
            )

            item["priority"] = calculate_priority(
                categories=item["categories"],
                title=item.get("title", ""),
                summary=item["summary"],
            )

    except Exception:
        # Article enrichment is best-effort.
        # The feed item itself remains valid.
        pass

    return item


# ============================================================
# LINK EXTRACTION
# ============================================================

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

    for anchor in soup.find_all("a", href=True):
        title = _clean_text(
            anchor.get_text(" ", strip=True)
        )

        href = anchor.get("href")

        if not href:
            continue

        url = _normalize_url(
            urljoin(base_url, href)
        )

        if not url:
            continue

        if not _is_fda_url(url):
            continue

        if _is_archive_artifact(
            title,
            url,
        ):
            continue

        if len(title) < 10:
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

    return results


# ============================================================
# PRESS ANNOUNCEMENTS
# ============================================================

def _fetch_press_announcements(
    max_items=50,
    max_pages=DEFAULT_MAX_PAGES,
):
    results = []

    session = _get_session()

    for page in range(max_pages):
        if len(results) >= max_items:
            break

        if page == 0:
            url = FDA_PRESS_ANNOUNCEMENTS_URL
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

        html = response.text

        page_items = _extract_links(
            html=html,
            base_url=url,
            source="FDA_PRESS",
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


# ============================================================
# GENERIC FDA SOURCE
# ============================================================

def _fetch_source_items(
    url,
    source,
    max_items=50,
):
    try:
        html = _fetch_html(url)
    except Exception:
        return []

    items = _extract_links(
        html=html,
        base_url=url,
        source=source,
    )

    return items[:max_items]


# ============================================================
# SPECIAL PARSER: NOVEL DRUG APPROVALS
# ============================================================

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

    tables = soup.find_all("table")

    for table in tables:
        for row in table.find_all("tr"):
            cells = row.find_all(
                ["td", "th"]
            )

            if len(cells) < 4:
                continue

            values = [
                _clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in cells
            ]

            if len(values) < 4:
                continue

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
                f"FDA Novel Drug Approval: "
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

            published_at = _extract_date(
                approval_date
            )

            results.append(
                build_fda_news_item(
                    title=title,
                    url=FDA_NOVEL_APPROVALS_2026_URL,
                    summary=summary,
                    published_at=published_at,
                    source="FDA_NOVEL_APPROVALS",
                )
            )

            if len(results) >= max_items:
                return results

    return results


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_fda_news(news_items):
    if not news_items:
        return []

    results = []
    seen_urls = set()
    seen_titles = set()

    for item in news_items:
        if not isinstance(item, dict):
            continue

        title = _clean_text(
            item.get("title", "")
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

        normalized_title = re.sub(
            r"[^a-z0-9]+",
            " ",
            title.lower(),
        ).strip()

        if url and url in seen_urls:
            continue

        if (
            normalized_title
            and normalized_title in seen_titles
        ):
            continue

        if url:
            seen_urls.add(url)

        if normalized_title:
            seen_titles.add(
                normalized_title
            )

        results.append(item)

    return results


# ============================================================
# MAIN FEED
# ============================================================

def get_fda_news(
    max_news=DEFAULT_MAX_NEWS,
    max_pages=DEFAULT_MAX_PAGES,
):
    try:
        max_news = int(max_news)
    except (TypeError, ValueError):
        max_news = DEFAULT_MAX_NEWS

    if max_news <= 0:
        return []

    try:
        max_pages = int(max_pages)
    except (TypeError, ValueError):
        max_pages = DEFAULT_MAX_PAGES

    if max_pages <= 0:
        max_pages = DEFAULT_MAX_PAGES

    all_items = []

    # --------------------------------------------------------
    # 1. FDA Press Announcements
    # --------------------------------------------------------

    press_items = _fetch_press_announcements(
        max_items=max_news,
        max_pages=max_pages,
    )

    all_items.extend(press_items)

    # --------------------------------------------------------
    # 2. What's New Related to Drugs
    # --------------------------------------------------------

    whats_new = _fetch_source_items(
        url=FDA_WHATS_NEW_URL,
        source="FDA_WHATS_NEW",
        max_items=max_news,
    )

    all_items.extend(whats_new)

    # --------------------------------------------------------
    # 3. Notable Approvals
    # --------------------------------------------------------

    notable = _fetch_source_items(
        url=FDA_NOTABLE_APPROVALS_URL,
        source="FDA_NOTABLE_APPROVALS",
        max_items=max_news,
    )

    all_items.extend(notable)

    # --------------------------------------------------------
    # 4. Novel Drug Approvals 2026
    # --------------------------------------------------------

    novel = _fetch_novel_approvals_2026(
        max_items=max_news,
    )

    all_items.extend(novel)

    # --------------------------------------------------------
    # 5. Oncology Approval Notifications
    # --------------------------------------------------------

    oncology = _fetch_source_items(
        url=FDA_ONCOLOGY_APPROVALS_URL,
        source="FDA_ONCOLOGY_APPROVALS",
        max_items=max_news,
    )

    all_items.extend(oncology)

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    all_items = deduplicate_fda_news(
        all_items
    )

    # --------------------------------------------------------
    # Sort newest first where date is known.
    # Undated items remain after dated items.
    # --------------------------------------------------------

    def sort_key(item):
        value = item.get(
            "published_at"
        )

        if not value:
            return ""

        return str(value)

    dated = [
        item
        for item in all_items
        if item.get("published_at")
    ]

    undated = [
        item
        for item in all_items
        if not item.get("published_at")
    ]

    dated.sort(
        key=sort_key,
        reverse=True,
    )

    ordered = dated + undated

    # --------------------------------------------------------
    # Enrich the most relevant items with article content.
    #
    # We do not enrich every item indefinitely because the
    # production radar runs every 15 minutes.
    # --------------------------------------------------------

    session = _get_session()

    enrichment_limit = min(
        len(ordered),
        max_news,
    )

    enriched = []

    for item in ordered[:enrichment_limit]:
        enriched.append(
            _enrich_article_item(
                item,
                session=session,
            )
        )

    return enriched[:max_news]


# ============================================================
# COMPATIBILITY API
# ============================================================

def get_fda_catalyst_news(
    max_items=DEFAULT_MAX_NEWS,
):
    news = get_fda_news(
        max_news=max_items,
    )

    return filter_fda_catalysts(
        news
    )


def filter_fda_catalysts(news_items):
    if not news_items:
        return []

    results = []

    for item in news_items:
        if not isinstance(item, dict):
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

        if categories or priority in {
            "EXTREME",
            "HIGH",
        }:
            results.append(item)

    return results


def sort_fda_news(news_items):
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


def get_fda_sources():
    return {
        "press_announcements": FDA_PRESS_ANNOUNCEMENTS_URL,
        "drugs": FDA_DRUGS_URL,
        "whats_new": FDA_WHATS_NEW_URL,
        "notable_approvals": FDA_NOTABLE_APPROVALS_URL,
        "novel_approvals_2026": (
            FDA_NOVEL_APPROVALS_2026_URL
        ),
        "oncology_approvals": (
            FDA_ONCOLOGY_APPROVALS_URL
        ),
    }


# ============================================================
# PUBLIC EXPORTS
# ============================================================

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
]