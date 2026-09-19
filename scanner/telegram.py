"""
Pharma Radar — Telegram Alerts

Gestisce l'invio degli alert Pharma Radar tramite Telegram Bot API.
"""

import os
from datetime import date

import requests
from scanner.priority import get_alert_tier, enrich_alert_priority

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


# Display-only aliases. The underlying entity/program identity remains unchanged.
DRUG_DISPLAY_NAMES = {
    "zilganersen": "Zilganersen (Zanvastro)",
}

EVENT_DISPLAY_NAMES = {
    "FDA_APPROVAL": "FDA APPROVAL",
    "FDA_REJECTION": "FDA REJECTION",
    "FDA_SAFETY_WARNING": "FDA SAFETY WARNING",
    "CLINICAL_RESULTS": "CLINICAL RESULTS",
    "LABEL_EXPANSION": "LABEL EXPANSION",
    "REGULATORY_FILING": "REGULATORY FILING",
    "TRIAL_HOLD": "TRIAL HOLD",
    "TRIAL_HOLD_LIFTED": "TRIAL HOLD LIFTED",
    "PHASE_ADVANCED": "PHASE ADVANCED",
    "DATE_ACCELERATED": "DATE ACCELERATED",
    "DATE_DELAYED": "DATE DELAYED",
}


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


def _drug_name(alert, program):
    """Use a real short drug name when available; never use the article body."""
    for key in ("drug_name", "drug"):
        value = _clean_text(alert.get(key), 100)
        if value and len(value) <= 100:
            return value
    return DRUG_DISPLAY_NAMES.get(str(program).strip().lower(), program)


def _event_display_name(subtype, event_type):
    raw = _clean_text(subtype or event_type, 100).upper()
    if raw in EVENT_DISPLAY_NAMES:
        return EVENT_DISPLAY_NAMES[raw]
    return raw.replace("_", " ") if raw else "CATALYST"


def _parse_iso_date(value):
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None


def _timeline_details(alert, event, subtype):
    """Return trader-readable details for clinical-trial timeline changes."""
    if str(subtype or "").upper() not in {"DATE_ACCELERATED", "DATE_DELAYED"}:
        return None

    old_value = event.get("old_value")
    new_value = event.get("new_value")
    old_date = _parse_iso_date(old_value)
    new_date = _parse_iso_date(new_value)
    field = _clean_text(event.get("field") or alert.get("changed_field"), 100)

    field_labels = {
        "primary_completion_date": "Primary Completion",
        "study_completion_date": "Study Completion",
        "completion_date": "Completion",
    }
    field_display = field_labels.get(field, field.replace("_", " ").title() if field else "Trial Timeline")

    details = [
        "🚨 TRIAL TIMELINE CHANGE",
        f"📌 Field: {field_display}",
    ]
    if old_value:
        details.append(f"📅 Old date: {old_value}")
    if new_value:
        details.append(f"📅 New date: {new_value}")
    if old_date and new_date:
        delta_days = (new_date - old_date).days
        if delta_days < 0:
            details.append(f"⏩ Accelerated: {abs(delta_days)} days")
        elif delta_days > 0:
            details.append(f"⏳ Delayed: {delta_days} days")
        else:
            details.append("↔️ Change: 0 days")
    details.append("ℹ️ Timeline change only — clinical outcome not yet reported.")
    return details


def _why_it_matters(alert, event, subtype):
    explainer = alert.get("catalyst_explainer") or {}
    why = _clean_text(explainer.get("why_it_matters"), 280)
    if why:
        return why

    why = _clean_text(event.get("why_it_matters") or event.get("trading_impact_reason"), 280)
    if why:
        return why

    fallback = {
        "FDA_APPROVAL": "FDA approval converts the program into an approved product and marks a major regulatory and commercial milestone.",
        "FDA_REJECTION": "FDA rejection is a major regulatory setback that can materially change the program's commercial outlook.",
        "FDA_SAFETY_WARNING": "A new FDA safety warning can materially affect the product's risk profile, label and commercial outlook.",
        "CLINICAL_RESULTS": "Clinical results can materially change the probability of success and valuation of the program.",
        "LABEL_EXPANSION": "A label expansion increases the addressable patient population and can materially change the product's commercial opportunity.",
    }
    return fallback.get(str(subtype).upper())


def format_catalyst_alert(alert):
    """Create a compact Telegram alert optimized for rapid human scanning."""
    ticker = _clean_text(alert.get("ticker", "UNKNOWN"), 20).upper()
    program = _clean_text(alert.get("program", "UNKNOWN"), 80)
    drug_name = _drug_name(alert, program)
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
    reaction = alert.get("market_reaction") or event.get("market_reaction") or {}
    reaction_pct = alert.get("reaction_pct", reaction.get("reaction_pct"))
    reaction_direction = alert.get("reaction_direction", reaction.get("reaction_direction", "UNKNOWN"))
    title = _clean_text(alert.get("title") or event.get("title"), 260)
    why = _why_it_matters(alert, event, subtype)
    event_display = _event_display_name(subtype, event_type)

    if alert_priority is None:
        priority_event = dict(event)
        priority_event.update({"score": score, "trading_impact": trading_impact, "urgency": urgency})
        alert_priority = enrich_alert_priority(priority_event).get("alert_priority", 0)
    alert_tier = event.get("alert_tier", alert.get("alert_tier")) or get_alert_tier(alert_priority)
    tier_icon = get_severity_icon(alert_tier)

    lines = [
        "🚨 PHARMA RADAR",
        "━━━━━━━━━━━━━━━━━━",
        f"{tier_icon} {alert_tier}",
        "",
        f"🧬 {ticker}",
        f"💊 {drug_name}",
        "",
        f"📰 {event_display}",
        title or "Catalyst detected",
    ]

    timeline_details = _timeline_details(alert, event, subtype)
    if timeline_details:
        lines.extend(["", *timeline_details])

    lines.extend([
        "",
        f"🎯 Catalyst: {score}/100 · {label}",
        f"🚨 Priority: {alert_priority}/100 · {alert_tier}",
        f"📊 Setup: {setup_score}/100 · Window: {window}",
        "",
        "📈 Market reaction: " + (
            f"{_num(reaction_pct)}% · {reaction_direction}"
            if reaction_pct is not None and _num(reaction_pct) is not None
            else " | ".join(
                f"{label_window} {_num(reaction.get(f'reaction_{label_window}_pct'))}%"
                for label_window in ("1m", "5m", "15m", "30m", "60m")
                if _num(reaction.get(f"reaction_{label_window}_pct")) is not None
            ) or "N/A"
        ),
    ])

    if why:
        lines.extend(["", "💡 WHY IT MATTERS", why])

    source = _clean_text(alert.get("source") or event.get("source"))
    if source:
        lines.extend(["", f"🔎 Source: {source}"])

    lines.extend(["", "⚠️ Informational only — no automatic buy/sell signal.", "━━━━━━━━━━━━━━━━━━"])
    return "\n".join(str(line) for line in lines)


def format_divergence_alert(divergence):
    """Create a non-operational alert for strong catalyst/market divergence."""
    ticker = _clean_text(divergence.get("ticker", "UNKNOWN"), 20).upper()
    program = _clean_text(divergence.get("program", "UNKNOWN"), 80)
    daily_pct = _num(divergence.get("daily_pct"))
    catalyst = divergence.get("catalyst_score", "N/A")
    ti = divergence.get("trading_intelligence_score", "N/A")
    edge = divergence.get("historical_edge_median_1d_pct", "N/A")
    win = divergence.get("historical_edge_win_rate_1d")
    win_text = f"{float(win) * 100:.1f}%" if win is not None else "N/A"
    return "\n".join([
        "⚠️ PHARMA RADAR — DIVERGENCE",
        "━━━━━━━━━━━━━━━━━━",
        f"🧬 {ticker}",
        f"💊 {program}",
        "",
        "📈 Positive catalyst / 📉 negative market reaction",
        f"🎯 Catalyst: {catalyst}/100",
        f"🧠 TI Score: {ti}/100",
        f"📚 Historical edge: {edge}% · Win rate: {win_text}",
        f"📉 Daily reaction: {daily_pct}% · DIVERGENT",
        "",
        "ℹ️ Informational monitor only — this is not a buy/sell signal.",
        "━━━━━━━━━━━━━━━━━━",
    ])


def send_catalyst_alert(alert):
    return send_telegram(format_catalyst_alert(alert))


def send_catalyst_alerts(alerts):
    return [send_catalyst_alert(alert) for alert in alerts]


def send_divergence_alerts(divergences):
    return [send_telegram(format_divergence_alert(item)) for item in divergences]
