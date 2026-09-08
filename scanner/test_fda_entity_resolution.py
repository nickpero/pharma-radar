"""Tests for FDA Entity Resolution 5.9A."""

from scanner.fda_entity_resolution import resolve_fda_entities
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


if __name__ == "__main__":
    test_program_only_resolution_is_high_confidence()
    test_company_and_program_resolution_is_high_confidence()
    test_generic_rare_does_not_resolve_to_rare_ticker()
    print("FDA ENTITY RESOLUTION TESTS PASSED")
