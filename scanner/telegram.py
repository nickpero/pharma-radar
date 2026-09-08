"""
Pharma Radar — Telegram Alerts

Gestisce l'invio degli alert Pharma Radar tramite Telegram Bot API.
"""

import os
import requests
from scanner.priority import get_alert_tier, enrich_alert_priority

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
    response = requests.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=30,
    )
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
    return {"CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "🟠"}.get(
        str(label or "LOW").upper(), "⚪"
    )


def _clean_text(value, limit=None):
    text = " ".join(str(value or "").split())
    return text[:limit] if limit else text


def _num(value, digits=2):
    try:
        return f"{float(value):+.{digits}f}"
    except (TypeError, ValueError):
        return None


def _known(value):
    text = _clean_text(value)
    return text if text and text.upper() not in {"UNKNOWN", "N/A", "NONE", "NULL", "UNAVAILABLE"} else None


def _add_explainer(lines, alert):
    explainer = alert.get("catalyst_explainer") or {}
    if not explainer:
        return

    why = _clean_text(explainer.get("why_it_matters"), 600)
    impact = _clean_text(explainer.get("company_impact"), 600)
    what_is = _clean_text(explainer.get("what_is"), 450)
    indication = _clean_text(explainer.get("indication"), 300)
    stage = _clean_text(explainer.get("stage"), 100)

    if not any((why, impact, what_is, indication, stage)):
        return

    lines.extend(["", "💡 WHY IT MATTERS"])
    if why:
        lines.append(why)
    elif impact:
        lines.append(impact)
    if what_is:
        lines.append(f"Drug: {what_is}")
    if indication:
        lines.append(f"Indication: {indication}")
    if stage:
        lines.append(f"Stage: {stage}")


def format_catalyst_alert(alert):
    """Crea un alert Telegram compatto, gerarchico e leggibile in pochi secondi."""
    ticker = _clean_text(alert.get("ticker", "UNKNOWN")).upper()
    program = _clean_text(alert.get("program", "UNKNOWN"))
    nct_id = _clean_text(alert.get("nct_id"))
    event = alert.get("event", {})
    if not isinstance(event, dict):
        event = {}

    event_type = event.get("type", alert.get("event_type", "UNKNOWN"))
    score = event.get("score", alert.get("score", 0))
    label = event.get("label", alert.get("label", "LOW"))
    subtype = event.get("subtype", alert.get("subtype", ""))
    trading_impact = event.get("trading_impact", alert.get("trading_impact", "LOW"))
    urgency = event.get("urgency", alert.get("urgency", "LOW"))
    alert_priority = alert.get("alert_priority", event.get("alert_priority"))
    setup_score = alert.get("trading_setup_score", event.get("trading_setup_score", 0))
    window = alert.get("trading_window", event.get("trading_window", "UNKNOWN"))
    data_quality = alert.get("data_quality", event.get("data_quality", "LOW"))
    reaction_strength = alert.get("reaction_strength", event.get("reaction_strength", "UNKNOWN"))
    reaction_interpretation = alert.get("reaction_interpretation", event.get("reaction_interpretation", "UNKNOWN"))
    confirmation_score = alert.get("catalyst_confirmation_score", event.get("catalyst_confirmation_score"))
    confirmation_label = alert.get("catalyst_confirmation", event.get("catalyst_confirmation"))
    price_change = alert.get("price_change_pct", event.get("price_change_pct"))
    volume_ratio = alert.get("volume_ratio", event.get("volume_ratio"))
    reaction = alert.get("market_reaction") or event.get("market_reaction") or {}
    reaction_pct = alert.get("reaction_pct", reaction.get("reaction_pct"))
    reaction_direction = alert.get("reaction_direction", reaction.get("reaction_direction", "UNKNOWN"))
    title = _clean_text(alert.get("title") or event.get("title"), 600)
    summary = _clean_text(alert.get("summary") or event.get("summary"), 800)

    if alert_priority is None:
        priority_event = dict(event)
        priority_event.update({"score": score, "trading_impact": trading_impact, "urgency": urgency})
        alert_priority = enrich_alert_priority(priority_event).get("alert_priority", 0)
    alert_tier = event.get("alert_tier", alert.get("alert_tier")) or get_alert_tier(alert_priority)
    tier_icon = get_severity_icon(alert_tier)

    lines = [
        f"{tier_icon} PHARMA RADAR — {alert_tier}",
        "",
        f"🧬 {ticker} — {program}",
    ]
    if nct_id:
        lines.append(f"🧪 {nct_id}")

    lines.extend(["", f"📰 {subtype or event_type}", title or "Catalyst detected"])
    if summary and summary.lower() != title.lower():
        lines.append(summary)

    lines.extend([
        "",
        f"🎯 Catalyst  {score}/100 {label}",
        f"🚨 Priority  {alert_priority}/100 {alert_tier}",
        f"📊 Setup     {setup_score}/100 | Window: {window}",
    ])

    if _known(data_quality) and str(data_quality).upper() != "HIGH":
        lines.append(f"Quality: {data_quality}")

    confirmation = _known(confirmation_label)
    if confirmation_score is not None or confirmation:
        if confirmation_score is not None:
            lines.append(f"🧠 Confirmation  {confirmation_score}/100 | {confirmation or 'PENDING'}")
        else:
            lines.append(f"🧠 Confirmation  {confirmation}")

    market_bits = []
    if price_change is not None:
        value = _num(price_change)
        if value is not None:
            market_bits.append(f"Price {value}%")
    if volume_ratio is not None:
        try:
            market_bits.append(f"Volume {float(volume_ratio):.1f}x")
        except (TypeError, ValueError):
            pass

    reaction_values = [
        ("1m", reaction.get("reaction_1m_pct")),
        ("5m", reaction.get("reaction_5m_pct")),
        ("15m", reaction.get("reaction_15m_pct")),
        ("30m", reaction.get("reaction_30m_pct")),
        ("60m", reaction.get("reaction_60m_pct")),
    ]
    available = []
    for label_window, value in reaction_values:
        formatted = _num(value)
        if formatted is not None:
            available.append(f"{label_window} {formatted}%")

    overall = _num(reaction_pct)
    if overall is not None:
        market_bits.insert(0, f"Overall {overall}%")
    if available:
        market_bits.extend(available)

    lines.extend(["", "📈 MARKET"])
    if market_bits:
        lines.append(" | ".join(market_bits))
    else:
        lines.append("Reaction: N/A")

    reaction_context = []
    if _known(reaction_strength):
        reaction_context.append(str(reaction_strength))
    if _known(reaction_interpretation):
        reaction_context.append(str(reaction_interpretation))
    if reaction_context:
        lines.append(" | ".join(reaction_context))

    _add_explainer(lines, alert)

    source = _clean_text(alert.get("source") or event.get("source"))
    if source:
        lines.extend(["", f"🔎 Source: {source}"])

    lines.extend(["", "⚠️ No automatic buy/sell recommendation"])
    return "\n".join(str(line) for line in lines)


def send_catalyst_alert(alert):
    return send_telegram(format_catalyst_alert(alert))


def send_catalyst_alerts(alerts):
    return [send_catalyst_alert(alert) for alert in alerts]
