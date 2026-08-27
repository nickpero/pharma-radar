from scanner.trial_scanner import scan
from scanner.telegram import (
    send_telegram,
    send_catalyst_alerts,
)


# ============================================
# BUILD SUMMARY
# ============================================

def build_summary(result):

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
        f"🏢 Companies: {result['companies']}",
        f"🔬 Trials found: {result['total_trials']}",
        f"🎯 Relevant trials: {result['relevant_trials']}",
        f"🧹 Filtered out: {result['filtered_trials']}",
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
