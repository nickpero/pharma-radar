from scanner.catalyst_reaction_adapter import classify_alert_reaction


def test_adapter_preserves_review_unknown_direction():
    result = classify_alert_reaction({
        "ticker": "SXTP",
        "subtype": "CLINICAL_REVIEW_UPDATE",
        "direction": "UNKNOWN",
        "market_data": {"price_change_pct": -24.3},
        "published_at": "2026-10-06T12:00:00Z",
    })
    assert result["anomaly"] == "REVIEW_WITH_SELL_OFF"
    assert result["direction"] == "UNKNOWN"


def test_adapter_uses_nested_event_fields():
    result = classify_alert_reaction({
        "ticker": "KAPA",
        "program": "ENV-105",
        "event": {"subtype": "TOPLINE_RESULTS", "direction": "POSITIVE"},
        "market_data": {"price_change_pct": -22.6},
        "source_url": "https://example.com/ir",
    })
    assert result["anomaly"] == "POSITIVE_CATALYST_NEGATIVE_REACTION"
    assert result["source_url"] == "https://example.com/ir"


def test_adapter_without_market_data_returns_none():
    assert classify_alert_reaction({"ticker": "ABC", "market_data": {}}) is None
