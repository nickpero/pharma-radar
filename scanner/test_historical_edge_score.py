from scanner.historical_edge_score import calculate_historical_edge, enrich_historical_edge


def segments():
    return {
        "summary": {"events": 100, "1D": {"n": 100, "median_directional_ar_pct": 1.0, "win_rate": 0.55}},
        "by_subtype": {
            "FDA_APPROVAL": {"events": 20, "1D": {"n": 20, "median_directional_ar_pct": 2.0, "win_rate": 0.70}},
            "FDA_REJECTION": {"events": 30, "1D": {"n": 30, "median_directional_ar_pct": 3.0, "win_rate": 0.65}},
        },
        "by_direction": {
            "POSITIVE": {"events": 50, "1D": {"n": 50, "median_directional_ar_pct": 1.5, "win_rate": 0.60}},
            "NEGATIVE": {"events": 50, "1D": {"n": 50, "median_directional_ar_pct": 0.5, "win_rate": 0.50}},
        },
    }


def edge_data():
    return {
        "by_ticker": {
            "TEST": {"events": 10, "windows": {"1D": {"n": 10, "median_directional_abnormal_return_pct": 4.0, "win_rate": 0.80}}},
            "WEAK": {"events": 2, "windows": {"1D": {"n": 2, "median_directional_abnormal_return_pct": -5.0, "win_rate": 0.0}}},
        }
    }


def test_positive_historical_edge_and_ticker_adjustment():
    result = calculate_historical_edge(
        {"ticker": "TEST", "subtype": "FDA_REJECTION", "direction": "POSITIVE"},
        segments(),
        edge_data(),
    )
    assert result["historical_edge_score"] > 70
    assert result["historical_edge_label"] == "POSITIVE"
    assert result["historical_edge_confidence"] == "HIGH"
    assert result["historical_edge_ticker_adjustment"] > 0
    assert result["historical_edge_ticker_sample"] == 10


def test_small_ticker_sample_is_not_used_for_adjustment():
    result = calculate_historical_edge(
        {"ticker": "WEAK", "subtype": "FDA_APPROVAL", "direction": "NEGATIVE"},
        segments(),
        edge_data(),
    )
    assert result["historical_edge_ticker_sample"] == 2
    assert result["historical_edge_ticker_adjustment"] == 0


def test_unknown_subtype_falls_back_to_global_but_stays_unknown():
    result = calculate_historical_edge(
        {"ticker": "UNKNOWN", "subtype": "NOT_IN_DATA", "direction": "UNKNOWN"},
        segments(),
        edge_data(),
    )
    assert result["historical_edge_sample"] == 0
    assert result["historical_edge_confidence"] == "UNKNOWN"
    assert result["historical_edge_label"] == "UNKNOWN"
    assert result["historical_edge_score"] == 62.0


def test_enrich_preserves_event_fields():
    result = enrich_historical_edge({"ticker": "TEST", "subtype": "FDA_APPROVAL", "score": 100}, segments(), edge_data())
    assert result["score"] == 100
    assert "historical_edge_score" in result


if __name__ == "__main__":
    test_positive_historical_edge_and_ticker_adjustment()
    test_small_ticker_sample_is_not_used_for_adjustment()
    test_unknown_subtype_falls_back_to_global_but_stays_unknown()
    test_enrich_preserves_event_fields()
    print("OK — Historical Edge Score tests passed")
