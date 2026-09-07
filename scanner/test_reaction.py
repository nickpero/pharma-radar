from scanner.reaction import classify_reaction, enrich_reaction_classification


def test_confirmed_positive():
    event = {"score": 90, "direction": "POSITIVE", "reaction": {"movement_pct": 8.0, "volume_ratio": 4.0}}
    assert classify_reaction(event) == "CONFIRMED"


def test_underreaction():
    event = {"score": 90, "direction": "POSITIVE", "reaction": {"movement_pct": 0.8, "volume_ratio": 1.0}}
    assert classify_reaction(event) == "UNDERREACTION"


def test_divergence():
    event = {"score": 95, "direction": "POSITIVE", "reaction": {"movement_pct": -5.0, "volume_ratio": 3.0}}
    assert classify_reaction(event) == "DIVERGENCE"


def test_overreaction():
    event = {"score": 90, "direction": "POSITIVE", "reaction": {"movement_pct": 25.0, "volume_ratio": 8.0}}
    assert classify_reaction(event) == "OVERREACTION"


def test_enrichment():
    event = {"score": 90, "direction": "POSITIVE", "reaction": {"movement_pct": 7.0, "volume_ratio": 3.0}}
    assert enrich_reaction_classification(event)["reaction_classification"] == "CONFIRMED"


def test_missing_market_reaction_is_safe():
    assert classify_reaction({"score": 90, "direction": "POSITIVE"}) == "UNKNOWN"


if __name__ == "__main__":
    test_confirmed_positive()
    test_underreaction()
    test_divergence()
    test_overreaction()
    test_enrichment()
    test_missing_market_reaction_is_safe()
    print("Phase 5.2 Reaction Classification tests passed")
