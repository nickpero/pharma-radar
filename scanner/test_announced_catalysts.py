from datetime import date

import pytest

from scanner.announced_catalysts import (
    alerts_due,
    classify_announced_event,
    deduplicate_events,
    upcoming_announced_events,
)


def event(**overrides):
    value = {
        "event_id": "EVT-1",
        "ticker": "ABC",
        "company": "ABC Bio",
        "program": "Drug A",
        "phase": "PHASE3",
        "event_name": "Interim efficacy results",
        "event_type": "CLINICAL_READOUT",
        "date": "2026-10-22",
        "source": "Company IR",
        "source_url": "https://example.com/ir",
    }
    value.update(overrides)
    return value


def test_readout_keeps_clinical_outcome():
    item = classify_announced_event(event())
    assert item["event_type"] == "CLINICAL_READOUT"
    assert item["clinical_outcome_available"] is True


def test_trial_milestone_never_implies_outcome():
    item = classify_announced_event(event(event_type="TRIAL_MILESTONE", direction="POSITIVE"))
    assert item["clinical_outcome_available"] is False
    assert item["actionability"] == "WATCH"
    assert item["direction"] == "UNKNOWN"


def test_blinded_review_never_becomes_readout():
    item = classify_announced_event(event(event_type="CLINICAL_REVIEW", direction="NEGATIVE"))
    assert item["clinical_outcome_available"] is False
    assert item["actionability"] == "WATCH"
    assert item["direction"] == "UNKNOWN"


def test_missing_primary_source_rejected():
    with pytest.raises(ValueError, match="source"):
        classify_announced_event(event(source="", source_url=""))


def test_deduplicates_same_event_and_preserves_distinct_ids():
    rows = deduplicate_events([event(), event(), event(event_id="EVT-2")])
    assert len(rows) == 2


def test_upcoming_event_uses_watchlist_and_window():
    rows = upcoming_announced_events(
        [event(date=None, window_start="2026-10-20", window_end="2026-10-24")],
        days=14,
        today=date(2026, 10, 15),
        watchlist={"ABC": {"company": "ABC Bio"}},
    )
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-10-20"
    assert rows[0]["date_precision"] == "WINDOW"


def test_due_alert_lead_window_and_dedup_state():
    rows = alerts_due([event(date="2026-10-22")], today=date(2026, 10, 15), lead_days=(7,))
    assert len(rows) == 1
    assert rows[0]["days_until_event"] == 7
    already_sent = alerts_due(
        [event(date="2026-10-22")],
        today=date(2026, 10, 15),
        lead_days=(7,),
        sent_fingerprints=[rows[0]["alert_fingerprint"]],
    )
    assert already_sent == []


def test_invalid_event_type_rejected():
    with pytest.raises(ValueError, match="Unsupported event_type"):
        classify_announced_event(event(event_type="GOOD_NEWS"))



def test_material_date_change_changes_dedup_identity():
    original = deduplicate_events([event(date="2026-10-22")])[0]
    revised = deduplicate_events([event(date="2026-10-29")])[0]
    assert original["event_fingerprint"] != revised["event_fingerprint"]
