from scanner.fda_news import build_fda_news_item
from scanner.fda_pipeline import (
    process_fda_news_item,
    process_fda_news,
    filter_fda_trading_alerts,
    sort_fda_events,
    get_top_fda_events,
)


# ============================================
# TEST WATCHLIST
# ============================================

WATCHLIST = {
    "CAPR": {
        "company": "Capricor Therapeutics",
        "programs": [
            "deramiocel",
        ],
    },

    "ARGX": {
        "company": "argenx",
        "programs": [
            "VYVGART",
        ],
    },
}


# ============================================
# APPROVAL PIPELINE
# ============================================

def test_approval_pipeline():

    news = build_fda_news_item(
        title=(
            "FDA approves deramiocel "
            "from Capricor Therapeutics"
        ),
        summary=(
            "The FDA announced approval "
            "of the treatment today."
        ),
        url="https://www.fda.gov/",
        published_at="2026-08-30",
    )

    result = process_fda_news_item(
        news,
        WATCHLIST,
    )

    assert result is not None

    assert result["source"] == "FDA"

    assert result["ticker"] == "CAPR"

    assert result["company"] == (
        "Capricor Therapeutics"
    )

    assert result["program"] == (
        "deramiocel"
    )

    assert result["subtype"] == (
        "FDA_APPROVAL"
    )

    assert result["direction"] == (
        "CATALYST"
    )

    assert result["trading_impact"] == (
        "EXTREME"
    )

    assert result["trading_priority"] == 4

    assert result["urgency"] == (
        "IMMEDIATE"
    )

    assert result["pipeline"] == (
        "FDA_NEWS"
    )

    assert result["pipeline_stage"] == (
        "TRADING_INTELLIGENCE"
    )


# ============================================
# REJECTION PIPELINE
# ============================================

def test_rejection_pipeline():

    news = build_fda_news_item(
        title=(
            "FDA rejects deramiocel "
            "from Capricor Therapeutics"
        ),
        summary=(
            "The FDA issued a complete "
            "response letter."
        ),
        published_at="2026-08-30",
    )

    result = process_fda_news_item(
        news,
        WATCHLIST,
    )

    assert result is not None

    assert result["ticker"] == "CAPR"

    assert result["program"] == (
        "deramiocel"
    )

    assert result["subtype"] == (
        "FDA_REJECTION"
    )

    assert result["direction"] == (
        "NEGATIVE"
    )

    assert result["trading_impact"] == (
        "EXTREME"
    )

    assert result["urgency"] == (
        "IMMEDIATE"
    )


# ============================================
# SAFETY PIPELINE
# ============================================

def test_safety_pipeline():

    news = build_fda_news_item(
        title=(
            "FDA announces safety warning "
            "for VYVGART"
        ),
        summary=(
            "The agency identified "
            "a significant safety concern "
            "for argenx."
        ),
        published_at="2026-08-30",
    )

    result = process_fda_news_item(
        news,
        WATCHLIST,
    )

    assert result is not None

    assert result["ticker"] == "ARGX"

    assert result["program"] == (
        "VYVGART"
    )

    assert result["subtype"] == (
        "FDA_SAFETY_WARNING"
    )

    assert result["direction"] == (
        "NEGATIVE"
    )

    assert result["trading_impact"] == (
        "EXTREME"
    )

    assert result["urgency"] == (
        "IMMEDIATE"
    )


# ============================================
# NON RELEVANT NEWS
# ============================================

def test_non_relevant_news():

    news = build_fda_news_item(
        title=(
            "FDA publishes general "
            "regulatory information"
        ),
        summary=(
            "The agency released "
            "general information."
        ),
        published_at="2026-08-30",
    )

    result = process_fda_news_item(
        news,
        WATCHLIST,
    )

    assert result is None


# ============================================
# UNMATCHED FDA NEWS
# ============================================

def test_unmatched_news():

    news = build_fda_news_item(
        title=(
            "FDA approves unrelated "
            "cancer treatment"
        ),
        summary=(
            "The treatment belongs "
            "to another company."
        ),
        published_at="2026-08-30",
    )

    result = process_fda_news_item(
        news,
        WATCHLIST,
    )

    assert result is None


# ============================================
# MULTIPLE NEWS
# ============================================

def test_multiple_news():

    news = [

        build_fda_news_item(
            title=(
                "FDA approves deramiocel "
                "from Capricor Therapeutics"
            ),
            summary=(
                "FDA approval announced."
            ),
            published_at="2026-08-30",
        ),

        build_fda_news_item(
            title=(
                "FDA publishes general "
                "information"
            ),
            summary=(
                "General regulatory update."
            ),
            published_at="2026-08-30",
        ),

        build_fda_news_item(
            title=(
                "FDA announces safety warning "
                "for VYVGART"
            ),
            summary=(
                "argenx treatment affected."
            ),
            published_at="2026-08-30",
        ),
    ]

    results = process_fda_news(
        news,
        WATCHLIST,
    )

    assert len(results) == 2

    tickers = {
        result["ticker"]
        for result in results
    }

    assert "CAPR" in tickers
    assert "ARGX" in tickers


# ============================================
# FILTER TRADING ALERTS
# ============================================

def test_filter_trading_alerts():

    events = [

        {
            "ticker": "CAPR",
            "trading_impact": "EXTREME",
        },

        {
            "ticker": "ARGX",
            "trading_impact": "HIGH",
        },

        {
            "ticker": "TEST",
            "trading_impact": "LOW",
        },
    ]

    alerts = filter_fda_trading_alerts(
        events
    )

    assert len(alerts) == 2

    tickers = {
        event["ticker"]
        for event in alerts
    }

    assert "CAPR" in tickers
    assert "ARGX" in tickers
    assert "TEST" not in tickers


# ============================================
# TEST SORT
# ============================================

def test_sort_events():

    events = [

        {
            "ticker": "LOW",
            "trading_impact": "LOW",
        },

        {
            "ticker": "EXTREME",
            "trading_impact": "EXTREME",
        },

        {
            "ticker": "MEDIUM",
            "trading_impact": "MEDIUM",
        },

        {
            "ticker": "HIGH",
            "trading_impact": "HIGH",
        },
    ]

    ordered = sort_fda_events(
        events
    )

    assert ordered[0]["ticker"] == (
        "EXTREME"
    )

    assert ordered[1]["ticker"] == (
        "HIGH"
    )

    assert ordered[2]["ticker"] == (
        "MEDIUM"
    )

    assert ordered[3]["ticker"] == (
        "LOW"
    )


# ============================================
# TEST TOP EVENTS
# ============================================

def test_top_events():

    events = [

        {
            "ticker": "A",
            "trading_impact": "LOW",
        },

        {
            "ticker": "B",
            "trading_impact": "EXTREME",
        },

        {
            "ticker": "C",
            "trading_impact": "HIGH",
        },
    ]

    top = get_top_fda_events(
        events,
        limit=2,
    )

    assert len(top) == 2

    assert top[0]["ticker"] == "B"

    assert top[1]["ticker"] == "C"


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    test_approval_pipeline()
    test_rejection_pipeline()
    test_safety_pipeline()
    test_non_relevant_news()
    test_unmatched_news()
    test_multiple_news()
    test_filter_trading_alerts()
    test_sort_events()
    test_top_events()

    print(
        "✅ FDA Pipeline tests passed"
    )