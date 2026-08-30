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
from scanner.telegram import (
    send_telegram,
    send_catalyst_alerts,
)


# ============================================
# BUILD SUMMARY
# ============================================

def build_summary(result):
    """
    Costruisce il messaggio di riepilogo
    della scansione Pharma Radar.
    """

    alerts = result.get(
        "alerts",
        []
    )

    errors = result.get(
        "errors",
        []
    )

    detected_changes = result.get(
        "detected_changes",
        []
    )

    lines = [
        "🧬 PHARMA RADAR — SCAN",
        "",
        f"🏢 Companies: {result.get('companies', 0)}",
        f"🔬 Trials found: {result.get('total_trials', 0)}",
        f"🎯 Relevant trials: {result.get('relevant_trials', 0)}",
        f"🧹 Filtered out: {result.get('filtered_trials', 0)}",
        f"🔄 Changes detected: {len(detected_changes)}",
        f"🚨 Alerts: {len(alerts)}",
        f"❌ Errors: {len(errors)}",
        "",
    ]

    # ========================================
    # ALERT SUMMARY
    # ========================================

    if alerts:

        lines.append(
            "🚨 CATALYST ALERTS"
        )

        lines.append("")

        for alert in alerts:

            event = alert.get(
                "event",
                {}
            )

            if not isinstance(event, dict):
                event = {}

            lines.append(
                f"• {alert.get('ticker', 'UNKNOWN')} "
                f"— {alert.get('program', 'UNKNOWN')}"
            )

            lines.append(
                f"  {alert.get('nct_id', 'UNKNOWN')}"
            )

            lines.append(
                f"  {event.get('type', 'UNKNOWN')} "
                f"— {event.get('subtype', '')}"
            )

            lines.append(
                f"  🎯 Score: "
                f"{event.get('score', 0)}/100 "
                f"— {event.get('label', 'LOW')}"
            )

            lines.append("")

    else:

        # IMPORTANT:
        # Manteniamo questa stringa esattamente
        # come richiesta dai test esistenti.

        lines.append(
            "🟢 No catalyst alerts"
        )

        lines.append("")

    # ========================================
    # ERRORS
    # ========================================

    if errors:

        lines.append(
            "❌ ERRORS"
        )

        for error in errors:

            lines.append(
                f"• {error.get('ticker', 'UNKNOWN')} "
                f"— {error.get('program', 'UNKNOWN')}"
            )

            if error.get("error"):

                lines.append(
                    f"  {error.get('error')}"
                )

        lines.append("")

    # ========================================
    # STATUS
    # ========================================

    if alerts:

        lines.append(
            "Status: REVIEW"
        )

    elif errors:

        lines.append(
            "Status: WARNING"
        )

    else:

        lines.append(
            "Status: CLEAN"
        )

    return "\n".join(
        lines
    )


# ============================================
# SEND ALERTS
# ============================================

def send_alerts(result):
    """
    Invia i catalyst alert individualmente.

    Se non ci sono alert non viene effettuata
    alcuna chiamata Telegram.
    """

    alerts = result.get(
        "alerts",
        []
    )

    if not alerts:
        return []

    return send_catalyst_alerts(
        alerts
    )


# ============================================
# MAIN
# ============================================

def main():
    """
    Esegue una scansione completa di Pharma Radar.
    """

    print(
        "Starting Pharma Radar..."
    )

    result = scan()

    summary = build_summary(
        result
    )

    print()
    print(summary)

    # ========================================
    # TELEGRAM SUMMARY
    # ========================================

    send_telegram(
        summary
    )

    # ========================================
    # TELEGRAM CATALYST ALERTS
    # ========================================

    send_alerts(
        result
    )


# ============================================
# ENTRY POINT
# ============================================

if __name__ == "__main__":

    main()