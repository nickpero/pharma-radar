import os
import tempfile
from unittest.mock import patch

from scanner.pharma_email import format_pharma_intelligence_email, email_is_configured, send_pharma_intelligence_email
from scanner.pharma_email_state import email_delivery_key, load_email_state


def _alert(label="CRITICAL"):
    return {
        "ticker": "SMMT",
        "program": "ivonescimab",
        "company": "Summit Therapeutics",
        "label": label,
        "alert_priority": 100,
        "title": "FDA catalyst",
        "summary": "Important regulatory event.",
        "source": "FDA",
        "source_url": "https://www.fda.gov/example",
        "event_timestamp": "2026-09-08T12:00:00Z",
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
    assert "Azienda: Summit Therapeutics" in message
    assert "💊 COS'È / COSA FA" in message
    assert "🩺 INDICAZIONE" in message
    assert "🧪 FASE DI SVILUPPO" in message
    assert "🎯 PERCHÉ CONTA" in message
    assert "🏢 IMPATTO POTENZIALE SULL'AZIENDA" in message
    assert "📈 REAZIONE DEL MERCATO" in message
    assert "5m +3.05%" in message
    assert "15m +2.29%" in message
    assert "https://www.fda.gov/example" in message


def test_low_alert_is_not_sent():
    assert send_pharma_intelligence_email(_alert("LOW")) is False


def test_configuration_is_boolean():
    assert isinstance(email_is_configured(), bool)


def test_delivery_key_is_stable():
    assert email_delivery_key(_alert()) == email_delivery_key(dict(_alert()))


def test_successful_send_is_persisted_and_deduplicated():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        alert = _alert()
        with patch("scanner.pharma_email.DEFAULT_PATH", path, create=True):
            with patch("scanner.pharma_email.load_email_state", return_value=load_email_state(path)):
                with patch("scanner.pharma_email_state.load_email_state", return_value=set()):
                    with patch("scanner.pharma_email_state.save_email_state") as save_state:
                        with patch("scanner.pharma_email.smtplib.SMTP_SSL") as smtp_cls:
                            smtp = smtp_cls.return_value.__enter__.return_value
                            with patch.dict(os.environ, {
                                "PHARMA_SMTP_HOST": "smtp.example.com",
                                "PHARMA_SMTP_PORT": "465",
                                "PHARMA_SMTP_USERNAME": "user",
                                "PHARMA_SMTP_PASSWORD": "pass",
                                "PHARMA_EMAIL_FROM": "from@example.com",
                                "PHARMA_EMAIL_TO": "to@example.com",
                            }, clear=False):
                                assert send_pharma_intelligence_email(alert) is True
                                assert smtp.send_message.called
                                assert save_state.called


def test_smtp_failure_is_fail_safe():
    with patch.dict(os.environ, {
        "PHARMA_SMTP_HOST": "smtp.example.com",
        "PHARMA_SMTP_PORT": "465",
        "PHARMA_SMTP_USERNAME": "user",
        "PHARMA_SMTP_PASSWORD": "pass",
        "PHARMA_EMAIL_FROM": "from@example.com",
        "PHARMA_EMAIL_TO": "to@example.com",
    }, clear=False):
        with patch("scanner.pharma_email.smtplib.SMTP_SSL", side_effect=OSError("network down")):
            assert send_pharma_intelligence_email(_alert()) is False


if __name__ == "__main__":
    test_email_contains_intelligence_sections()
    test_low_alert_is_not_sent()
    test_configuration_is_boolean()
    test_delivery_key_is_stable()
    print("✅ Pharma Intelligence email tests passed")
