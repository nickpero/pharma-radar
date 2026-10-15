from scanner.catalyst_reaction_adapter import classify_alert_reaction


def test_adapter_preserves_review_unknown_direction():
    result = classify_alert_reaction({
        "ticker": "SXTP",
        "subtype": "CLINICAL_REVIEW_UPDATE",
        "direction": "NEGATIVE",
        "market_data": {"price_change_pct": -24.3, "timestamp": "2026-10-06T15:00:00-04:00"},
        "published_at": "2026-10-06T12:00:00Z",
    })
    assert result["anomaly"] == "REVIEW_WITH_SELL_OFF"
    assert result["direction"] == "UNKNOWN"


def test_adapter_uses_nested_event_fields():
    result = classify_alert_reaction({
        "ticker": "KAPA",
        "program": "ENV-105",
        "event": {"subtype": "TOPLINE_RESULTS", "direction": "POSITIVE"},
        "market_data": {"price_change_pct": -22.6, "timestamp": "2026-10-06T15:00:00-04:00"},
        "source_url": "https://example.com/ir",
    })
    assert result["anomaly"] == "POSITIVE_CATALYST_NEGATIVE_REACTION"
    assert result["source_url"] == "https://example.com/ir"


def test_adapter_without_market_data_returns_none():
    assert classify_alert_reaction({"ticker": "ABC", "market_data": {}}) is None


def test_press_release_timestamp_is_not_used_as_market_timestamp():
    result = classify_alert_reaction({
        "ticker": "ABC",
        "subtype": "CLINICAL_RESULTS",
        "direction": "POSITIVE",
        "published_at": "2026-10-06T15:00:00-04:00",
        "market_data": {"price_change_pct": -22.0},
    })
    assert result is None



def test_nonclinical_regulatory_event_is_not_sent_to_clinical_classifier():
    assert classify_alert_reaction({
        "ticker": "ABC",
        "subtype": "FDA_APPROVAL",
        "direction": "POSITIVE",
        "market_data": {"price_change_pct": -20.0, "timestamp": "2026-10-06T15:00:00-04:00"},
    }) is None
