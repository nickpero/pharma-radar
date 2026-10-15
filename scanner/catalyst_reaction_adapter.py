"""Adapter from scanner alerts to clinical catalyst reaction anomaly labels."""

from scanner.catalyst_reaction import classify_catalyst_reaction

REVIEW_TYPES = {"CLINICAL_REVIEW_UPDATE", "DSMB_UPDATE", "BLINDED_REVIEW", "SAFETY_REVIEW"}
MILESTONE_TYPES = {"PRIMARY_COMPLETION", "STUDY_COMPLETION", "EXPECTED_TRIAL_COMPLETION"}
READOUT_TYPES = {
    "CLINICAL_RESULTS", "CLINICAL_READOUT", "TOPLINE_RESULTS", "PHASE_DATA_UPDATE",
    "PRIMARY_ENDPOINT_MET", "PRIMARY_ENDPOINT_FAILED", "SECONDARY_ENDPOINT_MET",
    "SECONDARY_ENDPOINT_FAILED", "EFFICACY_SIGNAL", "EXPLORATORY_DATA",
}


def classify_alert_reaction(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    subtype = str(event.get("subtype") or alert.get("subtype") or "").upper()
    event_label = str(event.get("type") or alert.get("event_type") or "").upper()
    if subtype in REVIEW_TYPES:
        event_type = "CLINICAL_REVIEW"
    elif subtype in MILESTONE_TYPES:
        event_type = "TRIAL_MILESTONE"
    elif subtype in READOUT_TYPES or event_label in READOUT_TYPES:
        event_type = "CLINICAL_READOUT"
    else:
        # FDA/regulatory, financing, commercial and generic news are outside
        # this clinical reaction classifier.
        return None

    market = alert.get("market_data") or {}
    reaction = alert.get("market_reaction") or {}
    normalized = {
        "ticker": alert.get("ticker"),
        "program": alert.get("program"),
        "event_type": event_type,
        "direction": event.get("direction") or alert.get("direction") or "UNKNOWN",
        "price_change_pct": market.get("price_change_pct", alert.get("price_change_pct")),
        "price_timestamp": market.get("timestamp") or reaction.get("price_timestamp") or alert.get("price_timestamp"),
        "source": alert.get("source"),
        "source_url": alert.get("source_url") or alert.get("url"),
        "new_catalyst": alert.get("is_new_catalyst"),
    }
    return classify_catalyst_reaction(normalized)
