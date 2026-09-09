"""Multi-source historical catalyst discovery for Pharma Radar.

Historical catalyst discovery deliberately separates true tradable catalysts
from generic trial-record milestones. SEC historical endpoints are not relied
on here because GitHub-hosted runners may receive access-denied responses.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .historical_clinical_trials import discover_clinical_trials
from .historical_fda import discover_fda

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "data" / "watchlist.json"
OUTPUT = ROOT / "data" / "historical_discovered_events.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_key(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or "|".join(
        str(event.get(k) or "")
        for k in ("ticker", "program", "subtype", "event_timestamp", "source")
    ))


def discover(start_year: int = 2015) -> dict[str, Any]:
    watchlist = _load(WATCHLIST)
    start_date = date(start_year, 1, 1)
    session = requests.Session()
    events: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    source_counts: dict[str, int] = {}

    for ticker, item in watchlist.items():
        company = str(item.get("company") or ticker)
        programs = [str(x) for x in item.get("programs") or []]
        try:
            for event in discover_fda(session, ticker, company, start_date):
                events[_event_key(event)] = event
        except Exception as exc:
            errors.append({"ticker": ticker, "source": "FDA", "error": str(exc)})

        try:
            for event in discover_clinical_trials(session, ticker, company, programs, start_date):
                events[_event_key(event)] = event
        except Exception as exc:
            errors.append({"ticker": ticker, "source": "ClinicalTrials.gov", "error": str(exc)})

    ordered = sorted(events.values(), key=lambda x: str(x.get("event_timestamp") or ""))
    for event in ordered:
        source = str(event.get("source") or "UNKNOWN")
        source_counts[source] = source_counts.get(source, 0) + 1

    payload = {
        "version": "3.0-multisource",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_year": start_year,
        "tickers": len(watchlist),
        "events": ordered,
        "events_count": len(ordered),
        "by_source": source_counts,
        "errors": errors[:500],
        "notes": [
            "SEC historical discovery is intentionally excluded from this runner because data.sec.gov and efts.sec.gov returned 403 on GitHub-hosted runners.",
            "FDA discovery uses wildcard sponsor matching against Drugs@FDA/openFDA and excludes generic ANDA approvals.",
            "ClinicalTrials.gov events are conservative informational milestones; they do not imply positive or negative efficacy.",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


if __name__ == "__main__":
    year = 2015
    result = discover(year)
    print(json.dumps({k: result[k] for k in ("start_year", "tickers", "events_count", "by_source", "errors")}, indent=2))
