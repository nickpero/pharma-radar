"""Phase 4.1 helpers for explainable Trading Intelligence."""

from datetime import datetime, timezone

EVENT_TIMESTAMP_KEYS = ("published_at", "event_timestamp", "published", "publication_date", "date", "timestamp")


def event_timestamp(event):
    event = dict(event or {})
    for key in EVENT_TIMESTAMP_KEYS:
        value = event.get(key)
        if value not in (None, ""):
            return value
    return None


def minutes_since(timestamp, now=None):
    if not timestamp:
        return None
    try:
        value = str(timestamp).strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        return max(0.0, (reference - dt).total_seconds() / 60.0)
    except (TypeError, ValueError):
        return None


def trading_window(minutes):
    if minutes is None:
        return "UNKNOWN"
    if minutes <= 120:
        return "0-2H"
    if minutes <= 1440:
        return "2-24H"
    if minutes <= 10080:
        return "1-7D"
    return "EXPIRED"


def surprise_basis(event, surprise):
    event = dict(event or {})
    explicit = str(event.get("event_surprise") or "").upper()
    if explicit in {"UNEXPECTED", "EXPECTED", "MIXED"}:
        return "EXPLICIT_EVENT_FIELD"
    if surprise in {"UNEXPECTED", "EXPECTED"}:
        return "EXPECTATION_LANGUAGE"
    if surprise == "MIXED":
        return "MIXED_EXPECTATION_LANGUAGE"
    return "NO_EXPECTATION_DATA"


def awareness_basis(price_change_pct, volume_ratio):
    return "PRICE_VOLUME_PROXY" if price_change_pct is not None or volume_ratio is not None else "NO_MARKET_DATA"
