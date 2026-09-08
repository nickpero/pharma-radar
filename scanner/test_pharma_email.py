from scanner.pharma_email import format_pharma_intelligence_email, email_is_configured, send_pharma_intelligence_email


def _alert(label="CRITICAL"):
    return {
        "ticker": "SMMT",
        "program": "ivonescimab",
        "label": label,
        "alert_priority": 100,
        "title": "FDA catalyst",
        "summary": "Important regulatory event.",
        "source": "FDA",
        "reaction_strength": "STRONG POSITIVE",
        "reaction_interpretation": "CONFIRMED",
        "market_reaction": {"reaction_5m_pct": 3.05, "reaction_15m_pct": 2.29},
        "event": {"type": "FDA_EVENT", "subtype": "FDA_APPROVAL", "score": 100, "label": label},
        "catalyst_explainer": {
            "what_is": "Descrizione source-grounded del programma.",
            "indication": "Indicazione di test.",
            "stage": "Phase 3",
            "why_it_matters": "Passaggio regolatorio decisivo.",
            "company_impact": "Può modificare le aspettative sul programma.",
        },
    }


def test_email_contains_intelligence_sections():
    message = format_pharma_intelligence_email(_alert())
    assert "PHARMA RADAR — PHARMA INTELLIGENCE" in message
    assert "SMMT — ivonescimab" in message
    assert "💊 COS'È / COSA FA" in message
    assert "🩺 INDICAZIONE" in message
    assert "🧪 FASE DI SVILUPPO" in message
    assert "🎯 PERCHÉ CONTA" in message
    assert "🏢 IMPATTO POTENZIALE SULL'AZIENDA" in message
    assert "📈 REAZIONE DEL MERCATO" in message
    assert "5m +3.05%" in message
    assert "15m +2.29%" in message


def test_low_alert_is_not_sent():
    assert send_pharma_intelligence_email(_alert("LOW")) is False


def test_configuration_is_boolean():
    assert isinstance(email_is_configured(), bool)


if __name__ == "__main__":
    test_email_contains_intelligence_sections()
    test_low_alert_is_not_sent()
    test_configuration_is_boolean()
    print("✅ Pharma Intelligence email tests passed")
