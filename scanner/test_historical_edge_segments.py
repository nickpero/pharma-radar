from scanner.audit_historical_edge_segments import _baseline_backtest, _metric, _size_bucket, _summary


def event(direction="POSITIVE", ar1=2.0, ar3=3.0, ar5=1.0, cap=5_000_000_000):
    return {
        "ticker": "TEST",
        "direction": direction,
        "market_metrics": {
            "market_cap": cap,
            "volume_expansion": 1.5,
            "windows": {
                "1D": {"directional_abnormal_return_pct": ar1},
                "3D": {"directional_abnormal_return_pct": ar3},
                "5D": {"directional_abnormal_return_pct": ar5},
            },
        },
    }


def test_metric_reads_directional_return():
    assert _metric(event(), "1D") == 2.0
    assert _metric(event(), "5D") == 1.0


def test_summary_counts_and_win_rate():
    result = _summary([event(ar1=2), event(ar1=-1)])
    assert result["events"] == 2
    assert result["1D"]["n"] == 2
    assert result["1D"]["win_rate"] == 0.5


def test_market_cap_buckets():
    assert _size_bucket(event(cap=1_000_000_000)) == "SMALL_<2B"
    assert _size_bucket(event(cap=5_000_000_000)) == "MID_2B_10B"
    assert _size_bucket(event(cap=20_000_000_000)) == "LARGE_>=10B"


def test_baseline_is_directional_and_serializable():
    result = _baseline_backtest([event(ar1=2), event(ar1=-1)])
    assert result["windows"]["1D"]["n"] == 2
    assert result["windows"]["1D"]["win_rate"] == 0.5
    assert result["costs_bps"] == 0
