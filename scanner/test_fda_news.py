from scanner.fda_news import (
    classify_fda_text,
    get_fda_priority,
    build_fda_news_item,
    filter_fda_catalysts,
    get_fda_sources,
)


def test_approval():

    categories = classify_fda_text(
        "FDA approves new drug for cancer",
        "The FDA announced approval today."
    )

    assert "APPROVAL" in categories

    assert (
        get_fda_priority(categories)
        == "EXTREME"
    )


def test_rejection():

    categories = classify_fda_text(
        "FDA issues complete response letter",
        "The application was rejected."
    )

    assert "REJECTION" in categories

    assert (
        get_fda_priority(categories)
        == "EXTREME"
    )


def test_safety():

    categories = classify_fda_text(
        "FDA announces new safety warning",
        "The agency identified a safety concern."
    )

    assert "SAFETY" in categories

    assert (
        get_fda_priority(categories)
        == "EXTREME"
    )


def test_clinical():

    categories = classify_fda_text(
        "Phase 3 clinical trial results",
        "The study reached its primary endpoint."
    )

    assert "CLINICAL" in categories

    assert (
        get_fda_priority(categories)
        == "HIGH"
    )


def test_build_news_item():

    item = build_fda_news_item(
        title="FDA approves new treatment",
        summary="The FDA approved the treatment today.",
        url="https://www.fda.gov/",
        published_at="2026-08-29"
    )

    assert item["source"] == "FDA"
    assert item["title"] == "FDA approves new treatment"
    assert "APPROVAL" in item["categories"]
    assert item["priority"] == "EXTREME"


def test_filter_catalysts():

    news = [

        build_fda_news_item(
            "FDA approves new drug",
            "FDA approval announced."
        ),

        build_fda_news_item(
            "FDA publishes general information",
            "General regulatory information."
        ),

    ]

    catalysts = filter_fda_catalysts(
        news
    )

    assert len(catalysts) == 1

    assert (
        catalysts[0]["priority"]
        == "EXTREME"
    )


def test_sources():

    sources = get_fda_sources()

    assert "drug_approvals" in sources
    assert "press_announcements" in sources

    assert sources["drug_approvals"].startswith(
        "https://www.fda.gov/"
    )

    assert sources["press_announcements"].startswith(
        "https://www.fda.gov/"
    )


if __name__ == "__main__":

    test_approval()
    test_rejection()
    test_safety()
    test_clinical()
    test_build_news_item()
    test_filter_catalysts()
    test_sources()

    print(
        "✅ FDA News tests passed"
  )
