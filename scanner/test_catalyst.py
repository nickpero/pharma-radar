from scanner.catalyst import (
    classify_change,
    classify_status_change,
    classify_trial_changes,
)


def test_status_change():

    event = classify_status_change(
        "RECRUITING",
        "COMPLETED"
    )

    assert event["type"] == "STATUS_CHANGE"
    assert event["severity"] == "HIGH"
    assert event["direction"] == "CATALYST"


def test_negative_status_change():

    event = classify_status_change(
        "RECRUITING",
        "TERMINATED"
    )

    assert event["type"] == "STATUS_CHANGE"
    assert event["severity"] == "HIGH"
    assert event["direction"] == "NEGATIVE"


def test_positive_status_change():

    event = classify_status_change(
        "NOT_YET_RECRUITING",
        "RECRUITING"
    )

    assert event["type"] == "STATUS_CHANGE"
    assert event["severity"] == "MEDIUM"
    assert event["direction"] == "POSITIVE"


def test_date_change():

    event = classify_change(
        "completion_date",
        "2027-06-30",
        "2027-03-31"
    )

    assert event["type"] == "DATE_CHANGE"
    assert event["severity"] == "HIGH"


def test_enrollment_change():

    event = classify_change(
        "enrollment",
        100,
        150
    )

    assert event["type"] == "ENROLLMENT_CHANGE"
    assert event["severity"] == "MEDIUM"


def test_phase_change():

    event = classify_change(
        "phases",
        ["PHASE2"],
        ["PHASE3"]
    )

    assert event["type"] == "PHASE_CHANGE"
    assert event["severity"] == "HIGH"


def test_protocol_change():

    event = classify_change(
        "official_title",
        "Old title",
        "New title"
    )

    assert event["type"] == "PROTOCOL_CHANGE"
    assert event["severity"] == "HIGH"


def test_generic_change():

    event = classify_change(
        "conditions",
        ["Condition A"],
        ["Condition B"]
    )

    assert event["type"] == "FIELD_CHANGE"
    assert event["severity"] == "LOW"


def test_multiple_changes():

    changes = {
        "status": {
            "old": "RECRUITING",
            "new": "COMPLETED"
        },
        "completion_date": {
            "old": "2027-06-30",
            "new": "2027-03-31"
        }
    }

    events = classify_trial_changes(
        changes
    )

    assert len(events) == 2
    assert events[0]["type"] == "STATUS_CHANGE"
    assert events[1]["type"] == "DATE_CHANGE"


if __name__ == "__main__":
    test_status_change()
    test_negative_status_change()
    test_positive_status_change()
    test_date_change()
    test_enrollment_change()
    test_phase_change()
    test_protocol_change()
    test_generic_change()
    test_multiple_changes()

    print(
        "✅ Catalyst Engine tests passed"
  )
