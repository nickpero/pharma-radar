from scanner.trial_scanner import scan
from scanner.telegram import send_telegram, format_catalyst_alert


def build_summary(result):

    lines = [
        "🧬 PHARMA RADAR — SCAN",
        "",
        f"🏢 Companies: {result['companies']}",
        f"🔬 Trials found: {result['total_trials']}",
        f"🎯 Relevant trials: {result['relevant_trials']}",
        f"🧹 Filtered out: {result['filtered_trials']}",
        f"🚨 Alerts: {len(result['alerts'])}",
        f"❌ Errors: {len(result['errors'])}",
        "",
    ]

    if result["alerts"]:

        lines.append(
            "🚨 CATALYST ALERTS"
        )

        lines.append("")

        for alert in result["alerts"]:

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

    if result["errors"]:

        lines.append(
            "❌ ERRORS"
        )

        for error in result["errors"]:

            lines.append(
                f"• {error.get('ticker', 'UNKNOWN')} "
                f"— {error.get('program', 'UNKNOWN')}"
            )

        lines.append("")

    if result["alerts"]:

        lines.append(
            "Status: REVIEW"
        )

    elif result["errors"]:

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


def send_alerts(result):

    alerts = result.get(
        "alerts",
        []
    )

    for alert in alerts:

        message = format_catalyst_alert(
            alert
        )

        send_telegram(
            message
        )


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

    # =====================================
    # TELEGRAM SUMMARY
    # =====================================

    send_telegram(
        summary
    )

    # =====================================
    # TELEGRAM CATALYST ALERTS
    # =====================================

    send_alerts(
        result
    )


if __name__ == "__main__":

    main()
