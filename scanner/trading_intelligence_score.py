"""Pharma Radar — Trading Intelligence Score V1.1.

Combines catalyst relevance, historical edge, market reaction, surprise,
volume and data quality into one 0-100 decision-support score.
No buy/sell decision is generated.
"""
from __future__ import annotations


def _num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def _reaction_score(event):
    reaction = event.get("market_reaction") or {}
    if reaction.get("reaction_status") != "AVAILABLE":
        daily = _num(event.get("price_change_pct"))
        if daily is None:
            daily = _num((event.get("market_data") or {}).get("price_change_pct"))
        direction = str(event.get("direction") or "UNKNOWN").upper()
        if daily is None or direction not in {"POSITIVE", "NEGATIVE", "CATALYST"}:
            return 50.0
        if direction == "CATALYST":
            direction = "POSITIVE"
        magnitude = min(abs(daily), 10.0) / 10.0 * 100.0
        aligned = (direction == "POSITIVE" and daily > 0) or (direction == "NEGATIVE" and daily < 0)
        return 50.0 + min(magnitude / 2.0, 12.0) if aligned else 50.0 - min(magnitude / 2.0, 12.0)

    direction = str(event.get("direction") or "UNKNOWN").upper()
    observed = _num(reaction.get("reaction_15m_pct"))
    if observed is None:
        observed = _num(reaction.get("reaction_pct"))
    if observed is None:
        return 50.0
    magnitude = min(abs(observed), 10.0) / 10.0 * 100.0
    if direction == "POSITIVE":
        return 50.0 + magnitude / 2 if observed > 0 else 50.0 - magnitude / 2
    if direction == "NEGATIVE":
        return 50.0 + magnitude / 2 if observed < 0 else 50.0 - magnitude / 2
    return 50.0


def _reaction_source(event):
    reaction = event.get("market_reaction") or {}
    if reaction.get("reaction_status") == "AVAILABLE":
        return "INTRADAY"
    if (
        _num(event.get("price_change_pct")) is not None
        or _num((event.get("market_data") or {}).get("price_change_pct")) is not None
    ):
        return "DAILY_SNAPSHOT"
    return "NONE"


def _volume_score(event):
    ratio = _num(event.get("volume_ratio"))
    if ratio is None:
        ratio = _num((event.get("market_data") or {}).get("volume_ratio"))
    if ratio is None:
        return 50.0
    if ratio <= 1:
        return 35.0
    return _clamp(35.0 + (min(ratio, 5.0) - 1.0) * 16.25)


def _surprise_score(event):
    value = str(event.get("event_surprise") or "UNKNOWN").upper()
    return {"HIGH": 100.0, "MEDIUM": 75.0, "LOW": 50.0, "UNKNOWN": 50.0}.get(value, 50.0)


def _quality_score(event):
    value = str(event.get("data_quality") or "UNKNOWN").upper()
    return {"HIGH": 100.0, "MEDIUM": 75.0, "LOW": 50.0, "UNKNOWN": 40.0}.get(value, 40.0)


def calculate_trading_intelligence_score(event):
    """Return component scores and a transparent weighted composite."""
    catalyst = _num(event.get("score"), 0.0)
    edge = _num(event.get("historical_edge_score"), 50.0)
    reaction = _reaction_score(event)
    surprise = _surprise_score(event)
    volume = _volume_score(event)
    quality = _quality_score(event)
    score = catalyst * 0.30 + edge * 0.25 + reaction * 0.20 + surprise * 0.10 + volume * 0.10 + quality * 0.05
    score = round(_clamp(score), 1)
    label = "CRITICAL" if score >= 85 else "HIGH" if score >= 75 else "MEDIUM" if score >= 60 else "LOW"
    return {
        "trading_intelligence_version": "1.1",
        "trading_intelligence_score": score,
        "trading_intelligence_label": label,
        "ti_catalyst_score": round(catalyst, 1),
        "ti_historical_edge_score": round(edge, 1),
        "ti_market_reaction_score": round(reaction, 1),
        "ti_market_reaction_source": _reaction_source(event),
        "ti_surprise_score": round(surprise, 1),
        "ti_volume_score": round(volume, 1),
        "ti_data_quality_score": round(quality, 1),
    }


def enrich_trading_intelligence_score(event):
    result = dict(event or {})
    result.update(calculate_trading_intelligence_score(result))
    return result


def enrich_trading_intelligence_scores(events):
    return [enrich_trading_intelligence_score(event) for event in (events or [])]
