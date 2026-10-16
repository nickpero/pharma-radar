from scanner.catalyst_reaction import classify_catalyst_reaction


def test_positive_readout_with_large_selloff_is_flagged():
    result = classify_catalyst_reaction({
        "ticker": "KAPA", "event_type": "CLINICAL_READOUT",
        "direction": "POSITIVE", "price_change_pct": -22.6,
        "price_timestamp": "2026-10-06T15:00:00-04:00",
        "source_url": "https://example.com/ir",
    })
    assert result["anomaly"] == "POSITIVE_CATALYST_NEGATIVE_REACTION"
    assert result["is_trade_recommendation"] is False


def test_blinded_review_selloff_is_not_negative_efficacy():
    result = classify_catalyst_reaction({
        "ticker": "SXTP", "event_type": "CLINICAL_REVIEW",
        "direction": "UNKNOWN", "price_change_pct": -24.3,
        "price_timestamp": "2026-10-06T15:00:00-04:00",
    })
    assert result["anomaly"] == "REVIEW_WITH_SELL_OFF"
    assert "not classified as negative efficacy" in result["explanation"]


def test_trial_milestone_selloff_is_not_a_readout():
    result = classify_catalyst_reaction({
        "ticker": "ABC", "event_type": "TRIAL_MILESTONE",
        "direction": "UNKNOWN", "price_change_pct": -15.0,
        "price_timestamp": "2026-10-06T15:00:00-04:00",
    })
    assert result["anomaly"] == "MILESTONE_WITH_SELL_OFF"


def test_move_without_catalyst_is_flagged_only_when_explicit():
    event = {"ticker": "XYZ", "new_catalyst": False, "price_change_pct": -12.0,
             "price_timestamp": "2026-10-06T15:00:00-04:00"}
    assert classify_catalyst_reaction(event)["anomaly"] == "MOVE_WITHOUT_NEW_CATALYST"
    assert classify_catalyst_reaction({"ticker": "XYZ", "price_change_pct": -12.0}) is None


def test_small_move_is_not_anomaly():
    assert classify_catalyst_reaction({
        "ticker": "ABC", "event_type": "CLINICAL_READOUT",
        "direction": "POSITIVE", "price_change_pct": 1.0,
        "price_timestamp": "2026-10-06T15:00:00-04:00",
    })["anomaly"] == "POSITIVE_CATALYST_LOW_REACTION"



def test_untimestamped_daily_move_is_not_compared_to_event():
    assert classify_catalyst_reaction({
        "ticker": "ABC", "event_type": "CLINICAL_READOUT",
        "direction": "POSITIVE", "price_change_pct": -15.0,
    }) is None
