from scanner.fda_news import build_fda_news_item
from scanner.fda_catalyst import build_fda_catalyst
from scanner.fda_score import score_fda_event
from scanner.trading_intelligence import enrich_trading_event


def test_fda_approval_pipeline():

    news = build_fda_news_item(
        title="FDA approves new cancer drug",
        summary="The FDA announced approval today.",
        url="https://www.fda.gov/",
        published_at="2026-08-29",
    )

    assert news["source"] == "FDA"
    assert "APPROVAL" in news["categories"]
    assert news["priority"] == "EXTREME"

    catalyst = build_fda_catalyst(
        news
    )

    assert catalyst["type"] == "FDA_EVENT"
    assert catalyst["subtype"] == "FDA_APPROVAL"
    assert catalyst["direction"] == "CATALYST"

    scored = score_fda_event(
        catalyst
    )

    assert scored["score"] <= 100
    assert scored["fda_score_bonus"] == 25

    trading = enrich_trading_event(
        scored
    )

    assert trading["trading_impact"] == "EXTREME"
    assert trading["trading_priority"] == 4
    assert trading["urgency"] == "IMMEDIATE"


def test_fda_rejection_pipeline():

    news = build_fda_news_item(
        title="FDA issues complete response letter",
        summary="The application was rejected.",
        published_at="2026-08-29",
    )

    catalyst = build_fda_catalyst(
        news
    )

    assert catalyst["subtype"] == "FDA_REJECTION"
    assert catalyst["direction"] == "NEGATIVE"

    scored = score_fda_event(
        catalyst
    )

    assert scored["fda_score_bonus"] == 25

    trading = enrich_trading_event(
        scored
    )

    assert trading["trading_impact"] == "EXTREME"
    assert trading["urgency"] == "IMMEDIATE"


def test_fda_safety_pipeline():

    news = build_fda_news_item(
        title="FDA announces new safety warning",
        summary="The agency identified a safety concern.",
        published_at="2026-08-29",
    )

    catalyst = build_fda_catalyst(
        news
    )

    assert catalyst["subtype"] == "FDA_SAFETY_WARNING"
    assert catalyst["direction"] == "NEGATIVE"

    scored = score_fda_event(
        catalyst
    )

    trading = enrich_trading_event(
        scored
    )

    assert trading["trading_impact"] == "EXTREME"
    assert trading["urgency"] == "IMMEDIATE"


def test_fda_clinical_pipeline():

    news = build_fda_news_item(
        title="Phase 3 clinical trial results",
        summary="The study reached its primary endpoint.",
        published_at="2026-08-29",
    )

    catalyst = build_fda_catalyst(
        news
    )

    assert catalyst["subtype"] == "CLINICAL_RESULTS"

    scored = score_fda_event(
        catalyst
    )

    trading = enrich_trading_event(
        scored
    )

    assert trading["trading_impact"] == "EXTREME"
    assert trading["urgency"] == "IMMEDIATE"


def test_fda_label_pipeline():

    news = build_fda_news_item(
        title="FDA expands indication",
        summary="The label was updated.",
        published_at="2026-08-29",
    )

    catalyst = build_fda_catalyst(
        news
    )

    assert catalyst["subtype"] == "LABEL_EXPANSION"

    scored = score_fda_event(
        catalyst
    )

    trading = enrich_trading_event(
        scored
    )

    assert trading["trading_impact"] == "EXTREME"
    assert trading["urgency"] == "IMMEDIATE"


if __name__ == "__main__":

    test_fda_approval_pipeline()
    test_fda_rejection_pipeline()
    test_fda_safety_pipeline()
    test_fda_clinical_pipeline()
    test_fda_label_pipeline()

    print(
        "✅ FDA → Catalyst → Score → Trading Intelligence pipeline passed"
    )
