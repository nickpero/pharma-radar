from scanner.catalyst_score import (
    calculate_catalyst_score,
    score_catalyst_event,
    score_catalyst_events,
    event_direction,
    score_label,
)


def test_primary_endpoint():

    result = calculate_catalyst_score(
        "PRIMARY_ENDPOINT_MET"
    )

    assert result["score"] == 100
    assert result["label"] == "CRITICAL"
    assert result["direction"] == "POSITIVE"


def test_primary_endpoint_failed():

    result = calculate_catalyst_score(
        "PRIMARY_ENDPOINT_FAILED"
    )

    assert result["score"] == 100
    assert result["label"] == "CRITICAL"
    assert result["direction"] == "NEGATIVE"


def test_trial_completed():

    result = calculate_catalyst_score(
        "TRIAL_COMPLETED"
    )

    assert result["score"] == 90
    assert result["label"] == "VERY HIGH"
    assert result["direction"] == "POSITIVE"


def test_phase_three_bonus():

    result = calculate_catalyst_score(
        "TRIAL_COMPLETED",
        phase="PHASE3"
    )

    assert result["score"] == 100
    assert result["label"] == "CRITICAL"


def test_phase_two_bonus():

    result = calculate_catalyst_score(
        "PHASE_2_STARTED",
        phase="PHASE2"
    )

    assert result["score"] == 75
    assert result["label"] == "HIGH"


def test_negative_event_bonus():

    result = calculate_catalyst_score(
        "DATE_DELAYED"
    )

    assert result["direction"] == "NEGATIVE"
    assert result["score"] == 85
    assert result["label"] == "VERY HIGH"


def test_event_direction():

    assert (
        event_direction(
            "PRIMARY_ENDPOINT_MET"
        )
        == "POSITIVE"
    )

    assert (
        event_direction(
            "PRIMARY_ENDPOINT_FAILED"
        )
        == "NEGATIVE"
    )

    assert (
        event_direction(
            "OTHER"
        )
        == "UNKNOWN"
    )


def test_labels():

    assert score_label(100) == "CRITICAL"
    assert score_label(95) == "CRITICAL"
    assert score_label(90) == "VERY HIGH"
    assert score_label(85) == "VERY HIGH"
    assert score_label(80) == "HIGH"
    assert score_label(70) == "HIGH"
    assert score_label(60) == "MEDIUM"
    assert score_label(59) == "LOW"


def test_score_event_object():

    event = {
        "type": "TRIAL_COMPLETED",
        "phase": "PHASE3",
        "direction": "POSITIVE",
        "nct_id": "NCT12345678",
    }

    scored = score_catalyst_event(
        event
    )

    assert scored["score"] == 100
    assert scored["label"] == "CRITICAL"
    assert scored["direction"] == "POSITIVE"
    assert scored["nct_id"] == "NCT12345678"


def test_multiple_events():

    events = [
        {
            "type": "PRIMARY_ENDPOINT_MET",
        },
        {
            "type": "TRIAL_COMPLETED",
        },
        {
            "type": "PHASE_1_STARTED",
        },
    ]

    scored = score_catalyst_events(
        events
    )

    assert len(scored) == 3

    assert scored[0]["score"] == 100
    assert scored[1]["score"] == 90
    assert scored[2]["score"] == 60


if __name__ == "__main__":

    test_primary_endpoint()
    test_primary_endpoint_failed()
    test_trial_completed()
    test_phase_three_bonus()
    test_phase_two_bonus()
    test_negative_event_bonus()
    test_event_direction()
    test_labels()
    test_score_event_object()
    test_multiple_events()

    print(
        "✅ Catalyst Score Engine tests passed"
  )
