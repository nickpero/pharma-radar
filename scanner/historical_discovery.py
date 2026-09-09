"""Discover real historical pharma catalysts from SEC EDGAR and FDA Drugs@FDA.

The discovery layer is deliberately conservative: it only emits events backed by
primary regulatory/corporate sources and never invents prices or market returns.
Market prices are resolved later by the Historical Edge builder.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "data" / "watchlist.json"
OUTPUT = ROOT / "data" / "historical_discovered_events.json"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
FDA_URL = "https://api.fda.gov/drug/drugsfda.json"
DEFAULT_START_YEAR = 2018

CATALYST_ITEMS = {"1.01", "1.02", "2.02", "7.01", "8.01"}
FORMS = {"8-K", "8-K/A", "6-K", "6-K/A"}

PATTERNS = [
    ("FDA_REJECTION", "NEGATIVE", ("complete response letter", "not approved", "rejected", "rejection", "refused", "denied")),
    ("TRIAL_HOLD", "NEGATIVE", ("clinical hold", "placed on hold", "study hold")),
    ("FDA_SAFETY_WARNING", "NEGATIVE", ("boxed warning", "safety warning", "serious safety signal", "safety concern")),
    ("CLINICAL_RESULTS", "NEGATIVE", ("failed to meet", "did not meet", "missed the primary endpoint", "failed the primary endpoint", "futility", "negative topline")),
    ("CLINICAL_RESULTS", "POSITIVE", ("met the primary endpoint", "met its primary endpoint", "positive topline", "positive results", "statistically significant", "clinical benefit", "topline results", "clinical trial results")),
    ("FDA_APPROVAL", "POSITIVE", ("fda approves", "fda approved", "receives fda approval", "received fda approval", "full approval", "granted approval")),
    ("LABEL_EXPANSION", "POSITIVE", ("label expansion", "expanded indication", "new indication", "expanded use")),
    ("PHASE_ADVANCED", "POSITIVE", ("advanced to phase", "advances to phase", "phase 2", "phase 3")),
    ("DATE_ACCELERATED", "POSITIVE", ("accelerated timeline", "earlier than expected", "accelerated the timeline")),
    ("DATE_DELAYED", "NEGATIVE", ("delayed timeline", "delay in the timeline", "later than expected", "delayed submission")),
    ("REGULATORY_FILING", "POSITIVE", ("nda submission", "bla submission", "regulatory submission", "submitted the application", "filing accepted")),
]


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return unescape(" ".join(self.parts))


def _html_text(value: str) -> str:
    parser = _TextParser()
    try:
        parser.feed(value)
        return re.sub(r"\s+", " ", parser.text()).strip()
    except Exception:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _headers(source: str) -> dict[str, str]:
    return {"User-Agent": f"Pharma-Radar/1.0 {source}", "Accept-Encoding": "gzip, deflate"}


def _event_id(item: dict[str, Any]) -> str:
    import hashlib
    raw = "|".join(str(item.get(k) or "") for k in ("ticker", "program", "subtype", "event_timestamp", "source", "url"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _classify(text: str) -> tuple[str, str] | None:
    normalized = text.lower()
    # Reject boilerplate-only hits: look for the strongest phrase first.
    for subtype, direction, phrases in PATTERNS:
        if any(phrase in normalized for phrase in phrases):
            return subtype, direction
    return None


def _program_from_text(text: str, programs: list[str]) -> str | None:
    lower = text.lower()
    for program in programs:
        if program and program.lower() in lower:
            return program
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _sec_company_map(session: requests.Session) -> dict[str, dict[str, str]]:
    response = session.get(SEC_TICKERS_URL, headers=_headers("sec-ticker-map"), timeout=30)
    response.raise_for_status()
    payload = response.json()
    result: dict[str, dict[str, str]] = {}
    for row in payload.values():
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            result[ticker] = {"cik": str(row.get("cik_str") or ""), "name": str(row.get("title") or "")}
    return result


def _submission_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    recent = ((payload.get("filings") or {}).get("recent") or {})
    keys = ["accessionNumber", "filingDate", "acceptanceDateTime", "form", "items", "primaryDocument", "primaryDocDescription"]
    count = len(recent.get("form") or [])
    for i in range(count):
        rows.append({key: (recent.get(key) or [None] * count)[i] for key in keys})
    return rows


def _all_sec_rows(session: requests.Session, cik: str, start_date: date) -> list[dict[str, Any]]:
    padded = str(cik).zfill(10)
    response = session.get(SEC_SUBMISSIONS_URL.format(cik=padded), headers=_headers("sec-submissions"), timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = _submission_rows(payload)
    for older in ((payload.get("filings") or {}).get("files") or []):
        name = older.get("name")
        if not name:
            continue
        item_response = session.get(f"https://data.sec.gov/submissions/{name}", headers=_headers("sec-submissions-history"), timeout=30)
        if item_response.ok:
            try:
                rows.extend(_submission_rows({"filings": {"recent": item_response.json()}}))
            except Exception:
                continue
    return [row for row in rows if (_parse_date(row.get("filingDate")) or date.min) >= start_date]


def discover_sec(session: requests.Session, ticker: str, company: str, programs: list[str], cik: str, start_date: date, max_filings: int = 300) -> list[dict[str, Any]]:
    rows = _all_sec_rows(session, cik, start_date)
    candidates: list[dict[str, Any]] = []
    for row in rows:
        form = str(row.get("form") or "").upper()
        if form not in FORMS:
            continue
        items = {x.strip() for x in str(row.get("items") or "").replace(";", ",").split(",") if x.strip()}
        desc = str(row.get("primaryDocDescription") or "").lower()
        if form.startswith("8-K") and not (items & CATALYST_ITEMS) and not any(k in desc for k in ("clinical", "trial", "results", "fda", "approval", "drug", "data")):
            continue
        candidates.append(row)
    candidates = sorted(candidates, key=lambda x: str(x.get("filingDate") or ""), reverse=True)[:max_filings]

    events: list[dict[str, Any]] = []
    for row in candidates:
        accession = str(row.get("accessionNumber") or "")
        document = str(row.get("primaryDocument") or "")
        if not accession or not document:
            continue
        archive_cik = str(int(cik))
        url = SEC_ARCHIVE_URL.format(cik=archive_cik, accession=accession.replace("-", ""), document=document)
        try:
            response = session.get(url, headers=_headers("sec-filing"), timeout=30)
            if not response.ok:
                continue
            text = _html_text(response.text)[:180_000]
        except Exception:
            continue
        title = str(row.get("primaryDocDescription") or document)
        classified = _classify(f"{title} {text}")
        if not classified:
            continue
        subtype, direction = classified
        program = _program_from_text(text, programs) or _program_from_text(title, programs)
        event = {
            "event_id": None,
            "ticker": ticker,
            "company": company,
            "program": program,
            "subtype": subtype,
            "direction": direction,
            "event_timestamp": row.get("acceptanceDateTime") or row.get("filingDate"),
            "source": "SEC",
            "source_type": "PRIMARY_CORPORATE",
            "url": url,
            "accession_number": accession,
            "form": row.get("form"),
            "items": row.get("items"),
            "title": title,
        }
        event["event_id"] = _event_id(event)
        events.append(event)
    return events


def _fda_query(session: requests.Session, sponsor: str, start_date: date) -> list[dict[str, Any]]:
    start = start_date.strftime("%Y%m%d")
    query = f'sponsor_name:"{sponsor}" AND submissions.submission_status:AP AND submissions.submission_status_date:[{start} TO 99991231]'
    response = session.get(FDA_URL, params={"search": query, "limit": 99}, timeout=30)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json().get("results") or []


def discover_fda(session: requests.Session, ticker: str, company: str, start_date: date) -> list[dict[str, Any]]:
    results = _fda_query(session, company, start_date)
    events: list[dict[str, Any]] = []
    for result in results:
        app = str(result.get("application_number") or "")
        if not (app.startswith("NDA") or app.startswith("BLA")):
            continue
        products = result.get("products") or []
        product = products[0] if products else {}
        brand = str(product.get("brand_name") or "")
        ingredients = product.get("active_ingredients") or []
        generic = str((ingredients[0] or {}).get("name") or "") if ingredients else ""
        for submission in result.get("submissions") or []:
            if str(submission.get("submission_status") or "").upper() != "AP":
                continue
            action = str(submission.get("submission_status_date") or "")
            if len(action) != 8 or not action.isdigit():
                continue
            event_date = datetime.strptime(action, "%Y%m%d").date()
            if event_date < start_date:
                continue
            subtype = "FDA_APPROVAL" if str(submission.get("submission_type") or "").upper() == "ORIG" else "LABEL_EXPANSION"
            program = generic or brand or app
            event = {
                "event_id": None,
                "ticker": ticker,
                "company": company,
                "program": program,
                "subtype": subtype,
                "direction": "POSITIVE",
                "event_timestamp": event_date.isoformat(),
                "source": "FDA",
                "source_type": "PRIMARY_REGULATORY",
                "url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app.replace('NDA','').replace('BLA','')}",
                "application_number": app,
                "brand_name": brand,
                "generic_name": generic,
            }
            event["event_id"] = _event_id(event)
            events.append(event)
    return events


def discover(start_year: int = DEFAULT_START_YEAR) -> dict[str, Any]:
    start_date = date(start_year, 1, 1)
    watchlist = _load(WATCHLIST)
    session = requests.Session()
    sec_map = _sec_company_map(session)
    events: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []

    for ticker, item in watchlist.items():
        company = str(item.get("company") or ticker)
        programs = [str(x) for x in item.get("programs") or []]
        try:
            sec = sec_map.get(ticker, {})
            cik = sec.get("cik")
            if cik:
                for event in discover_sec(session, ticker, company, programs, cik, start_date):
                    events[event["event_id"]] = event
        except Exception as exc:
            errors.append({"ticker": ticker, "source": "SEC", "error": str(exc)})
        try:
            for event in discover_fda(session, ticker, company, start_date):
                events[event["event_id"]] = event
        except Exception as exc:
            errors.append({"ticker": ticker, "source": "FDA", "error": str(exc)})

    ordered = sorted(events.values(), key=lambda x: str(x.get("event_timestamp") or ""))
    payload = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_year": start_year,
        "tickers": len(watchlist),
        "events": ordered,
        "events_count": len(ordered),
        "by_source": {source: sum(1 for x in ordered if x.get("source") == source) for source in ("SEC", "FDA")},
        "errors": errors[:200],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = discover()
    print(json.dumps({k: result[k] for k in ("start_year", "tickers", "events_count", "by_source", "errors")}, indent=2))
