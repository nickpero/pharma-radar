from scanner.trading_intelligence_score import calculate_trading_intelligence_score


def test_strong_confirmed_event():
    result = calculate_trading_intelligence_score({
        "score": 100,
        "historical_edge_score": 85,
        "direction": "POSITIVE",
        "market_reaction": {"reaction_status": "AVAILABLE", "reaction_15m_pct": 5.0},
        "event_surprise": "HIGH",
        "volume_ratio": 3.0,
        "data_quality": "HIGH",
    })
    assert result["trading_intelligence_score"] >= 85
    assert result["trading_intelligence_label"] == "CRITICAL"


def test_weak_event_stays_low():
    result = calculate_trading_intelligence_score({"score": 15, "historical_edge_score": 30, "direction": "UNKNOWN"})
    assert result["trading_intelligence_score"] < 60
    assert result["trading_intelligence_label"] == "LOW"


def test_missing_market_data_is_neutral_not_fatal():
    result = calculate_trading_intelligence_score({"score": 70, "historical_edge_score": 70})
    assert result["ti_market_reaction_score"] == 50.0
    assert 0 <= result["trading_intelligence_score"] <= 100


if __name__ == "__main__":
    test_strong_confirmed_event()
    test_weak_event_stays_low()
    test_missing_market_data_is_neutral_not_fatal()
    print("OK — Trading Intelligence Score tests passed")
