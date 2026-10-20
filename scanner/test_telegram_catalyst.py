from datetime import datetime, timezone

from scanner.telegram import send_catalyst_alert
from scanner.telegram_intelligence import select_intelligent_alerts


def main():
    # This synthetic event is deliberately labelled TEST in the delivered
    # message. It exercises the production qualification gate and Telegram API,
    # but it is not a real catalyst and must never be treated as trading news.
    now = datetime.now(timezone.utc).isoformat()
    candidate = {
        "ticker": "TEST",
        "company": "Synthetic Test Company",
        "program": "Synthetic test program",
        "source": "FDA",
        "source_type": "PRIMARY_REGULATORY",
        "first_published_at": now,
        "published_at": now,
        "event_date": now,
        "title": "🧪 TEST ONLY — synthetic qualified alert; NOT a real catalyst",
        "alert_priority": 95,
        "alert_tier": "CRITICAL",
        "trading_setup_score": 85,
        "trading_window": "NEXT_24H",
        "event": {
            "type": "FDA_EVENT",
            "subtype": "FDA_APPROVAL",
            "severity": "HIGH",
            "direction": "CATALYST",
            "score": 95,
            "label": "CRITICAL",
            "published_at": now,
            "title": "🧪 TEST ONLY — synthetic qualified alert; NOT a real catalyst",
        },
        "catalyst_explainer": {
            "why_it_matters": "TEST ONLY: validates qualification and Telegram delivery. No real company event."
        },
    }

    selected = select_intelligent_alerts([candidate])
    if len(selected) != 1:
        raise RuntimeError(f"Expected one qualified test alert, got {len(selected)}")
    alert = selected[0]
    if alert.get("telegram_action") not in {"IMMEDIATE", "FAST", "WATCH"}:
        raise RuntimeError(f"Test alert was not qualified for delivery: {alert.get('telegram_action')}")
    if alert.get("quality_gate") != "QUALITY_GATE_PASS":
        raise RuntimeError(f"Test alert failed the primary-source/freshness gate: {alert.get('quality_gate')}")

    print("Sending clearly labelled synthetic TEST alert through the production qualification gate...")
    result = send_catalyst_alert(alert)
    if not isinstance(result, dict) or result.get("ok") is not True or not result.get("result", {}).get("message_id"):
        raise RuntimeError(f"Telegram did not confirm delivery: {result!r}")

    print(f"Telegram API confirmed test message_id={result['result']['message_id']}")
    print("🟢 QUALIFIED CATALYST → TELEGRAM TEST PASSED")
    print("IMPORTANT: synthetic test only; this is not a real catalyst or investment signal.")


if __name__ == "__main__":
    main()
