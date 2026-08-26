def format_catalyst_event(event):
    event_type = event.get("type", "UNKNOWN")
    severity = event.get("severity", "LOW")
    direction = event.get("direction", "UNKNOWN")

    severity_icons = {
        "HIGH": "🔴",
        "MEDIUM": "🟠",
        "LOW": "🟢"
    }

    icon = severity_icons.get(
        severity,
        "⚪"
    )

    if event_type == "STATUS_CHANGE":
        description = "Status change"

    elif event_type == "DATE_CHANGE":
        description = "Clinical date change"

    elif event_type == "ENROLLMENT_CHANGE":
        description = "Enrollment change"

    elif event_type == "PHASE_CHANGE":
        description = "Phase change"

    elif event_type == "PROTOCOL_CHANGE":
        description = "Protocol change"

    elif event_type == "NEW_TRIAL":
        description = "New clinical trial"

    else:
        description = "Clinical trial change"

    return (
        f"{icon} {description} "
        f"[{severity}] "
        f"{direction}"
    )


def build_scan_report(
    companies,
    total_trials,
    relevant_trials,
    filtered_trials,
    relevant_details,
    changes,
    errors
):
    lines = [
        "🧬 PHARMA RADAR — SCAN",
        "",
        f"🏢 Companies: {companies}",
        f"🔬 Trials found: {total_trials}",
        f"🎯 Relevant trials: {relevant_trials}",
        f"🧹 Filtered out: {filtered_trials}",
        f"🔄 Events detected: {len(changes)}",
        f"❌ Errors: {len(errors)}",
        ""
    ]

    # =================================
    # ERRORS
    # =================================

    if errors:

        lines.append("⚠️ SEARCH ERRORS")
        lines.append("")

        for error in errors[:10]:

            lines.append(
                f"• {error['ticker']} — "
                f"{error['program']}"
            )

            lines.append(
                f"  {error['error']}"
            )

        lines.append("")

    # =================================
    # CATALYST EVENTS
    # =================================

    if changes:

        lines.append("🚨 CATALYST EVENTS")
        lines.append("")

        for change in changes[:15]:

            lines.append(
                f"• {change['ticker']} — "
                f"{change['program']}"
            )

            lines.append(
                f"  {change['nct_id']}"
            )

            catalyst_events = change.get(
                "catalyst_events",
                []
            )

            for event in catalyst_events:

                lines.append(
                    f"  {format_catalyst_event(event)}"
                )

            # Dettaglio delle modifiche

            raw_changes = change.get(
                "changes",
                {}
            )

            for field, values in raw_changes.items():

                old_value = values.get(
                    "old"
                )

                new_value = values.get(
                    "new"
                )

                lines.append(
                    f"  {field}: "
                    f"{old_value} → "
                    f"{new_value}"
                )

            lines.append("")

    # =================================
    # RELEVANT TRIALS
    # =================================

    if relevant_details:

        lines.append(
            "🎯 RELEVANT TRIALS"
        )

        for detail in relevant_details[:15]:

            lines.append(
                f"• {detail['ticker']} — "
                f"{detail['program']}"
            )

            lines.append(
                f"  {detail['nct_id']} — "
                f"{detail['status']}"
            )

            if detail.get("title"):

                lines.append(
                    f"  {detail['title']}"
                )

        lines.append("")

    # =================================
    # FINAL STATUS
    # =================================

    if errors:
        status = "WARNING"

    elif changes:
        status = "REVIEW"

    else:
        status = "CLEAN"

    lines.append(
        "🟢 Scan completed"
    )

    lines.append("")

    lines.append(
        f"Status: {status}"
    )

    return "\n".join(lines)
