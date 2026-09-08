from scanner.catalyst_explainer import enrich_catalyst_explainer, enrich_catalyst_explainers


def _base(label="CRITICAL", subtype="FDA_APPROVAL"):
    return {
        "ticker": "SMMT",
        "company": "Summit Therapeutics",
        "program": "ivonescimab",
        "label": label,
        "subtype": subtype,
        "direction": "POSITIVE",
        "trial": {
            "conditions": ["Non-small cell lung cancer"],
            "phase": "PHASE3",
            "brief_summary": "Ivonescimab is being studied in patients with advanced non-small cell lung cancer.",
        },
        "market_reaction": {
            "reaction_1m_pct": 0.76,
            "reaction_5m_pct": 3.05,
            "reaction_15m_pct": 2.29,
        },
        "reaction_strength": "STRONG POSITIVE",
        "reaction_interpretation": "CONFIRMED",
    }


def test_critical_alert_gets_italian_explainer():
    result = enrich_catalyst_explainer(_base())
    explainer = result["catalyst_explainer"]
    assert explainer["language"] == "it"
    assert explainer["source_grounded"] is True
    assert "non-small cell lung cancer" in explainer["what_is"].lower()
    assert explainer["indication"] == "Non-small cell lung cancer"
    assert explainer["stage"] == "PHASE3"
    assert "approvazione FDA" in explainer["why_it_matters"]
    assert "5m +3.05%" in explainer["market_reaction"]


def test_low_alert_is_not_enriched():
    result = enrich_catalyst_explainer(_base(label="LOW"))
    assert "catalyst_explainer" not in result


def test_missing_scientific_description_is_explicit():
    alert = _base()
    alert["trial"] = {}
    result = enrich_catalyst_explainer(alert)
    assert "non contiene una descrizione sufficiente" in result["catalyst_explainer"]["what_is"]
    assert result["catalyst_explainer"]["indication"] == "Non disponibile nella fonte analizzata"


def test_batch_enrichment():
    results = enrich_catalyst_explainers([_base(), _base(label="LOW")])
    assert "catalyst_explainer" in results[0]
    assert "catalyst_explainer" not in results[1]


if __name__ == "__main__":
    test_critical_alert_gets_italian_explainer()
    test_low_alert_is_not_enriched()
    test_missing_scientific_description_is_explicit()
    test_batch_enrichment()
    print("Catalyst explainer tests passed")
