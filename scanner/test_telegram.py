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
    assert "CAPR — deramiocel" in message
    assert "NCT05126758" in message
    assert "STATUS_CHANGE" in message
    assert "TRIAL_COMPLETED" in message
    assert "Score: 95/100" in message
    assert "CRITICAL" in message
    assert "Direction: CATALYST" in message
    assert "RECRUITING" in message
    assert "COMPLETED" in message


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
    assert "📉" in message
    assert "Direction: NEGATIVE" in message
    assert "TERMINATED" in message


def test_unknown_direction():
    alert = {
        "ticker": "ZYME",
        "program": "zanidatamab",
        "nct_id": "NCT99999999",
        "event": {
            "type": "FIELD_CHANGE",
            "severity": "LOW",
            "direction": "UNKNOWN",
            "subtype": "FIELD_UPDATED",
            "score": 15,
            "label": "LOW",
            "old_value": "A",
            "new_value": "B",
        },
    }
    message = format_catalyst_alert(alert)
    assert "⚪" in message
    assert "Direction: UNKNOWN" in message


def test_priority_hierarchy_is_visible():
    alert = {
        "ticker": "NUVL",
        "program": "zidesamtinib",
        "event": {
            "type": "FDA_EVENT",
            "severity": "HIGH",
            "direction": "CATALYST",
            "subtype": "FDA_APPROVAL",
            "score": 100,
            "label": "CRITICAL",
            "trading_impact": "EXTREME",
            "urgency": "IMMEDIATE",
            "match_confidence": "HIGH",
        },
    }
    message = format_catalyst_alert(alert)
    assert "PRIORITY: CRITICAL — 100/100" in message


def test_priority_tier_is_derived_when_missing():
    alert = {
        "ticker": "ZYME",
        "program": "zanidatamab",
        "event": {
            "type": "STATUS_CHANGE",
            "score": 60,
            "trading_impact": "MEDIUM",
            "urgency": "NORMAL",
            "match_confidence": "HIGH",
        },
    }
    message = format_catalyst_alert(alert)
    assert "PRIORITY: WATCH" in message


def test_full_trading_intelligence_is_visible():
    alert = {
        "ticker": "NUVL",
        "program": "zidesamtinib",
        "nct_id": None,
        "score": 100,
        "label": "CRITICAL",
        "trading_setup_score": 92,
        "trading_window": "0-2H",
        "market_awareness": "MEDIUM",
        "event_surprise": "UNEXPECTED",
        "price_change_pct": 6.25,
        "volume_ratio": 3.5,
        "market_cap": 250_000_000,
        "short_interest_pct": 25.0,
        "event": {
            "type": "FDA_EVENT",
            "severity": "HIGH",
            "direction": "CATALYST",
            "subtype": "FDA_APPROVAL",
            "score": 100,
            "label": "CRITICAL",
            "trading_impact": "EXTREME",
            "urgency": "IMMEDIATE",
        },
    }
    message = format_catalyst_alert(alert)
    assert "📊 TRADING INTELLIGENCE" in message
    assert "Trading Setup: 92/100" in message
    assert "Window: 0-2H" in message
    assert "Market Awareness: MEDIUM" in message
    assert "Event Surprise: UNEXPECTED" in message
    assert "Price vs prev close: +6.25%" in message
    assert "Volume vs 20d avg: 3.5x" in message
    assert "Market Cap: $250M" in message
    assert "Short Interest: 25.0%" in message


if __name__ == "__main__":
    test_catalyst_message_format()
    test_real_newlines()
    test_negative_direction()
    test_unknown_direction()
    test_priority_hierarchy_is_visible()
    test_priority_tier_is_derived_when_missing()
    test_full_trading_intelligence_is_visible()
    print("✅ Telegram formatter tests passed")
