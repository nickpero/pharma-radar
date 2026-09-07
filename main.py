"""Pharma Radar — Main entry point."""

from scanner.trial_scanner import scan
from scanner.telegram import send_telegram, send_catalyst_alerts


def build_summary(result):
    alerts = result.get("alerts", [])
    errors = result.get("errors", [])
    detected_changes = result.get("detected_changes", [])
    lines = [
        "🧬 PHARMA RADAR — SCAN", "",
        f"🏢 Companies: {result.get('companies', 0)}",
        f"🔬 Trials found: {result.get('total_trials', 0)}",
        f"🎯 Relevant trials: {result.get('relevant_trials', 0)}",
        f"🧹 Filtered out: {result.get('filtered_trials', 0)}",
        f"🔄 Changes detected: {len(detected_changes)}",
        f"📰 FDA news: {len(result.get('fda_news', []))}",
        f"🚨 Alerts: {len(alerts)}", f"❌ Errors: {len(errors)}", "",
    ]
    if alerts:
        lines.extend(["🚨 CATALYST ALERTS", ""])
        for alert in alerts:
            event = alert.get("event", {}) if isinstance(alert.get("event", {}), dict) else {}
            tier = alert.get("alert_tier", event.get("alert_tier", "LOW"))
            priority = alert.get("alert_priority", event.get("alert_priority", 0))
            setup_score = alert.get("trading_setup_score", event.get("trading_setup_score", 0))
            window = alert.get("trading_window", event.get("trading_window", "UNKNOWN"))
            awareness = alert.get("market_awareness", event.get("market_awareness", "UNKNOWN"))
            surprise = alert.get("event_surprise", event.get("event_surprise", "UNKNOWN"))
            quality = alert.get("data_quality", event.get("data_quality", "LOW"))
            price_change = alert.get("price_change_pct", event.get("price_change_pct"))
            volume_ratio = alert.get("volume_ratio", event.get("volume_ratio"))
            market_cap = alert.get("market_cap", event.get("market_cap"))
            short_interest = alert.get("short_interest_pct", event.get("short_interest_pct"))
            lines.append(f"• {alert.get('ticker', 'UNKNOWN')} — {alert.get('program', 'UNKNOWN')}")
            if alert.get("nct_id"):
                lines.append(f"  🧬 {alert['nct_id']}")
            if alert.get("title") or event.get("title"):
                lines.append(f"  📰 {alert.get('title') or event.get('title')}")
            lines.append(f"  {event.get('type', 'UNKNOWN')} — {event.get('subtype', '')}")
            lines.append(f"  🎯 Alert Priority: {priority}/100 — {tier}")
            lines.append(f"  Score: {event.get('score', 0)}/100 — {event.get('label', 'LOW')}")
            lines.append(f"  📊 Trading Intelligence: Setup {setup_score}/100 | Window {window} | Awareness {awareness} | Surprise {surprise} | Quality {quality}")
            if price_change is not None:
                lines.append(f"  📈 Price: {float(price_change):+.2f}%")
            if volume_ratio is not None:
                lines.append(f"  📊 Volume: {float(volume_ratio):.1f}x 20d")
            if market_cap is not None:
                lines.append(f"  💰 Market Cap: ${float(market_cap) / 1_000_000:,.0f}M")
            if short_interest is not None:
                lines.append(f"  🩳 Short Interest: {float(short_interest):.1f}%")
            lines.append("")
    else:
        lines.extend(["🟢 No catalyst alerts", ""])
    if errors:
        lines.append("❌ ERRORS")
        for error in errors:
            lines.append(f"• {error.get('ticker', 'UNKNOWN')} — {error.get('program', 'UNKNOWN')}")
            if error.get("error"):
                lines.append(f"  {error.get('error')}")
        lines.append("")
    lines.append("Status: REVIEW" if alerts else "Status: WARNING" if errors else "Status: CLEAN")
    return "\n".join(lines)


def send_alerts(result):
    alerts = result.get("alerts", [])
    return send_catalyst_alerts(alerts) if alerts else []


def main():
    print("Starting Pharma Radar...")
    result = scan()
    summary = build_summary(result)
    print(); print(summary)
    send_telegram(summary)
    send_alerts(result)


if __name__ == "__main__":
    main()
