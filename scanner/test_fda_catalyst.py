from scanner.fda_catalyst import (
    build_fda_catalyst,
    build_fda_catalysts,
    build_relevant_fda_catalysts,
)


def test_fda_approval():
    news = {
        "source": "FDA", "title": "FDA approves new cancer drug",
        "summary": "The FDA announced approval today.", "url": "https://www.fda.gov/",
        "published_at": "2026-08-29", "categories": ["APPROVAL"], "priority": "EXTREME",
    }
    event = build_fda_catalyst(news)
    assert event["type"] == "FDA_EVENT"
    assert event["subtype"] == "FDA_APPROVAL"
    assert event["severity"] == "HIGH"
    # APPROVAL is a trading catalyst in the legacy scoring contract.
    assert event["direction"] == "CATALYST"
    assert event["catalyst_type"] == "APPROVAL"
    assert event["source"] == "FDA"
    assert event["title"] == news["title"]


def test_fda_rejection():
    news = {"source": "FDA", "title": "FDA issues complete response letter", "summary": "The application was rejected.", "categories": ["REJECTION"], "priority": "EXTREME"}
    event = build_fda_catalyst(news)
    assert event["type"] == "FDA_EVENT"
    assert event["subtype"] == "FDA_REJECTION"
    assert event["severity"] == "HIGH"
    assert event["direction"] == "NEGATIVE"


def test_fda_safety():
    news = {"source": "FDA", "title": "FDA announces safety warning", "summary": "The agency identified a safety concern.", "categories": ["SAFETY"], "priority": "EXTREME"}
    event = build_fda_catalyst(news)
    assert event["type"] == "FDA_EVENT"
    assert event["subtype"] == "FDA_SAFETY_WARNING"
    assert event["severity"] == "HIGH"
    assert event["direction"] == "NEGATIVE"


def test_fda_clinical():
    news = {"source": "FDA", "title": "Phase 3 clinical trial results", "summary": "The study reached its primary endpoint.", "categories": ["CLINICAL"], "priority": "HIGH"}
    event = build_fda_catalyst(news)
    assert event["type"] == "FDA_EVENT"
    assert event["subtype"] == "CLINICAL_RESULTS"
    assert event["severity"] == "HIGH"
    assert event["direction"] == "POSITIVE"


def test_fda_label():
    news = {"source": "FDA", "title": "FDA expands indication", "summary": "The label was updated.", "categories": ["LABEL"], "priority": "HIGH"}
    event = build_fda_catalyst(news)
    assert event["type"] == "FDA_EVENT"
    assert event["subtype"] == "LABEL_EXPANSION"
    assert event["severity"] == "HIGH"
    assert event["direction"] == "CATALYST"


def test_unknown_category():
    news = {"source": "FDA", "title": "FDA publishes information", "summary": "General regulatory information.", "categories": [], "priority": "LOW"}
    event = build_fda_catalyst(news)
    assert event["type"] == "FDA_EVENT"
    assert event["subtype"] == "FDA_UPDATE"
    assert event["severity"] == "LOW"
    assert event["direction"] == "UNKNOWN"


def test_multiple_catalysts():
    news = [
        {"source": "FDA", "title": "FDA approves drug", "categories": ["APPROVAL"], "priority": "EXTREME"},
        {"source": "FDA", "title": "FDA rejection", "categories": ["REJECTION"], "priority": "EXTREME"},
    ]
    events = build_fda_catalysts(news)
    assert len(events) == 2
    assert events[0]["direction"] == "CATALYST"
    assert events[1]["direction"] == "NEGATIVE"


def test_relevant_catalysts():
    news = [
        {"source": "FDA", "title": "FDA approves drug", "categories": ["APPROVAL"], "priority": "EXTREME"},
        {"source": "FDA", "title": "FDA publishes information", "categories": [], "priority": "LOW"},
    ]
    events = build_relevant_fda_catalysts(news)
    assert len(events) == 1
    assert events[0]["subtype"] == "FDA_APPROVAL"


if __name__ == "__main__":
    test_fda_approval()
    test_fda_rejection()
    test_fda_safety()
    test_fda_clinical()
    test_fda_label()
    test_unknown_category()
    test_multiple_catalysts()
    test_relevant_catalysts()
    print("FDA CATALYST TESTS PASSED")
