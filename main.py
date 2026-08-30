"""
Pharma Radar — Main

Orchestratore principale del Pharma Radar.

Pipeline:

Clinical Trials
    ↓
Catalyst
    ↓
Score
    ↓
Trading Intelligence
    ↓
Telegram

FDA News
    ↓
FDA Catalyst
    ↓
FDA Score
    ↓
Trading Intelligence
    ↓
Telegram

IMPORTANTE:
Il Radar non fornisce raccomandazioni di acquisto
o vendita. Determina la rilevanza e la priorità
operativa degli eventi.
"""


from scanner.trial_scanner import scan

from scanner.telegram import (
    send_telegram,
    send_catalyst_alerts,
)

from scanner.fda_news import (
    build_fda_news_item,
    filter_fda_catalysts,
)

from scanner.fda_catalyst import (
    build_relevant_fda_catalysts,
)

from scanner.fda_score import (
    score_fda_events,
)

from scanner.trading_intelligence import (
    enrich_trading_events,
)


# ============================================
# FDA NEWS INPUT
# ============================================

def process_fda_news(news_items):
    """
    Processa una lista di FDA News Items.

    Pipeline:

    FDA News
        ↓
    FDA Catalyst
        ↓
    FDA Score
        ↓
    Trading Intelligence
    """

    if not news_items:
        return []

    # ----------------------------------------
    # Build FDA News Items
    # ----------------------------------------

    normalized_news = []

    for item in news_items:

        if not isinstance(item, dict):
            continue

        news = build_fda_news_item(
            title=item.get(
                "title",
                ""
            ),
            summary=item.get(
                "summary",
                ""
            ),
            url=item.get(
                "url"
            ),
            published_at=item.get(
                "published_at"
            ),
        )

        normalized_news.append(
            news
        )

    # ----------------------------------------
    # Filter relevant FDA news
    # ----------------------------------------

    relevant_news = filter_fda_catalysts(
        normalized_news
    )

    if not relevant_news:
        return []

    # ----------------------------------------
    # Build FDA catalysts
    # ----------------------------------------

    catalysts = build_relevant_fda_catalysts(
        relevant_news
    )

    if not catalysts:
        return []

    # ----------------------------------------
    # FDA scoring
    # ----------------------------------------

    scored_events = score_fda_events(
        catalysts
    )

    # ----------------------------------------
    # Trading Intelligence
    # ----------------------------------------

    trading_events = enrich_trading_events(
        scored_events
    )

    return trading_events


# ============================================
# BUILD FDA SUMMARY
# ============================================

def build_fda_summary(events):
    """
    Costruisce il riepilogo Telegram
    degli eventi FDA.
    """

    if not events:

        return (
            "🏛️ PHARMA RADAR — FDA\n\n"
            "🟢 No FDA catalyst alerts"
        )

    lines = [
        "🏛️ PHARMA RADAR — FDA",
        "",
        f"🚨 FDA Catalysts: {len(events)}",
        "",
    ]

    for event in events:

        subtype = event.get(
            "subtype",
            "FDA_UPDATE"
        )

        score = event.get(
            "score",
            0
        )

        label = event.get(
            "label",
            "LOW"
        )

        impact = event.get(
            "trading_impact",
            "LOW"
        )

        urgency = event.get(
            "urgency",
            "LOW"
        )

        title = event.get(
            "title",
            ""
        )

        lines.append(
            f"🚨 {subtype}"
        )

        if title:

            lines.append(
                f"📰 {title}"
            )

        lines.append(
            f"🎯 Score: {score}/100"
        )

        lines.append(
            f"🏷 Label: {label}"
        )

        lines.append(
            f"💹 Trading Impact: {impact}"
        )

        lines.append(
            f"⚡ Urgency: {urgency}"
        )

        if event.get("url"):

            lines.append(
                f"🔗 {event['url']}"
            )

        lines.append("")

    return "\n".join(
        lines
    )


# ============================================
# BUILD SUMMARY
# ============================================

def build_summary(
    result,
    fda_events=None
):

    fda_events = fda_events or []

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
        f"🚨 Clinical Alerts: {len(alerts)}",
        f"🏛️ FDA Catalysts: {len(fda_events)}",
        f"❌ Errors: {len(errors)}",
        "",
    ]

    # ========================================
    # CLINICAL ALERT SUMMARY
    # ========================================

    if alerts:

        lines.append(
            "🚨 CLINICAL CATALYST ALERTS"
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
            "🟢 No clinical catalyst alerts"
        )

        lines.append("")

    # ========================================
    # FDA SUMMARY
    # ========================================

    if fda_events:

        lines.append(
            "🏛️ FDA CATALYSTS"
        )

        lines.append("")

        for event in fda_events:

            lines.append(
                f"• {event.get('subtype', 'FDA_UPDATE')}"
            )

            lines.append(
                f"  🎯 Score: "
                f"{event.get('score', 0)}/100 "
                f"— {event.get('label', 'LOW')}"
            )

            lines.append(
                f"  💹 Impact: "
                f"{event.get('trading_impact', 'LOW')}"
            )

            lines.append(
                f"  ⚡ Urgency: "
                f"{event.get('urgency', 'LOW')}"
            )

            lines.append("")

    else:

        lines.append(
            "🟢 No FDA catalyst alerts"
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

    if alerts or fda_events:

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
# SEND CLINICAL ALERTS
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
# SEND FDA ALERTS
# ============================================

def send_fda_alerts(events):

    if not events:
        return None

    message = build_fda_summary(
        events
    )

    return send_telegram(
        message
    )


# ============================================
# MAIN
# ============================================

def main():

    print(
        "Starting Pharma Radar..."
    )

    # ========================================
    # CLINICAL TRIAL SCAN
    # ========================================

    result = scan()

    # ========================================
    # FDA NEWS
    # ========================================

    # Il feed reale FDA verrà collegato
    # nel modulo FDA Feed dedicato.
    #
    # Per ora la pipeline accetta una lista
    # di news già recuperate.

    fda_news = []

    fda_events = process_fda_news(
        fda_news
    )

    # ========================================
    # SUMMARY
    # ========================================

    summary = build_summary(
        result,
        fda_events
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
    # CLINICAL CATALYST ALERTS
    # ========================================

    send_alerts(
        result
    )

    # ========================================
    # FDA CATALYST ALERTS
    # ========================================

    send_fda_alerts(
        fda_events
    )


# ============================================
# ENTRY POINT
# ============================================

if __name__ == "__main__":

    main()