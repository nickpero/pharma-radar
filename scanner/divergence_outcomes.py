"""Pharma Radar — Divergence Outcomes V1.1.

Research-only tracker for forward T+1/T+3/T+5 outcomes after a detected
positive-catalyst / negative-market-reaction divergence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scanner.market_data import get_daily_series

STATE_FILE = Path("data/divergence_outcomes.json")
FORWARD_DAYS = (1, 3, 5)


def _load():
    if not STATE_FILE.exists():
        return {"version": "1.0", "events": []}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return data
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {"version": "1.0", "events": []}


def _save(data):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _date(value):
    if not value:
        return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _num(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct(start, end):
    if start in (None, 0) or end is None:
        return None
    return (end - start) / start * 100.0


def _outcomes_for_event(event, points):
    event_date = _date(event.get("event_date") or event.get("event_timestamp"))
    event_price = _num(event.get("event_price"))
    event_price_timestamp = event.get("event_price_timestamp") or event.get("event_timestamp")
    if event_date is None:
        return None
    rows = sorted(
        (point.get("date"), float(point["close"]))
        for point in (points or [])
        if point.get("date") is not None and point.get("close") is not None
    )
    if not rows:
        return None

    event_rows = [row for row in rows if row[0] == event_date]
    if not event_rows:
        event_rows = [row for row in rows if row[0] > event_date]
    if not event_rows:
        return None

    entry_date, entry_close = event_rows[0]
    anchor_price = event_price if event_price is not None and event_price > 0 else entry_close
    future = [(date, close) for date, close in rows if date > entry_date][:5]
    result = {
        "entry_date": entry_date.isoformat(),
        "entry_close": entry_close,
        "event_price": anchor_price,
        "event_price_source": "EVENT_INTRADAY" if event_price is not None and event_price > 0 else "DAILY_CLOSE_FALLBACK",
        "event_price_timestamp": event_price_timestamp,
        "event_to_close_pct": _pct(anchor_price, entry_close),
        "outcomes": {},
    }
    for n in FORWARD_DAYS:
        if len(future) >= n:
            date, close = future[n - 1]
            result["outcomes"][f"t{n}"] = {
                "date": date.isoformat(),
                "close": close,
                "return_pct": _pct(anchor_price, close),
            }

    path = [close for _, close in future]
    result["max_favorable_pct"] = max((_pct(entry_close, close) for close in path), default=None)
    result["max_adverse_pct"] = min((_pct(entry_close, close) for close in path), default=None)
    result["recovered_by_t5"] = bool(len(future) >= 5 and future[-1][1] > anchor_price)
    result["max_recovery"] = bool(path and max(path) > anchor_price)
    return result


def record_divergences(divergences):
    data = _load()
    existing = {
        (e.get("ticker"), e.get("program"), e.get("event_timestamp") or e.get("event_date"))
        for e in data["events"]
    }
    added = 0
    for item in divergences or []:
        key = (item.get("ticker"), item.get("program"), item.get("event_timestamp") or item.get("event_date"))
        if key in existing:
            continue
        record = dict(item)
        record["created_at"] = datetime.now(timezone.utc).isoformat()
        record["status"] = "PENDING"
        data["events"].append(record)
        existing.add(key)
        added += 1
    if added:
        _save(data)
    return added


def update_divergence_outcomes():
    data = _load()
    changed = 0
    for event in data["events"]:
        if event.get("status") == "COMPLETE":
            continue
        points = get_daily_series(event.get("ticker"))
        outcome = _outcomes_for_event(event, points)
        if not outcome:
            continue
        before = json.dumps(event.get("outcomes_snapshot"), sort_keys=True)
        event["outcomes_snapshot"] = outcome
        if all(f"t{n}" in outcome.get("outcomes", {}) for n in FORWARD_DAYS):
            event["status"] = "COMPLETE"
        after = json.dumps(outcome, sort_keys=True)
        if before != after:
            changed += 1
    if changed:
        _save(data)
    return changed


def summarize_divergence_outcomes():
    data = _load()
    summary = {
        "sample_total": len(data["events"]),
        "completed": sum(e.get("status") == "COMPLETE" for e in data["events"]),
        "by_horizon": {},
    }
    for n in FORWARD_DAYS:
        vals = []
        for event in data["events"]:
            row = (event.get("outcomes_snapshot") or {}).get("outcomes", {}).get(f"t{n}")
            if row and row.get("return_pct") is not None:
                vals.append(float(row["return_pct"]))
        if not vals:
            continue
        vals.sort()
        mid = len(vals) // 2
        median = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2
        gains = sum(v for v in vals if v > 0)
        losses = sum(-v for v in vals if v < 0)
        summary["by_horizon"][f"t{n}"] = {
            "n": len(vals),
            "median_return_pct": round(median, 4),
            "mean_return_pct": round(sum(vals) / len(vals), 4),
            "win_rate": round(sum(v > 0 for v in vals) / len(vals), 4),
            "profit_factor": round(gains / losses, 4) if losses else None,
        }
    return summary


def track_divergence_outcomes(divergences=None):
    added = record_divergences(divergences or [])
    updated = update_divergence_outcomes()
    return {"added": added, "updated": updated, "summary": summarize_divergence_outcomes()}
