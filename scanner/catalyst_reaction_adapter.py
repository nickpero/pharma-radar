"""Adapter from scanner alerts to catalyst reaction anomaly labels."""

from scanner.catalyst_reaction import classify_catalyst_reaction


def classify_alert_reaction(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    subtype = str(event.get("subtype") or alert.get("subtype") or "").upper()
    if subtype in {"CLINICAL_REVIEW_UPDATE", "DSMB_UPDATE", "BLINDED_REVIEW"}:
        event_type = "CLINICAL_REVIEW"
    elif subtype in {"PRIMARY_COMPLETION", "STUDY_COMPLETION", "EXPECTED_TRIAL_COMPLETION"}:
        event_type = "TRIAL_MILESTONE"
    else:
        event_type = str(alert.get("event_type") or "CLINICAL_READOUT").upper()
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
