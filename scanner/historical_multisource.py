"""Multi-source historical catalyst discovery for Pharma Radar.

SEC is attempted only through the existing discovery module. When SEC hosts are
blocked on GitHub Actions, FDA and ClinicalTrials.gov still populate the same
historical event dataset so the Historical Edge pipeline can proceed.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .historical_clinical_trials import discover_clinical_trials
from .historical_discovery import discover_fda

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "data" / "watchlist.json"
OUTPUT = ROOT / "data" / "historical_discovered_events.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_key(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or "|".join(str(event.get(k) or "") for k in ("ticker", "program", "subtype", "event_timestamp", "source")))


def _fda_token_events(session: requests.Session, ticker: str, company: str, start_date: date) -> list[dict[str, Any]]:
    """Broaden FDA sponsor discovery beyond exact corporate-name matches."""
    from . import historical_discovery as hd

    tokens = [x for x in company.replace(",", " ").split() if len(x) >= 5]
    generic = {"therapeutics", "pharmaceuticals", "pharma", "sciences", "biopharma", "inc", "ltd", "corp", "corporation"}
    tokens = [x for x in tokens if x.lower().strip(".") not in generic]
    events: dict[str, dict[str, Any]] = {}
    for token in tokens[:2]:
        query = f'sponsor_name:{token} AND submissions.submission_status:AP AND submissions.submission_status_date:[{start_date:%Y%m%d} TO 99991231]'
        response = session.get(hd.FDA_URL, params={"search": query, "limit": 99}, timeout=30)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        for result in response.json().get("results") or []:
            app = str(result.get("application_number") or "")
            if not (app.startswith("NDA") or app.startswith("BLA")):
                continue
            for submission in result.get("submissions") or []:
                if str(submission.get("submission_status") or "").upper() != "AP":
                    continue
                raw_date = str(submission.get("submission_status_date") or "")
                if len(raw_date) != 8 or not raw_date.isdigit():
                    continue
                event_date = datetime.strptime(raw_date, "%Y%m%d").date()
                if event_date < start_date:
                    continue
                products = result.get("products") or []
                product = products[0] if products else {}
                ingredients = product.get("active_ingredients") or []
                generic = str((ingredients[0] or {}).get("name") or "") if ingredients else ""
                brand = str(product.get("brand_name") or "")
                subtype = "FDA_APPROVAL" if str(submission.get("submission_type") or "").upper() == "ORIG" else "LABEL_EXPANSION"
                event = {
                    "event_id": None, "ticker": ticker, "company": company,
                    "program": generic or brand or app, "subtype": subtype, "direction": "POSITIVE",
                    "event_timestamp": event_date.isoformat(), "source": "FDA", "source_type": "PRIMARY_REGULATORY",
                    "url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app.replace('NDA','').replace('BLA','')}",
                    "application_number": app, "brand_name": brand, "generic_name": generic,
                    "sponsor_match": token,
                }
                event["event_id"] = hd._event_id(event)
                events[_event_key(event)] = event
    return list(events.values())


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
            for event in _fda_token_events(session, ticker, company, start_date):
                events[_event_key(event)] = event
        except Exception as exc:
            errors.append({"ticker": ticker, "source": "FDA_ALIAS", "error": str(exc)})
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
        "version": "2.0-multisource",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_year": start_year,
        "tickers": len(watchlist),
        "events": ordered,
        "events_count": len(ordered),
        "by_source": source_counts,
        "errors": errors[:500],
        "notes": [
            "SEC historical discovery is intentionally excluded from this runner because both data.sec.gov and efts.sec.gov return 403 on GitHub-hosted runners.",
            "FDA sponsor discovery includes exact and token-based matching.",
            "ClinicalTrials.gov events are dated trial milestones and are conservative informational events, not inferred efficacy outcomes.",
        ],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


if __name__ == "__main__":
    year = 2015
    result = discover(year)
    print(json.dumps({k: result[k] for k in ("start_year", "tickers", "events_count", "by_source", "errors")}, indent=2))
