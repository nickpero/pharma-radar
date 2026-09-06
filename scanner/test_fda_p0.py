"""P0 acceptance test: live FDA article -> body enrichment -> matcher -> catalyst."""

import requests

from scanner.fda_enrichment import enrich_fda_news_item
from scanner.fda_feed import build_fda_news_item
from scanner.fda_matcher import identify_fda_target
from scanner.fda_pipeline import process_fda_news_item
from scanner.trial_scanner import load_watchlist

ZIDESAMTINIB_URL = (
    "https://www.fda.gov/drugs/resources-information-approved-drugs/"
    "fda-approves-zidesamtinib-ros1-positive-non-small-cell-lung-cancer"
)


def fetch_live_article():
    response = requests.get(
        ZIDESAMTINIB_URL,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; PharmaRadar/1.0; +https://www.fda.gov/)"
        },
    )
    response.raise_for_status()
    return response.text


def test_live_fda_zidesamtinib_p0():
    html = fetch_live_article()
    item = {
        "source": "FDA LIVE",
        "title": "FDA approves zidesamtinib for ROS1-positive non-small cell lung cancer",
        "summary": "FDA approval of zidesamtinib.",
        "url": ZIDESAMTINIB_URL,
    }

    from scanner.fda_enrichment import _extract_article_text
    item["content"] = _extract_article_text(html, item["title"])
    item["article_text"] = item["content"]
    item["body"] = item["content"]
    item["text"] = f"{item['title']} {item['summary']} {item['content']}"

    assert len(item["content"]) > 200, "FDA article body was not extracted"
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
    item = build_fda_news_item(
        title="FDA discusses a rare blood disorder",
        summary="The agency issued general information about a rare condition.",
        url="https://www.fda.gov/news-events/press-announcements/example",
        content="Patients with a rare blood disorder may need specialized care.",
    )
    target = identify_fda_target(item, watchlist)
    assert target is None, "Generic word 'rare' must not match RARE"


if __name__ == "__main__":
    test_live_fda_zidesamtinib_p0()
    test_rare_false_positive_protection()
    print("P0 FDA LIVE ENRICHMENT TESTS PASSED")
