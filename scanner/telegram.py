"""
Pharma Radar — Telegram Alerts

Gestisce l'invio degli alert Pharma Radar
tramite Telegram Bot API.
"""

import os
import requests


TELEGRAM_API = "https://api.telegram.org"

MAX_MESSAGE_LENGTH = 4096


# ============================================
# SEND TELEGRAM
# ============================================

def send_telegram(message):
    """
    Invia un messaggio Telegram usando Bot API.
    """

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN"
    )

    chat_id = os.getenv(
        "TELEGRAM_CHAT_ID"
    )

    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not configured"
        )

    if not chat_id:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID is not configured"
        )

    if not isinstance(message, str):
        message = str(message)

    if not message.strip():
        raise ValueError(
            "Telegram message is empty"
        )

    if len(message) > MAX_MESSAGE_LENGTH:
        message = (
            message[:MAX_MESSAGE_LENGTH - 20]
            + "\n\n[TRUNCATED]"
        )

    url = (
        f"{TELEGRAM_API}/"
        f"bot{token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        data=payload,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# ============================================
# DIRECTION ICON
# ============================================

def get_direction_icon(direction):

    direction = str(
        direction or "UNKNOWN"
    ).upper()

    if direction in {
        "POSITIVE",
        "CATALYST",
    }:
        return "📈"

    if direction == "NEGATIVE":
        return "📉"

    return "⚪"


# ============================================
# SEVERITY ICON
# ============================================

def get_severity_icon(label):

    label = str(
        label or "LOW"
    ).upper()

    if label == "CRITICAL":
        return "🚨"

    if label == "HIGH":
        return "🔴"

    if label == "MEDIUM":
        return "🟠"

    return "⚪"


# ============================================
# CATALYST ALERT FORMAT
# ============================================

def format_catalyst_alert(alert):
    """
    Crea il messaggio Telegram per un catalyst.

    Mantiene l'intestazione compatibile con
    i test esistenti del Pharma Radar.
    """

    ticker = alert.get(
        "ticker",
        "UNKNOWN"
    )

    company = alert.get(
        "company",
        ""
    )

    program = alert.get(
        "program",
        "UNKNOWN"
    )

    nct_id = alert.get(
        "nct_id",
        "UNKNOWN"
    )

    event = alert.get(
        "event",
        {}
    )

    if not isinstance(event, dict):
        event = {}

    event_type = event.get(
        "type",
        alert.get(
            "event_type",
            "UNKNOWN"
        )
    )

    severity = event.get(
        "severity",
        alert.get(
            "severity",
            "UNKNOWN"
        )
    )

    direction = event.get(
        "direction",
        alert.get(
            "direction",
            "UNKNOWN"
        )
    )

    score = event.get(
        "score",
        alert.get(
            "score",
            0
        )
    )

    label = event.get(
        "label",
        alert.get(
            "label",
            "LOW"
        )
    )

    subtype = event.get(
        "subtype",
        alert.get(
            "subtype",
            ""
        )
    )

    old_value = event.get(
        "old_value"
    )

    new_value = event.get(
        "new_value"
    )

    # ========================================
    # ICONS
    # ========================================

    direction_icon = get_direction_icon(
        direction
    )

    severity_icon = get_severity_icon(
        label
    )

    # ========================================
    # COMPANY
    # ========================================

    if company and company != ticker:

        company_line = (
            f"{ticker} — {company}"
        )

    else:

        company_line = ticker

    # ========================================
    # EVENT
    # ========================================

    if subtype:

        event_line = (
            f"🎯 {subtype}"
        )

    else:

        event_line = (
            f"🎯 {event_type}"
        )

    # ========================================
    # CHANGES
    # ========================================

    change_lines = []

    if old_value is not None:

        change_lines.append(
            f"Old: {old_value}"
        )

    if new_value is not None:

        change_lines.append(
            f"New: {new_value}"
        )

    # ========================================
    # MESSAGE
    # ========================================

    lines = [
        "🚨 PHARMA RADAR — CATALYST",
        "",
        f"{severity_icon} {company_line}",
        f"💊 {program}",
        f"🧬 {nct_id}",
        "",
        event_line,
        f"Type: {event_type}",
    ]

    if change_lines:

        lines.extend([
            "",
            *change_lines,
        ])

    lines.extend([
        "",
        f"🎯 Score: {score}/100",
        f"{severity_icon} Severity: {severity}",
        f"{direction_icon} Direction: {direction}",
        f"🏷 Label: {label}",
    ])

    return "\n".join(
        str(line)
        for line in lines
    )


# ============================================
# SEND SINGLE ALERT
# ============================================

def send_catalyst_alert(alert):
    """
    Formatta e invia un singolo catalyst.
    """

    message = format_catalyst_alert(
        alert
    )

    return send_telegram(
        message
    )


# ============================================
# SEND MULTIPLE ALERTS
# ============================================

def send_catalyst_alerts(alerts):
    """
    Invia tutti gli alert catalyst
    separatamente.
    """

    results = []

    for alert in alerts:

        results.append(
            send_catalyst_alert(
                alert
            )
        )

    return results
