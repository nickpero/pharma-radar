"""Pharma Radar — SEC EDGAR 8-K primary corporate feed."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
REQUEST_TIMEOUT = 20
USER_AGENT = "PharmaRadar/1.0"

# Only material/current-report classes useful for catalyst discovery.
CATALYST_ITEMS = {"1.01", "1.02", "2.01", "2.03", "3.01", "5.02", "7.01", "8.01"}


def normalize_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _headers():
    return {"User-Agent": USER_AGENT, "Accept": "application/json,text/html,application/xhtml+xml"}


def _get_json(url):
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=_headers())
    response.raise_for_status()
    return response.json()


def get_ticker_cik_map():
    data = _get_json(SEC_TICKERS_URL)
    result = {}
    for row in data.values():
        ticker = normalize_text(row.get("ticker")).upper()
        cik = str(row.get("cik_str", "")).zfill(10)
        if ticker and cik:
            result[ticker] = cik
    return result


def _extract_items(form, accession, primary_doc, items):
    return [item for item in str(items or "").split(",") if item in CATALYST_ITEMS]


def _filing_url(cik, accession, primary_doc):
    cik_number = str(int(cik))
    accession_no_dash = accession.replace("-", "")
    return f"{SEC_ARCHIVES}/{cik_number}/{accession_no_dash}/{primary_doc}"


def _extract_text(html):
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return normalize_text(soup.get_text(" ", strip=True))[:20000]


def build_sec_item(ticker, company, cik, accession, form, filing_date, primary_doc, items, text):
    url = _filing_url(cik, accession, primary_doc)
    title = f"SEC {form} — {company} ({ticker})"
    summary = f"SEC filing {form}; items: {', '.join(items)}"
    raw = "|".join((ticker, accession, primary_doc))
    return {
        "source": "SEC",
        "source_type": "PRIMARY_CORPORATE",
        "ticker": ticker,
        "company": company,
        "cik": cik,
        "accession": accession,
        "form": form,
        "filing_items": items,
        "title": title,
        "summary": summary,
        "content": text,
        "url": url,
        "published_at": filing_date,
        "item_id": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


def get_sec_filings_for_ticker(ticker, company, max_filings=10):
    try:
        cik = get_ticker_cik_map().get(str(ticker).upper())
        if not cik:
            return []
        submissions = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        recent = submissions.get("filings", {}).get("recent", {})
        results = []
        for idx, form in enumerate(recent.get("form", [])):
            if form != "8-K":
                continue
            accession = recent["accessionNumber"][idx]
            primary_doc = recent["primaryDocument"][idx]
            filing_date = recent["filingDate"][idx]
            items = _extract_items(form, accession, primary_doc, recent.get("items", [""])[idx])
            if not items:
                continue
            url = _filing_url(cik, accession, primary_doc)
            response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            text = _extract_text(response.text)
            results.append(build_sec_item(ticker, company, cik, accession, form, filing_date, primary_doc, items, text))
            if len(results) >= max_filings:
                break
        return results
    except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
        print(f"SEC FEED ERROR {ticker}: {type(exc).__name__}: {exc}", flush=True)
        return []


def get_sec_news(watchlist, max_filings_per_company=3):
    results = []
    for ticker, config in (watchlist or {}).items():
        company = config.get("company", ticker) if isinstance(config, dict) else ticker
        results.extend(get_sec_filings_for_ticker(ticker, company, max_filings=max_filings_per_company))
    return results
