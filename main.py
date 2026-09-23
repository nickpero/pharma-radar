"""Pharma Radar — Main entry point."""

from datetime import datetime, timezone

from scanner.trial_scanner import scan
from scanner.trading_intelligence_score import enrich_trading_intelligence_scores
from scanner.trading_intelligence_rule import enrich_trading_intelligence_rules
from scanner.catalyst_memory import record_events
from scanner.telegram import send_telegram, send_catalyst_alerts, send_divergence_alerts
from scanner.telegram_intelligence import select_intelligent_alerts, _dedup_key
from scanner.alert_state import load_sent_alerts, save_sent_alerts, filter_unsent, mark_sent
from scanner.pharma_email import send_pharma_intelligence_emails
from scanner.divergence_monitor import detect_divergences
from scanner.divergence_outcomes import track_divergence_outcomes
from scanner.data_quality_audit import audit_alerts
from scanner.data_quality_audit import audit_alerts
from scanner.data_quality_audit import audit_alerts
from scanner.data_quality_audit import audit_alerts


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
    ti = alert.get("trading_intelligence_score", "N/A")
    ti_label = alert.get("trading_intelligence_label", "")
    return [
        f"🧬 {ticker} · {program}", f"📰 {subtype}", title,
        f"🎯 Catalyst: {score}/100 · {label}", f"🚨 Priority: {priority}/100 · {tier}",
        f"📊 Setup: {setup}/100 · {window}", f"🧠 TI Score: {ti}/100 · {ti_label}",
        f"📈 Reaction: {_reaction_line(alert)}",
    ]


def build_summary(result, intelligent_alerts=None):
    alerts = result.get("alerts", [])
    errors = result.get("errors", [])
    detected_changes = result.get("detected_changes", [])
    if intelligent_alerts is None:
        intelligent_alerts = select_intelligent_alerts(alerts)

    qualified = sum(1 for alert in alerts if alert.get("trading_intelligence_qualified") is True)
    watched = sum(1 for alert in alerts if alert.get("trading_intelligence_watch") is True)

    lines = [
        "🧬 PHARMA RADAR — SCAN",
        "━━━━━━━━━━━━━━━━━━",
        f"🏢 Companies: {result.get('companies', 0)}",
        f"🔬 Trials: {result.get('total_trials', 0)}",
        f"🎯 Relevant: {result.get('relevant_trials', 0)}",
        f"📰 FDA news: {len(result.get('fda_news', []))}",
        f"🔄 Changes: {len(detected_changes)}",
        f"🧠 TI Qualified: {qualified}",
        f"👀 TI Watch: {watched}",
        "",
        f"🚨 NEW ACTIONABLE ALERTS: {len(intelligent_alerts)}",
    ]

    if errors:
        lines.append(f"❌ Errors: {len(errors)}")

    if intelligent_alerts:
        lines.extend([
            "", "━━━━━━━━━━━━━━━━━━", "",
            f"🚨 {len(intelligent_alerts)} NEW PRIORITY ALERT" if len(intelligent_alerts) == 1 else f"🚨 {len(intelligent_alerts)} NEW PRIORITY ALERTS",
            "",
        ])
        for index, alert in enumerate(intelligent_alerts):
            lines.extend(_alert_summary_line(alert))
            if index < len(intelligent_alerts) - 1:
                lines.extend(["", "──────────────", ""])
    else:
        lines.extend(["", "━━━━━━━━━━━━━━━━━━", "", "🟢 NO NEW ACTIONABLE CATALYSTS"])

    if errors:
        lines.extend(["", "❌ ERRORS"])
        for error in errors:
            lines.append(f"• {error.get('ticker', 'UNKNOWN')} — {error.get('program', 'UNKNOWN')}: {error.get('error', '')}")

    lines.extend(["", "━━━━━━━━━━━━━━━━━━"])
    return "\n".join(lines)


def _new_telegram_alerts(result):
    intelligent_alerts = select_intelligent_alerts(result.get("alerts", []))
    state = load_sent_alerts()
    return filter_unsent(intelligent_alerts, state, lambda alert: repr(_dedup_key(alert)))


def send_alerts(result, alerts=None):
    alerts = _new_telegram_alerts(result) if alerts is None else alerts
    if not alerts:
        return []
    responses = send_catalyst_alerts(alerts)
    state = load_sent_alerts()
    timestamp = datetime.now(timezone.utc).isoformat()
    mark_sent(alerts, state, lambda alert: repr(_dedup_key(alert)), timestamp)
    save_sent_alerts(state)
    return responses


def send_email_alerts(result):
    # Pharma Intelligence email is knowledge-first and intentionally independent
    # of Trading Intelligence qualification, market reaction, and TI score.
    alerts = result.get("alerts", [])
    return send_pharma_intelligence_emails(alerts) if alerts else 0


def _new_divergence_alerts(result):
    # Divergence monitoring also sees catalyst restatements that were suppressed
    # from NEW ACTIONABLE alerts; the market reaction remains useful context.
    divergences = detect_divergences(result.get("monitoring_alerts", result.get("alerts", [])))
    state = load_sent_alerts()
    today = datetime.now(timezone.utc).date().isoformat()
    fresh = []
    for item in divergences:
        key = repr(("DIVERGENCE_V1", today, item.get("ticker"), item.get("program")))
        if key not in state:
            item["_dedup_key"] = key
            fresh.append(item)
    return fresh


def send_divergence_alerts_once(result):
    divergences = _new_divergence_alerts(result)
    if not divergences:
        return []
    responses = send_divergence_alerts(divergences)
    state = load_sent_alerts()
    timestamp = datetime.now(timezone.utc).isoformat()
    for item in divergences:
        state[item["_dedup_key"]] = timestamp
    save_sent_alerts(state)
    return responses


def main():
    print("Starting Pharma Radar...")
    result = scan()
    result["alerts"] = enrich_trading_intelligence_scores(result.get("alerts", []))
    result["alerts"] = enrich_trading_intelligence_rules(result["alerts"])

    qualified = sum(1 for alert in result["alerts"] if alert.get("trading_intelligence_qualified") is True)
    watched = sum(1 for alert in result["alerts"] if alert.get("trading_intelligence_watch") is True)
    rule_version = next(
        (alert.get("trading_intelligence_rule_version") for alert in result["alerts"] if alert.get("trading_intelligence_rule_version")),
        "1.1",
    )
    print(f"Trading Intelligence Rule V{rule_version}: {qualified}/{len(result['alerts'])} alerts qualified")
    print(f"Trading Intelligence Watch V{rule_version}: {watched}/{len(result['alerts'])} alerts watched")
    for alert in result["alerts"]:
        ticker = str(alert.get("ticker", "UNKNOWN")).upper()
        failed_watch = alert.get("trading_intelligence_watch_failed", [])
        failed_rule = alert.get("trading_intelligence_rule_failed", [])
        market_checks = alert.get("trading_intelligence_market_confirmation", {})
        market_data = alert.get("market_data") or {}
        print(
            f"TI diagnostics {ticker}: "
            f"TI={alert.get('trading_intelligence_score', 'N/A')} "
            f"catalyst={alert.get('ti_catalyst_score', 'N/A')} "
            f"edge_score={alert.get('ti_historical_edge_score', 'N/A')} "
            f"reaction={alert.get('ti_market_reaction_score', 'N/A')} "
            f"volume={alert.get('ti_volume_score', 'N/A')} "
            f"surprise={alert.get('ti_surprise_score', 'N/A')} "
            f"quality={alert.get('ti_data_quality_score', 'N/A')} "
            f"priority={alert.get('alert_priority', 'N/A')} "
            f"hist_n={alert.get('historical_edge_sample', 'N/A')} "
            f"hist_med={alert.get('historical_edge_median_1d_pct', 'N/A')} "
            f"hist_win={alert.get('historical_edge_win_rate_1d', 'N/A')} "
            f"daily_pct={market_data.get('price_change_pct', 'N/A')} "
            f"market_source={alert.get('trading_intelligence_market_confirmation_source', 'N/A')} "
            f"market_status={alert.get('trading_intelligence_market_status', 'N/A')} "
            f"reaction_source={alert.get('ti_market_reaction_source', 'N/A')} "
            f"market={market_checks} "
            f"WATCH_FAILED={failed_watch or []} "
            f"RULE_FAILED={failed_rule or []}"
        )

    quality = audit_alerts(result["alerts"])
    print(f"Data Quality Audit V1.0: {quality['status']} — alerts={quality['alerts']} warnings={quality['warnings']}")
    for row in quality["rows"]:
        if row["issues"]:
            print(f"DATA QUALITY {row['ticker']}: {row['issues']}")

    record_events(result["alerts"])
    new_alerts = _new_telegram_alerts(result)
    if new_alerts:
        summary = build_summary(result, intelligent_alerts=new_alerts)
        print()
        print(summary)
        send_telegram(summary)

    divergence_sent = send_divergence_alerts_once(result)
    print(f"Telegram divergence alerts sent: {len(divergence_sent)}")

    sent = send_alerts(result, alerts=new_alerts)
    print(f"Telegram catalyst alerts sent: {len(sent)}")
    sent = send_email_alerts(result)
    print(f"Pharma Intelligence emails sent: {sent}")

    divergences = detect_divergences(result.get("alerts", []))
    outcome = track_divergence_outcomes(divergences)
    print(f"Divergence Monitor V1.1: {len(divergences)} detected")
    print(f"Divergence Outcomes V1.1: added={outcome['added']} updated={outcome['updated']} summary={outcome['summary']}")
    for item in divergences:
        print(
            f"DIVERGENCE {item['ticker']}: daily={item['daily_pct']:+.2f}% "
            f"catalyst={item['catalyst_score']} TI={item['trading_intelligence_score']} "
            f"status={item['status']}"
        )

    if not new_alerts:
        print()
        print(build_summary(result, intelligent_alerts=[]))


if __name__ == "__main__":
    main()
