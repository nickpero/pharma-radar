"""Pharma Radar — early corporate catalyst discovery via Google News RSS.

This is a discovery layer, not a primary-source confirmation layer. It is used
to surface newly published company/program news quickly; SEC/FDA/company-primary
feeds remain the confirmation layer.
"""
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import requests

RSS_ENDPOINT = "https://news.google.com/rss/search"
REQUEST_TIMEOUT = 15
BATCH_SIZE = 10
MAX_ITEMS_PER_FEED = 30
MAX_AGE_HOURS = 24
# Fast discovery is deliberately broader than Google News alone. The query
# asks Google News to surface company releases carried by major distributors
# and specialist biotech publications, while primary sources remain the
# confirmation layer.
DISCOVERY_DOMAINS = (
    "globenewswire.com", "businesswire.com", "prnewswire.com",
    "biospace.com", "fiercebiotech.com",
)
DOMAIN_LABELS = {
    "globenewswire.com": ("GlobeNewswire", "TRUSTED_DISTRIBUTION"),
    "businesswire.com": ("Business Wire", "TRUSTED_DISTRIBUTION"),
    "prnewswire.com": ("PR Newswire", "TRUSTED_DISTRIBUTION"),
    "biospace.com": ("BioSpace", "SPECIALIST"),
    "fiercebiotech.com": ("Fierce Biotech", "SPECIALIST"),
}
USER_AGENT = "PharmaRadar/1.0 (GitHub Actions; early discovery)"
CATALYST_HINTS = (
    "approval", "approved", "fda", "phase", "trial", "data", "results",
    "endpoint", "study", "formulation", "formulated", "milestone",
    "enrollment", "enrolled", "dosing", "launch", "regulatory", "clearance",
    "hold", "lifted", "submission", "agreement", "license", "acquisition",
    "partnership", "topline", "clinical",
)


def _clean(value):
    value = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def _published_at(value):
    try:
        dt = parsedate_to_datetime(str(value))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _terms(company, ticker):
    company = _clean(company)
    ticker = _clean(ticker).upper()
    return [t for t in (company, ticker) if t]


def _query(batch):
    # Company names are quoted; tickers are included as exact tokens.
    clauses = []
    for ticker, company in batch:
        company = _clean(company)
        ticker = _clean(ticker).upper()
        if company:
            clauses.append(f'"{company}"')
        if ticker:
            clauses.append(ticker)
    # Keep one bounded request per company batch. Domain restrictions increase
    # source diversity without multiplying HTTP requests for every provider.
    company_clause = " OR ".join(clauses)
    domain_clause = " OR ".join(f"site:{domain}" for domain in DISCOVERY_DOMAINS)
    return f"({company_clause}) ({domain_clause})"


def _feed_url(query):
    return f"{RSS_ENDPOINT}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"


def _entry_value(entry, tag):
    node = entry.find(tag)
    return node.text if node is not None else ""


def _source_info(entry, url):
    node = entry.find("source")
    source_name = _clean(node.text) if node is not None else ""
    source_url = _clean(node.get("url")) if node is not None else ""
    haystack = f"{source_url} {url}".lower()
    for domain, metadata in DOMAIN_LABELS.items():
        if domain in haystack:
            return metadata
    return (source_name or "Google News", "DISCOVERY")


def _matches_watchlist(text, ticker, company):
    lowered = _clean(text).lower()
    company_match = company and company.lower() in lowered
    ticker_match = re.search(rf"\b{re.escape(ticker.lower())}\b", lowered)
    return bool(company_match or ticker_match)


def _is_catalyst_like(title, summary):
    text = f"{title} {summary}".lower()
    return any(token in text for token in CATALYST_HINTS)


def _parse_feed(xml_text, batch):
    root = ET.fromstring(xml_text)
    rows = []
    for item in root.findall(".//item")[:MAX_ITEMS_PER_FEED]:
        title = _clean(_entry_value(item, "title"))
        summary = _clean(_entry_value(item, "description"))
        url = _clean(_entry_value(item, "link"))
        published = _published_at(_entry_value(item, "pubDate"))
        provider, source_type = _source_info(item, url)
        if not title or not published or not url:
            continue
        for ticker, company in batch:
            if not _matches_watchlist(f"{title} {summary}", ticker, company):
                continue
            if not _is_catalyst_like(title, summary):
                continue
            published_dt = datetime.fromisoformat(published)
            age = (datetime.now(timezone.utc) - published_dt).total_seconds() / 3600.0
            if age < -1 or age > MAX_AGE_HOURS:
                continue
            raw_id = f"{ticker}|{company}|{url}|{published}"
            rows.append({
                "source": "EARLY_DISCOVERY",
                "source_type": source_type,
                "provider": provider,
                "source_reliability": "TRUSTED_DISTRIBUTION" if source_type == "TRUSTED_DISTRIBUTION" else ("SPECIALIST" if source_type == "SPECIALIST" else "DISCOVERY"),
                "ticker": ticker,
                "company": company,
                "title": title,
                "summary": summary,
                "content": summary,
                "url": url,
                "published_at": published,
                "first_published_at": published,
                "event_date": published[:10],
                "early_discovery": True,
                "item_id": hashlib.sha256(raw_id.encode("utf-8")).hexdigest(),
            })
            break
    return rows


def get_early_news(watchlist, batch_size=BATCH_SIZE):
    """Return fresh watchlist-matched news for rapid catalyst discovery."""
    companies = []
    for ticker, config in (watchlist or {}).items():
        if not isinstance(config, dict):
            continue
        companies.append((str(ticker).upper(), str(config.get("company") or ticker)))
    results = []
    for start in range(0, len(companies), batch_size):
        batch = companies[start:start + batch_size]
        query = _query(batch)
        if not query:
            continue
        try:
            response = requests.get(
                _feed_url(query),
                headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            results.extend(_parse_feed(response.text, batch))
        except (requests.RequestException, ET.ParseError) as exc:
            print(f"EARLY DISCOVERY ERROR: batch={start // batch_size + 1} {type(exc).__name__}: {exc}", flush=True)
    unique = {}
    for row in results:
        unique[(row["ticker"], row["url"])] = row
    return sorted(unique.values(), key=lambda item: item.get("published_at", ""), reverse=True)
