from scanner.telegram_intelligence import alert_action, select_intelligent_alerts
from scanner.telegram import format_catalyst_alert


def _alert(ticker, priority, setup, tier, strength="UNKNOWN", interpretation="UNKNOWN"):
    return {
        "ticker": ticker,
        "program": "drug",
        "subtype": "FDA_APPROVAL",
        "alert_priority": priority,
        "alert_tier": tier,
        "trading_setup_score": setup,
        "reaction_strength": strength,
        "reaction_interpretation": interpretation,
    }


def test_critical_is_immediate():
    assert alert_action(_alert("NUVL", 100, 60, "CRITICAL")) == "IMMEDIATE"


def test_expired_is_silent_even_if_priority_is_critical():
    alert = _alert("ZYME", 100, 52, "CRITICAL")
    alert["trading_window"] = "EXPIRED"
    assert alert_action(alert) == "SILENT"
    assert select_intelligent_alerts([alert]) == []


def test_high_strong_reaction_is_immediate():
    assert alert_action(_alert("CAPR", 70, 65, "HIGH", "STRONG POSITIVE", "CONFIRMED")) == "IMMEDIATE"


def test_high_without_strong_reaction_is_fast():
    assert alert_action(_alert("ZYME", 65, 64, "HIGH")) == "FAST"


def test_watch_requires_setup_and_reaction_context():
    alert = _alert("RNA", 45, 80, "WATCH", "POSITIVE", "CONFIRMED")
    assert alert_action(alert) == "WATCH"
    assert alert_action(_alert("RNA", 45, 80, "WATCH")) == "SILENT"


def test_deduplicates_same_source_url_and_keeps_best_alert():
    low = _alert("SMMT", 100, 52, "CRITICAL")
    high = _alert("SMMT", 100, 54, "CRITICAL")
    for item in (low, high):
        item.update({
            "program": "ivonescimab",
            "title": "SEC 8-K — Summit Therapeutics (SMMT)",
            "url": "https://www.sec.gov/Archives/edgar/data/example/8k.htm",
        })
    selected = select_intelligent_alerts([low, high])
    assert len(selected) == 1
    assert selected[0]["trading_setup_score"] == 54


def test_same_title_different_setup_is_collapsed():
    first = _alert("SMMT", 100, 52, "CRITICAL")
    second = _alert("SMMT", 100, 54, "CRITICAL")
    first.update({"program": "ivonescimab", "title": "SEC 8-K — Summit Therapeutics (SMMT)"})
    second.update({"program": "ivonescimab", "title": "SEC 8-K — Summit Therapeutics (SMMT)"})
    selected = select_intelligent_alerts([first, second])
    assert len(selected) == 1
    assert selected[0]["trading_setup_score"] == 54


def test_different_headlines_remain_separate_events():
    first = _alert("SMMT", 100, 52, "CRITICAL")
    second = _alert("SMMT", 100, 54, "CRITICAL")
    first.update({"program": "ivonescimab", "title": "Phase 3 positive results"})
    second.update({"program": "ivonescimab", "title": "FDA approval announcement"})
    selected = select_intelligent_alerts([first, second])
    assert len(selected) == 2


def test_silent_alerts_are_filtered():
    selected = select_intelligent_alerts([_alert("SVRA", 20, 30, "LOW")])
    assert selected == []


def test_telegram_shows_reaction_even_without_available_status():
    alert = _alert("SMMT", 100, 69, "CRITICAL", "STRONG POSITIVE", "CONFIRMED")
    alert["market_reaction"] = {"reaction_status": "UNAVAILABLE", "reaction_5m_pct": 3.05, "reaction_15m_pct": 2.29}
    message = format_catalyst_alert(alert)
    assert "5m +3.05%" in message
    assert "15m +2.29%" in message
    assert "MARKET REACTION: UNAVAILABLE" not in message


def test_telegram_shows_catalyst_confirmation():
    alert = _alert("IONS", 100, 54, "CRITICAL")
    alert["catalyst_confirmation_score"] = 0
    alert["catalyst_confirmation"] = "UNCONFIRMED"
    message = format_catalyst_alert(alert)
    assert "🧠 CONFIRMATION" in message
    assert "0/100 — UNCONFIRMED" in message


def test_telegram_shows_confirmed_catalyst_confirmation():
    alert = _alert("SMMT", 100, 69, "CRITICAL", "STRONG POSITIVE", "CONFIRMED")
    alert["catalyst_confirmation_score"] = 82
    alert["catalyst_confirmation"] = "CONFIRMED"
    message = format_catalyst_alert(alert)
    assert "🧠 CONFIRMATION" in message
    assert "82/100 — CONFIRMED" in message


if __name__ == "__main__":
    test_critical_is_immediate()
    test_expired_is_silent_even_if_priority_is_critical()
    test_high_strong_reaction_is_immediate()
    test_high_without_strong_reaction_is_fast()
    test_watch_requires_setup_and_reaction_context()
    test_deduplicates_same_source_url_and_keeps_best_alert()
    test_same_title_different_setup_is_collapsed()
    test_different_headlines_remain_separate_events()
    test_silent_alerts_are_filtered()
    test_telegram_shows_reaction_even_without_available_status()
    test_telegram_shows_catalyst_confirmation()
    test_telegram_shows_confirmed_catalyst_confirmation()
    print("✅ Telegram intelligence tests passed")
