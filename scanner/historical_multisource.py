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
from .historical_fda_crl import discover_fda_crl

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "data" / "watchlist.json"
HISTORICAL_UNIVERSE = ROOT / "data" / "historical_universe.json"
OUTPUT = ROOT / "data" / "historical_discovered_events.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_key(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or "|".join(
        str(event.get(k) or "")
        for k in ("ticker", "program", "subtype", "event_timestamp", "source")
    ))


def _universe() -> dict[str, Any]:
    """Load the dedicated historical universe, falling back to live watchlist."""
    if HISTORICAL_UNIVERSE.exists():
        return _load(HISTORICAL_UNIVERSE)
    return _load(WATCHLIST)


def discover(start_year: int = 2015) -> dict[str, Any]:
    universe = _universe()
    start_date = date(start_year, 1, 1)
    session = requests.Session()
    events: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    source_counts: dict[str, int] = {}

    for ticker, item in universe.items():
        company = str(item.get("company") or ticker)
        programs = [str(x) for x in item.get("programs") or []]

        try:
            for event in discover_fda(session, ticker, company, start_date, programs=programs):
                events[_event_key(event)] = event
        except Exception as exc:
            errors.append({"ticker": ticker, "source": "FDA", "error": str(exc)})

        try:
            for event in discover_fda_crl(session, ticker, company, start_date):
                events[_event_key(event)] = event
        except Exception as exc:
            errors.append({"ticker": ticker, "source": "FDA_CRL", "error": str(exc)})

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
        "version": "3.3-multisource-historical-universe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_year": start_year,
        "tickers": len(universe),
        "live_watchlist_tickers": len(_load(WATCHLIST)),
        "events": ordered,
        "events_count": len(ordered),
        "by_source": source_counts,
        "errors": errors[:500],
        "notes": [
            "Historical discovery uses a dedicated expanded universe so live alert watchlist size is not changed.",
            "SEC historical discovery is intentionally excluded from this runner because data.sec.gov and efts.sec.gov returned 403 on GitHub-hosted runners.",
            "FDA Drugs@FDA discovery uses sponsor-name plus watchlist program/brand/active-ingredient searches and excludes generic ANDA approvals.",
            "FDA Complete Response Letters are treated as negative regulatory catalysts; the CRL dataset currently covers recent historical years rather than the full 2015-present period.",
            "ClinicalTrials.gov events are conservative informational milestones; they do not imply positive or negative efficacy.",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = discover(2015)
    print(json.dumps({k: result[k] for k in ("start_year", "tickers", "live_watchlist_tickers", "events_count", "by_source", "errors")}, indent=2))
