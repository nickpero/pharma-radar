"""Pharma Radar — Trading Intelligence Rule V1.1.

Conservative qualification layer for research/paper-trading.
It does not generate buy/sell decisions; it only determines whether an
alert meets the research qualification or watch criteria.
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
    intraday_available = reaction.get("reaction_status") == "AVAILABLE"
    price_direction_intraday = direction in {"POSITIVE", "NEGATIVE"} and reaction_direction == direction

    daily_price = _num(event.get("price_change_pct"))
    if daily_price is None:
        daily_price = _num((event.get("market_data") or {}).get("price_change_pct"))
    daily_direction_known = direction in {"POSITIVE", "NEGATIVE", "CATALYST"}
    daily_expected_positive = direction in {"POSITIVE", "CATALYST"}
    daily_price_direction = (
        daily_direction_known
        and daily_price is not None
        and abs(daily_price) >= 1.0
        and ((daily_expected_positive and daily_price > 0) or (direction == "NEGATIVE" and daily_price < 0))
    )
    daily_divergent = (
        daily_direction_known
        and daily_price is not None
        and abs(daily_price) >= 2.0
        and ((daily_expected_positive and daily_price < 0) or (direction == "NEGATIVE" and daily_price > 0))
    )
    price_direction = price_direction_intraday if intraday_available else daily_price_direction
    price_source = "INTRADAY" if price_direction_intraday and intraday_available else "DAILY_SNAPSHOT" if (daily_price_direction or daily_divergent) else "NONE"
    if intraday_available:
        market_status = "CONFIRMED" if price_direction_intraday else "DIVERGENT" if direction in {"POSITIVE", "NEGATIVE", "CATALYST"} and reaction_direction != direction else "UNAVAILABLE"
    else:
        market_status = "CONFIRMED" if daily_price_direction else "DIVERGENT" if daily_divergent else "UNAVAILABLE"

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
    return checks, sum(checks.values()), price_source, market_status


def qualify_trading_intelligence(event):
    """Evaluate the conservative V1.1 research qualification rule."""
    alert_tier = str(event.get("alert_tier") or "LOW").upper()
    priority = _num(event.get("alert_priority"), 0.0) or 0.0
    ti_score = _num(event.get("trading_intelligence_score"), 0.0) or 0.0
    edge_sample = _num(event.get("historical_edge_sample"), 0.0) or 0.0
    edge_median = _num(event.get("historical_edge_median_1d_pct"), 0.0) or 0.0
    edge_win_rate = _num(event.get("historical_edge_win_rate_1d"), 0.0) or 0.0
    source_ok = _source_reliable(event)
    market_checks, market_confirmations, market_confirmation_source, market_status = _market_confirmation(event)

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
    return {
        "trading_intelligence_rule_version": "1.1",
        "trading_intelligence_qualified": qualified,
        "trading_intelligence_watch": watch,
        "trading_intelligence_watch_checks": watch_checks,
        "trading_intelligence_watch_failed": [name for name, passed in watch_checks.items() if not passed],
        "trading_intelligence_rule_checks": checks,
        "trading_intelligence_rule_failed": [name for name, passed in checks.items() if not passed],
        "trading_intelligence_market_confirmation_count": market_confirmations,
        "trading_intelligence_market_confirmation": market_checks,
        "trading_intelligence_market_confirmation_source": market_confirmation_source,
        "trading_intelligence_market_status": market_status,
    }


def enrich_trading_intelligence_rule(event):
    result = dict(event or {})
    result.update(qualify_trading_intelligence(result))
    return result


def enrich_trading_intelligence_rules(events):
    return [enrich_trading_intelligence_rule(event) for event in (events or [])]
