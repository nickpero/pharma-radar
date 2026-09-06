"""Pharma Radar — SEC EDGAR 8-K primary corporate feed with proxy fallback."""
from __future__ import annotations

import hashlib
import os
import re

import requests

SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
SEC_BROWSE = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_PROXY = "https://filingfirehose.com/v1/public/8k"
JINA_READER = "https://r.jina.ai/"
REQUEST_TIMEOUT = 20
DEFAULT_USER_AGENT = "PharmaRadar/1.0 (GitHub Actions; 41898282+github-actions[bot]@users.noreply.github.com)"
USER_AGENT = os.getenv("SEC_USER_AGENT", DEFAULT_USER_AGENT)
JINA_API_KEY = os.getenv("JINA_API_KEY", "")

WATCHLIST_CIK = {
    "CAPR": "0001133869", "SVRA": "0001160308", "ZYME": "0001937653",
    "MIRM": "0001759425", "TENX": "0000034956", "NUVL": "0001861560",
    "RARE": "0001515673", "IONS": "0000874015", "STOK": "0001623526",
    "ANNX": "0001528115", "IMMX": "0001873835", "ALMS": "0001847367",
    "RNA": "0001599901", "RGNX": "0001590877", "EYPT": "0001314102",
    "SMMT": "0001599298",
}

CATALYST_ITEMS = {"1.01", "1.02", "2.01", "2.03", "3.01", "5.02", "7.01", "8.01"}


def normalize_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _headers(accept="application/json,text/html,application/xhtml+xml"):
    return {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Encoding": "gzip, deflate",
    }


def _get_json(url):
    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=_headers())
    response.raise_for_status()
    return response.json()


def _get_jina_text(url):
    """Read a blocked SEC URL through Jina Reader as content enrichment."""
    headers = {"Accept": "text/plain", "User-Agent": USER_AGENT}
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"
    response = requests.get(
        JINA_READER + url,
        timeout=REQUEST_TIMEOUT,
        headers=headers,
    )
    response.raise_for_status()
    return normalize_text(response.text)


def _filing_index_url(cik, accession):
    if not accession:
        return ""
    return f"{SEC_ARCHIVES}/{int(cik)}/{accession.replace('-', '')}/{accession}-index.html"


def _extract_document_names(index_text):
    """Extract HTML document filenames from an EDGAR index rendered by Jina."""
    names = re.findall(r"\b[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:htm|html)\b", index_text or "", flags=re.I)
    unique = []
    for name in names:
        clean = name.strip(".,;:()[]")
        if clean.lower() not in {n.lower() for n in unique}:
            unique.append(clean)
    return unique


def _resolve_primary_document(cik, accession):
    """Resolve the primary 8-K HTML document from the EDGAR index."""
    index_url = _filing_index_url(cik, accession)
    if not index_url:
        return ""
    try:
        index_text = _get_jina_text(index_url)
    except requests.RequestException as exc:
        print(f"SEC INDEX UNAVAILABLE: {type(exc).__name__}: {exc}", flush=True)
        return ""

    names = _extract_document_names(index_text)
    if not names:
        print(f"SEC INDEX EMPTY: accession={accession}", flush=True)
        return ""

    # Prefer the primary 8-K document. EDGAR commonly uses `_8k` or `8-k`.
    preferred = [
        n for n in names
        if re.search(r"(?:_8k|8-k)\.(?:htm|html)$", n, flags=re.I)
    ]
    if not preferred:
        # Fallback to an exhibit press release if the index does not expose the primary doc.
        preferred = [
            n for n in names
            if re.search(r"(?:ex99[-_]?1|ex-99[-.]?1)\.(?:htm|html)$", n, flags=re.I)
        ]
    if not preferred:
        print(f"SEC PRIMARY DOC NOT FOUND: accession={accession} docs={names[:8]}", flush=True)
        return ""

    filename = preferred[0]
    document_url = f"{SEC_ARCHIVES}/{int(cik)}/{accession.replace('-', '')}/{filename}"
    print(f"SEC PRIMARY DOC RESOLVED: accession={accession} file={filename}", flush=True)
    return document_url


def _enrich_proxy_row(row, cik, accession):
    """Fetch filing body text after the SEC endpoint is blocked."""
    filing_url = _filing_url(cik, accession)
    primary_doc_url = _resolve_primary_document(cik, accession)
    if not primary_doc_url:
        return "", filing_url
    try:
        text = _get_jina_text(primary_doc_url)
        if len(text) < 200:
            print(f"SEC CONTENT TOO SHORT: accession={accession} chars={len(text)}", flush=True)
            return "", filing_url
        print(f"SEC CONTENT ENRICHED: accession={accession} chars={len(text)}", flush=True)
        return text, primary_doc_url
    except requests.RequestException as exc:
        print(f"SEC CONTENT UNAVAILABLE: {type(exc).__name__}: {exc}", flush=True)
        return "", filing_url


def get_ticker_cik_map():
    return dict(WATCHLIST_CIK)


def _extract_items(items) -> list[str]:
    text = normalize_text(items)
    found = []
    for match in re.finditer(r"(?:Item\s*)?(\d+\.\d{2})", text, flags=re.I):
        item = match.group(1)
        if item in CATALYST_ITEMS and item not in found:
            found.append(item)
    return found


def _filing_url(cik, accession, primary_doc=""):
    if not accession:
        return ""
    if primary_doc:
        return f"{SEC_ARCHIVES}/{int(cik)}/{accession.replace('-', '')}/{primary_doc}"
    return f"{SEC_ARCHIVES}/{int(cik)}/{accession.replace('-', '')}/"


def _item_context(items):
    labels = {
        "1.01": "material definitive agreement",
        "1.02": "termination of material definitive agreement",
        "2.01": "completion of acquisition or disposition",
        "2.03": "creation of direct financial obligation",
        "3.01": "delisting or listing compliance event",
        "5.02": "director or officer change",
        "7.01": "Regulation FD disclosure",
        "8.01": "other material event",
    }
    return "; ".join(f"Item {code}: {labels.get(code, 'SEC current report event')}" for code in items)


def build_sec_item(ticker, company, cik, accession, form, filing_date, primary_doc="", items=None,
                   text="", title=None, url=None, detected_items=None, suspected_buried_events=None):
    items = list(items or [])
    detected_items = list(detected_items or [])
    suspected_buried_events = suspected_buried_events or {}
    url = url or _filing_url(cik, accession, primary_doc)
    raw = "|".join((ticker, accession, primary_doc or ""))
    context = _item_context(items or detected_items)
    buried = normalize_text(suspected_buried_events)
    content = normalize_text(" ".join(filter(None, [text, context, buried])))
    return {
        "source": "SEC",
        "source_type": "PRIMARY_CORPORATE",
        "provider": "FilingFirehose" if not text else "SEC_EDGAR_VIA_JINA",
        "ticker": ticker,
        "company": company,
        "cik": cik,
        "accession": accession,
        "form": form,
        "filing_items": items,
        "detected_items": detected_items,
        "suspected_buried_events": suspected_buried_events,
        "title": title or f"SEC {form} — {company} ({ticker})",
        "summary": f"SEC filing {form}; items: {', '.join(items or detected_items)}",
        "content": content,
        "url": url,
        "published_at": filing_date,
        "item_id": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


def _fetch_sec_direct(ticker, company, cik, max_filings=3):
    """Try the official SEC endpoint. GitHub Actions currently returns 403."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    recent = _get_json(url).get("filings", {}).get("recent", {})
    results = []
    forms = recent.get("form", [])
    for idx, form in enumerate(forms):
        if form != "8-K":
            continue
        items = _extract_items(recent.get("items", [""])[idx])
        if not items:
            continue
        accession = recent["accessionNumber"][idx]
        filing_date = recent["filingDate"][idx]
        primary_doc = recent["primaryDocument"][idx]
        results.append(build_sec_item(ticker, company, cik, accession, form, filing_date, primary_doc, items))
        if len(results) >= max_filings:
            break
    return results


def _fetch_proxy(max_filings=50):
    """Use FilingFirehose public 8-K feed when GitHub cannot reach SEC directly."""
    params = {"limit": min(int(max_filings), 50)}
    data = _get_json(SEC_PROXY + "?limit=" + str(params["limit"]))
    if isinstance(data, dict):
        return data.get("filings", [])
    if isinstance(data, list):
        return data
    return []


def get_sec_news(watchlist, max_filings_per_company=3):
    try:
        results = []
        for ticker, config in (watchlist or {}).items():
            company = config.get("company", ticker) if isinstance(config, dict) else ticker
            cik = WATCHLIST_CIK.get(str(ticker).upper())
            if not cik:
                continue
            results.extend(_fetch_sec_direct(ticker, company, cik, max_filings=max_filings_per_company))
        return results
    except requests.RequestException as exc:
        print(f"SEC DIRECT UNAVAILABLE: {type(exc).__name__}: {exc}", flush=True)

    try:
        proxy_rows = _fetch_proxy(max_filings=50)
        by_cik = {str(cik).lstrip("0") or "0": ticker for ticker, cik in WATCHLIST_CIK.items()}
        company_by_ticker = {
            ticker: ((watchlist.get(ticker, {}) or {}).get("company", ticker) if isinstance(watchlist.get(ticker, {}), dict) else ticker)
            for ticker in WATCHLIST_CIK
        }
        results = []
        for row in proxy_rows:
            cik = str(row.get("cik", "")).lstrip("0") or "0"
            ticker = by_cik.get(cik)
            if not ticker:
                continue
            reported = _extract_items(row.get("filer_reported_items", []))
            detected = _extract_items(row.get("detected_items", []))
            items = reported or detected
            if not items:
                continue
            accession = str(row.get("accession_number", ""))
            text, content_url = _enrich_proxy_row(row, WATCHLIST_CIK[ticker], accession)
            results.append(build_sec_item(
                ticker=ticker,
                company=company_by_ticker[ticker],
                cik=WATCHLIST_CIK[ticker],
                accession=accession,
                form=row.get("form_type", "8-K"),
                filing_date=str(row.get("filed_at", ""))[:10],
                items=items,
                detected_items=detected,
                suspected_buried_events=row.get("suspected_buried_events", {}),
                text=text,
                title=f"SEC 8-K — {company_by_ticker[ticker]} ({ticker})",
                url=content_url or (f"https://www.sec.gov/Archives/edgar/data/{int(WATCHLIST_CIK[ticker])}/{accession.replace('-', '')}/" if accession else ""),
            ))
        return results
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        print(f"SEC PROXY ERROR: {type(exc).__name__}: {exc}", flush=True)
        return []


def get_sec_filings_for_ticker(ticker, company, max_filings=3):
    """Compatibility wrapper used by tests and older callers."""
    cik = WATCHLIST_CIK.get(str(ticker).upper())
    if not cik:
        return []
    try:
        return _fetch_sec_direct(str(ticker).upper(), company, cik, max_filings=max_filings)
    except requests.RequestException:
        try:
            rows = _fetch_proxy(max_filings=50)
            ticker = str(ticker).upper()
            results = []
            for row in rows:
                if str(row.get("cik", "")).lstrip("0") != cik.lstrip("0"):
                    continue
                items = _extract_items(row.get("filer_reported_items", []))
                if items:
                    accession = str(row.get("accession_number", ""))
                    text, content_url = _enrich_proxy_row(row, cik, accession)
                    results.append(build_sec_item(
                        ticker, company, cik, accession, "8-K", str(row.get("filed_at", ""))[:10],
                        items=items, text=text, url=content_url or None,
                    ))
                if len(results) >= max_filings:
                    break
            return results
        except requests.RequestException:
            return []
