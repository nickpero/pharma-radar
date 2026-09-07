from datetime import datetime, timedelta, timezone

from scanner.market_data import build_market_reaction


def _points():
    base = datetime(2026, 9, 7, 14, 0, tzinfo=timezone.utc)
    key_prices = {0: 100, 1: 101, 5: 103, 15: 105, 30: 110, 35: 115}
    points = []
    last_price = 100
    for minute in range(36):
        last_price = key_prices.get(minute, last_price)
        points.append({
            "timestamp": base + timedelta(minutes=minute),
            "price": last_price,
            "volume": 1000 + minute * 10,
        })
    return points


def test_market_reaction_calculates_event_and_current_move():
    result = build_market_reaction(
        _points(),
        "2026-09-07T14:00:00+00:00",
        now="2026-09-07T14:35:00+00:00",
        previous_close=98,
    )
    assert result["reaction_status"] == "AVAILABLE"
    assert result["event_price"] == 100
    assert result["current_price"] == 115
    assert result["reaction_pct"] == 15.0
    assert result["reaction_direction"] == "POSITIVE"
    assert result["gap_pct"] == (100 - 98) / 98 * 100


def test_market_reaction_has_multi_window_and_extremes():
    result = build_market_reaction(
        _points(),
        "2026-09-07T14:00:00+00:00",
        now="2026-09-07T14:35:00+00:00",
    )
    assert result["reaction_1m_pct"] == 1.0
    assert result["reaction_5m_pct"] == 3.0
    assert result["reaction_15m_pct"] == 5.0
    assert result["reaction_30m_pct"] == 10.0
    assert result["post_catalyst_high"] == 115
    assert result["post_catalyst_low"] == 100
    assert result["pre_event_15m_pct"] is None


def test_market_reaction_handles_bad_timestamp():
    result = build_market_reaction(_points(), "not-a-date")
    assert result["reaction_status"] == "UNAVAILABLE"
    assert result["reaction_direction"] == "UNKNOWN"


if __name__ == "__main__":
    test_market_reaction_calculates_event_and_current_move()
    test_market_reaction_has_multi_window_and_extremes()
    test_market_reaction_handles_bad_timestamp()
    print("Trading Intelligence Phase 5.1 tests passed")
