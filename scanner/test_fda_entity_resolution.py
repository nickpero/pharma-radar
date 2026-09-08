"""Tests and live validation for FDA Entity Resolution 5.9A."""

from scanner.fda_entity_resolution import resolve_fda_entities
from scanner.fda_enrichment import enrich_fda_news
from scanner.fda_feed import get_fda_news
from scanner.fda_matcher import identify_fda_target
from scanner.trial_scanner import load_watchlist


def test_program_only_resolution_is_high_confidence():
    watchlist = load_watchlist()
    item = {
        "title": "FDA approves zidesamtinib for ROS1-positive cancer",
        "content": "The FDA approved zidesamtinib for patients with ROS1-positive disease.",
    }
    resolved = resolve_fda_entities(item, watchlist)
    entity = resolved["fda_entity_resolution"]
    assert entity["ticker"] == "NUVL"
    assert entity["program"].lower() == "zidesamtinib"
    assert entity["resolution_type"] == "PROGRAM"
    assert entity["confidence"] == "HIGH"


def test_company_and_program_resolution_is_high_confidence():
    watchlist = load_watchlist()
    item = {
        "title": "FDA approves zidesamtinib",
        "content": "Nuvalent announced that the FDA approved zidesamtinib.",
    }
    resolved = resolve_fda_entities(item, watchlist)
    entity = resolved["fda_entity_resolution"]
    assert entity["ticker"] == "NUVL"
    assert entity["resolution_type"] == "COMPANY_AND_PROGRAM"
    assert entity["confidence"] == "HIGH"


def test_generic_rare_does_not_resolve_to_rare_ticker():
    watchlist = load_watchlist()
    item = {
        "title": "FDA discusses a rare blood disorder",
        "content": "General information about a rare blood disorder.",
    }
    resolved = resolve_fda_entities(item, watchlist)
    assert "fda_entity_resolution" not in resolved


def test_live_fda_entity_resolution_sample():
    """Validate resolution against 20 current official FDA announcements."""
    watchlist = load_watchlist()
    news = get_fda_news(max_news=20)
    assert len(news) >= 10, "FDA feed returned too few live announcements"

    enriched = enrich_fda_news(news, max_items=20)
    resolved_count = 0
    matcher_count = 0
    details = []

    for item in enriched[:20]:
        resolved = resolve_fda_entities(item, watchlist)
        entity = resolved.get("fda_entity_resolution")
        target = identify_fda_target(resolved, watchlist)
        if entity:
            resolved_count += 1
            details.append((item.get("title", ""), entity["ticker"], entity["program"], entity["confidence"]))
        if target:
            matcher_count += 1

    print(f"FDA 5.9A LIVE SAMPLE: news={len(news)} enriched={len(enriched[:20])} resolved={resolved_count} matcher={matcher_count}")
    for title, ticker, program, confidence in details:
        print(f"  RESOLVED {ticker} — {program} — {confidence} — {title}")

    # Coverage smoke test: at least one current watchlist catalyst should be
    # recoverable from the live article body. This is not a target-rate goal.
    assert resolved_count >= 1, "No watchlist entity resolved from 20 live FDA articles"


if __name__ == "__main__":
    test_program_only_resolution_is_high_confidence()
    test_company_and_program_resolution_is_high_confidence()
    test_generic_rare_does_not_resolve_to_rare_ticker()
    test_live_fda_entity_resolution_sample()
    print("FDA ENTITY RESOLUTION TESTS PASSED")
