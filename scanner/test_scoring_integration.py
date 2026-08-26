from scanner.score import score_events


def test_scored_status_catalyst():

    events = [
        {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "CATALYST",
            "subtype": "TRIAL_COMPLETED",
            "field": "status",
            "old_value": "ACTIVE_NOT_RECRUITING",
            "new_value": "COMPLETED",
        }
    ]

    scored = score_events(events)

    assert len(scored) == 1

    event = scored[0]

    assert event["score"] == 100
    assert event["label"] == "CRITICAL"


def test_scored_positive_date():

    events = [
        {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "POSITIVE",
            "subtype": "DATE_ACCELERATED",
            "field": "completion_date",
            "old_value": "2027-06-30",
            "new_value": "2027-03-31",
        }
    ]

    scored = score_events(events)

    event = scored[0]

    assert event["score"] == 100
    assert event["label"] == "CRITICAL"


def test_scored_negative_date():

    events = [
        {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "NEGATIVE",
            "subtype": "DATE_DELAYED",
            "field": "completion_date",
            "old_value": "2027-06-30",
            "new_value": "2027-12-31",
        }
    ]

    scored = score_events(events)

    event = scored[0]

    assert event["score"] == 100
    assert event["label"] == "CRITICAL"


def test_scored_medium_event():

    events = [
        {
            "type": "ENROLLMENT_CHANGE",
            "severity": "MEDIUM",
            "direction": "UNKNOWN",
            "subtype": "ENROLLMENT_UPDATED",
            "field": "enrollment",
            "old_value": 100,
            "new_value": 150,
        }
    ]

    scored = score_events(events)

    event = scored[0]

    assert event["score"] == 45
    assert event["label"] == "MEDIUM"


def test_scored_low_event():

    events = [
        {
            "type": "FIELD_CHANGE",
            "severity": "LOW",
            "direction": "UNKNOWN",
            "subtype": "FIELD_UPDATED",
            "field": "conditions",
            "old_value": [],
            "new_value": [],
        }
    ]

    scored = score_events(events)

    event = scored[0]

    assert event["score"] == 15
    assert event["label"] == "LOW"


def test_scored_multiple_events():

    events = [
        {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "CATALYST",
            "subtype": "TRIAL_COMPLETED",
        },
        {
            "type": "ENROLLMENT_CHANGE",
            "severity": "MEDIUM",
            "direction": "UNKNOWN",
            "subtype": "ENROLLMENT_UPDATED",
        },
        {
            "type": "FIELD_CHANGE",
            "severity": "LOW",
            "direction": "UNKNOWN",
            "subtype": "FIELD_UPDATED",
        },
    ]

    scored = score_events(events)

    assert len(scored) == 3

    assert scored[0]["score"] == 100
    assert scored[0]["label"] == "CRITICAL"

    assert scored[1]["score"] == 45
    assert scored[1]["label"] == "MEDIUM"

    assert scored[2]["score"] == 15
    assert scored[2]["label"] == "LOW"


if __name__ == "__main__":

    test_scored_status_catalyst()
    test_scored_positive_date()
    test_scored_negative_date()
    test_scored_medium_event()
    test_scored_low_event()
    test_scored_multiple_events()

    print(
        "✅ Scoring integration tests passed"
  )
