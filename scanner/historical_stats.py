"""Pharma Radar — Phase 5.5 historical catalyst intelligence."""

from datetime import datetime, timezone

from scanner.catalyst_memory import find_similar_events

HORIZONS = ("reaction_1m_pct", "reaction_5m_pct", "reaction_15m_pct", "reaction_30m_pct", "reaction_60m_pct")
MIN_SAMPLE = 3


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _prior_only(event, rows):
    current = _parse_ts(event.get("event_timestamp") or event.get("published_at"))
    if current is None:
        return []
    result = []
    for row in rows:
        ts = _parse_ts(row.get("event_timestamp"))
        if ts is not None and ts < current:
            result.append(row)
    return result


def _values(rows, key):
    values = []
    for row in rows:
        reaction = row.get("reaction") or {}
        value = _num(reaction.get(key))
        if value is not None:
            values.append(value)
    return values


def _mean(values):
    return round(sum(values) / len(values), 2) if values else None


def _median(values):
    if not values:
        return None
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return round(values[mid], 2)
    return round((values[mid - 1] + values[mid]) / 2, 2)


def _rate(rows, predicate):
    applicable = [row for row in rows if predicate(row) is not None]
    if not applicable:
        return None
    return round(sum(1 for row in applicable if predicate(row)) / len(applicable) * 100, 1)


def _reaction_value(row):
    reaction = row.get("reaction") or {}
    return _num(reaction.get("reaction_15m_pct"))


def calculate_historical_stats(event, rows):
    prior = _prior_only(event, rows)
    sample = len(prior)
    horizons = {}
    for key in HORIZONS:
        values = _values(prior, key)
        horizons[key] = {"n": len(values), "mean_pct": _mean(values), "median_pct": _median(values)}

    positive_rate = _rate(prior, lambda row: (None if _reaction_value(row) is None else _reaction_value(row) > 0))
    negative_rate = _rate(prior, lambda row: (None if _reaction_value(row) is None else _reaction_value(row) < 0))
    confirmed_rate = _rate(prior, lambda row: str(row.get("reaction_interpretation") or "").upper() == "CONFIRMED" if row.get("reaction_interpretation") is not None else None)
    divergence_rate = _rate(prior, lambda row: str(row.get("reaction_interpretation") or "").upper() == "DIVERGENCE" if row.get("reaction_interpretation") is not None else None)
    overreaction_rate = _rate(prior, lambda row: str(row.get("reaction_interpretation") or "").upper() == "OVERREACTION" if row.get("reaction_interpretation") is not None else None)
    underreaction_rate = _rate(prior, lambda row: str(row.get("reaction_interpretation") or "").upper() == "UNDERREACTION" if row.get("reaction_interpretation") is not None else None)

    confidence = "UNKNOWN" if sample < MIN_SAMPLE else ("HIGH" if sample >= 10 else "MEDIUM")
    return {
        "sample_size": sample,
        "confidence": confidence,
        "reaction_horizons": horizons,
        "positive_rate_15m_pct": positive_rate,
        "negative_rate_15m_pct": negative_rate,
        "confirmed_rate_pct": confirmed_rate,
        "divergence_rate_pct": divergence_rate,
        "overreaction_rate_pct": overreaction_rate,
        "underreaction_rate_pct": underreaction_rate,
    }


def enrich_historical_stats(event, path=None, limit=50):
    result = dict(event or {})
    rows = find_similar_events(result, limit=limit, **({"path": path} if path is not None else {}))
    stats = calculate_historical_stats(result, rows)
    result["historical_stats"] = stats
    result["historical_sample_size"] = stats["sample_size"]
    result["historical_confidence"] = stats["confidence"]
    return result


def enrich_historical_stats_batch(events, path=None, limit=50):
    return [enrich_historical_stats(event, path=path, limit=limit) for event in (events or [])]
