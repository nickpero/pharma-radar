from scanner.robust_historical_backtest import _stats


def test_stats_applies_friction_and_calculates_pf():
    result = _stats([2.0, -1.0, 3.0], 30.0)
    assert result["n"] == 3
    assert result["win_rate"] == 2 / 3
    assert result["profit_factor"] is not None
    assert result["median_net_return_pct"] == 1.7


def test_stats_empty():
    assert _stats([], 30.0) == {"n": 0}


if __name__ == "__main__":
    test_stats_applies_friction_and_calculates_pf()
    test_stats_empty()
    print("Robust historical backtest tests passed")
