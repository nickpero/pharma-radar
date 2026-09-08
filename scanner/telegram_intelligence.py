"""Pharma Radar — Phase 5.6 intelligent Telegram alert policy."""

import re


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reaction(event):
    return event.get("market_reaction") or event.get("reaction") or {}


def _is_expired(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    window = alert.get("trading_window", event.get("trading_window", ""))
    return str(window or "").strip().upper() == "EXPIRED"


def alert_action(alert):
    """Classify how aggressively an alert should be delivered to Telegram.

    Conservative policy: regulatory/catalyst priority is necessary, while strong
    market reaction can upgrade an alert. Missing reaction data never creates a
    stronger signal by itself.

    EXPIRED events are retained for historical/contextual use but never become
    operational Telegram alerts.
    """
    if _is_expired(alert):
        return "SILENT"

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


def _normalise_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _event_identity(alert):
    """Build a stable identity for one underlying catalyst/news item."""
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    source_id = (
        alert.get("source_item_id") or alert.get("item_id") or
        event.get("source_item_id") or event.get("item_id")
    )
    url = alert.get("url") or event.get("url")
    title = alert.get("title") or event.get("title")
    timestamp = alert.get("event_timestamp") or event.get("published_at")
    if source_id:
        identity = ("ID", _normalise_text(source_id))
    elif url:
        identity = ("URL", _normalise_text(url))
    elif title:
        identity = ("TITLE", _normalise_text(title))
    else:
        identity = ("TIME", _normalise_text(timestamp))
    return (
        _normalise_text(alert.get("ticker") or event.get("ticker") or "UNKNOWN").upper(),
        _normalise_text(alert.get("program") or event.get("program") or "UNKNOWN"),
        _normalise_text(alert.get("subtype") or event.get("subtype") or ""),
        identity,
    )


def _dedup_key(alert):
    return _event_identity(alert)


def _rank(alert):
    reaction = alert.get("market_reaction") or {}
    available_reaction = any(
        reaction.get(key) is not None
        for key in ("reaction_pct", "reaction_5m_pct", "reaction_15m_pct", "reaction_30m_pct", "reaction_60m_pct")
    )
    return (
        _num(alert.get("alert_priority")) or 0,
        _num(alert.get("trading_setup_score")) or 0,
        int(available_reaction),
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
        if current is None or _rank(item) > _rank(current):
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
