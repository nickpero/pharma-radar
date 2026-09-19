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
