from scanner.telegram import format_catalyst_alert


def test_catalyst_message_format():
    alert = {
        "ticker": "CAPR",
        "program": "deramiocel",
        "nct_id": "NCT05126758",
        "event": {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "CATALYST",
            "subtype": "TRIAL_COMPLETED",
            "score": 95,
            "label": "CRITICAL",
            "old_value": "RECRUITING",
            "new_value": "COMPLETED",
        },
    }
    message = format_catalyst_alert(alert)
    assert "🚨 PHARMA RADAR — CRITICAL" in message
    assert "🧬 CAPR — deramiocel" in message
    assert "🧪 NCT05126758" in message
    assert "📰 TRIAL_COMPLETED" in message
    assert "🎯 CATALYST" in message
    assert "95/100 — CRITICAL" in message
    assert "🚨 PRIORITY" in message
    assert "🧠 CONFIRMATION" in message
    assert "0/100 — UNCONFIRMED" in message
    assert "📊 TRADING SETUP" in message
    assert "📈 MARKET REACTION" in message
    assert "⚠️ Nessuna raccomandazione automatica" in message


def test_real_newlines():
    alert = {
        "ticker": "SVRA",
        "program": "molgramostim",
        "nct_id": "NCT04544293",
        "event": {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "POSITIVE",
            "subtype": "DATE_ACCELERATED",
            "score": 100,
            "label": "CRITICAL",
            "old_value": "2027-06-30",
            "new_value": "2027-03-31",
        },
    }
    message = format_catalyst_alert(alert)
    assert "\n" in message
    assert "%0A" not in message


def test_negative_direction():
    alert = {
        "ticker": "CAPR",
        "program": "deramiocel",
        "nct_id": "NCT12345678",
        "event": {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "NEGATIVE",
            "subtype": "TRIAL_STOPPED",
            "score": 95,
            "label": "CRITICAL",
            "old_value": "RECRUITING",
            "new_value": "TERMINATED",
        },
    }
    message = format_catalyst_alert(alert)
    assert "📉" not in message
    assert "TRIAL_STOPPED" in message
    assert "95/100 — CRITICAL" in message
    assert "TERMINATED" not in message


def test_unknown_direction():
    alert = {
        "ticker": "ZYME",
        "program": "zanidatamab",
        "nct_id": "NCT99999999",
        "event": {
            "type": "STATUS_CHANGE",
            "severity": "LOW",
            "direction": "UNKNOWN",
            "subtype": "TRIAL_STATUS_UNKNOWN",
            "score": 15,
            "label": "LOW",
        },
    }
    message = format_catalyst_alert(alert)
    assert "ZYME — zanidatamab" in message
    assert "TRIAL_STATUS_UNKNOWN" in message
    assert "15/100 — LOW" in message


if __name__ == "__main__":
    test_catalyst_message_format()
    test_real_newlines()
    test_negative_direction()
    test_unknown_direction()
    print("✅ Telegram tests passed")
