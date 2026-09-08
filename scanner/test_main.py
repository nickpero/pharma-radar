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
    assert "Trials found: 174" in message
    assert "Relevant trials: 137" in message
    assert "Filtered out: 37" in message
    assert "Alerts: 0" in message
    assert "🟢 No catalyst alerts" in message
    assert "Status: CLEAN" in message
    assert "%0A" not in message
    assert "\n" in message


def test_alert_summary():
    result = {
        "companies": 20,
        "total_trials": 174,
        "relevant_trials": 137,
        "filtered_trials": 37,
        "alerts": [{
            "ticker": "CAPR", "program": "deramiocel", "nct_id": "NCT05126758",
            "trading_setup_score": 88, "trading_window": "0-2H", "market_awareness": "LOW",
            "event_surprise": "UNEXPECTED", "price_change_pct": 5.5, "volume_ratio": 3.2,
            "market_cap": 250_000_000, "short_interest_pct": 12.5,
            "reaction_strength": "POSITIVE", "reaction_interpretation": "CONFIRMED",
            "market_reaction": {"reaction_1m_pct": 1.2, "reaction_5m_pct": 3.4, "reaction_15m_pct": 4.1},
            "event": {"type": "STATUS_CHANGE", "subtype": "TRIAL_COMPLETED", "score": 95, "label": "CRITICAL"},
        }],
        "errors": [],
    }
    message = build_summary(result)
    assert "🚨 CATALYST ALERTS" in message
    assert "CAPR — deramiocel" in message
    assert "NCT05126758" in message
    assert "STATUS_CHANGE" in message
    assert "TRIAL_COMPLETED" in message
    assert "Score: 95/100" in message
    assert "CRITICAL" in message
    assert "Trading Intelligence: Setup 88/100" in message
    assert "Window 0-2H" in message
    assert "Awareness LOW" in message
    assert "Surprise UNEXPECTED" in message
    assert "Reaction: POSITIVE | CONFIRMED" in message
    assert "Market reaction: 1m +1.20% | 5m +3.40% | 15m +4.10%" in message
    assert "Price: +5.50%" in message
    assert "Volume: 3.2x 20d" in message
    assert "Market Cap: $250M" in message
    assert "Short Interest: 12.5%" in message
    assert "Status: REVIEW" in message
    assert "%0A" not in message


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
    test_alert_summary()
    test_error_summary()
    print("✅ Main integration tests passed")
