from scanner.telegram import format_catalyst_alert


def test_catalyst_message_format():
    alert = {
        "ticker": "CAPR",
        "program": "deramiocel",
        "nct_id": "NCT05126758",
        "alert_priority": 100,
        "alert_tier": "CRITICAL",
        "trading_setup_score": 80,
        "trading_window": "IMMEDIATE",
        "catalyst_confirmation_score": 0,
        "catalyst_confirmation": "UNCONFIRMED",
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
    assert "🚨 PHARMA RADAR" in message
    assert "🚨 CRITICAL" in message
    assert "🧬 CAPR" in message
    assert "💊 deramiocel" in message
    assert "📰 TRIAL COMPLETED" in message
    assert "🎯 Catalyst: 95/100 · CRITICAL" in message
    assert "🚨 Priority: 100/100 · CRITICAL" in message
    assert "📊 Setup: 80/100 · Window: IMMEDIATE" in message
    assert "📈 Market reaction:" in message


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
            "field": "primary_completion_date",
        },
    }
    message = format_catalyst_alert(alert)
    assert "\n" in message
    assert "%0A" not in message


def test_timeline_acceleration_details():
    alert = {
        "ticker": "VRTX",
        "program": "suzetrigine",
        "nct_id": "NCT12345678",
        "event": {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "POSITIVE",
            "subtype": "DATE_ACCELERATED",
            "score": 100,
            "label": "CRITICAL",
            "old_value": "2027-06-30",
            "new_value": "2027-04-30",
            "field": "primary_completion_date",
        },
    }
    message = format_catalyst_alert(alert)
    assert "🚨 TRIAL TIMELINE CHANGE" in message
    assert "📌 Field: Primary Completion" in message
    assert "📅 Old date: 2027-06-30" in message
    assert "📅 New date: 2027-04-30" in message
    assert "⏩ Accelerated: 61 days" in message
    assert "ℹ️ Timeline change only — clinical outcome not yet reported." in message


def test_timeline_delay_details():
    alert = {
        "ticker": "SVRA",
        "program": "molgramostim",
        "nct_id": "NCT04544293",
        "event": {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "NEGATIVE",
            "subtype": "DATE_DELAYED",
            "score": 100,
            "label": "CRITICAL",
            "old_value": "2027-03-31",
            "new_value": "2027-06-30",
            "field": "study_completion_date",
        },
    }
    message = format_catalyst_alert(alert)
    assert "🚨 TRIAL TIMELINE CHANGE" in message
    assert "📌 Field: Study Completion" in message
    assert "⏳ Delayed: 91 days" in message


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
    assert "🧬 CAPR" in message
    assert "📰 TRIAL STOPPED" in message
    assert "🎯 Catalyst: 95/100 · CRITICAL" in message


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
    assert "ZYME" in message
    assert "zanidatamab" in message
    assert "TRIAL STATUS UNKNOWN" in message
    assert "🎯 Catalyst: 15/100 · LOW" in message


if __name__ == "__main__":
    test_catalyst_message_format()
    test_real_newlines()
    test_timeline_acceleration_details()
    test_timeline_delay_details()
    test_negative_direction()
    test_unknown_direction()
    print("✅ Telegram tests passed")
