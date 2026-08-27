from scanner.catalyst import (
    classify_status_change,
    classify_date_change,
    classify_enrollment_change,
    classify_trial_changes,
    enrich_events,
)


def test_completed_status():

    event = classify_status_change(
        "RECRUITING",
        "COMPLETED",
    )

    assert event["type"] == "STATUS_CHANGE"
    assert event["subtype"] == "TRIAL_COMPLETED"
    assert event["direction"] == "POSITIVE"


def test_terminated_status():

    event = classify_status_change(
        "RECRUITING",
        "TERMINATED",
    )

    assert event["subtype"] == "TRIAL_TERMINATED"
    assert event["direction"] == "NEGATIVE"


def test_suspended_status():

    event = classify_status_change(
        "RECRUITING",
        "SUSPENDED",
    )

    assert event["subtype"] == "TRIAL_SUSPENDED"
    assert event["direction"] == "NEGATIVE"


def test_recruiting_status():

    event = classify_status_change(
        "NOT_YET_RECRUITING",
        "RECRUITING",
    )

    assert event["subtype"] == "TRIAL_RECRUITING"
    assert event["direction"] == "POSITIVE"


def test_date_accelerated():

    event = classify_date_change(
        "2027-12-01",
        "2027-06-01",
    )

    assert event["type"] == "DATE_CHANGE"
    assert event["subtype"] == "DATE_ACCELERATED"
    assert event["direction"] == "POSITIVE"


def test_date_delayed():

    event = classify_date_change(
        "2027-06-01",
        "2028-01-01",
    )

    assert event["subtype"] == "DATE_DELAYED"
    assert event["direction"] == "NEGATIVE"


def test_same_date():

    event = classify_date_change(
        "2027-06-01",
        "2027-06-01",
    )

    assert event is None


def test_enrollment_increased():

    event = classify_enrollment_change(
        100,
        150,
    )

    assert event is not None
    assert event["type"] == "ENROLLMENT_CHANGE"
    assert event["subtype"] == "ENROLLMENT_INCREASED"


def test_enrollment_decreased():

    event = classify_enrollment_change(
        150,
        100,
    )

    assert event is None


def test_classify_trial_changes():

    changes = {
        "status": {
            "old": "RECRUITING",
            "new": "COMPLETED",
        },
        "primary_completion_date": {
            "old": "2027-12-01",
            "new": "2027-06-01",
        },
        "enrollment": {
            "old": 100,
            "new": 150,
        },
    }

    events = classify_trial_changes(
        changes
    )

    assert len(events) == 3

    assert events[0]["subtype"] == (
        "TRIAL_COMPLETED"
    )

    assert events[1]["subtype"] == (
        "DATE_ACCELERATED"
    )

    assert events[2]["subtype"] == (
        "ENROLLMENT_INCREASED"
    )


def test_enrich_events():

    events = [
        {
            "type": "STATUS_CHANGE",
            "subtype": "TRIAL_COMPLETED",
        }
    ]

    trial = {
        "phase": "PHASE3",
        "primary_completion_date": "2027-06-01",
    }

    enriched = enrich_events(
        events,
        trial,
    )

    assert enriched[0]["phase"] == "PHASE3"
    assert enriched[0]["event_date"] == (
        "2027-06-01"
    )


if __name__ == "__main__":

    test_completed_status()
    test_terminated_status()
    test_suspended_status()
    test_recruiting_status()
    test_date_accelerated()
    test_date_delayed()
    test_same_date()
    test_enrollment_increased()
    test_enrollment_decreased()
    test_classify_trial_changes()
    test_enrich_events()

    print(
        "✅ Catalyst classification tests passed"
    )
