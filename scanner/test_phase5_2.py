from scanner.reaction import classify_reaction


def test_strong_negative_reaction_against_positive_catalyst():
    event = {"score": 100, "direction": "CATALYST", "reaction": {"movement_pct": -8.0, "volume_ratio": 5.0}}
    assert classify_reaction(event) == "DIVERGENCE"


def test_small_positive_move_on_high_catalyst_is_underreaction():
    event = {"score": 80, "direction": "POSITIVE", "reaction": {"movement_pct": 1.5, "volume_ratio": 1.2}}
    assert classify_reaction(event) == "UNDERREACTION"


def test_extreme_move_is_overreaction():
    event = {"score": 75, "direction": "NEGATIVE", "reaction": {"movement_pct": -22.0, "volume_ratio": 6.0}}
    assert classify_reaction(event) == "OVERREACTION"


if __name__ == "__main__":
    test_strong_negative_reaction_against_positive_catalyst()
    test_small_positive_move_on_high_catalyst_is_underreaction()
    test_extreme_move_is_overreaction()
    print("Phase 5.2 regression tests passed")
