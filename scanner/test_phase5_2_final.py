from scanner.reaction import classify_reaction, classify_reaction_strength, classify_reaction_interpretation


def e(score=90, direction="POSITIVE", move=8, volume=4):
    return {"score": score, "direction": direction, "market_reaction": {"reaction_pct": move, "volume_ratio": volume}}


def test_strength():
    assert classify_reaction_strength(e(move=12)) == "STRONG POSITIVE"
    assert classify_reaction_strength(e(move=5)) == "POSITIVE"
    assert classify_reaction_strength(e(move=0.5)) == "NEUTRAL"
    assert classify_reaction_strength(e(move=-5)) == "NEGATIVE"
    assert classify_reaction_strength(e(move=-12)) == "STRONG NEGATIVE"


def test_interpretations():
    assert classify_reaction_interpretation(e(move=8)) == "CONFIRMED"
    assert classify_reaction_interpretation(e(move=1.5, volume=1)) == "UNDERREACTION"
    assert classify_reaction_interpretation(e(score=95, move=-5)) == "DIVERGENCE"
    assert classify_reaction_interpretation(e(move=25, volume=8)) == "OVERREACTION"
    assert classify_reaction_interpretation(e(direction="NEGATIVE", move=-7)) == "CONFIRMED"


def test_safe_unknown():
    result = classify_reaction({"score": 90, "direction": "POSITIVE"})
    assert result == {"reaction_strength": "UNKNOWN", "reaction_interpretation": "UNKNOWN"}


if __name__ == "__main__":
    test_strength()
    test_interpretations()
    test_safe_unknown()
    print("Phase 5.2 final tests passed")
