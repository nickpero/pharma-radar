"""Pharma Radar — Phase 5.4 historical catalyst memory.

Small, transparent JSON-backed event store. The production workflow already
commits state after every scan, so this file survives scheduled GitHub runs.
Records are keyed deterministically to avoid duplicate observations.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MEMORY_FILE = Path("data/catalyst_history.json")
MAX_RECORDS = 5000


def _key(event):
    parts = [
        str(event.get("ticker") or "UNKNOWN").upper(),
        str(event.get("program") or "UNKNOWN").lower(),
        str(event.get("subtype") or event.get("event") or "UNKNOWN").upper(),
        str(event.get("event_timestamp") or event.get("published_at") or ""),
        str(event.get("nct_id") or ""),
        str(event.get("url") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def load_memory(path=MEMORY_FILE):
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _snapshot(event):
    reaction = event.get("market_reaction") or {}
    return {
        "memory_version": "5.4",
        "memory_key": _key(event),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "ticker": event.get("ticker"),
        "company": event.get("company"),
        "program": event.get("program"),
        "nct_id": event.get("nct_id"),
        "source": event.get("source"),
        "source_type": event.get("source_type"),
        "subtype": event.get("subtype"),
        "direction": event.get("direction"),
        "severity": event.get("severity"),
        "score": event.get("score"),
        "label": event.get("label"),
        "trading_impact": event.get("trading_impact"),
        "urgency": event.get("urgency"),
        "alert_priority": event.get("alert_priority"),
        "event_timestamp": event.get("event_timestamp") or event.get("published_at"),
        "event_surprise": event.get("event_surprise"),
        "trading_setup_score": event.get("trading_setup_score"),
        "trading_setup_version": event.get("trading_setup_version"),
        "reaction_strength": event.get("reaction_strength"),
        "reaction_interpretation": event.get("reaction_interpretation"),
        "price_change_pct": event.get("price_change_pct"),
        "volume_ratio": event.get("volume_ratio"),
        "market_cap": event.get("market_cap"),
        "short_interest_pct": event.get("short_interest_pct"),
        "reaction": reaction,
        "url": event.get("url"),
    }


def record_events(events, path=MEMORY_FILE):
    """Upsert alert snapshots and return the number of newly stored records."""
    memory = load_memory(path)
    added = 0
    for event in events or []:
        if not isinstance(event, dict):
            continue
        key = _key(event)
        if key not in memory:
            added += 1
        memory[key] = _snapshot(event)
    if len(memory) > MAX_RECORDS:
        ordered = sorted(memory.items(), key=lambda item: item[1].get("recorded_at", ""), reverse=True)
        memory = dict(ordered[:MAX_RECORDS])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as file:
        json.dump(memory, file, ensure_ascii=False, indent=2, sort_keys=True)
    tmp.replace(path)
    return added


def history_records(path=MEMORY_FILE):
    return list(load_memory(path).values())


def find_similar_events(event, limit=10, path=MEMORY_FILE):
    """Return prior events for the same ticker and catalyst subtype, newest first."""
    ticker = str(event.get("ticker") or "").upper()
    subtype = str(event.get("subtype") or "").upper()
    rows = [
        row for row in history_records(path)
        if str(row.get("ticker") or "").upper() == ticker
        and (not subtype or str(row.get("subtype") or "").upper() == subtype)
        and row.get("memory_key") != _key(event)
    ]
    rows.sort(key=lambda row: row.get("event_timestamp") or row.get("recorded_at") or "", reverse=True)
    return rows[: max(0, int(limit))]


def memory_summary(path=MEMORY_FILE):
    rows = history_records(path)
    return {
        "records": len(rows),
        "tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "catalysts": len({row.get("subtype") for row in rows if row.get("subtype")}),
    }
