"""P0 acceptance test: live FDA article -> body enrichment -> matcher -> catalyst."""

from datetime import datetime, timezone

from scanner.fda_enrichment import enrich_fda_news_item
from scanner.fda_news import build_fda_news_item
from scanner.fda_matcher import identify_fda_target
from scanner.fda_pipeline import process_fda_news_item
from scanner.trial_scanner import load_watchlist

ZIDESAMTINIB_URL = (
    "https://www.fda.gov/drugs/resources-information-approved-drugs/"
    "fda-approves-zidesamtinib-ros1-positive-non-small-cell-lung-cancer"
)


def test_live_fda_zidesamtinib_p0():
    item = build_fda_news_item(
        title="FDA approves zidesamtinib for ROS1-positive non-small cell lung cancer",
        summary="FDA approval of zidesamtinib.",
        url=ZIDESAMTINIB_URL,
        source="FDA LIVE",
    )
    item = enrich_fda_news_item(item)
    assert len(item.get("content", "")) > 200, "FDA article body was not extracted"
    assert "zidesamtinib" in item["content"].lower(), "FDA article body lacks zidesamtinib"
    assert "nuvalent" in item["content"].lower(), "FDA article body lacks Nuvalent"

    watchlist = load_watchlist()
    target = identify_fda_target(item, watchlist)
    assert target is not None, "Live FDA zidesamtinib article did not match watchlist"
    assert target["ticker"] == "NUVL"
    assert target["program"].lower() == "zidesamtinib"
    assert target["confidence"] == "HIGH"

    event = process_fda_news_item(item, watchlist)
    assert event is not None, "Live FDA article did not reach catalyst pipeline"
    assert event["ticker"] == "NUVL"
    assert event["program"].lower() == "zidesamtinib"
    assert event.get("score", 0) > 0


def test_rare_false_positive_protection():
    watchlist = load_watchlist()
    item = {
        "title": "FDA discusses a rare blood disorder",
        "summary": "The agency issued general information about a rare condition.",
        "url": "https://www.fda.gov/news-events/press-announcements/example",
        "source": "FDA TEST",
        "content": "Patients with a rare blood disorder may need specialized care.",
    }
    target = identify_fda_target(item, watchlist)
    assert target is None, "Generic word 'rare' must not match RARE"


if __name__ == "__main__":
    test_live_fda_zidesamtinib_p0()
    test_rare_false_positive_protection()
    print("P0 FDA LIVE ENRICHMENT TESTS PASSED")


def test_live_fda_voceryq_approval_reaches_ino_critical_catalyst():
    """VOCERYQ/INO-3107 approval must resolve to INO and an extreme FDA catalyst."""
    published_at = datetime.now(timezone.utc).isoformat()
    item = build_fda_news_item(
        title="FDA approves VOCERYQ for adults with recurrent respiratory papillomatosis",
        summary=(
            "INOVIO Pharmaceuticals announced accelerated FDA approval of VOCERYQ, "
            "previously referred to as INO-3107, for adults with recurrent respiratory "
            "papillomatosis. The approved product contains doruxapapogene ralaplasmid "
            "and lalikinogene sifuplasmid-gxfd."
        ),
        url="https://www.fda.gov/news-events/press-announcements/fda-approves-voceryq",
        published_at=published_at,
        source="FDA",
        content=(
            "The U.S. Food and Drug Administration granted accelerated approval to "
            "VOCERYQ (doruxapapogene ralaplasmid and lalikinogene sifuplasmid-gxfd), "
            "previously referred to as INO-3107, developed by INOVIO Pharmaceuticals, "
            "to reduce the frequency of surgical papilloma excisions in adults with "
            "recurrent respiratory papillomatosis. "
        ) * 3,
    )
    watchlist = load_watchlist()
    target = identify_fda_target(item, watchlist)
    assert target is not None, "VOCERYQ approval did not resolve to a watchlist program"
    assert target["ticker"] == "INO"
    assert target["program"] == "INO-3107"
    assert target["confidence"] == "HIGH"

    event = process_fda_news_item(item, watchlist)
    assert event is not None, "VOCERYQ approval did not reach the FDA catalyst pipeline"
    assert event["ticker"] == "INO"
    assert event["program"] == "INO-3107"
    assert event["subtype"] == "FDA_APPROVAL"
    assert event["trading_impact"] == "EXTREME"
    assert event["urgency"] == "IMMEDIATE"
