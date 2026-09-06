"""
Pharma Radar — Main

Entry point principale di Pharma Radar.

Gestisce:
- scansione Clinical Trials
- costruzione del summary
- invio del summary su Telegram
- invio dei catalyst alert
"""

from scanner.trial_scanner import scan
from scanner.telegram import send_telegram, send_catalyst_alerts


def build_summary(result):
    """Costruisce il messaggio di riepilogo della scansione Pharma Radar."""
    alerts = result.get("alerts", [])
    errors = result.get("errors", [])
    detected_changes = result.get("detected_changes", [])

    lines = [
        "🧬 PHARMA RADAR — SCAN",
        "",
        f"🏢 Companies: {result.get('companies', 0)}",
        f"🔬 Trials found: {result.get('total_trials', 0)}",
        f"🎯 Relevant trials: {result.get('relevant_trials', 0)}",
        f"🧹 Filtered out: {result.get('filtered_trials', 0)}",
        f"🔄 Changes detected: {len(detected_changes)}",
        f"📰 FDA news: {len(result.get('fda_news', []))}",
        f"🚨 Alerts: {len(alerts)}",
        f"❌ Errors: {len(errors)}",
        "",
    ]

    if alerts:
        lines.extend(["🚨 CATALYST ALERTS", ""])

        for alert in alerts:
            event = alert.get("event", {})
            if not isinstance(event, dict):
                event = {}

            tier = alert.get("alert_tier", event.get("alert_tier", "LOW"))
            priority = alert.get("alert_priority", event.get("alert_priority", 0))

            lines.append(
                f"• {alert.get('ticker', 'UNKNOWN')} — "
                f"{alert.get('program', 'UNKNOWN')}"
            )
            lines.append(f"  {alert.get('nct_id', 'UNKNOWN')}")
            lines.append(
                f"  {event.get('type', 'UNKNOWN')} — "
                f"{event.get('subtype', '')}"
            )
            lines.append(
                f"  🎯 Alert Priority: {priority}/100 — {tier}"
            )
            lines.append(
                f"  Score: {event.get('score', 0)}/100 — "
                f"{event.get('label', 'LOW')}"
            )
            lines.append("")
    else:
        lines.extend(["🟢 No catalyst alerts", ""])

    if errors:
        lines.append("❌ ERRORS")
        for error in errors:
            lines.append(
                f"• {error.get('ticker', 'UNKNOWN')} — "
                f"{error.get('program', 'UNKNOWN')}"
            )
            if error.get("error"):
                lines.append(f"  {error.get('error')}")
        lines.append("")

    if alerts:
        lines.append("Status: REVIEW")
    elif errors:
        lines.append("Status: WARNING")
    else:
        lines.append("Status: CLEAN")

    return "\n".join(lines)


def send_alerts(result):
    """Invia i catalyst alert individualmente, già ordinati per priorità."""
    alerts = result.get("alerts", [])
    if not alerts:
        return []
    return send_catalyst_alerts(alerts)


def main():
    """Esegue una scansione completa di Pharma Radar."""
    print("Starting Pharma Radar...")
    result = scan()
    summary = build_summary(result)
    print()
    print(summary)
    send_telegram(summary)
    send_alerts(result)


if __name__ == "__main__":
    main()
