"""P1 regression tests for FDA matcher coverage and false-positive protection."""

from scanner.fda_matcher import identify_fda_target
from scanner.trial_scanner import load_watchlist


CASES = [
    ("CAPR", "deramiocel"),
    ("SVRA", "MOLBREEVI"),
    ("ZYME", "Ziihera"),
    ("MIRM", "Livmarli"),
    ("PHVS", "Ekterly"),
    ("TENX", "TNX-103"),
    ("NUVL", "Jideytro"),
    ("RARE", "etuvetidigene autotemcel"),
    ("TLX", "Pixclara"),
    ("IONS", "ION363"),
    ("ARGX", "efgartigimod"),
    ("QURE", "AMT130"),
    ("STOK", "STK-001"),
    ("ANNX", "ANX-007"),
    ("IMMX", "NXC201"),
    ("ALMS", "ESK001"),
    ("RNA", "delpacibart"),
    ("RGNX", "RGX-202"),
    ("EYPT", "EYP-1901"),
    ("SMMT", "AK112"),
]


def test_all_watchlist_program_aliases_match():
    watchlist = load_watchlist()
    for ticker, alias in CASES:
        item = {
            "title": f"FDA update for {alias}",
            "summary": f"The agency issued an update concerning {alias}.",
            "content": f"The company reported regulatory information for {alias}.",
        }
        target = identify_fda_target(item, watchlist)
        assert target is not None, f"No FDA match for {ticker}/{alias}"
        assert target["ticker"] == ticker, f"Wrong ticker for {alias}: {target}"
        assert target["confidence"] == "HIGH", f"Low confidence for {ticker}/{alias}"


def test_generic_words_do_not_trigger_targets():
    watchlist = load_watchlist()
    generic_items = [
        {"title": "FDA discusses rare disease", "content": "A rare disease requires specialist care."},
        {"title": "FDA discusses summit", "content": "The agency held a summit on public health."},
        {"title": "FDA discusses capital", "content": "The notice contains general information."},
    ]
    for item in generic_items:
        assert identify_fda_target(item, watchlist) is None, f"False positive: {item}"


if __name__ == "__main__":
    test_all_watchlist_program_aliases_match()
    test_generic_words_do_not_trigger_targets()
    print("P1 FDA MATCHER TESTS PASSED")
