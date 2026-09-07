"""Pharma Radar — Market profile data (best effort)."""

import requests


YAHOO_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
REQUEST_TIMEOUT = 10
USER_AGENT = "PharmaRadar/1.0"


def _raw(value):
    if isinstance(value, dict):
        return value.get("raw")
    return value


def get_market_profile(ticker, session=None):
    """Fetch market cap and short interest without making trading decisions."""
    ticker = str(ticker or "").strip().upper()
    if not ticker or ticker in {"UNKNOWN", "N/A"}:
        return None
    client = session or requests
    try:
        response = client.get(
            YAHOO_SUMMARY_URL.format(ticker=ticker),
            params={"modules": "price,defaultKeyStatistics"},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
        result = payload["quoteSummary"]["result"][0]
        price = result.get("price", {})
        stats = result.get("defaultKeyStatistics", {})
        market_cap = _raw(price.get("marketCap"))
        short_pct = _raw(stats.get("shortPercentOfFloat"))
        if short_pct is not None:
            short_pct = float(short_pct) * 100.0
        if market_cap is None and short_pct is None:
            return None
        return {
            "ticker": ticker,
            "market_cap": market_cap,
            "short_interest_pct": short_pct,
            "market_profile_source": "YAHOO_QUOTE_SUMMARY",
        }
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError):
        return None
