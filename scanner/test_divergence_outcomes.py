from datetime import date

from scanner.divergence_outcomes import _outcomes_for_event


def test_forward_outcomes_and_recovery():
    event = {"event_date": "2026-09-10", "ticker": "IONS"}
    points = [
        {"date": date(2026, 9, 10), "close": 100.0},
        {"date": date(2026, 9, 11), "close": 98.0},
        {"date": date(2026, 9, 12), "close": 101.0},
        {"date": date(2026, 9, 15), "close": 103.0},
        {"date": date(2026, 9, 16), "close": 99.0},
        {"date": date(2026, 9, 17), "close": 104.0},
    ]
    result = _outcomes_for_event(event, points)
    assert result["outcomes"]["t1"]["return_pct"] == -2.0
    assert result["outcomes"]["t3"]["return_pct"] == 3.0
    assert result["outcomes"]["t5"]["return_pct"] == 4.0
    assert result["max_recovery"] is True
    assert result["recovered_by_t5"] is True


def test_event_before_first_available_session_anchors_to_next_session():
    event = {"event_date": "2026-09-10", "ticker": "IONS"}
    points = [
        {"date": date(2026, 9, 11), "close": 100.0},
        {"date": date(2026, 9, 12), "close": 101.0},
    ]
    result = _outcomes_for_event(event, points)
    assert result["entry_date"] == "2026-09-11"
    assert result["outcomes"]["t1"]["return_pct"] == 1.0


if __name__ == "__main__":
    test_forward_outcomes_and_recovery()
    test_event_before_first_available_session_anchors_to_next_session()
    print("OK — Divergence Outcomes tests passed")

def test_event_price_anchor_and_event_to_close():
    event = {
        "event_timestamp": "2026-09-10T15:00:00Z",
        "event_date": "2026-09-10",
        "event_price": 110.0,
        "event_price_timestamp": "2026-09-10T15:00:00Z",
        "ticker": "IONS",
    }
    points = [
        {"date": date(2026, 9, 10), "close": 100.0},
        {"date": date(2026, 9, 11), "close": 108.0},
        {"date": date(2026, 9, 12), "close": 112.0},
        {"date": date(2026, 9, 15), "close": 115.0},
        {"date": date(2026, 9, 16), "close": 105.0},
        {"date": date(2026, 9, 17), "close": 120.0},
    ]
    result = _outcomes_for_event(event, points)
    assert result["event_price"] == 110.0
    assert result["event_price_source"] == "EVENT_INTRADAY"
    assert round(result["event_to_close_pct"], 6) == round(-9.090909090909092, 6)
    assert round(result["outcomes"]["t1"]["return_pct"], 6) == round(-1.8181818181818181, 6)
    assert round(result["outcomes"]["t5"]["return_pct"], 6) == round(9.090909090909092, 6)

