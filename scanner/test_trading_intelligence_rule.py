from scanner.trading_intelligence_rule import qualify_trading_intelligence


def _qualified():
    return {
        "alert_tier": "HIGH",
        "alert_priority": 85,
        "trading_intelligence_score": 88,
        "source_type": "PRIMARY_REGULATORY",
        "historical_edge_sample": 35,
        "historical_edge_median_1d_pct": 2.1,
        "historical_edge_win_rate_1d": 0.61,
        "direction": "POSITIVE",
        "reaction_interpretation": "CONFIRMED",
        "market_reaction": {"reaction_direction": "POSITIVE"},
        "volume_ratio": 2.0,
    }


def test_qualified_event_passes():
    result = qualify_trading_intelligence(_qualified())
    assert result["trading_intelligence_qualified"] is True
    assert result["trading_intelligence_rule_failed"] == []
    assert result["trading_intelligence_market_confirmation_count"] == 3


def test_insufficient_history_fails():
    event = _qualified()
    event["historical_edge_sample"] = 29
    result = qualify_trading_intelligence(event)
    assert result["trading_intelligence_qualified"] is False
    assert "historical_sample" in result["trading_intelligence_rule_failed"]


def test_two_of_three_market_checks_are_required():
    event = _qualified()
    event["reaction_interpretation"] = "UNKNOWN"
    event["volume_ratio"] = 1.0
    result = qualify_trading_intelligence(event)
    assert result["trading_intelligence_market_confirmation_count"] == 1
    assert result["trading_intelligence_qualified"] is False


if __name__ == "__main__":
    test_qualified_event_passes()
    test_insufficient_history_fails()
    test_two_of_three_market_checks_are_required()
    print("OK — Trading Intelligence Rule tests passed")
