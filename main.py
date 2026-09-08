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
    if not available:
        return "  ⚡ Market reaction: UNAVAILABLE"
    return "  ⚡ Market reaction: " + " | ".join(available)


def build_summary(result):
    alerts = result.get("alerts", [])
    errors = result.get("errors", [])
    detected_changes = result.get("detected_changes", [])
    intelligent_alerts = select_intelligent_alerts(alerts)
    lines = [
        "🧬 PHARMA RADAR — SCAN", "",
        f"🏢 Companies: {result.get('companies', 0)}",
        f"🔬 Trials found: {result.get('total_trials', 0)}",
        f"🎯 Relevant trials: {result.get('relevant_trials', 0)}",
        f"🧹 Filtered out: {result.get('filtered_trials', 0)}",
        f"🔄 Changes detected: {len(detected_changes)}",
        f"📰 FDA news: {len(result.get('fda_news', []))}",
        f"🚨 Alerts: {len(alerts)}",
        f"🧠 Telegram intelligent alerts: {len(intelligent_alerts)}",
        f"📧 Pharma Intelligence email: {'READY' if email_is_configured() else 'NOT CONFIGURED'}",
        f"❌ Errors: {len(errors)}", "",
    ]
    if alerts:
        lines.extend(["🚨 CATALYST ALERTS", ""])
        for alert in alerts:
            event = alert.get("event", {}) if isinstance(alert.get("event", {}), dict) else {}
            tier = alert.get("alert_tier", event.get("alert_tier", "LOW"))
            priority = alert.get("alert_priority", event.get("alert_priority", 0))
            setup_score = alert.get("trading_setup_score", event.get("trading_setup_score", 0))
            window = alert.get("trading_window", event.get("trading_window", "UNKNOWN"))
            awareness = alert.get("market_awareness", event.get("market_awareness", "UNKNOWN"))
            surprise = alert.get("event_surprise", event.get("event_surprise", "UNKNOWN"))
            quality = alert.get("data_quality", event.get("data_quality", "LOW"))
            action = next((item.get("telegram_action") for item in intelligent_alerts if item.get("ticker") == alert.get("ticker") and item.get("program") == alert.get("program") and item.get("subtype") == alert.get("subtype")), None)
            price_change = alert.get("price_change_pct", event.get("price_change_pct"))
            volume_ratio = alert.get("volume_ratio", event.get("volume_ratio"))
            market_cap = alert.get("market_cap", event.get("market_cap"))
            short_interest = alert.get("short_interest_pct", event.get("short_interest_pct"))
            lines.append(f"• {alert.get('ticker', 'UNKNOWN')} — {alert.get('program', 'UNKNOWN')}")
            if alert.get("nct_id"):
                lines.append(f"  🧬 {alert['nct_id']}")
            if alert.get("title") or event.get("title"):
                lines.append(f"  📰 {alert.get('title') or event.get('title')}")
            lines.append(f"  {event.get('type', 'UNKNOWN')} — {event.get('subtype', '')}")
            lines.append(f"  🎯 Alert Priority: {priority}/100 — {tier}")
            if action:
                lines.append(f"  🧠 Telegram Action: {action}")
            lines.append(f"  Score: {event.get('score', 0)}/100 — {event.get('label', 'LOW')}")
            lines.append(f"  📊 Trading Intelligence: Setup {setup_score}/100 | Window {window} | Awareness {awareness} | Surprise {surprise} | Quality {quality}")
            lines.append(f"  ⚡ Reaction: {alert.get('reaction_strength', event.get('reaction_strength', 'UNKNOWN'))} | {alert.get('reaction_interpretation', event.get('reaction_interpretation', 'UNKNOWN'))}")
            lines.append(_reaction_line(alert))
            if price_change is not None:
                lines.append(f"  📈 Price: {float(price_change):+.2f}%")
            if volume_ratio is not None:
                lines.append(f"  📊 Volume: {float(volume_ratio):.1f}x 20d")
            if market_cap is not None:
                lines.append(f"  💰 Market Cap: ${float(market_cap) / 1_000_000:,.0f}M")
            if short_interest is not None:
                lines.append(f"  🩳 Short Interest: {float(short_interest):.1f}%")
            lines.append("")
    else:
        lines.extend(["🟢 No catalyst alerts", ""])
    if errors:
        lines.append("❌ ERRORS")
        for error in errors:
            lines.append(f"• {error.get('ticker', 'UNKNOWN')} — {error.get('program', 'UNKNOWN')}")
            if error.get("error"):
                lines.append(f"  {error.get('error')}")
        lines.append("")
    lines.append("Status: REVIEW" if alerts else "Status: WARNING" if errors else "Status: CLEAN")
    return "\n".join(lines)


def send_alerts(result):
    alerts = select_intelligent_alerts(result.get("alerts", []))
    return send_catalyst_alerts(alerts) if alerts else []


def send_email_alerts(result):
    """Send Pharma Intelligence emails for CRITICAL/HIGH catalyst alerts."""
    alerts = result.get("alerts", [])
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
