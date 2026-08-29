from scanner.trading_intelligence import (
    get_trading_impact,
    trading_priority_score,
    get_urgency,
    enrich_trading_event,
    enrich_trading_events,
)


def test_extreme_catalyst():

    event = {
        "type": "STATUS_CHANGE",
        "severity": "HIGH",
        "direction": "CATALYST",
        "subtype": "TRIAL_COMPLETED",
        "score": 100,
    }

    assert get_trading_impact(
        event
    ) == "EXTREME"

    assert trading_priority_score(
        event
    ) == 4

    assert get_urgency(
        event
    ) == "IMMEDIATE"


def test_positive_date_acceleration():

    event = {
        "type": "DATE_CHANGE",
        "severity": "HIGH",
        "direction": "POSITIVE",
        "subtype": "DATE_ACCELERATED",
        "score": 100,
    }

    assert get_trading_impact(
        event
    ) == "HIGH"

    assert trading_priority_score(
        event
    ) == 3

    assert get_urgency(
        event
    ) == "FAST"


def test_negative_date_delay():

    event = {
        "type": "DATE_CHANGE",
        "severity": "HIGH",
        "direction": "NEGATIVE",
        "subtype": "DATE_DELAYED",
        "score": 100,
    }

    assert get_trading_impact(
        event
    ) == "HIGH"

    assert trading_priority_score(
        event
    ) == 3

    assert get_urgency(
        event
    ) == "FAST"


def test_phase_change():

    event = {
        "type": "PHASE_CHANGE",
        "severity": "HIGH",
        "direction": "POSITIVE",
        "subtype": "PHASE_ADVANCED",
        "score": 90,
    }

    assert get_trading_impact(
        event
    ) == "HIGH"

    assert get_urgency(
        event
    ) == "FAST"


def test_enrollment_change():

    event = {
        "type": "ENROLLMENT_CHANGE",
        "severity": "MEDIUM",
        "direction": "UNKNOWN",
        "subtype": "ENROLLMENT_UPDATED",
        "score": 45,
    }

    assert get_trading_impact(
        event
    ) == "MEDIUM"

    assert trading_priority_score(
        event
    ) == 2

    assert get_urgency(
        event
    ) == "NORMAL"


def test_low_generic_event():

    event = {
        "type": "FIELD_CHANGE",
        "severity": "LOW",
        "direction": "UNKNOWN",
        "subtype": "FIELD_UPDATED",
        "score": 15,
    }

    assert get_trading_impact(
        event
    ) == "LOW"

    assert trading_priority_score(
        event
    ) == 1

    assert get_urgency(
        event
    ) == "LOW"


def test_enrich_event():

    event = {
        "type": "STATUS_CHANGE",
        "severity": "HIGH",
        "direction": "CATALYST",
        "subtype": "TRIAL_COMPLETED",
        "score": 100,
    }

    enriched = enrich_trading_event(
        event
    )

    assert enriched["score"] == 100
    assert enriched["trading_impact"] == "EXTREME"
    assert enriched["trading_priority"] == 4
    assert enriched["urgency"] == "IMMEDIATE"

    # Original event must not be modified

    assert "trading_impact" not in event


def test_multiple_events():

    events = [

        {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "CATALYST",
            "subtype": "TRIAL_COMPLETED",
            "score": 100,
        },

        {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "POSITIVE",
            "subtype": "DATE_ACCELERATED",
            "score": 90,
        },

        {
            "type": "FIELD_CHANGE",
            "severity": "LOW",
            "direction": "UNKNOWN",
            "subtype": "FIELD_UPDATED",
            "score": 15,
        },
    ]

    enriched = enrich_trading_events(
        events
    )

    assert len(enriched) == 3

    assert enriched[0]["trading_impact"] == "EXTREME"
    assert enriched[0]["urgency"] == "IMMEDIATE"

    assert enriched[1]["trading_impact"] == "HIGH"
    assert enriched[1]["urgency"] == "FAST"

    assert enriched[2]["trading_impact"] == "LOW"
    assert enriched[2]["urgency"] == "LOW"


if __name__ == "__main__":

    test_extreme_catalyst()
    test_positive_date_acceleration()
    test_negative_date_delay()
    test_phase_change()
    test_enrollment_change()
    test_low_generic_event()
    test_enrich_event()
    test_multiple_events()

    print(
        "✅ Trading Intelligence tests passed"
  )
