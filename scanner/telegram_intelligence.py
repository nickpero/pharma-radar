"""Pharma Radar — Phase 5.6 intelligent Telegram alert policy."""

import re
from datetime import datetime, timezone

MAX_NEW_NEWS_AGE_HOURS = 24
# Telegram actionable alerts are intentionally limited to the last 24h.
# 24-72h events remain useful internally but must not fire a new actionable alert.
MAX_CATALYST_ALERT_AGE_HOURS = 72
MAX_TELEGRAM_ACTIONABLE_AGE_HOURS = 24

_PRIMARY_SOURCES = {"SEC", "FDA", "FDA RSS", "CLINICALTRIALS", "COMPANY", "COMPANY IR", "COURT", "EMA", "EU CTIS"}


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reaction(event):
    return event.get("market_reaction") or event.get("reaction") or {}


def _parse_timestamp(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def catalyst_freshness(alert, now=None):
    """Classify catalyst age: new, recent reaction, or historical."""
    dt = _parse_timestamp(alert.get("published_at") or alert.get("event_timestamp"))
    if dt is None:
        return "UNKNOWN_TIME"
    reference = now or datetime.now(timezone.utc)
    age_hours = max(0.0, (reference - dt).total_seconds() / 3600.0)
    if age_hours <= 24:
        return "NEW_0_24H"
    if age_hours <= MAX_CATALYST_ALERT_AGE_HOURS:
        return "REACTION_24_72H"
    return "HISTORICAL_GT_72H"


def primary_source_verified(alert):
    source = str(alert.get("source") or "").upper()
    source_type = str(alert.get("source_type") or "").upper()
    return source in _PRIMARY_SOURCES or source_type.startswith("PRIMARY_")


def alert_quality_gate(alert, now=None):
    """Final pre-Telegram gate: primary source + <=72h + non-expired."""
    freshness = catalyst_freshness(alert, now)
    primary = primary_source_verified(alert)
    if _is_expired(alert):
        return {"eligible": False, "reason": "EXPIRED", "freshness": freshness, "primary_source": primary}
    if freshness == "REACTION_24_72H":
        return {"eligible": False, "reason": "NOT_NEW_24H", "freshness": freshness, "primary_source": primary}
    if freshness == "HISTORICAL_GT_72H":
        return {"eligible": False, "reason": "HISTORICAL_GT_72H", "freshness": freshness, "primary_source": primary}
    if not primary:
        return {"eligible": False, "reason": "PRIMARY_SOURCE_NOT_VERIFIED", "freshness": freshness, "primary_source": False}
    return {"eligible": True, "reason": "QUALITY_GATE_PASS", "freshness": freshness, "primary_source": True}


def _is_stale_news(alert, now=None):
    return alert_quality_gate(alert, now)["reason"] == "HISTORICAL_GT_72H"


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

    if not alert_quality_gate(alert)["eligible"]:
        return "SILENT"

    if alert.get("post_spike_watch") is True:
        return "WATCH"

    if _is_stale_news(alert):
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
    # Prefer the normalized headline as the primary identity. The same
    # catalyst is often published through SEC/FDA/company URLs that differ
    # while the underlying headline is identical. URL/source IDs remain
    # fallbacks when no usable title exists.
    if title:
        identity = ("TITLE", _normalise_text(title))
    elif source_id:
        identity = ("ID", _normalise_text(source_id))
    elif url:
        identity = ("URL", _normalise_text(url))
    else:
        identity = ("TIME", _normalise_text(timestamp))
    return (
        _normalise_text(alert.get("ticker") or event.get("ticker") or "UNKNOWN").upper(),
        _normalise_text(alert.get("program") or event.get("program") or "UNKNOWN"),
        _normalise_text(alert.get("subtype") or event.get("subtype") or "UNKNOWN").upper(),
        identity,
        "POST_SPIKE_WATCH" if alert.get("post_spike_watch") is True else "CATALYST",
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
        gate = alert_quality_gate(item)
        item["quality_gate"] = gate["reason"]
        item["catalyst_freshness"] = gate["freshness"]
        item["primary_source_verified"] = gate["primary_source"]
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
