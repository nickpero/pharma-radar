from scanner.fda_score import (
    enrich_fda_event,
    score_fda_event,
    score_fda_events,
)


def test_approval_enrichment():

    event = {
        "type": "FDA_EVENT",
        "subtype": "FDA_APPROVAL",
        "severity": "HIGH",
        "direction": "CATALYST",
    }

    enriched = enrich_fda_event(event)

    assert enriched["fda_score_bonus"] == 25

    # Original event must not be modified

    assert "fda_score_bonus" not in event


def test_rejection_enrichment():

    event = {
        "type": "FDA_EVENT",
        "subtype": "FDA_REJECTION",
        "severity": "HIGH",
        "direction": "NEGATIVE",
    }

    enriched = enrich_fda_event(event)

    assert enriched["fda_score_bonus"] == 25


def test_safety_enrichment():

    event = {
        "type": "FDA_EVENT",
        "subtype": "FDA_SAFETY_WARNING",
        "severity": "HIGH",
        "direction": "NEGATIVE",
    }

    enriched = enrich_fda_event(event)

    assert enriched["fda_score_bonus"] == 25


def test_clinical_enrichment():

    event = {
        "type": "FDA_EVENT",
        "subtype": "CLINICAL_RESULTS",
        "severity": "HIGH",
        "direction": "POSITIVE",
    }

    enriched = enrich_fda_event(event)

    assert enriched["fda_score_bonus"] == 20


def test_label_enrichment():

    event = {
        "type": "FDA_EVENT",
        "subtype": "LABEL_EXPANSION",
        "severity": "HIGH",
        "direction": "CATALYST",
    }

    enriched = enrich_fda_event(event)

    assert enriched["fda_score_bonus"] == 15


def test_unknown_fda_event():

    event = {
        "type": "FDA_EVENT",
        "subtype": "FDA_UPDATE",
        "severity": "LOW",
        "direction": "UNKNOWN",
    }

    enriched = enrich_fda_event(event)

    assert enriched["fda_score_bonus"] == 0


def test_approval_score():

    event = {
        "type": "FDA_EVENT",
        "subtype": "FDA_APPROVAL",
        "severity": "HIGH",
        "direction": "CATALYST",
    }

    scored = score_fda_event(event)

    assert scored["score"] <= 100

    assert scored["fda_score_bonus"] == 25


def test_rejection_score():

    event = {
        "type": "FDA_EVENT",
        "subtype": "FDA_REJECTION",
        "severity": "HIGH",
        "direction": "NEGATIVE",
    }

    scored = score_fda_event(event)

    assert scored["score"] <= 100

    assert scored["fda_score_bonus"] == 25


def test_multiple_fda_events():

    events = [

        {
            "type": "FDA_EVENT",
            "subtype": "FDA_APPROVAL",
            "severity": "HIGH",
            "direction": "CATALYST",
        },

        {
            "type": "FDA_EVENT",
            "subtype": "FDA_REJECTION",
            "severity": "HIGH",
            "direction": "NEGATIVE",
        },

        {
            "type": "FDA_EVENT",
            "subtype": "CLINICAL_RESULTS",
            "severity": "HIGH",
            "direction": "POSITIVE",
        },
    ]

    scored = score_fda_events(
        events
    )

    assert len(scored) == 3

    assert scored[0]["subtype"] == "FDA_APPROVAL"
    assert scored[1]["subtype"] == "FDA_REJECTION"
    assert scored[2]["subtype"] == "CLINICAL_RESULTS"

    for event in scored:
        assert event["score"] <= 100


def test_empty_events():

    assert score_fda_events([]) == []


if __name__ == "__main__":

    test_approval_enrichment()
    test_rejection_enrichment()
    test_safety_enrichment()
    test_clinical_enrichment()
    test_label_enrichment()
    test_unknown_fda_event()

    test_approval_score()
    test_rejection_score()

    test_multiple_fda_events()
    test_empty_events()

    print(
        "✅ FDA Score tests passed"
    )
