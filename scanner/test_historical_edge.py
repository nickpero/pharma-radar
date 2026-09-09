"""Unit tests for the Historical Edge Engine."""

from scanner.historical_edge import (
    abnormal_return,
    aggregate_historical_edge,
    calculate_event_metrics,
    classify_edge,
    confidence_for_sample,
    safe_return,
    volume_expansion,
)


def test_safe_return():
    assert round(safe_return(100, 110), 6) == 10.0
    assert safe_return(0, 110) is None
    assert safe_return(None, 110) is None


def test_abnormal_return():
    assert round(abnormal_return(12, 4), 6) == 8.0
    assert round(abnormal_return(12, 4, beta=1.5), 6) == 6.0
    assert abnormal_return(None, 4) is None


def test_volume_expansion():
    assert round(volume_expansion(300, 100), 6) == 3.0
    assert volume_expansion(300, 0) is None


def test_confidence_and_edge():
    assert confidence_for_sample(4) == "LOW"
    assert confidence_for_sample(10) == "MEDIUM"
    assert confidence_for_sample(25) == "HIGH"
    assert classify_edge(4.0, 0.70, 10) == "POSITIVE"
    assert classify_edge(-4.0, 0.30, 10) == "NEGATIVE"
    assert classify_edge(1.0, 0.70, 10) == "NEUTRAL"
    assert classify_edge(5.0, 0.80, 4) == "NEUTRAL"


def test_calculate_event_metrics():
    event = {
        "ticker": "TEST",
        "company": "Test Bio",
        "program": "drug-x",
        "subtype": "FDA_APPROVAL",
        "event_id": "evt-1",
        "event_timestamp": "2026-01-02T15:00:00Z",
    }
    bars = {
        "event": {"close": 100, "volume": 300, "baseline_volume": 100},
        "1D": {"close": 110},
        "3D": {"close": 115},
        "5D": {"close": 120},
    }
    benchmark = {
        "event": {"close": 100},
        "1D": {"close": 102},
        "3D": {"close": 103},
        "5D": {"close": 104},
    }

    metrics = calculate_event_metrics(event, bars, benchmark)
    assert metrics["ticker"] == "TEST"
    assert round(metrics["volume_expansion"], 6) == 3.0
    assert round(metrics["windows"]["1D"]["stock_return_pct"], 6) == 10.0
    assert round(metrics["windows"]["1D"]["abnormal_return_pct"], 6) == 8.0


def test_aggregate_historical_edge():
    metrics = []
    for i, value in enumerate([5.0, 4.0, 3.5, 6.0, 4.5]):
        metrics.append({
            "ticker": "TEST",
            "subtype": "FDA_APPROVAL",
            "windows": {"1D": {"abnormal_return_pct": value}},
        })
    result = aggregate_historical_edge(metrics)
    stats = result["FDA_APPROVAL"]["windows"]["1D"]
    assert stats["n"] == 5
    assert round(stats["median_abnormal_return_pct"], 6) == 4.5
    assert stats["win_rate"] == 1.0
    assert stats["edge"] == "POSITIVE"
    assert stats["confidence"] == "LOW"


if __name__ == "__main__":
    tests = [
        test_safe_return,
        test_abnormal_return,
        test_volume_expansion,
        test_confidence_and_edge,
        test_calculate_event_metrics,
        test_aggregate_historical_edge,
    ]
    for test in tests:
        test()
    print("Historical Edge Engine tests passed")
