from datetime import datetime, timezone

from scanner.trading_setup_41 import enrich_trading_setup


def test_nested_timestamp_resolves_window():
    event = {
        "score": 80,
        "trading_impact": "EXTREME",
        "urgency": "IMMEDIATE",
        "match_confidence": "HIGH",
        "event": {"published_at": "2026-09-07T12:00:00+00:00"},
    }
    result = enrich_trading_setup(event, {"price_change_pct": 1, "volume_ratio": 1}, datetime(2026, 9, 7, 12, 5, tzinfo=timezone.utc))
    assert result["trading_window"] == "0-2H"
    assert result["event_timestamp"] == "2026-09-07T12:00:00+00:00"


def test_data_quality_levels():
    event = {"published_at": "2026-09-07T12:00:00+00:00", "market_cap": 250_000_000, "short_interest_pct": 25}
    high = enrich_trading_setup(event, {"price_change_pct": 2, "volume_ratio": 2})
    low = enrich_trading_setup({}, {})
    assert high["data_quality"] == "HIGH"
    assert low["data_quality"] == "LOW"


def test_unknown_timestamp_remains_explicit():
    result = enrich_trading_setup({"score": 50}, {})
    assert result["trading_window"] == "UNKNOWN"
    assert result["data_quality"] == "LOW"


if __name__ == "__main__":
    test_nested_timestamp_resolves_window()
    test_data_quality_levels()
    test_unknown_timestamp_remains_explicit()
    print("Trading Intelligence Phase 4.1 tests passed")
