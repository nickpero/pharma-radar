from datetime import date
from scanner.catalyst_calendar import build_upcoming_calendar, format_calendar


def test_calendar_uses_watchlist_and_precision():
    watchlist = {"ABC": {"company": "ABC Pharma", "programs": ["Drug A"]}}
    trials = {
        "ABC:Drug A:NCT1": {
            "nct_id": "NCT1",
            "title": "Study A",
            "status": "RECRUITING",
            "completion_date": "2026-10",
            "phases": ["PHASE3"],
        },
        "XYZ:Drug B:NCT2": {
            "nct_id": "NCT2",
            "status": "RECRUITING",
            "completion_date": "2026-10-15",
            "phases": ["PHASE2"],
        },
    }
    rows = build_upcoming_calendar(
        days=90,
        watchlist=watchlist,
        trials=trials,
        today=date(2026, 9, 29),
    )
    assert len(rows) == 1
    assert rows[0]["ticker"] == "ABC"
    assert rows[0]["date_precision"] == "MONTH"


def test_completed_trials_are_excluded():
    rows = build_upcoming_calendar(
        days=90,
        watchlist={"ABC": {"company": "ABC", "programs": ["Drug"]}},
        trials={"ABC:Drug:NCT1": {
            "nct_id": "NCT1", "status": "COMPLETED",
            "completion_date": "2026-10-15", "phases": ["PHASE3"]
        }},
        today=date(2026, 9, 29),
    )
    assert rows == []


def test_format():
    message = format_calendar([{
        "date": "2026-10",
        "date_precision": "MONTH",
        "ticker": "ABC",
        "milestone": "STUDY_COMPLETION",
        "programs": ["Drug A"],
        "phase": "PHASE3",
        "nct_id": "NCT1",
        "status": "RECRUITING",
    }], days=90)
    assert "CATALYST CALENDAR" in message
    assert "2026-10 (month)" in message


if __name__ == "__main__":
    test_calendar_uses_watchlist_and_precision()
    test_completed_trials_are_excluded()
    test_format()
    print("Catalyst calendar tests passed")


def test_completion_is_not_a_clinical_readout():
    rows = build_upcoming_calendar(
        days=30,
        watchlist={"ABC": {"company": "ABC", "programs": ["Drug A"]}},
        trials={"ABC:Drug A:NCT1": {
            "nct_id": "NCT1",
            "status": "RECRUITING",
            "primary_completion_date": "2026-10-10",
            "phases": ["PHASE3"],
        }},
        today=date(2026, 10, 6),
    )
    assert rows[0]["milestone"] == "PRIMARY_COMPLETION"
    assert rows[0]["milestone_type"] == "EXPECTED_TRIAL_COMPLETION"
    assert rows[0]["clinical_outcome_available"] is False
