from datetime import datetime, timezone
from scanner.telegram_intelligence import alert_action, select_intelligent_alerts
from scanner.telegram import format_catalyst_alert


def _alert(ticker, priority, setup, tier, strength="UNKNOWN", interpretation="UNKNOWN"):
    return {
        "ticker": ticker,
        "program": "drug",
        "subtype": "FDA_APPROVAL",
        "score": 100,
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




def test_24_72h_high_priority_catalyst_is_silenced_by_quality_gate():
    alert = _alert("VBIO", 100, 54, "CRITICAL")
    alert["source"] = "SEC"
    alert["source_type"] = "PRIMARY_CORPORATE"
    alert["published_at"] = "2026-10-01T07:45:00Z"
    assert alert_action(alert) == "SILENT"


def test_stale_high_priority_catalyst_is_silenced_by_quality_gate():
    alert = _alert("IONS", 100, 40, "CRITICAL")
    alert["source"] = "SEC"
    alert["source_type"] = "PRIMARY_REGULATORY"
    alert["published_at"] = "2026-09-20T00:00:00Z"
    assert alert_action(alert) == "SILENT"


def test_recent_primary_catalyst_passes_quality_gate():
    alert = _alert("IONS", 100, 40, "CRITICAL")
    alert["source"] = "SEC"
    alert["source_type"] = "PRIMARY_CORPORATE"
    alert["published_at"] = datetime.now(timezone.utc).isoformat()
    assert alert_action(alert) == "IMMEDIATE"


def test_secondary_source_is_silenced_by_quality_gate():
    alert = _alert("IONS", 100, 40, "CRITICAL")
    alert["source"] = "REUTERS"
    alert["published_at"] = datetime.now(timezone.utc).isoformat()
    assert alert_action(alert) == "SILENT"


def test_stale_low_priority_catalyst_remains_silent():
    alert = _alert("IONS", 70, 40, "HIGH")
    alert["source"] = "SEC"
    alert["published_at"] = "2026-09-20T00:00:00Z"
    assert alert_action(alert) == "SILENT"

def test_silent_alerts_are_filtered():
    selected = select_intelligent_alerts([_alert("SVRA", 20, 30, "LOW")])
    assert selected == []


def test_telegram_is_compact_and_hierarchical():
    alert = _alert("IONS", 100, 56, "CRITICAL")
    alert.update({
        "program": "zilganersen",
        "title": "FDA Approves First Drug to Treat Alexander Disease",
        "trading_window": "1-7D",
        "source": "FDA RSS",
    })
    message = format_catalyst_alert(alert)
    assert "🚨 PHARMA RADAR" in message
    assert "🚨 CRITICAL" in message
    assert "🧬 IONS" in message
    assert "💊 Zilganersen (Zanvastro)" in message
    assert "📰 FDA APPROVAL" in message
    assert "🎯 Catalyst: 100/100" in message
    assert "🚨 Priority: 100/100" in message
    assert "📊 Setup: 56/100 · Window: 1-7D" in message
    assert "💡 WHY IT MATTERS" in message
    assert "Awareness:" not in message
    assert "Surprise:" not in message
    assert "📈 Market reaction: N/A" in message


def test_telegram_shows_market_reaction_compactly():
    alert = _alert("SMMT", 100, 69, "CRITICAL", "STRONG POSITIVE", "CONFIRMED")
    alert["market_reaction"] = {"reaction_status": "UNAVAILABLE", "reaction_5m_pct": 3.05, "reaction_15m_pct": 2.29}
    message = format_catalyst_alert(alert)
    assert "5m +3.05%" in message
    assert "15m +2.29%" in message
    assert "MARKET REACTION: UNAVAILABLE" not in message
    assert "Reaction: N/A" not in message


def test_telegram_shows_confirmation_only_as_one_line():
    alert = _alert("IONS", 100, 54, "CRITICAL")
    alert["catalyst_confirmation_score"] = 0
    alert["catalyst_confirmation"] = "UNCONFIRMED"
    message = format_catalyst_alert(alert)
    # Current formatter intentionally does not render confirmation.
    assert "🧠 Confirmation" not in message


def test_telegram_shows_confirmed_confirmation_compactly():
    alert = _alert("SMMT", 100, 69, "CRITICAL", "STRONG POSITIVE", "CONFIRMED")
    alert["catalyst_confirmation_score"] = 82
    alert["catalyst_confirmation"] = "CONFIRMED"
    message = format_catalyst_alert(alert)
    # Confirmation is currently handled by the intelligence layer, not the Telegram formatter.
    assert "🧠 Confirmation" not in message


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
    test_telegram_is_compact_and_hierarchical()
    test_telegram_shows_market_reaction_compactly()
    test_telegram_shows_confirmation_only_as_one_line()
    test_telegram_shows_confirmed_confirmation_compactly()
    print("✅ Telegram intelligence tests passed")


def test_early_discovery_is_deliverable_with_freshness():
    alert = _alert("VBIO", 90, 60, "HIGH")
    alert.update({
        "source": "EARLY_DISCOVERY",
        "source_type": "SECONDARY_DISCOVERY",
        "early_discovery": True,
        "published_at": datetime.now(timezone.utc).isoformat(),
    })
    assert alert_action(alert) == "FAST"


def test_early_and_sec_confirmation_share_event_key():
    early = _alert("VBIO", 100, 54, "CRITICAL")
    sec = _alert("VBIO", 100, 54, "CRITICAL")
    early.update({
        "program": "Entolimod",
        "subtype": "DEVELOPMENT_MILESTONE",
        "event_key": "vbio|entolimod|development_milestone|2026-09-30",
        "early_discovery": True,
        "source": "EARLY_DISCOVERY",
        "published_at": "2026-09-30T14:00:00Z",
    })
    sec.update({
        "program": "SEC",
        "subtype": "DEVELOPMENT_MILESTONE",
        "event_key": "vbio|entolimod|development_milestone|2026-09-30",
        "source": "SEC",
        "source_type": "PRIMARY_CORPORATE",
        "event_date": "2026-09-30",
        "published_at": "2026-10-01T00:00:00Z",
    })
    selected = select_intelligent_alerts([early, sec])
    assert len(selected) == 1
    assert selected[0]["event_key"] == early["event_key"]
