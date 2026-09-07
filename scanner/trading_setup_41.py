"""Pharma Radar — Trading Setup 4.1 refinements.

Keeps Phase 4 scoring stable while hardening timestamp resolution and data-quality reporting.
"""

from datetime import datetime, timezone

from scanner.trading_setup import enrich_trading_setup as _base_enrich


def _timestamp(event):
    nested = event.get("event") if isinstance(event.get("event"), dict) else {}
    for value in (
        event.get("published_at"),
        event.get("event_timestamp"),
        event.get("timestamp"),
        nested.get("published_at"),
        nested.get("event_timestamp"),
        nested.get("timestamp"),
    ):
        if value:
            return value
    return None


def _minutes_since(value, now=None):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        reference = now or datetime.now(timezone.utc)
        return max(0.0, (reference - dt).total_seconds() / 60.0)
    except (TypeError, ValueError):
        return None


def _quality(event, market_data):
    count = sum([
        bool(_timestamp(event)),
        market_data.get("price_change_pct") is not None,
        market_data.get("volume_ratio") is not None,
        event.get("market_cap") is not None,
        event.get("short_interest_pct") is not None,
    ])
    return "HIGH" if count >= 4 else "MEDIUM" if count >= 2 else "LOW"


def enrich_trading_setup(event, market_data=None, now=None):
    event = dict(event or {})
    market_data = market_data or event.get("market_data") or {}
    timestamp = _timestamp(event)
    result = _base_enrich(event, market_data=market_data, now=now)
    minutes = _minutes_since(timestamp, now=now)
    if result.get("trading_window") == "UNKNOWN" and minutes is not None:
        if minutes <= 120:
            result["trading_window"] = "0-2H"
        elif minutes <= 1440:
            result["trading_window"] = "2-24H"
        elif minutes <= 10080:
            result["trading_window"] = "1-7D"
        else:
            result["trading_window"] = "EXPIRED"
    result["event_timestamp"] = timestamp
    result["data_quality"] = _quality(result, market_data)
    return result
