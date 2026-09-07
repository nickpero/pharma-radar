from datetime import datetime, timezone

from scanner.phase41 import event_timestamp, minutes_since, trading_window, surprise_basis, awareness_basis


def test_event_timestamp_fallbacks():
    assert event_timestamp({"published_at": "2026-09-07T08:00:00+00:00", "event_timestamp": "bad"}) == "2026-09-07T08:00:00+00:00"
    assert event_timestamp({"event_timestamp": "2026-09-07T08:00:00+00:00"}) == "2026-09-07T08:00:00+00:00"
    assert event_timestamp({"publication_date": "2026-09-07T08:00:00+00:00"}) == "2026-09-07T08:00:00+00:00"
    assert event_timestamp({}) is None


def test_window_boundaries():
    assert trading_window(0) == "0-2H"
    assert trading_window(120) == "0-2H"
    assert trading_window(121) == "2-24H"
    assert trading_window(1440) == "2-24H"
    assert trading_window(1441) == "1-7D"
    assert trading_window(10080) == "1-7D"
    assert trading_window(10081) == "EXPIRED"
    assert trading_window(None) == "UNKNOWN"


def test_minutes_since_uses_timezone_safely():
    now = datetime(2026, 9, 7, 8, 5, tzinfo=timezone.utc)
    assert minutes_since("2026-09-07T08:00:00Z", now=now) == 5
    assert minutes_since(None, now=now) is None


def test_explainability_bases():
    assert surprise_basis({"event_surprise": "UNEXPECTED"}, "UNEXPECTED") == "EXPLICIT_EVENT_FIELD"
    assert surprise_basis({"title": "Results beat expectations"}, "UNEXPECTED") == "EXPECTATION_LANGUAGE"
    assert surprise_basis({"title": "FDA approval"}, "UNKNOWN") == "NO_EXPECTATION_DATA"
    assert awareness_basis(5.0, 2.0) == "PRICE_VOLUME_PROXY"
    assert awareness_basis(None, None) == "NO_MARKET_DATA"


if __name__ == "__main__":
    test_event_timestamp_fallbacks()
    test_window_boundaries()
    test_minutes_since_uses_timezone_safely()
    test_explainability_bases()
    print("Phase 4.1 helper tests passed")
