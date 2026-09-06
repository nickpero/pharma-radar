from scanner.priority import (
    get_alert_priority,
    enrich_alert_priority,
    sort_by_alert_priority,
)


def test_extreme_immediate_high_confidence_beats_low():
    critical = {
        "score": 100,
        "trading_impact": "EXTREME",
        "urgency": "IMMEDIATE",
        "match_confidence": "HIGH",
    }
    low = {
        "score": 60,
        "trading_impact": "LOW",
        "urgency": "LOW",
        "match_confidence": "LOW",
    }
    assert get_alert_priority(critical) > get_alert_priority(low)
    assert get_alert_priority(critical) == 100


def test_enrichment_preserves_event():
    event = {
        "score": 90,
        "trading_impact": "HIGH",
        "urgency": "FAST",
        "match_confidence": "HIGH",
    }
    result = enrich_alert_priority(event)
    assert result["score"] == 90
    assert result["alert_priority"] > 0
    assert "alert_priority" not in event


def test_sort_uses_priority_then_score():
    events = [
        {"alert_priority": 70, "score": 100},
        {"alert_priority": 80, "score": 60},
        {"alert_priority": 80, "score": 90},
    ]
    ordered = sort_by_alert_priority(events)
    assert [e["score"] for e in ordered] == [90, 60, 100]


if __name__ == "__main__":
    test_extreme_immediate_high_confidence_beats_low()
    test_enrichment_preserves_event()
    test_sort_uses_priority_then_score()
    print("✅ Alert priority tests passed")
