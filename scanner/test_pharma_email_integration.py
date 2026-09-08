import os
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


def test_first_send_then_duplicate_is_suppressed(tmp_path):
    state_path = tmp_path / "email_state.json"
    alert = _alert()
    with patch.object(pharma_email, "EMAIL_STATE_PATH", state_path), \
         patch.object(pharma_email, "email_is_configured", return_value=True), \
         patch.object(pharma_email, "send_pharma_intelligence_email", return_value=True) as send:
        assert pharma_email.send_pharma_intelligence_emails([alert]) == 1
        assert pharma_email.send_pharma_intelligence_emails([alert]) == 0
        assert send.call_count == 1


def test_new_catalyst_is_sent(tmp_path):
    state_path = tmp_path / "email_state.json"
    with patch.object(pharma_email, "EMAIL_STATE_PATH", state_path), \
         patch.object(pharma_email, "email_is_configured", return_value=True), \
         patch.object(pharma_email, "send_pharma_intelligence_email", return_value=True) as send:
        assert pharma_email.send_pharma_intelligence_emails([_alert("Catalyst A")]) == 1
        assert pharma_email.send_pharma_intelligence_emails([_alert("Catalyst B")]) == 1
        assert send.call_count == 2


def test_failed_send_is_not_marked(tmp_path):
    state_path = tmp_path / "email_state.json"
    alert = _alert()
    with patch.object(pharma_email, "EMAIL_STATE_PATH", state_path), \
         patch.object(pharma_email, "email_is_configured", return_value=True), \
         patch.object(pharma_email, "send_pharma_intelligence_email", side_effect=[False, True]) as send:
        assert pharma_email.send_pharma_intelligence_emails([alert]) == 0
        assert pharma_email.send_pharma_intelligence_emails([alert]) == 1
        assert send.call_count == 2


def test_unconfigured_is_noop(tmp_path):
    state_path = tmp_path / "email_state.json"
    with patch.object(pharma_email, "EMAIL_STATE_PATH", state_path), \
         patch.object(pharma_email, "email_is_configured", return_value=False), \
         patch.object(pharma_email, "send_pharma_intelligence_email") as send:
        assert pharma_email.send_pharma_intelligence_emails([_alert()]) == 0
        send.assert_not_called()


if __name__ == "__main__":
    test_first_send_then_duplicate_is_suppressed(Path("/tmp/pharma-email-test"))
    print("✅ Pharma Intelligence email integration tests passed")
