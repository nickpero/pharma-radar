"""Tests for the daily Historical Edge market-data adapter."""

from datetime import date

from scanner.historical_market_data import YahooDailyProvider


def test_window_bars_skips_weekends_and_maps_forward_sessions():
    rows = {
        "2026-08-19": {"close": 100.0, "volume": 10},
        "2026-08-20": {"close": 110.0, "volume": 20},
        "2026-08-21": {"close": 120.0, "volume": 30},
        "2026-08-24": {"close": 130.0, "volume": 40},
        "2026-08-25": {"close": 140.0, "volume": 50},
        "2026-08-26": {"close": 150.0, "volume": 60},
    }
    bars = YahooDailyProvider._window_bars(rows, date(2026, 8, 19))
    assert bars["event"]["close"] == 100.0
    assert bars["1D"]["close"] == 110.0
    assert bars["3D"]["close"] == 130.0
    assert bars["5D"]["close"] == 150.0


def test_window_bars_uses_next_session_for_weekend_event():
    rows = {
        "2026-08-21": {"close": 100.0},
        "2026-08-24": {"close": 110.0},
        "2026-08-25": {"close": 120.0},
    }
    bars = YahooDailyProvider._window_bars(rows, date(2026, 8, 22))
    assert bars["event"]["close"] == 110.0
    assert bars["1D"]["close"] == 120.0


def test_window_bars_calculates_twenty_session_volume_baseline():
    rows = {f"2026-08-{day:02d}": {"close": 100.0, "volume": day} for day in range(1, 22)}
    bars = YahooDailyProvider._window_bars(rows, date(2026, 8, 21))
    assert bars["event"]["volume"] == 21
    assert bars["event"]["baseline_volume"] == sum(range(1, 21)) / 20


def test_chunks_use_five_year_ranges():
    chunks = list(YahooDailyProvider._chunks(date(2015, 6, 1), date(2026, 9, 1)))
    assert chunks == [
        (date(2015, 6, 1), date(2019, 12, 31)),
        (date(2020, 1, 1), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2026, 9, 1)),
    ]


if __name__ == "__main__":
    test_window_bars_skips_weekends_and_maps_forward_sessions()
    test_window_bars_uses_next_session_for_weekend_event()
    test_window_bars_calculates_twenty_session_volume_baseline()
    test_chunks_use_five_year_ranges()
    print("Historical market-data tests passed")
