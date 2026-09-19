from scanner.divergence_monitor import classify_divergence, detect_divergences


def _event():
    return {
        "ticker": "IONS",
        "program": "zilganersen",
        "direction": "CATALYST",
        "score": 100,
        "trading_intelligence_score": 70.3,
        "historical_edge_median_1d_pct": 1.3082,
        "historical_edge_win_rate_1d": 0.6768,
        "market_data": {"price_change_pct": -4.94},
        "trading_intelligence_market_status": "DIVERGENT",
    }


def test_strong_positive_catalyst_divergence():
    result = classify_divergence(_event())
    assert result is not None
    assert result["ticker"] == "IONS"
    assert result["daily_pct"] == -4.94


def test_small_move_is_not_divergence_alert():
    event = _event()
    event["market_data"]["price_change_pct"] = -1.5
    assert classify_divergence(event) is None


def test_non_positive_direction_is_not_divergence_alert():
    event = _event()
    event["direction"] = "NEGATIVE"
    assert classify_divergence(event) is None


def test_detect_multiple_divergences():
    first = _event()
    second = dict(_event(), ticker="RVMD")
    assert [x["ticker"] for x in detect_divergences([first, second])] == ["IONS", "RVMD"]


if __name__ == "__main__":
    test_strong_positive_catalyst_divergence()
    test_small_move_is_not_divergence_alert()
    test_non_positive_direction_is_not_divergence_alert()
    test_detect_multiple_divergences()
    print("OK — Divergence Monitor tests passed")
