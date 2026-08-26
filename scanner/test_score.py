from scanner.score import (
    score_event,
    score_label,
    enrich_event,
    score_events,
)


def test_critical_catalyst():

    event = {
        "type": "STATUS_CHANGE",
        "severity": "HIGH",
        "direction": "CATALYST",
        "subtype": "TRIAL_COMPLETED",
    }

    score = score_event(event)

    assert score == 100
    assert score_label(score) == "CRITICAL"


def test_positive_date_acceleration():

    event = {
        "type": "DATE_CHANGE",
        "severity": "HIGH",
        "direction": "POSITIVE",
        "subtype": "DATE_ACCELERATED",
    }

    score = score_event(event)

    assert score == 100
    assert score_label(score) == "CRITICAL"


def test_negative_date_delay():

    event = {
        "type": "DATE_CHANGE",
        "severity": "HIGH",
        "direction": "NEGATIVE",
        "subtype": "DATE_DELAYED",
    }

    score = score_event(event)

    assert score == 100
    assert score_label(score) == "CRITICAL"


def test_medium_enrollment():

    event = {
        "type": "ENROLLMENT_CHANGE",
        "severity": "MEDIUM",
        "direction": "UNKNOWN",
        "subtype": "ENROLLMENT_UPDATED",
    }

    score = score_event(event)

    assert score == 45
    assert score_label(score) == "MEDIUM"


def test_low_generic_event():

    event = {
        "type": "FIELD_CHANGE",
        "severity": "LOW",
        "direction": "UNKNOWN",
        "subtype": "FIELD_UPDATED",
    }

    score = score_event(event)

    assert score == 15
    assert score_label(score) == "LOW"


def test_enrich_event():

    event = {
        "type": "PHASE_CHANGE",
        "severity": "HIGH",
        "direction": "POSITIVE",
        "subtype": "PHASE_UPDATED",
    }

    enriched = enrich_event(event)

    assert "score" in enriched
    assert "label" in enriched

    assert enriched["score"] == 100
    assert enriched["label"] == "CRITICAL"


def test_score_multiple_events():

    events = [
        {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "NEGATIVE",
            "subtype": "TRIAL_STOPPED",
        },
        {
            "type": "FIELD_CHANGE",
            "severity": "LOW",
            "direction": "UNKNOWN",
            "subtype": "FIELD_UPDATED",
        },
    ]

    scored = score_events(events)

    assert len(scored) == 2

    assert scored[0]["score"] == 95
    assert scored[0]["label"] == "CRITICAL"

    assert scored[1]["score"] == 15
    assert scored[1]["label"] == "LOW"


if __name__ == "__main__":

    test_critical_catalyst()
    test_positive_date_acceleration()
    test_negative_date_delay()
    test_medium_enrollment()
    test_low_generic_event()
    test_enrich_event()
    test_score_multiple_events()

    print(
        "✅ Catalyst Score tests passed"
  )
