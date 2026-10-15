"""Market reaction versus catalyst classification.

Labels are descriptive research flags, not trade recommendations. A price move
is never attributed to a catalyst without timestamp/source evidence.
"""


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_catalyst_reaction(event, positive_low=0.0, negative_large=-10.0,
                              positive_large=10.0, neutral_move=-10.0,
                              low_reaction_max=3.0):
    """Classify observed event direction against a timestamped price move.

    Required event fields: event_type (CLINICAL_READOUT/TRIAL_MILESTONE/
    CLINICAL_REVIEW), direction (POSITIVE/NEGATIVE/UNKNOWN), and price_change_pct.
    """
    event_type = str(event.get("event_type") or "").upper()
    direction = str(event.get("direction") or "UNKNOWN").upper()
    move = _number(event.get("price_change_pct"))
    ticker = str(event.get("ticker") or "UNKNOWN").upper()
    timestamp = event.get("price_timestamp") or event.get("event_timestamp")
    if move is None:
        return None

    common = {
        "ticker": ticker,
        "event_type": event_type or "NO_CONFIRMED_CATALYST",
        "direction": direction,
        "price_change_pct": move,
        "price_timestamp": timestamp,
        "source_url": event.get("source_url") or event.get("source"),
        "is_trade_recommendation": False,
    }

    if event.get("new_catalyst") is False and abs(move) >= abs(negative_large):
        return {**common, "anomaly": "MOVE_WITHOUT_NEW_CATALYST",
                "explanation": "Large price move without a confirmed new catalyst in the supplied event set."}
    if event_type == "CLINICAL_REVIEW" and move <= neutral_move:
        return {**common, "anomaly": "REVIEW_WITH_SELL_OFF",
                "explanation": "A review/blinded update coincides with a large sell-off; the review is not classified as negative efficacy data."}
    if event_type == "TRIAL_MILESTONE" and move <= neutral_move:
        return {**common, "anomaly": "MILESTONE_WITH_SELL_OFF",
                "explanation": "A trial-completion milestone coincides with a large sell-off; no clinical result is inferred."}
    if direction in {"POSITIVE", "CATALYST"} and move <= negative_large:
        return {**common, "anomaly": "POSITIVE_CATALYST_NEGATIVE_REACTION",
                "explanation": "Positive catalyst direction and large negative price move diverge; investigate confounders before interpretation."}
    if direction in {"POSITIVE", "CATALYST"} and 0 <= move <= low_reaction_max:
        return {**common, "anomaly": "POSITIVE_CATALYST_LOW_REACTION",
                "explanation": "Positive catalyst with a limited positive/flat reaction; expectations and financing/news context may matter."}
    if direction == "NEGATIVE" and move >= positive_large:
        return {**common, "anomaly": "NEGATIVE_CATALYST_POSITIVE_REACTION",
                "explanation": "Negative catalyst direction and large positive price move diverge; verify other news and market context."}
    return None
