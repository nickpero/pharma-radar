"""Deterministic FDA P0 regression tests (no live network calls)."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

from scanner.fda_enrichment import enrich_fda_news_item
from scanner.fda_matcher import identify_fda_target
from scanner.fda_news import build_fda_news_item
from scanner.fda_pipeline import process_fda_news_item
from scanner.trial_scanner import load_watchlist


FDA_URL = (
    "https://www.fda.gov/drugs/resources-information-approved-drugs/"
    "fda-approves-zidesamtinib-ros1-positive-non-small-cell-lung-cancer"
)

ARTICLE_HTML = """
<html><head>
<meta property="article:published_time" content="2026-10-13T18:45:00Z">
</head><body><main>
<h1>FDA approves zidesamtinib</h1>
<p>The U.S. Food and Drug Administration approved zidesamtinib for adults with
ROS1-positive non-small cell lung cancer. Nuvalent, Inc. developed the
medicine. This announcement describes the regulatory decision and patient
population, with additional information about the indication and safety
considerations for clinicians and patients.</p>
</main></body></html>
"""


def test_fda_article_enrichment_resolves_zidesamtinib_without_network():
    response = Mock()
    response.text = ARTICLE_HTML
    response.raise_for_status.return_value = None
    item = {
        "title": "FDA approves zidesamtinib",
        "summary": "FDA approval announcement.",
        "url": FDA_URL,
        "published_at": None,
    }

    with patch("scanner.fda_enrichment.requests.get", return_value=response) as get:
        enriched = enrich_fda_news_item(item)

    get.assert_called_once()
    assert len(enriched["content"]) > 200
    assert "zidesamtinib" in enriched["content"].lower()
    assert "nuvalent" in enriched["content"].lower()
    assert enriched["published_at"] == "2026-10-13T18:45:00+00:00"

    target = identify_fda_target(enriched, load_watchlist())
    assert target is not None
    assert target["ticker"] == "NUVL"
    assert target["program"].lower() == "zidesamtinib"
    assert target["confidence"] == "HIGH"


def test_generic_rare_article_does_not_resolve_rare_ticker():
    item = {
        "title": "FDA discusses a rare blood disorder",
        "summary": "General information about a rare condition.",
        "content": "Patients with a rare blood disorder may need specialized care.",
    }
    assert identify_fda_target(item, load_watchlist()) is None


def test_enrichment_does_not_fetch_non_fda_urls():
    item = {
        "title": "FDA approves zidesamtinib",
        "url": "https://example.com/fda-article",
    }
    with patch("scanner.fda_enrichment.requests.get") as get:
        enriched = enrich_fda_news_item(item)
    get.assert_not_called()
    assert enriched["url"] == item["url"]
    assert "content" not in enriched


def test_voceryq_cber_approval_resolves_to_ino_critical_catalyst_without_network():
    published_at = datetime.now(timezone.utc).isoformat()
    item = build_fda_news_item(
        title="October 30, 2026 Approval Letter - VOCERYQ",
        summary=(
            "The FDA granted accelerated approval to VOCERYQ, developed by "
            "INOVIO Pharmaceuticals, to reduce the frequency of surgical "
            "papilloma excisions in adults with recurrent respiratory papillomatosis. "
            "VOCERYQ was previously referred to as INO-3107."
        ),
        url="https://www.fda.gov/media/196199/download",
        published_at=published_at,
        source="FDA CBER",
    )
    watchlist = load_watchlist()
    target = identify_fda_target(item, watchlist)
    assert target is not None
    assert target["ticker"] == "INO"
    assert target["program"] == "INO-3107"
    assert target["confidence"] == "HIGH"

    event = process_fda_news_item(item, watchlist)
    assert event is not None
    assert event["ticker"] == "INO"
    assert event["program"] == "INO-3107"
    assert event["subtype"] == "FDA_APPROVAL"
    assert event["trading_impact"] == "EXTREME"
    assert event["urgency"] == "IMMEDIATE"
