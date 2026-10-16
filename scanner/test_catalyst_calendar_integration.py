from datetime import date

from scanner.catalyst_calendar import build_upcoming_calendar, format_calendar


def test_announced_readout_joins_trial_milestones_and_is_source_backed():
    watchlist = {
        "ABC": {"company": "ABC Bio", "programs": ["Drug A", "Drug B"]},
    }
    trials = {
        "ABC:Drug B:NCT123": {
            "nct_id": "NCT123",
            "title": "Drug B pivotal trial",
            "status": "RECRUITING",
            "primary_completion_date": "2026-10-20",
            "phases": ["PHASE3"],
            "interventions": ["Drug B"],
        }
    }
    events = [{
        "event_id": "ABC-2026-READOUT",
        "ticker": "ABC",
        "program": "Drug A",
        "phase": "PHASE2",
        "event_name": "Interim efficacy data",
        "event_type": "CLINICAL_READOUT",
        "date": "2026-10-22",
        "source": "Company IR",
        "source_url": "https://example.com/ir",
    }]
    rows = build_upcoming_calendar(
        days=30, watchlist=watchlist, trials=trials,
        announced_events=events, today=date(2026, 10, 15),
    )
    assert len(rows) == 2
    milestone = next(row for row in rows if row["nct_id"] == "NCT123")
    assert milestone["program"] == "Drug B"
    assert milestone["clinical_outcome_available"] is False
    readout = next(row for row in rows if row.get("event_type") == "CLINICAL_READOUT")
    assert readout["program"] == "Drug A"
    assert readout["source"] == "https://example.com/ir"
    assert "Clinical readout/data" in format_calendar([readout])


def test_review_event_is_not_described_as_clinical_results():
    rows = build_upcoming_calendar(
        days=30,
        watchlist={"ABC": {"company": "ABC Bio", "programs": ["Drug A"]}},
        trials={},
        announced_events=[{
            "event_id": "ABC-REVIEW-1",
            "ticker": "ABC",
            "program": "Drug A",
            "event_name": "Blinded DSMB review",
            "event_type": "CLINICAL_REVIEW",
            "date": "2026-10-22",
            "source": "Company IR",
        }],
        today=date(2026, 10, 15),
    )
    assert len(rows) == 1
    assert rows[0]["clinical_outcome_available"] is False
    assert "no unblinded efficacy outcome inferred" in format_calendar(rows)
