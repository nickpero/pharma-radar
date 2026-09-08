"""
Pharma Radar — Telegram Alerts

Gestisce l'invio degli alert Pharma Radar tramite Telegram Bot API.
"""

import os
import requests
from scanner.priority import get_alert_tier, get_alert_tier_icon, enrich_alert_priority

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not configured")
    if not isinstance(message, str):
        message = str(message)
    if not message.strip():
        raise ValueError("Telegram message is empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH - 20] + "\n\n[TRUNCATED]"
    response = requests.post(f"{TELEGRAM_API}/bot{token}/sendMessage", data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True}, timeout=30)
    response.raise_for_status()
    return response.json()


def get_direction_icon(direction):
    direction = str(direction or "UNKNOWN").upper()
    if direction in {"POSITIVE", "CATALYST"}:
        return "📈"
    if direction == "NEGATIVE":
        return "📉"
    return "⚪"


def get_severity_icon(label):
    label = str(label or "LOW").upper()
    return {"CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "🟠"}.get(label, "⚪")


def get_trading_impact_icon(impact):
    return {"EXTREME": "🔥", "HIGH": "🔴", "MEDIUM": "🟠"}.get(str(impact or "LOW").upper(), "⚪")


def get_urgency_icon(urgency):
    return {"IMMEDIATE": "⚡", "FAST": "🚀", "NORMAL": "🕐"}.get(str(urgency or "LOW").upper(), "⚪")


def format_catalyst_alert(alert):
    """Crea il messaggio Telegram con Catalyst + Trading Intelligence 5.3."""
    ticker = alert.get("ticker", "UNKNOWN")
    program = alert.get("program", "UNKNOWN")
    nct_id = alert.get("nct_id")
    event = alert.get("event", {})
    if not isinstance(event, dict):
        event = {}

    event_type = event.get("type", alert.get("event_type", "UNKNOWN"))
    severity = event.get("severity", alert.get("severity", "UNKNOWN"))
    direction = event.get("direction", alert.get("direction", "UNKNOWN"))
    score = event.get("score", alert.get("score", 0))
    label = event.get("label", alert.get("label", "LOW"))
    subtype = event.get("subtype", alert.get("subtype", ""))
    trading_impact = event.get("trading_impact", alert.get("trading_impact", "LOW"))
    urgency = event.get("urgency", alert.get("urgency", "LOW"))
    alert_priority = alert.get("alert_priority", event.get("alert_priority"))
    setup_score = alert.get("trading_setup_score", event.get("trading_setup_score", 0))
    setup_version = alert.get("trading_setup_version", event.get("trading_setup_version", "4"))
    window = alert.get("trading_window", event.get("trading_window", "UNKNOWN"))
    awareness = alert.get("market_awareness", event.get("market_awareness", "UNKNOWN"))
    event_surprise = alert.get("event_surprise", event.get("event_surprise", "UNKNOWN"))
    data_quality = alert.get("data_quality", event.get("data_quality", "LOW"))
    reaction_strength = alert.get("reaction_strength", event.get("reaction_strength", "UNKNOWN"))
    reaction_interpretation = alert.get("reaction_interpretation", event.get("reaction_interpretation", "UNKNOWN"))
    price_change = alert.get("price_change_pct", event.get("price_change_pct"))
    volume_ratio = alert.get("volume_ratio", event.get("volume_ratio"))
    market_cap = alert.get("market_cap", event.get("market_cap"))
    short_interest = alert.get("short_interest_pct", event.get("short_interest_pct"))
    reaction = alert.get("market_reaction") or event.get("market_reaction") or {}
    reaction_pct = alert.get("reaction_pct", reaction.get("reaction_pct"))
    reaction_direction = alert.get("reaction_direction", reaction.get("reaction_direction", "UNKNOWN"))
    reaction_status = alert.get("reaction_status", reaction.get("reaction_status", "UNAVAILABLE"))
    reaction_5m = alert.get("reaction_5m_pct", reaction.get("reaction_5m_pct"))
    reaction_15m = alert.get("reaction_15m_pct", reaction.get("reaction_15m_pct"))
    reaction_30m = alert.get("reaction_30m_pct", reaction.get("reaction_30m_pct"))
    reaction_60m = alert.get("reaction_60m_pct", reaction.get("reaction_60m_pct"))
    title = alert.get("title") or event.get("title") or ""
    summary = alert.get("summary") or event.get("summary") or ""

    if alert_priority is None:
        priority_event = dict(event)
        priority_event.update({"score": score, "trading_impact": trading_impact, "urgency": urgency})
        alert_priority = enrich_alert_priority(priority_event).get("alert_priority", 0)
    alert_tier = event.get("alert_tier", alert.get("alert_tier")) or get_alert_tier(alert_priority)

    lines = [
        "🚨 PHARMA RADAR — CATALYST", "", f"{get_severity_icon(label)} {ticker} — {program}",
        f"🎯 PRIORITY: {alert_tier} — {alert_priority}/100",
    ]
    if nct_id:
        lines.append(f"🧬 {nct_id}")
    if title:
        lines.append(f"📰 {title}")
    if summary:
        compact = " ".join(str(summary).split())
        lines.append(f"  {compact[:500]}")

    lines.extend(["", f"Event: {event_type}", f"Subtype: {subtype}"])
    old_value = event.get("old_value")
    new_value = event.get("new_value")
    if old_value is not None:
        lines.append(f"Old: {old_value}")
    if new_value is not None:
        lines.append(f"New: {new_value}")
    lines.extend([
        "", f"🎯 Catalyst Score: {score}/100", f"{get_severity_icon(label)} Severity: {severity}",
        f"{get_direction_icon(direction)} Direction: {direction}", f"🏷 Label: {label}",
        f"{get_trading_impact_icon(trading_impact)} Trading Impact: {trading_impact}",
        f"{get_urgency_icon(urgency)} Urgency: {urgency}", "", "📊 TRADING INTELLIGENCE",
        f"🔥 Trading Setup: {setup_score}/100", f"🧠 Setup Version: {setup_version}", f"⏱ Window: {window}",
        f"👀 Market Awareness: {awareness}", f"🎯 Event Surprise: {event_surprise}",
        f"🧪 Data Quality: {data_quality}", f"⚡ Reaction Strength: {reaction_strength}",
        f"🧭 Reaction Interpretation: {reaction_interpretation}",
    ])
    if price_change is not None:
        lines.append(f"📈 Price vs prev close: {float(price_change):+.2f}%")
    if volume_ratio is not None:
        lines.append(f"📊 Volume vs 20d avg: {float(volume_ratio):.1f}x")
    if market_cap is not None:
        lines.append(f"💰 Market Cap: ${float(market_cap) / 1_000_000:,.0f}M")
    if short_interest is not None:
        lines.append(f"🩳 Short Interest: {float(short_interest):.1f}%")

    # Show any usable reaction data even when the provider did not set a perfect
    # AVAILABLE status. This avoids hiding real movements behind a status flag.
    reaction_values = [("1m", reaction.get("reaction_1m_pct")), ("5m", reaction_5m), ("15m", reaction_15m), ("30m", reaction_30m), ("60m", reaction_60m)]
    available_windows = [f"{label} {float(value):+.2f}%" for label, value in reaction_values if value is not None]
    if reaction_pct is not None or available_windows:
        lines.extend(["", "⚡ MARKET REACTION"])
        if reaction_pct is not None:
            lines.append(f"📈 Reaction: {float(reaction_pct):+.2f}% ({reaction_direction})")
        if available_windows:
            lines.append("⏱ " + " | ".join(available_windows))
    else:
        lines.append("⚡ MARKET REACTION: UNAVAILABLE")

    source = alert.get("source") or event.get("source")
    if source:
        lines.append(f"🔎 Source: {source}")
    return "\n".join(str(line) for line in lines)


def send_catalyst_alert(alert):
    return send_telegram(format_catalyst_alert(alert))


def send_catalyst_alerts(alerts):
    return [send_catalyst_alert(alert) for alert in alerts]
