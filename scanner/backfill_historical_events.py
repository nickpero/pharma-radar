"""Prepare a conservative historical-catalyst backfill queue.

The queue is deliberately non-synthetic: it never invents events or prices.
Existing catalyst memory is normalized into stable records so later historical
source discovery can safely enrich it without corrupting the live memory.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "data" / "catalyst_history.json"
WATCHLIST = ROOT / "data" / "watchlist.json"
OUTPUT = ROOT / "data" / "historical_backfill_queue.json"

VALID_SUBTYPES = {
    "FDA_APPROVAL", "FDA_REJECTION", "FDA_SAFETY_WARNING", "TRIAL_HOLD",
    "TRIAL_HOLD_LIFTED", "PHASE_ADVANCED", "CLINICAL_RESULTS",
    "REGULATORY_FILING", "LABEL_EXPANSION", "DATE_ACCELERATED",
    "DATE_DELAYED", "STATUS_CHANGE", "PHASE_CHANGE", "ENROLLMENT_CHANGE",
    "PROTOCOL_CHANGE", "NEW_TRIAL",
}


def _load(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _event_id(event: dict) -> str:
    raw = "|".join(str(event.get(k, "")) for k in (
        "ticker", "program", "subtype", "event_timestamp", "source", "url"
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_queue() -> dict:
    memory = _load(MEMORY, {})
    watchlist = _load(WATCHLIST, [])
    records = memory.values() if isinstance(memory, dict) else memory

    known = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        ticker = str(record.get("ticker") or "").upper()
        subtype = str(record.get("subtype") or "").upper()
        if not ticker or subtype not in VALID_SUBTYPES:
            continue
        item = {
            "event_id": _event_id(record),
            "ticker": ticker,
            "company": record.get("company"),
            "program": record.get("program"),
            "subtype": subtype,
            "direction": record.get("direction", "UNKNOWN"),
            "event_timestamp": record.get("event_timestamp"),
            "source": record.get("source"),
            "source_type": record.get("source_type"),
            "url": record.get("url"),
            "event_price": record.get("event_price"),
            "status": "READY" if record.get("event_price") is not None else "NEEDS_PRICE",
        }
        known[item["event_id"]] = item

    tickers = []
    if isinstance(watchlist, list):
        tickers = [str(x.get("ticker") or "").upper() for x in watchlist if isinstance(x, dict)]
    elif isinstance(watchlist, dict):
        tickers = [str(x).upper() for x in watchlist]

    observed = {x["ticker"] for x in known.values()}
    missing_tickers = sorted(set(filter(None, tickers)) - observed)

    output = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Historical catalyst backfill queue; no synthetic events or prices",
        "events": sorted(known.values(), key=lambda x: str(x.get("event_timestamp") or "")),
        "events_count": len(known),
        "watchlist_tickers": len(set(filter(None, tickers))),
        "tickers_with_history": len(observed),
        "tickers_without_history": missing_tickers,
        "ready_for_metrics": sum(x["status"] == "READY" for x in known.values()),
        "needs_price": sum(x["status"] == "NEEDS_PRICE" for x in known.values()),
    }
    OUTPUT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    result = build_queue()
    print(json.dumps({k: result[k] for k in (
        "events_count", "watchlist_tickers", "tickers_with_history",
        "ready_for_metrics", "needs_price", "tickers_without_history"
    )}, indent=2))
