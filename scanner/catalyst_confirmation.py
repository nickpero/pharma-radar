"""Pharma Radar — Phase 5.8 Catalyst Confirmation Engine.

Conservative confirmation layer: measures whether observed market action
supports the catalyst, without producing a buy/sell recommendation.
"""


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reaction(event):
    return event.get("market_reaction") or event.get("reaction") or {}


def _movement(reaction):
    for key in ("reaction_5m_pct", "reaction_15m_pct", "reaction_pct", "reaction_30m_pct", "reaction_60m_pct"):
        value = _num(reaction.get(key))
        if value is not None:
            return value
    return None


def _aligned(event, movement):
    direction = str(event.get("direction") or "UNKNOWN").upper()
    return (direction in {"POSITIVE", "CATALYST"} and movement >= 2) or (direction == "NEGATIVE" and movement <= -2)


def confirmation_score(event):
    """Return a 0-100 evidence score for catalyst/market confirmation."""
    score = 0
    catalyst_score = _num(event.get("score")) or 0
    reaction = _reaction(event)
    movement = _movement(reaction)
    volume = _num(reaction.get("volume_ratio"))
    if volume is None:
        volume = _num(event.get("volume_ratio"))

    if movement is not None:
        if _aligned(event, movement):
            score += 40
        elif abs(movement) < 2:
            score += 10
        else:
            score += 0
        if abs(movement) >= 5:
            score += 10
        if abs(movement) >= 20:
            score -= 15

    if volume is not None:
        if volume >= 3:
            score += 20
        elif volume >= 1.5:
            score += 12
        elif volume >= 1:
            score += 6

    interpretation = str(event.get("reaction_interpretation") or "UNKNOWN").upper()
    if interpretation == "CONFIRMED":
        score += 20
    elif interpretation == "UNDERREACTION":
        score += 8
    elif interpretation == "OVERREACTION":
        score -= 5
    elif interpretation == "DIVERGENCE":
        score -= 20

    if catalyst_score >= 80:
        score += 5
    elif catalyst_score >= 60:
        score += 3

    return max(0, min(100, int(round(score))))


def confirmation_label(score):
    if score >= 75:
        return "CONFIRMED"
    if score >= 50:
        return "PROBABLE"
    if score >= 25:
        return "WEAK"
    return "UNCONFIRMED"


def enrich_catalyst_confirmation(event):
    result = dict(event or {})
    score = confirmation_score(result)
    result["catalyst_confirmation_score"] = score
    result["catalyst_confirmation"] = confirmation_label(score)
    return result


def enrich_catalyst_confirmations(events):
    return [enrich_catalyst_confirmation(event) for event in (events or [])]
