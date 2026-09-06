"""Pharma Radar — SEC EDGAR 8-K primary corporate feed."""
from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
SEC_BROWSE = "https://www.sec.gov/cgi-bin/browse-edgar"
REQUEST_TIMEOUT = 20
DEFAULT_USER_AGENT = "PharmaRadar/1.0 (GitHub Actions; 41898282+github-actions[bot]@users.noreply.github.com)"
USER_AGENT = os.getenv("SEC_USER_AGENT", DEFAULT_USER_AGENT)

# CIKs for the US-listed issuers in the current Pharma Radar watchlist.
# We deliberately use EDGAR's official Atom/RSS filing feeds instead of the
# data.sec.gov submissions API because the latter returns HTTP 403 from the
# GitHub Actions runtime even with a declared User-Agent.
# Foreign issuers in the watchlist (ARGX, PHVS, QURE, TLX) do not use 8-K
# as their primary SEC current-report form and are skipped by this 8-K feed.
WATCHLIST_CIK = {
    "CAPR": "0001133869",
    "SVRA": "0001160308",
    "ZYME": "0001937653",
    "MIRM": "0001759425",
    "TENX": "0000034956",
    "NUVL": "0001861560",
    "RARE": "0001515673",
    "IONS": "0000874015",
    "STOK": "0001623526",
    "ANNX": "0001528115",
    "IMMX": "0001873835",
    "ALMS": "0001847367",
    "RNA": "0001599901",
    "RGNX": "0001590877",
    "EYPT": "0001314102",
    "SMMT": "0001599298",
}

CATALYST_ITEMS = {"1.01", "1.02", "2.01", "2.03", "3.01", "5.02", "7.01", "8.01"}


def normalize_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _headers(accept="application/atom+xml,application/xml,text/xml,text/html,application/xhtml+xml"):
    return {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Encoding": "gzip, deflate",
    }


def _get(url, accept=None):
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=_headers(accept) if accept else _headers())
    response.raise_for_status()
    return response


def get_ticker_cik_map():
    return dict(WATCHLIST_CIK)


def _extract_items(items) -> list[str]:
    text = normalize_text(items).replace("&nbsp;", " ")
    found = []
    for match in re.finditer(r"(?:Item\s*)?(\d+\.\d{2})", text, flags=re.I):
        item = match.group(1)
        if item in CATALYST_ITEMS and item not in found:
            found.append(item)
    return found


def _filing_url(cik, accession, primary_doc):
    return f"{SEC_ARCHIVES}/{int(cik)}/{accession.replace('-', '')}/{primary_doc}"


def _extract_text(html):
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return normalize_text(soup.get_text(" ", strip=True))[:20000]


def build_sec_item(ticker, company, cik, accession, form, filing_date, primary_doc, items, text, title=None, url=None):
    url = url or _filing_url(cik, accession, primary_doc)
    raw = "|".join((ticker, accession, primary_doc))
    item_text = normalize_text(text)
    return {
        "source": "SEC",
        "source_type": "PRIMARY_CORPORATE",
        "ticker": ticker,
        "company": company,
        "cik": cik,
        "accession": accession,
        "form": form,
        "filing_items": items,
        "title": title or f"SEC {form} — {company} ({ticker})",
        "summary": f"SEC filing {form}; items: {', '.join(items)}",
        "content": item_text,
        "url": url,
        "published_at": filing_date,
        "item_id": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


def _local_name(tag):
    return tag.rsplit("}", 1)[-1]


def _parse_atom(xml_bytes, ticker, company, cik, max_filings=3):
    root = ET.fromstring(xml_bytes)
    results = []
    for entry in list(root):
        if _local_name(entry.tag) != "entry":
            continue
        fields = {}
        for child in list(entry):
            name = _local_name(child.tag)
            fields.setdefault(name, []).append(normalize_text(child.text))
        title = (fields.get("title") or [""])[0]
        summary = (fields.get("summary") or fields.get("content") or [""])[0]
        updated = (fields.get("updated") or fields.get("published") or [""])[0]
        entry_id = (fields.get("id") or [""])[0]
        links = []
        for child in list(entry):
            if _local_name(child.tag) == "link":
                href = child.attrib.get("href")
                if href:
                    links.append(href)
        filing_url = next((u for u in links if "Archives/edgar/data" in u), "")
        accession_match = re.search(r"accession-number=([0-9-]+)", entry_id)
        if not accession_match:
            accession_match = re.search(r"/([0-9]{10}-[0-9]{2}-[0-9]{6})", filing_url)
        accession = accession_match.group(1) if accession_match else ""
        if not accession:
            continue
        items = _extract_items(summary)
        if not items:
            continue
        primary_doc = filing_url.rsplit("/", 1)[-1] if filing_url else ""
        results.append(build_sec_item(
            ticker, company, cik, accession, "8-K", updated[:10], primary_doc,
            items, summary, title=title, url=filing_url or None,
        ))
        if len(results) >= max_filings:
            break
    return results


def _fetch_filing_content(item):
    url = item.get("url")
    if not url:
        return item
    try:
        response = _get(url, "text/html,application/xhtml+xml")
        item["content"] = _extract_text(response.text)
    except requests.RequestException as exc:
        # RSS metadata is still useful; do not discard the filing because the
        # document endpoint is temporarily blocked while the feed is available.
        print(f"SEC DOCUMENT WARNING {item.get('ticker')}: {type(exc).__name__}: {exc}", flush=True)
    return item


def _company_atom_url(cik):
    return (
        f"{SEC_BROWSE}?action=getcompany&CIK={cik}&type=8-K"
        f"&dateb=&owner=include&count=40&search_text=&output=atom"
    )


def _global_atom_url():
    return (
        f"{SEC_BROWSE}?action=getcurrent&type=8-K&dateb=&owner=include"
        f"&count=40&search_text=&output=atom"
    )


def get_sec_filings_for_ticker(ticker, company, max_filings=3):
    ticker = str(ticker).upper()
    cik = WATCHLIST_CIK.get(ticker)
    if not cik:
        return []
    try:
        response = _get(_company_atom_url(cik))
        items = _parse_atom(response.content, ticker, company, cik, max_filings=max_filings)
        return [_fetch_filing_content(item) for item in items]
    except (requests.RequestException, ET.ParseError, ValueError, TypeError, IndexError) as exc:
        print(f"SEC FEED ERROR {ticker}: {type(exc).__name__}: {exc}", flush=True)
        return []


def get_sec_news(watchlist, max_filings_per_company=3):
    results = []
    # Company-specific Atom feeds are preferred because they avoid the 40-entry
    # global-feed coverage problem. If EDGAR blocks those feeds, fall back to
    # the official global latest-8-K feed and filter by the watchlist CIKs.
    for ticker, config in (watchlist or {}).items():
        company = config.get("company", ticker) if isinstance(config, dict) else ticker
        results.extend(get_sec_filings_for_ticker(ticker, company, max_filings=max_filings_per_company))

    if results:
        return results

    try:
        response = _get(_global_atom_url())
        by_cik = {cik: (ticker, (watchlist.get(ticker, {}) or {}).get("company", ticker)) for ticker, cik in WATCHLIST_CIK.items()}
        for ticker, company in ((v[0], v[1]) for v in by_cik.values()):
            cik = WATCHLIST_CIK[ticker]
            items = _parse_atom(response.content, ticker, company, cik, max_filings=max_filings_per_company)
            results.extend(_fetch_filing_content(item) for item in items)
        return results
    except (requests.RequestException, ET.ParseError, ValueError, TypeError, IndexError) as exc:
        print(f"SEC GLOBAL FEED ERROR: {type(exc).__name__}: {exc}", flush=True)
        return []
