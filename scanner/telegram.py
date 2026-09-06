"""
Pharma Radar — Telegram Alerts

Gestisce l'invio degli alert Pharma Radar
tramite Telegram Bot API.
"""

import os
import requests

from scanner.priority import get_alert_tier, get_alert_tier_icon, enrich_alert_priority


TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


def send_telegram(message):
    """Invia un messaggio Telegram usando Bot API."""
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

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    response = requests.post(url, data=payload, timeout=30)
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
    if label == "CRITICAL":
        return "🚨"
    if label == "HIGH":
        return "🔴"
    if label == "MEDIUM":
        return "🟠"
    return "⚪"


def get_trading_impact_icon(impact):
    impact = str(impact or "LOW").upper()
    if impact == "EXTREME":
        return "🔥"
    if impact == "HIGH":
        return "🔴"
    if impact == "MEDIUM":
        return "🟠"
    return "⚪"


def get_urgency_icon(urgency):
    urgency = str(urgency or "LOW").upper()
    if urgency == "IMMEDIATE":
        return "⚡"
    if urgency == "FAST":
        return "🚀"
    if urgency == "NORMAL":
        return "🕐"
    return "⚪"


def format_catalyst_alert(alert):
    """Crea il messaggio Telegram con gerarchia operativa P2.2."""
    ticker = alert.get("ticker", "UNKNOWN")
    program = alert.get("program", "UNKNOWN")
    nct_id = alert.get("nct_id", "UNKNOWN")
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
    alert_priority = event.get("alert_priority", alert.get("alert_priority"))

    # Telegram must remain robust for legacy/manual alerts that do not yet
    # carry the unified P2.1 priority field.
    if alert_priority is None:
        priority_event = dict(event)
        priority_event.update({
            "score": score,
            "trading_impact": trading_impact,
            "urgency": urgency,
        })
        alert_priority = enrich_alert_priority(priority_event).get("alert_priority", 0)

    alert_tier = event.get("alert_tier", alert.get("alert_tier")) or get_alert_tier(alert_priority)

    direction_icon = get_direction_icon(direction)
    severity_icon = get_severity_icon(label)
    trading_impact_icon = get_trading_impact_icon(trading_impact)
    urgency_icon = get_urgency_icon(urgency)
    tier_icon = get_alert_tier_icon(alert_tier)

    lines = [
        "🚨 PHARMA RADAR — CATALYST",
        "",
        f"{tier_icon} PRIORITY: {alert_tier} — {alert_priority}/100",
        f"{severity_icon} {ticker} — {program}",
        f"🧬 {nct_id}",
        "",
        f"Event: {event_type}",
        f"Subtype: {subtype}",
    ]

    old_value = event.get("old_value")
    new_value = event.get("new_value")
    if old_value is not None:
        lines.append(f"Old: {old_value}")
    if new_value is not None:
        lines.append(f"New: {new_value}")

    lines.extend([
        "",
        f"🎯 Score: {score}/100",
        f"{severity_icon} Severity: {severity}",
        f"{direction_icon} Direction: {direction}",
        f"🏷 Label: {label}",
        f"{trading_impact_icon} Trading Impact: {trading_impact}",
        f"{urgency_icon} Urgency: {urgency}",
    ])

    return "\n".join(str(line) for line in lines)


def send_catalyst_alert(alert):
    """Formatta e invia un singolo catalyst."""
    return send_telegram(format_catalyst_alert(alert))


def send_catalyst_alerts(alerts):
    """Invia i catalyst individualmente, già ordinati per priorità."""
    results = []
    for alert in alerts:
        results.append(send_catalyst_alert(alert))
    return results
