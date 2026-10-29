from datetime import datetime, timezone
import main
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
            "source": "SEC", "source_type": "PRIMARY_CORPORATE",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "event": {"type": "FDA_EVENT", "subtype": "FDA_APPROVAL", "score": 95, "label": "CRITICAL"},
        }],
        "errors": [],
    }
    message = build_summary(result)
    assert "🚨 PRIORITY ALERTS" in message
    assert "CAPR — deramiocel" in message
    assert "FDA_APPROVAL" in message
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
        "source": "SEC", "source_type": "PRIMARY_CORPORATE",
        "published_at": datetime.now(timezone.utc).isoformat(),
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


def test_degraded_source_summary_is_warning():
    result = {
        "companies": 82,
        "total_trials": 1103,
        "relevant_trials": 745,
        "filtered_trials": 358,
        "alerts": [],
        "errors": [],
        "source_diagnostics": {
            "EARLY_DISCOVERY": {"status": "OK", "count": 7},
            "EMA": {"status": "OK", "count": 11},
            "SEC": {"status": "DEGRADED_FALLBACK", "count": 12, "path": "proxy_fallback"},
        },
        "fda_news": [{}] * 30,
    }
    message = build_summary(result)
    assert "SEC=DEGRADED_FALLBACK(12)" in message
    assert "Source degradation detected" in message
    assert "Status: WARNING" in message
    assert "Status: CLEAN" not in message



def test_degraded_source_health_warning_sends_once(monkeypatch):
    sent_state = {}
    messages = []

    monkeypatch.setattr(main, "load_sent_alerts", lambda: dict(sent_state))
    monkeypatch.setattr(main, "save_sent_alerts", lambda state: sent_state.update(state))
    monkeypatch.setattr(main, "send_telegram", lambda message: messages.append(message) or {"ok": True})

    result = {
        "companies": 82,
        "alerts": [{"ticker": "UTHR"}],
        "fda_news": [{}] * 30,
        "source_diagnostics": {
            "SEC": {"status": "DEGRADED_FALLBACK", "count": 12, "path": "proxy_fallback"}
        },
    }
    assert main.send_source_health_alert_if_needed(result, actionable_alerts=[]) is True
    assert len(messages) == 1
    assert "PHARMA RADAR — AVVISO SULLA DISPONIBILITÀ DELLE FONTI" in messages[0]
    assert "SEC: DEGRADED_FALLBACK" in messages[0]
    assert "Questo è un avviso tecnico" in messages[0]
    assert "\\n" not in messages[0]
    assert main.send_source_health_alert_if_needed(result, actionable_alerts=[]) is False
    assert len(messages) == 1


def test_source_health_warning_is_not_suppressed_by_catalyst_alerts(monkeypatch):
    sent_state = {}
    messages = []
    monkeypatch.setattr(main, "load_sent_alerts", lambda: dict(sent_state))
    monkeypatch.setattr(main, "save_sent_alerts", lambda state: sent_state.update(state))
    monkeypatch.setattr(main, "send_telegram", lambda message: messages.append(message) or {"ok": True})
    result = {
        "companies": 82,
        "alerts": [{"ticker": "KYMR"}],
        "source_diagnostics": {"SEC": {"status": "DEGRADED_FALLBACK", "count": 12, "path": "proxy_fallback"}},
    }
    assert main.send_source_health_alert_if_needed(result, actionable_alerts=[{"ticker": "KYMR"}]) is True
    assert "Avvisi inviati in questa scansione: 1" in messages[0]
    assert "Copertura incompleta" in messages[0]


def test_source_health_warning_does_not_send_when_sources_are_healthy(monkeypatch):
    monkeypatch.setattr(main, "load_sent_alerts", lambda: {})
    monkeypatch.setattr(main, "send_telegram", lambda message: (_ for _ in ()).throw(AssertionError("unexpected Telegram send")))
    result = {"alerts": [], "source_diagnostics": {"EMA": {"status": "OK", "count": 5}}}
    assert main.send_source_health_alert_if_needed(result, actionable_alerts=[]) is False

if __name__ == "__main__":
    test_clean_summary()
    test_alert_summary_is_concise()
    test_duplicate_alerts_are_suppressed_in_summary()
    test_error_summary()
    print("✅ Main integration tests passed")
