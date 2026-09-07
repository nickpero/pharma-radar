"""Pharma Radar — Phase 5.2 market reaction classification."""


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_reaction(event):
    """Classify observed market reaction relative to catalyst strength.

    This is an attention/interpretation layer, never a buy/sell signal.
    """
    catalyst = _num(event.get("score"))
    reaction = event.get("reaction") or {}
    movement = _num(reaction.get("movement_pct"))
    volume = _num(reaction.get("volume_ratio"))
    direction = str(event.get("direction") or "UNKNOWN").upper()

    if catalyst is None or movement is None:
        return "UNKNOWN"

    # A strong catalyst moving against its expected direction is a divergence.
    positive_catalyst = direction in {"POSITIVE", "CATALYST"}
    negative_catalyst = direction == "NEGATIVE"
    aligned = (positive_catalyst and movement > 0) or (negative_catalyst and movement < 0)
    opposed = (positive_catalyst and movement < 0) or (negative_catalyst and movement > 0)

    if opposed and abs(movement) >= 2.0 and catalyst >= 60:
        return "DIVERGENCE"

    # Volume confirms the move; extreme price moves without confirmation are
    # treated conservatively as possible overreaction.
    if abs(movement) >= 10.0 and (volume is None or volume >= 3.0):
        return "OVERREACTION" if abs(movement) >= 20.0 else "CONFIRMED"

    if catalyst >= 60 and aligned:
        if abs(movement) >= 5.0 and (volume is None or volume >= 1.5):
            return "CONFIRMED"
        if abs(movement) < 2.0:
            return "UNDERREACTION"
        return "CONFIRMED"

    if catalyst >= 60 and abs(movement) < 2.0:
        return "UNDERREACTION"

    if abs(movement) >= 20.0:
        return "OVERREACTION"

    if aligned:
        return "CONFIRMED"
    return "UNKNOWN"


def enrich_reaction_classification(event):
    result = dict(event or {})
    result["reaction_classification"] = classify_reaction(result)
    return result


def enrich_reaction_classifications(events):
    return [enrich_reaction_classification(event) for event in (events or [])]
