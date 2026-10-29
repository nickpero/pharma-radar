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
    assert "📰 STUDIO COMPLETATO" in message
    assert "🎯 Catalizzatore: 95/100 · CRITICO" in message
    assert "🚨 Priorità: 100/100 · CRITICO" in message
    assert "📊 Configurazione: 80/100 · Finestra temporale: IMMEDIATA" in message
    assert "📈 Reazione del mercato:" in message


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
    assert "🚨 MODIFICA DELLE DATE DELLO STUDIO" in message
    assert "📌 Campo: Completamento primario" in message
    assert "📅 Data precedente: 2027-06-30" in message
    assert "📅 Nuova data: 2027-04-30" in message
    assert "⏩ Anticipata di 61 giorni" in message
    assert "ℹ️ È cambiata solo la tempistica: i risultati clinici non sono ancora stati comunicati." in message


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
    assert "🚨 MODIFICA DELLE DATE DELLO STUDIO" in message
    assert "📌 Campo: Completamento dello studio" in message
    assert "⏳ Posticipata di 91 giorni" in message


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
    assert "📰 STUDIO INTERROTTO" in message
    assert "🎯 Catalizzatore: 95/100 · CRITICO" in message


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
    assert "STATO DELLO STUDIO NON NOTO" in message
    assert "🎯 Catalizzatore: 15/100 · BASSO" in message


if __name__ == "__main__":
    test_catalyst_message_format()
    test_real_newlines()
    test_timeline_acceleration_details()
    test_timeline_delay_details()
    test_negative_direction()
    test_unknown_direction()
    print("✅ Telegram tests passed")
