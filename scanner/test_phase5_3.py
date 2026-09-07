from scanner.trading_setup_2 import build_trading_setup_2, enrich_trading_setup_2


def base():
    return {
        "score": 100,
        "trading_impact": "EXTREME",
        "urgency": "IMMEDIATE",
        "match_confidence": "HIGH",
        "direction": "POSITIVE",
        "published_at": "2026-09-07T14:00:00+00:00",
        "event_surprise": "UNEXPECTED",
        "reaction_interpretation": "CONFIRMED",
        "market_cap": 250_000_000,
        "short_interest_pct": 25,
        "market_reaction": {"reaction_status": "AVAILABLE", "reaction_pct": 12, "reaction_1m_pct": 2, "reaction_5m_pct": 5, "reaction_15m_pct": 8, "reaction_30m_pct": 10, "reaction_60m_pct": 12, "post_catalyst_high": 115, "post_catalyst_low": 100},
    }


def test_setup2_is_bounded():
    result = build_trading_setup_2(base(), {"volume_ratio": 5}, now="2026-09-07T14:05:00+00:00")
    assert 0 <= result["trading_setup_score"] <= 100
    assert result["trading_setup_version"] == "5.3"


def test_setup2_uses_reaction_and_structure():
    rich = build_trading_setup_2(base(), {"volume_ratio": 5}, now="2026-09-07T14:05:00+00:00")
    poor_event = {"score": 100, "trading_impact": "EXTREME", "urgency": "IMMEDIATE", "match_confidence": "HIGH", "direction": "POSITIVE", "published_at": "2026-09-07T14:00:00+00:00"}
    poor = build_trading_setup_2(poor_event, {"volume_ratio": 1}, now="2026-09-07T14:05:00+00:00")
    assert rich["trading_setup_score"] > poor["trading_setup_score"]
    assert rich["setup_reaction_component"] == 15
    assert rich["setup_reaction_quality"] == "HIGH"
    assert rich["setup_structure_component"] == 10


def test_divergence_is_not_treated_as_confirmation():
    event = base()
    event["reaction_interpretation"] = "DIVERGENCE"
    result = build_trading_setup_2(event, {"volume_ratio": 4}, now="2026-09-07T14:05:00+00:00")
    assert result["setup_reaction_component"] == 10
    assert result["trading_setup_score"] <= 100


def test_enrichment():
    result = enrich_trading_setup_2(base(), {"volume_ratio": 3}, now="2026-09-07T14:05:00+00:00")
    assert result["trading_setup_version"] == "5.3"
    assert "setup_surprise_component" in result


if __name__ == "__main__":
    test_setup2_is_bounded()
    test_setup2_uses_reaction_and_structure()
    test_divergence_is_not_treated_as_confirmation()
    test_enrichment()
    print("Trading Intelligence Phase 5.3 tests passed")
