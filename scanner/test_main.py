from main import build_summary


def test_clean_summary():
    result = {
        "companies": 20,
        "total_trials": 174,
        "relevant_trials": 137,
        "filtered_trials": 37,
        "alerts": [],
        "errors": [],
    }
    message = build_summary(result)
    assert "🧬 PHARMA RADAR — SCAN" in message
    assert "Companies: 20" in message
    assert "Trials: 174" in message
    assert "Relevant: 137" in message
    assert "Filtered: 37" in message
    assert "Raw alerts: 0" in message
    assert "Telegram alerts: 0" in message
    assert "🟢 No catalyst alerts" in message
    assert "Status: CLEAN" in message
    assert "%0A" not in message


def test_alert_summary_is_concise():
    result = {
        "companies": 20,
        "total_trials": 174,
        "relevant_trials": 137,
        "filtered_trials": 37,
        "alerts": [{
            "ticker": "CAPR", "program": "deramiocel", "nct_id": "NCT05126758",
            "alert_priority": 100, "alert_tier": "CRITICAL",
            "trading_setup_score": 88, "trading_window": "0-2H", "market_awareness": "LOW",
            "event_surprise": "UNEXPECTED", "price_change_pct": 5.5, "volume_ratio": 3.2,
            "reaction_strength": "POSITIVE", "reaction_interpretation": "CONFIRMED",
            "market_reaction": {"reaction_1m_pct": 1.2, "reaction_5m_pct": 3.4, "reaction_15m_pct": 4.1},
            "event": {"type": "STATUS_CHANGE", "subtype": "TRIAL_COMPLETED", "score": 95, "label": "CRITICAL"},
        }],
        "errors": [],
    }
    message = build_summary(result)
    assert "🚨 PRIORITY ALERTS" in message
    assert "CAPR — deramiocel" in message
    assert "TRIAL_COMPLETED" in message
    assert "Catalyst 95/100 CRITICAL" in message
    assert "Priority 100/100 CRITICAL" in message
    assert "Setup 88/100" in message
    assert "Window 0-2H" in message
    assert "Reaction POSITIVE | CONFIRMED" in message
    assert "1m +1.20% | 5m +3.40% | 15m +4.10%" in message
    assert "💹 Price +5.50%" in message
    assert "📊 Volume 3.2x" in message
    assert "COSA SIGNIFICA" not in message
    assert "Status: REVIEW" in message
    assert "%0A" not in message


def test_duplicate_alerts_are_suppressed_in_summary():
    base = {
        "ticker": "SMMT", "program": "ivonescimab", "subtype": "FDA_APPROVAL",
        "alert_priority": 100, "alert_tier": "CRITICAL", "trading_setup_score": 52,
        "title": "SEC 8-K — Summit Therapeutics (SMMT)",
    }
    duplicate = dict(base)
    duplicate["trading_setup_score"] = 54
    result = {"companies": 20, "total_trials": 0, "relevant_trials": 0, "filtered_trials": 0, "alerts": [base, duplicate], "errors": []}
    message = build_summary(result)
    assert "Telegram alerts: 1" in message
    assert message.count("SMMT — ivonescimab") == 1
    assert "duplicate/low-priority alerts suppressed" in message


def test_error_summary():
    result = {
        "companies": 20, "total_trials": 174, "relevant_trials": 137, "filtered_trials": 37,
        "alerts": [], "errors": [{"ticker": "CAPR", "program": "deramiocel", "error": "Test error"}],
    }
    message = build_summary(result)
    assert "❌ ERRORS" in message
    assert "CAPR — deramiocel" in message
    assert "Status: WARNING" in message


if __name__ == "__main__":
    test_clean_summary()
    test_alert_summary_is_concise()
    test_duplicate_alerts_are_suppressed_in_summary()
    test_error_summary()
    print("✅ Main integration tests passed")
