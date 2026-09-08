"""Pharma Radar — Main entry point."""

from scanner.trial_scanner import scan
from scanner.telegram import send_telegram, send_catalyst_alerts
from scanner.telegram_intelligence import select_intelligent_alerts
from scanner.pharma_email import send_pharma_intelligence_emails, email_is_configured


def _reaction(alert):
    return alert.get("market_reaction") or alert.get("reaction") or {}


def _reaction_line(alert):
    reaction = _reaction(alert)
    values = [("1m", reaction.get("reaction_1m_pct")), ("5m", reaction.get("reaction_5m_pct")), ("15m", reaction.get("reaction_15m_pct")), ("30m", reaction.get("reaction_30m_pct")), ("60m", reaction.get("reaction_60m_pct"))]
    available = [f"{label} {float(value):+.2f}%" for label, value in values if value is not None]
    return " | ".join(available) if available else "N/A"


def _alert_summary_line(alert):
    event = alert.get("event", {}) if isinstance(alert.get("event", {}), dict) else {}
    ticker = str(alert.get("ticker", "UNKNOWN")).upper()
    program = alert.get("program", "UNKNOWN")
    subtype = event.get("subtype", alert.get("subtype", "UNKNOWN"))
    priority = alert.get("alert_priority", event.get("alert_priority", 0))
    tier = alert.get("alert_tier", event.get("alert_tier", "LOW"))
    setup = alert.get("trading_setup_score", event.get("trading_setup_score", 0))
    window = alert.get("trading_window", event.get("trading_window", "UNKNOWN"))
    title = alert.get("title") or event.get("title") or "Catalyst detected"
    score = event.get("score", alert.get("score", 0))
    label = event.get("label", alert.get("label", "LOW"))
    return [
        f"🧬 {ticker} · {program}",
        f"📰 {subtype}",
        f"{title}",
        f"🎯 Catalyst {score} · {label}",
        f"🚨 Priority {priority} · {tier}",
        f"📊 Setup {setup} · {window}",
        f"📈 Reaction {_reaction_line(alert)}",
    ]


def build_summary(result):
    alerts = result.get("alerts", [])
    errors = result.get("errors", [])
    detected_changes = result.get("detected_changes", [])
    intelligent_alerts = select_intelligent_alerts(alerts)
    lines = [
        "🧬 PHARMA RADAR — SCAN",
        "",
        f"🏢 {result.get('companies', 0)} companies · 🔬 {result.get('total_trials', 0)} trials",
        f"🎯 {result.get('relevant_trials', 0)} relevant · 🧹 {result.get('filtered_trials', 0)} filtered",
        f"📰 {len(result.get('fda_news', []))} FDA news · 🔄 {len(detected_changes)} changes",
        f"🚨 {len(intelligent_alerts)} actionable alert(s)",
    ]
    if errors:
        lines.append(f"❌ {len(errors)} error(s)")
    lines.extend(["", "━━━━━━━━━━━━━━━━━━", ""])

    if intelligent_alerts:
        lines.append(f"🚨 {len(intelligent_alerts)} PRIORITY ALERT" if len(intelligent_alerts) == 1 else f"🚨 {len(intelligent_alerts)} PRIORITY ALERTS")
        lines.append("")
        for index, alert in enumerate(intelligent_alerts):
            lines.extend(_alert_summary_line(alert))
            if index < len(intelligent_alerts) - 1:
                lines.extend(["", "──────────────", ""])
    else:
        lines.append("🟢 NO ACTIONABLE CATALYSTS")

    if alerts and len(intelligent_alerts) < len(alerts):
        lines.extend(["", f"ℹ️ {len(alerts) - len(intelligent_alerts)} alert(s) suppressed"])

    if errors:
        lines.extend(["", "❌ ERRORS"])
        for error in errors:
            lines.append(f"• {error.get('ticker', 'UNKNOWN')} — {error.get('program', 'UNKNOWN')}: {error.get('error', '')}")

    lines.extend(["", "━━━━━━━━━━━━━━━━━━", "Status: REVIEW" if intelligent_alerts else "Status: WARNING" if errors else "Status: CLEAN"])
    return "\n".join(lines)


def send_alerts(result):
    alerts = select_intelligent_alerts(result.get("alerts", []))
    return send_catalyst_alerts(alerts) if alerts else []


def send_email_alerts(result):
    """Send Pharma Intelligence emails for CRITICAL/HIGH catalyst alerts."""
    alerts = select_intelligent_alerts(result.get("alerts", []))
    return send_pharma_intelligence_emails(alerts) if alerts else 0


def main():
    print("Starting Pharma Radar...")
    result = scan()
    summary = build_summary(result)
    print(); print(summary)
    send_telegram(summary)
    send_alerts(result)
    sent = send_email_alerts(result)
    print(f"Pharma Intelligence emails sent: {sent}")


if __name__ == "__main__":
    main()
