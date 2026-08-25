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

    # Errori
    if errors:
        lines.append("⚠️ SEARCH ERRORS")

        for error in errors[:10]:
            lines.append(
                f"• {error['ticker']} — "
                f"{error['program']}"
            )
            lines.append(
                f"  {error['error']}"
            )

        lines.append("")

    # Nuovi trial
    new_trials = [
        change
        for change in changes
        if change.get("type") == "NEW_TRIAL"
    ]

    if new_trials:
        lines.append("🆕 NEW TRIALS")

        for change in new_trials[:10]:
            trial = change["trial"]

            lines.append(
                f"• {change['ticker']} — "
                f"{change['program']}"
            )

            lines.append(
                f"  {change['nct_id']} — "
                f"{trial.get('status', 'UNKNOWN')}"
            )

            if trial.get("title"):
                lines.append(
                    f"  {trial['title']}"
                )

            if trial.get("sponsor"):
                lines.append(
                    f"  Sponsor: {trial['sponsor']}"
                )

        lines.append("")

    # Trial aggiornati
    updates = [
        change
        for change in changes
        if change.get("type") == "UPDATE"
    ]

    if updates:
        lines.append("🔄 TRIAL UPDATES")

        for change in updates[:10]:

            lines.append(
                f"• {change['ticker']} — "
                f"{change['program']}"
            )

            lines.append(
                f"  {change['nct_id']}"
            )

            for field, values in change[
                "changes"
            ].items():

                lines.append(
                    f"  {field}: "
                    f"{values['old']} → "
                    f"{values['new']}"
                )

        lines.append("")

    # Trial pertinenti
    if relevant_details:
        lines.append("🎯 RELEVANT TRIALS")

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

    # Stato finale
    if errors:
        status = "WARNING"

    elif changes:
        status = "REVIEW"

    else:
        status = "CLEAN"

    lines.extend([
        "🟢 Scan completed",
        "",
        f"Status: {status}"
    ])

    return "\n".join(lines)
