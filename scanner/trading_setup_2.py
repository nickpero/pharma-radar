"""Pharma Radar — Phase 5.3 Trading Setup 2.0.

Combines catalyst quality, surprise, real market reaction, volume,
timing and market structure into a transparent 0-100 attention score.
This is not a buy/sell signal.
"""

from scanner.trading_setup import (
    minutes_since,
    trading_window,
    infer_event_surprise,
    surprise_score,
    market_cap_score,
    short_interest_score,
)

SETUP2_MAX = 100


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reaction(event):
    return event.get("market_reaction") or {}


def reaction_component(event):
    reaction = _reaction(event)
    interpretation = str(event.get("reaction_interpretation") or event.get("reaction_classification") or "UNKNOWN").upper()
    movement = _num(reaction.get("reaction_pct"))
    if movement is None:
        return 0
    values = {
        "CONFIRMED": 15,
        "UNDERREACTION": 12,
        "DIVERGENCE": 10,
        "OVERREACTION": 4,
        "UNKNOWN": 2,
    }
    base = values.get(interpretation, 2)
    if abs(movement) >= 10 and interpretation == "CONFIRMED":
        return 15
    return base


def reaction_quality(event):
    reaction = _reaction(event)
    if reaction.get("reaction_status") != "AVAILABLE":
        return "LOW"
    present = sum(reaction.get(key) is not None for key in (
        "reaction_pct", "reaction_1m_pct", "reaction_5m_pct", "reaction_15m_pct",
        "reaction_30m_pct", "reaction_60m_pct", "post_catalyst_high", "post_catalyst_low",
    ))
    return "HIGH" if present >= 6 else "MEDIUM" if present >= 3 else "LOW"


def structure_component(event, market_data):
    """Reward informative liquidity/size structure, never direction."""
    volume = _num((market_data or {}).get("volume_ratio"))
    market_cap = _num(event.get("market_cap"))
    short_interest = _num(event.get("short_interest_pct"))
    score = 0
    if volume is not None:
        if volume >= 5:
            score += 4
        elif volume >= 3:
            score += 3
        elif volume >= 1.5:
            score += 2
        else:
            score += 1
    score += market_cap_score(market_cap)
    score += short_interest_score(short_interest)
    return min(10, score)


def build_trading_setup_2(event, market_data=None, now=None):
    """Return Setup 2.0 score and transparent component breakdown."""
    event = dict(event or {})
    market_data = market_data or event.get("market_data") or {}
    catalyst = max(0, min(100, _num(event.get("score")) or 0))
    impact = str(event.get("trading_impact", "LOW")).upper()
    urgency = str(event.get("urgency", "LOW")).upper()
    confidence = str(event.get("match_confidence", "LOW")).upper()

    catalyst_c = round(catalyst * 0.25)
    impact_c = {"EXTREME": 15, "HIGH": 12, "MEDIUM": 8, "LOW": 3}.get(impact, 3)
    urgency_c = {"IMMEDIATE": 10, "FAST": 8, "NORMAL": 5, "LOW": 2}.get(urgency, 2)
    confidence_c = {"HIGH": 5, "MEDIUM": 3, "LOW": 1}.get(confidence, 1)

    timestamp = event.get("published_at") or event.get("event_timestamp")
    minutes = minutes_since(timestamp, now=now)
    timing_c = 5 if minutes is not None and minutes <= 120 else 4 if minutes is not None and minutes <= 1440 else 2 if minutes is not None and minutes <= 10080 else 0
    surprise = infer_event_surprise(event)
    surprise_c = min(10, round(surprise_score(surprise) * 10 / 7))
    reaction_c = reaction_component(event)
    structure_c = structure_component(event, market_data)

    total = min(SETUP2_MAX, catalyst_c + impact_c + urgency_c + confidence_c + timing_c + surprise_c + reaction_c + structure_c)
    return {
        "trading_setup_score": total,
        "trading_setup_version": "5.3",
        "setup_catalyst_component": catalyst_c,
        "setup_impact_component": impact_c,
        "setup_urgency_component": urgency_c,
        "setup_confidence_component": confidence_c,
        "setup_timing_component": timing_c,
        "setup_surprise_component": surprise_c,
        "setup_reaction_component": reaction_c,
        "setup_structure_component": structure_c,
        "setup_reaction_quality": reaction_quality(event),
        "trading_window": trading_window(minutes),
        "event_surprise": surprise,
        "event_surprise_score": surprise_score(surprise),
    }


def enrich_trading_setup_2(event, market_data=None, now=None):
    result = dict(event or {})
    result.update(build_trading_setup_2(result, market_data=market_data, now=now))
    return result


def enrich_trading_setups_2(events, market_data_by_ticker=None, now=None):
    market_data_by_ticker = market_data_by_ticker or {}
    return [enrich_trading_setup_2(event, market_data_by_ticker.get(str(event.get("ticker") or "").upper(), event.get("market_data")), now=now) for event in (events or [])]
