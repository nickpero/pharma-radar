"""Pharma Radar — Trading Intelligence Rule V1.0.

Conservative qualification layer for research/paper-trading.
It does not generate buy/sell decisions and is not yet used to suppress
Telegram alerts; it only determines whether an alert meets the V1.0
research qualification criteria.
"""
from __future__ import annotations


def _num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _source_reliable(event):
    source_type = str(event.get("source_type") or "").upper()
    return source_type.startswith("PRIMARY_") or source_type in {"RELIABLE_REGULATORY", "PRIMARY_REGULATORY", "PRIMARY_CLINICAL"}


def _market_confirmation(event):
    reaction = event.get("market_reaction") or {}
    direction = str(event.get("direction") or "UNKNOWN").upper()
    reaction_direction = str(reaction.get("reaction_direction") or "UNKNOWN").upper()

    price_direction = direction in {"POSITIVE", "NEGATIVE"} and reaction_direction == direction
    volume_ratio = _num(event.get("volume_ratio"))
    if volume_ratio is None:
        volume_ratio = _num((event.get("market_data") or {}).get("volume_ratio"))
    volume_confirmation = volume_ratio is not None and volume_ratio >= 1.5

    interpretation = str(event.get("reaction_interpretation") or event.get("reaction_classification") or "UNKNOWN").upper()
    coherent_reaction = interpretation == "CONFIRMED" or price_direction

    checks = {
        "price_direction": bool(price_direction),
        "volume": bool(volume_confirmation),
        "coherent_reaction": bool(coherent_reaction),
    }
    return checks, sum(checks.values())


def qualify_trading_intelligence(event):
    """Evaluate the conservative V1.0 research qualification rule."""
    alert_tier = str(event.get("alert_tier") or "LOW").upper()
    priority = _num(event.get("alert_priority"), 0.0) or 0.0
    ti_score = _num(event.get("trading_intelligence_score"), 0.0) or 0.0
    edge_sample = _num(event.get("historical_edge_sample"), 0.0) or 0.0
    edge_median = _num(event.get("historical_edge_median_1d_pct"), 0.0) or 0.0
    edge_win_rate = _num(event.get("historical_edge_win_rate_1d"), 0.0) or 0.0
    source_ok = _source_reliable(event)
    market_checks, market_confirmations = _market_confirmation(event)

    checks = {
        "priority": alert_tier in {"CRITICAL", "HIGH"} or priority >= 60,
        "ti_score": ti_score >= 80,
        "source": source_ok,
        "historical_sample": edge_sample >= 30,
        "historical_edge": edge_median >= 1.0 and edge_win_rate >= 0.55,
        "market_confirmation": market_confirmations >= 2,
    }
    qualified = all(checks.values())
    watch_checks = {
        "priority": alert_tier in {"CRITICAL", "HIGH"} or priority >= 60,
        "ti_score": ti_score >= 75,
        "source": source_ok,
        "historical_sample": edge_sample >= 10,
        "historical_edge": edge_median >= 0.75 and edge_win_rate >= 0.55,
        "market_confirmation": market_confirmations >= 2,
    }
    watch = all(watch_checks.values())
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "trading_intelligence_rule_version": "1.1",
        "trading_intelligence_qualified": qualified,
        "trading_intelligence_watch": watch,
        "trading_intelligence_watch_checks": watch_checks,
        "trading_intelligence_watch_failed": [name for name, passed in watch_checks.items() if not passed],
        "trading_intelligence_rule_checks": checks,
        "trading_intelligence_rule_failed": failed,
        "trading_intelligence_market_confirmation_count": market_confirmations,
        "trading_intelligence_market_confirmation": market_checks,
    }


def enrich_trading_intelligence_rule(event):
    result = dict(event or {})
    result.update(qualify_trading_intelligence(result))
    return result


def enrich_trading_intelligence_rules(events):
    return [enrich_trading_intelligence_rule(event) for event in (events or [])]
