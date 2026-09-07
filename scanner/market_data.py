"""
Pharma Radar — Market Data

Lightweight market snapshot provider used by Trading Intelligence.
No trading action is performed here.
"""

from datetime import datetime, timezone

import requests


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
REQUEST_TIMEOUT = 10
USER_AGENT = "PharmaRadar/1.0"


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def get_market_snapshot(ticker, session=None):
    """Return a best-effort 1m/1d market snapshot for a US ticker."""
    ticker = str(ticker or "").strip().upper()
    if not ticker or ticker in {"UNKNOWN", "N/A"}:
        return None

    client = session or requests
    url = YAHOO_CHART_URL.format(ticker=ticker)
    params = {"range": "1mo", "interval": "1d", "events": "history"}
    try:
        response = client.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, TypeError):
        return None

    try:
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        indicators = result.get("indicators", {})
        quote = indicators.get("quote", [{}])[0]
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        current = _safe_float(meta.get("regularMarketPrice"))
        previous = _safe_float(meta.get("previousClose"))
        if current is None and closes:
            current = _safe_float(closes[-1])
        if previous is None and len(closes) >= 2:
            previous = _safe_float(closes[-2])

        volume = None
        if volumes:
            volume = _safe_float(volumes[-1])
        avg_volume = _mean([_safe_float(v) for v in volumes[-21:-1]])

        change_pct = None
        if current is not None and previous:
            change_pct = (current - previous) / previous * 100.0

        volume_ratio = None
        if volume is not None and avg_volume:
            volume_ratio = volume / avg_volume

        return {
            "ticker": ticker,
            "price": current,
            "previous_close": previous,
            "price_change_pct": change_pct,
            "volume": volume,
            "average_volume_20d": avg_volume,
            "volume_ratio": volume_ratio,
            "market_data_source": "YAHOO_CHART",
            "market_data_timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def enrich_market_data(events):
    """Add market snapshots to events with a ticker, best effort."""
    if not events:
        return []

    cache = {}
    enriched = []
    for event in events:
        result = dict(event)
        ticker = str(result.get("ticker") or "").upper()
        if ticker and ticker not in cache:
            cache[ticker] = get_market_snapshot(ticker)
        snapshot = cache.get(ticker)
        if snapshot:
            result["market_data"] = snapshot
        enriched.append(result)
    return enriched
