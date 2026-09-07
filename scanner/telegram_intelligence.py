"""Pharma Radar — Phase 5.6 intelligent Telegram alert policy."""


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reaction(event):
    return event.get("market_reaction") or event.get("reaction") or {}


def alert_action(alert):
    """Classify how aggressively an alert should be delivered to Telegram.

    Conservative policy: regulatory/catalyst priority is necessary, while strong
    market reaction can upgrade an alert. Missing reaction data never creates a
    stronger signal by itself.
    """
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    priority = _num(alert.get("alert_priority", event.get("alert_priority"))) or 0
    setup = _num(alert.get("trading_setup_score", event.get("trading_setup_score"))) or 0
    tier = str(alert.get("alert_tier", event.get("alert_tier", "LOW"))).upper()
    strength = str(alert.get("reaction_strength", event.get("reaction_strength", "UNKNOWN"))).upper()
    interpretation = str(alert.get("reaction_interpretation", event.get("reaction_interpretation", "UNKNOWN"))).upper()
    reaction = _reaction(alert)
    reaction_pct = _num(reaction.get("reaction_pct"))

    if tier == "CRITICAL" or priority >= 80:
        return "IMMEDIATE"
    if tier == "HIGH" or priority >= 60:
        if interpretation in {"DIVERGENCE", "OVERREACTION"} or strength.startswith("STRONG"):
            return "IMMEDIATE"
        return "FAST"
    if setup >= 75 and (reaction_pct is not None or strength != "UNKNOWN"):
        return "WATCH"
    return "SILENT"


def _dedup_key(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    return (
        str(alert.get("ticker", "UNKNOWN")).upper(),
        str(alert.get("program", "UNKNOWN")).lower(),
        str(alert.get("subtype", event.get("subtype", ""))).upper(),
    )


def select_intelligent_alerts(alerts):
    """Deduplicate and select alerts worth sending to Telegram."""
    selected = {}
    for alert in alerts or []:
        action = alert_action(alert)
        if action == "SILENT":
            continue
        item = dict(alert)
        item["telegram_action"] = action
        key = _dedup_key(item)
        current = selected.get(key)
        if current is None:
            selected[key] = item
            continue
        current_priority = _num(current.get("alert_priority")) or 0
        new_priority = _num(item.get("alert_priority")) or 0
        if new_priority > current_priority:
            selected[key] = item
    order = {"IMMEDIATE": 0, "FAST": 1, "WATCH": 2}
    return sorted(
        selected.values(),
        key=lambda alert: (
            order.get(alert.get("telegram_action", "WATCH"), 9),
            -(_num(alert.get("alert_priority")) or 0),
            -(_num(alert.get("trading_setup_score")) or 0),
        ),
    )


def enrich_telegram_actions(alerts):
    return [{**alert, "telegram_action": alert_action(alert)} for alert in (alerts or [])]
