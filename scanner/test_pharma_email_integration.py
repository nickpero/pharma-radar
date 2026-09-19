from pathlib import Path
from unittest.mock import patch

from scanner import pharma_email


def _alert(title="FDA catalyst", label="CRITICAL"):
    return {
        "ticker": "SMMT",
        "program": "ivonescimab",
        "label": label,
        "alert_priority": 100,
        "title": title,
        "source": "FDA",
        "url": "https://www.fda.gov/example",
        "event": {"type": "FDA_EVENT", "subtype": "FDA_APPROVAL", "score": 100, "label": label},
    }


def _smtp_mock():
    smtp = patch("scanner.pharma_email.smtplib.SMTP_SSL")
    instance = smtp.start()
    instance.return_value.__enter__.return_value = instance.return_value
    return smtp, instance.return_value


def test_first_send_then_duplicate_is_suppressed(tmp_path):
    state_path = tmp_path / "email_state.json"
    alert = _alert()
    with patch.object(pharma_email, "EMAIL_STATE_PATH", str(state_path)), \
         patch.object(pharma_email, "email_is_configured", return_value=True), \
         patch.object(pharma_email, "_smtp_config", return_value=("smtp.example", 465, "user", "pass", "from@example.com", "to@example.com")), \
         patch("scanner.pharma_email.smtplib.SMTP_SSL") as smtp_cls:
        smtp = smtp_cls.return_value.__enter__.return_value
        assert pharma_email.send_pharma_intelligence_emails([alert]) == 1
        assert pharma_email.send_pharma_intelligence_emails([alert]) == 0
        assert smtp.send_message.call_count == 1


def test_new_catalyst_is_sent(tmp_path):
    state_path = tmp_path / "email_state.json"
    with patch.object(pharma_email, "EMAIL_STATE_PATH", str(state_path)), \
         patch.object(pharma_email, "email_is_configured", return_value=True), \
         patch.object(pharma_email, "_smtp_config", return_value=("smtp.example", 465, "user", "pass", "from@example.com", "to@example.com")), \
         patch("scanner.pharma_email.smtplib.SMTP_SSL") as smtp_cls:
        smtp = smtp_cls.return_value.__enter__.return_value
        assert pharma_email.send_pharma_intelligence_emails([_alert("Catalyst A")]) == 1
        assert pharma_email.send_pharma_intelligence_emails([_alert("Catalyst B")]) == 1
        assert smtp.send_message.call_count == 2


def test_failed_send_is_not_marked(tmp_path):
    state_path = tmp_path / "email_state.json"
    alert = _alert()
    with patch.object(pharma_email, "EMAIL_STATE_PATH", str(state_path)), \
         patch.object(pharma_email, "email_is_configured", return_value=True), \
         patch.object(pharma_email, "_smtp_config", return_value=("smtp.example", 465, "user", "pass", "from@example.com", "to@example.com")), \
         patch("scanner.pharma_email.smtplib.SMTP_SSL") as smtp_cls:
        smtp = smtp_cls.return_value.__enter__.return_value
        smtp.send_message.side_effect = [OSError("temporary failure"), None]
        assert pharma_email.send_pharma_intelligence_emails([alert]) == 0
        assert pharma_email.send_pharma_intelligence_emails([alert]) == 1
        assert smtp.send_message.call_count == 2


def test_unconfigured_is_noop(tmp_path):
    state_path = tmp_path / "email_state.json"
    with patch.object(pharma_email, "EMAIL_STATE_PATH", str(state_path)), \
         patch.object(pharma_email, "email_is_configured", return_value=False), \
         patch("scanner.pharma_email.smtplib.SMTP_SSL") as smtp_cls:
        assert pharma_email.send_pharma_intelligence_emails([_alert()]) == 0
        smtp_cls.assert_not_called()


def test_low_priority_development_event_is_sent_for_knowledge():
    alert = {
        "ticker": "IONS",
        "program": "zilganersen",
        "label": "LOW",
        "alert_priority": 15,
        "title": "Trial completed",
        "source": "ClinicalTrials.gov",
        "source_type": "PRIMARY_CLINICAL",
        "nct_id": "NCT00000000",
        "trial": {
            "phase": "PHASE3",
            "status": "COMPLETED",
            "brief_summary": "Studio clinico completato.",
            "conditions": ["Rare disease"],
        },
        "event": {
            "type": "STATUS_CHANGE",
            "subtype": "TRIAL_COMPLETED",
            "old_value": "ACTIVE_NOT_RECRUITING",
            "new_value": "COMPLETED",
        },
    }
    assert pharma_email.is_pharma_intelligence_event(alert) is True
    assert "DEVELOPMENT" in pharma_email.format_pharma_intelligence_email(alert)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        test_first_send_then_duplicate_is_suppressed(Path(directory))
    print("✅ Pharma Intelligence email integration tests passed")
