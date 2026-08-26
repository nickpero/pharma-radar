import os
import requests


TELEGRAM_API = "https://api.telegram.org"


def send_telegram(message):
    """
    Invia un messaggio Telegram usando Bot API.

    Il testo viene passato direttamente come parametro
    alla libreria requests: NON viene fatto URL encoding
    manuale del messaggio.
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


def format_catalyst_alert(alert):
    """
    Crea il messaggio Telegram per un catalyst.
    """

    ticker = alert.get(
        "ticker",
        "UNKNOWN"
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

    event_type = event.get(
        "type",
        "UNKNOWN"
    )

    severity = event.get(
        "severity",
        "UNKNOWN"
    )

    direction = event.get(
        "direction",
        "UNKNOWN"
    )

    score = event.get(
        "score",
        0
    )

    label = event.get(
        "label",
        "LOW"
    )

    subtype = event.get(
        "subtype",
        ""
    )

    old_value = event.get(
        "old_value"
    )

    new_value = event.get(
        "new_value"
    )

    # ========================================
    # DIRECTION ICON
    # ========================================

    if direction in {
        "POSITIVE",
        "CATALYST",
    }:
        direction_icon = "📈"

    elif direction == "NEGATIVE":
        direction_icon = "📉"

    else:
        direction_icon = "⚪"

    # ========================================
    # SEVERITY ICON
    # ========================================

    if label == "CRITICAL":
        severity_icon = "🚨"

    elif label == "HIGH":
        severity_icon = "🔴"

    elif label == "MEDIUM":
        severity_icon = "🟠"

    else:
        severity_icon = "⚪"

    # ========================================
    # MESSAGE
    # ========================================

    lines = [
        "🚨 PHARMA RADAR — CATALYST",
        "",
        f"{severity_icon} {ticker} — {program}",
        f"🧬 {nct_id}",
        "",
        f"Event: {event_type}",
        f"Subtype: {subtype}",
        "",
        f"Old: {old_value}",
        f"New: {new_value}",
        "",
        f"🎯 Score: {score}/100",
        f"{severity_icon} {label}",
        f"{direction_icon} Direction: {direction}",
    ]

    return "\n".join(
        lines
    )


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


def send_catalyst_alerts(alerts):
    """
    Invia tutti gli alert catalyst.
    """

    results = []

    for alert in alerts:

        results.append(
            send_catalyst_alert(
                alert
            )
        )

    return results
