"""Pharma Radar — Main entry point."""

from datetime import datetime, timezone

from scanner.trial_scanner import scan
from scanner.trading_intelligence_score import enrich_trading_intelligence_scores
from scanner.trading_intelligence_rule import enrich_trading_intelligence_rules
from scanner.catalyst_memory import record_events
from scanner.telegram import send_telegram, send_catalyst_alerts
from scanner.telegram_intelligence import select_intelligent_alerts, _dedup_key
from scanner.alert_state import load_sent_alerts, save_sent_alerts, filter_unsent, mark_sent
from scanner.pharma_email import send_pharma_intelligence_emails


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
    alerts = select_intelligent_alerts(result.get("alerts", []))
    return send_pharma_intelligence_emails(alerts) if alerts else 0


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
        print(f"TI diagnostics {ticker}: WATCH_FAILED={failed_watch or []} RULE_FAILED={failed_rule or []}")

    record_events(result["alerts"])
    new_alerts = _new_telegram_alerts(result)
    if new_alerts:
        summary = build_summary(result, intelligent_alerts=new_alerts)
        print()
        print(summary)
        send_telegram(summary)

    sent = send_alerts(result, alerts=new_alerts)
    print(f"Telegram catalyst alerts sent: {len(sent)}")
    sent = send_email_alerts(result)
    print(f"Pharma Intelligence emails sent: {sent}")

    if not new_alerts:
        print()
        print(build_summary(result, intelligent_alerts=[]))


if __name__ == "__main__":
    main()
