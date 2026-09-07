"""Pharma Radar — Phase 5.2 market reaction classification."""


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reaction(event):
    return event.get("market_reaction") or event.get("reaction") or {}


def _movement(reaction):
    for key in ("reaction_pct", "movement_pct", "reaction_15m_pct"):
        value = _num(reaction.get(key))
        if value is not None:
            return value
    return None


def classify_reaction_strength(event):
    """Classify absolute price reaction independently of catalyst direction."""
    movement = _movement(_reaction(event))
    if movement is None:
        return "UNKNOWN"
    if movement >= 10:
        return "STRONG POSITIVE"
    if movement >= 2:
        return "POSITIVE"
    if movement <= -10:
        return "STRONG NEGATIVE"
    if movement <= -2:
        return "NEGATIVE"
    return "NEUTRAL"


def classify_reaction_interpretation(event):
    """Compare reaction with catalyst direction/strength.

    Conservative by design: missing data never becomes a directional signal.
    """
    catalyst = _num(event.get("score"))
    reaction = _reaction(event)
    movement = _movement(reaction)
    volume = _num(reaction.get("volume_ratio"))
    if volume is None:
        volume = _num(event.get("volume_ratio"))
    direction = str(event.get("direction") or "UNKNOWN").upper()

    if catalyst is None or movement is None:
        return "UNKNOWN"
    positive = direction in {"POSITIVE", "CATALYST"}
    negative = direction == "NEGATIVE"
    opposed = (positive and movement <= -2) or (negative and movement >= 2)
    aligned = (positive and movement >= 2) or (negative and movement <= -2)

    if catalyst >= 60 and opposed:
        return "DIVERGENCE"
    if abs(movement) >= 20:
        return "OVERREACTION"
    if catalyst >= 60 and aligned:
        if abs(movement) < 5:
            return "UNDERREACTION"
        return "CONFIRMED"
    if catalyst >= 60 and abs(movement) < 2:
        return "UNDERREACTION"
    if aligned:
        return "CONFIRMED"
    if volume is not None and volume >= 3 and abs(movement) >= 5:
        return "OVERREACTION"
    return "UNKNOWN"


def classify_reaction(event):
    """Return the Phase 5.2 two-layer reaction classification."""
    return {
        "reaction_strength": classify_reaction_strength(event),
        "reaction_interpretation": classify_reaction_interpretation(event),
    }


def enrich_reaction_classification(event):
    result = dict(event or {})
    result.update(classify_reaction(result))
    # Backward-compatible summary field used by alerts.
    result["reaction_classification"] = result["reaction_interpretation"]
    return result


def enrich_reaction_classifications(events):
    return [enrich_reaction_classification(event) for event in (events or [])]
