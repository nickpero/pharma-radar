from datetime import datetime, timezone, timedelta

from scanner.trading_setup import (
    minutes_since,
    trading_window,
    reaction_score,
    volume_score,
    market_awareness,
    build_trading_setup,
)


def test_fresh_event_is_in_immediate_window():
    now = datetime.now(timezone.utc)
    published = (now - timedelta(minutes=5)).isoformat()
    assert minutes_since(published, now=now) == 5
    assert trading_window(5) == "0-2H"


def test_seven_day_window_expires_after_limit():
    assert trading_window(10080) == "1-7D"
    assert trading_window(10081) == "EXPIRED"


def test_reaction_and_volume_scores():
    assert reaction_score(8, "POSITIVE") == 10
    assert reaction_score(-8, "POSITIVE") < 10
    assert volume_score(5) == 10


def test_market_awareness():
    assert market_awareness(1.0, 1.1) == "LOW"
    assert market_awareness(6.0, 2.0) == "MEDIUM"
    assert market_awareness(12.0, 1.0) == "HIGH"


def test_build_setup_is_bounded_and_preserves_unknowns():
    event = {
        "score": 100,
        "trading_impact": "EXTREME",
        "urgency": "IMMEDIATE",
        "match_confidence": "HIGH",
        "direction": "POSITIVE",
        "published_at": "2026-09-07T08:00:00+00:00",
        "event_surprise": "UNKNOWN",
    }
    result = build_trading_setup(
        event,
        market_data={"price_change_pct": 3.0, "volume_ratio": 3.0},
        now=datetime(2026, 9, 7, 8, 5, tzinfo=timezone.utc),
    )
    assert 0 <= result["trading_setup_score"] <= 100
    assert result["trading_window"] == "0-2H"
    assert result["event_surprise"] == "UNKNOWN"
    assert result["market_awareness"] == "MEDIUM"


if __name__ == "__main__":
    test_fresh_event_is_in_immediate_window()
    test_seven_day_window_expires_after_limit()
    test_reaction_and_volume_scores()
    test_market_awareness()
    test_build_setup_is_bounded_and_preserves_unknowns()
    print("✅ Trading Setup tests passed")
