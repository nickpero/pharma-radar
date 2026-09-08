from scanner.catalyst_confirmation import confirmation_label, confirmation_score, enrich_catalyst_confirmation


def event(movement=5, volume=2, direction="POSITIVE", interpretation="CONFIRMED", score=100):
    return {
        "score": score,
        "direction": direction,
        "reaction_interpretation": interpretation,
        "market_reaction": {"reaction_5m_pct": movement, "volume_ratio": volume},
    }


def test_strong_aligned_reaction_confirms():
    result = enrich_catalyst_confirmation(event())
    assert result["catalyst_confirmation_score"] >= 75
    assert result["catalyst_confirmation"] == "CONFIRMED"


def test_divergence_is_not_confirmation():
    result = enrich_catalyst_confirmation(event(movement=-5, volume=2, interpretation="DIVERGENCE"))
    assert result["catalyst_confirmation_score"] < 50
    assert result["catalyst_confirmation"] in {"WEAK", "UNCONFIRMED"}


def test_missing_reaction_stays_unconfirmed():
    result = enrich_catalyst_confirmation({"score": 100, "direction": "POSITIVE"})
    assert result["catalyst_confirmation_score"] == 0
    assert result["catalyst_confirmation"] == "UNCONFIRMED"


def test_overreaction_is_penalized():
    result = enrich_catalyst_confirmation(event(movement=25, volume=5, interpretation="OVERREACTION"))
    assert result["catalyst_confirmation_score"] < 75


def test_labels():
    assert confirmation_label(80) == "CONFIRMED"
    assert confirmation_label(60) == "PROBABLE"
    assert confirmation_label(30) == "WEAK"
    assert confirmation_label(10) == "UNCONFIRMED"


if __name__ == "__main__":
    test_strong_aligned_reaction_confirms()
    test_divergence_is_not_confirmation()
    test_missing_reaction_stays_unconfirmed()
    test_overreaction_is_penalized()
    test_labels()
    print("Phase 5.8 catalyst confirmation tests passed")
