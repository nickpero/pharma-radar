"""Broad US biotech/pharma equity universe for Pharma Radar Daily Top 5."""
from __future__ import annotations
import json
import requests

SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener"
FALLBACK_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
REQUEST_TIMEOUT = 15
PAGE_SIZE = 250
MAX_PAGES = 6
USER_AGENT = "PharmaRadar/1.0 (GitHub Actions; broad biotech universe)"
INDUSTRY_HINTS = ("biotechnology", "drug manufacturers", "diagnostics & research")
LAST_UNIVERSE_STATUS = {"status": "NOT_RUN", "count": 0, "pages": 0, "last_error": None, "source": "YAHOO_FINANCE_SCREENER"}

def _as_float(value):
    if isinstance(value, dict):
        value = value.get("raw", value.get("value"))
    try: return float(value)
    except (TypeError, ValueError): return None

def _is_biotech_pharma_quote(quote):
    industry = str(quote.get("industry") or "").strip().lower()
    sector = str(quote.get("sector") or "").strip().lower()
    name = str(quote.get("longName") or quote.get("shortName") or "").strip().lower()
    if any(hint in industry for hint in INDUSTRY_HINTS): return True
    return not industry and sector in {"healthcare", "health care"} and any(term in name for term in ("bio", "therapeutic", "pharma", "genetic", "oncology"))

def _to_market_row(quote):
    ticker = str(quote.get("symbol") or "").strip().upper()
    change = _as_float(quote.get("regularMarketChangePercent"))
    if change is None: change = _as_float(quote.get("percentchange"))
    price = _as_float(quote.get("regularMarketPrice"))
    volume = _as_float(quote.get("regularMarketVolume"))
    average_volume = _as_float(quote.get("averageDailyVolume3Month") or quote.get("averageDailyVolume10Day"))
    if not ticker or change is None: return None
    return {
        "ticker": ticker,
        "company": str(quote.get("longName") or quote.get("shortName") or ticker),
        "short_name": str(quote.get("shortName") or quote.get("longName") or ticker),
        "industry": quote.get("industry"), "sector": quote.get("sector"),
        "exchange": quote.get("exchange") or quote.get("fullExchangeName"),
        "price": price, "price_change_pct": change, "volume": volume,
        "volume_ratio": volume / average_volume if volume is not None and average_volume else None,
        "market_data_source": "YAHOO_FINANCE_SCREENER",
    }

def _query_payload():
    industries = ["Biotechnology", "Drug Manufacturers - Specialty & Generic", "Drug Manufacturers - General", "Diagnostics & Research"]
    return {"operator": "and", "operands": [
        {"operator": "eq", "operands": ["region", "us"]},
        {"operator": "or", "operands": [{"operator": "eq", "operands": ["industry", industry]} for industry in industries]},
    ]}

def _fetch_page(client, offset, page_size=PAGE_SIZE):
    params = {"formatted":"true","lang":"en-US","region":"US","corsDomain":"finance.yahoo.com",
              "size":str(page_size),"offset":str(offset),"sortField":"percentchange","sortType":"DESC",
              "quoteType":"EQUITY","query":json.dumps(_query_payload(),separators=(",",":"))}
    response = client.get(SCREENER_URL, params=params, timeout=REQUEST_TIMEOUT,
                          headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    response.raise_for_status()
    result = response.json().get("finance",{}).get("result") or []
    if not result: return [], 0
    block = result[0]
    quotes = block.get("quotes") or []
    return quotes, int(block.get("total") or len(quotes))

def _fetch_fallback(client, page_size=PAGE_SIZE):
    params = {"formatted":"true","lang":"en-US","region":"US","count":str(page_size),"scrIds":"day_gainers"}
    response = client.get(FALLBACK_URL, params=params, timeout=REQUEST_TIMEOUT,
                          headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    response.raise_for_status()
    result = response.json().get("finance",{}).get("result") or []
    quotes = result[0].get("quotes") or [] if result else []
    return [q for q in quotes if _is_biotech_pharma_quote(q)]

def get_biotech_universe(session=None, max_pages=MAX_PAGES, page_size=PAGE_SIZE):
    """Return ticker->market row for a broad US biotech/pharma screener scan."""
    global LAST_UNIVERSE_STATUS
    client = session or requests
    found, pages, last_error = {}, 0, None
    try:
        total = None
        for page in range(max(1, int(max_pages))):
            quotes, reported_total = _fetch_page(client, page * page_size, page_size)
            pages += 1
            total = reported_total if total is None else total
            for quote in quotes:
                if _is_biotech_pharma_quote(quote):
                    row = _to_market_row(quote)
                    if row: found[row["ticker"]] = row
            if not quotes or (page + 1) * page_size >= total: break
        if found:
            LAST_UNIVERSE_STATUS.update({"status":"OK","count":len(found),"pages":pages,"last_error":None,"source":"YAHOO_FINANCE_SCREENER"})
            print(f"BIOTECH UNIVERSE STATUS: OK tickers={len(found)} pages={pages}", flush=True)
            return found
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        last_error = f"{type(exc).__name__}: {exc}"
        print(f"BIOTECH UNIVERSE PRIMARY SCREENER ERROR: {last_error}", flush=True)
    try:
        for quote in _fetch_fallback(client, page_size):
            row = _to_market_row(quote)
            if row: found[row["ticker"]] = row
        status = "DEGRADED" if found else "ERROR"
        LAST_UNIVERSE_STATUS.update({"status":status,"count":len(found),"pages":pages,"last_error":last_error,"source":"YAHOO_DAY_GAINERS_FALLBACK"})
        print(f"BIOTECH UNIVERSE STATUS: {status} tickers={len(found)}", flush=True)
        return found
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        fallback_error = f"{type(exc).__name__}: {exc}"
        LAST_UNIVERSE_STATUS.update({"status":"ERROR","count":0,"pages":pages,
            "last_error":f"{last_error}; fallback: {fallback_error}" if last_error else fallback_error,
            "source":"YAHOO_FINANCE_SCREENER"})
        print(f"BIOTECH UNIVERSE FALLBACK ERROR: {fallback_error}", flush=True)
        return {}
