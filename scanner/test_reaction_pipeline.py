from scanner.reaction import enrich_reaction_classification


def test_phase5_2_consumes_phase5_1_market_reaction():
    event = {
        "score": 100,
        "direction": "POSITIVE",
        "market_reaction": {
            "reaction_pct": -6.0,
            "reaction_15m_pct": -5.0,
            "volume_ratio": 4.0,
            "reaction_status": "AVAILABLE",
        },
    }
    result = enrich_reaction_classification(event)
    assert result["reaction_strength"] == "NEGATIVE"
    assert result["reaction_interpretation"] == "DIVERGENCE"
    assert result["reaction_classification"] == "DIVERGENCE"


if __name__ == "__main__":
    test_phase5_2_consumes_phase5_1_market_reaction()
    print("Phase 5.2 pipeline integration test passed")
