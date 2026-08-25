def build_scan_report(
    companies,
    total_trials,
    changes,
    errors
):
    lines = [
        "🧬 PHARMA RADAR — SCAN",
        "",
        f"🏢 Companies: {companies}",
        f"🔬 Trials found: {total_trials}",
        f"🔄 Changes detected: {len(changes)}",
        f"❌ Errors: {len(errors)}",
        "",
    ]

    if errors:
        lines.append("⚠️ SEARCH ERRORS")
        for error in errors[:10]:
            lines.append(
                f"• {error['ticker']} — {error['program']}"
            )
        lines.append("")

    if changes:
        lines.append("🚨 CHANGES")
        for change in changes[:10]:
            lines.append(
                f"• {change['ticker']} — "
                f"{change['program']} — "
                f"{change['nct_id']}"
            )
    else:
        lines.append("🟢 No changes detected")

    lines.extend([
        "",
        "Status: CLEAN" if not changes else "Status: REVIEW"
    ])

    return "\n".join(lines)
