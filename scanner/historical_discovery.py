"""Discover real historical pharma catalysts from SEC EDGAR and FDA Drugs@FDA."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST = ROOT / "data" / "watchlist.json"
SEC_CIK_MAP = ROOT / "data" / "sec_cik_map.json"
OUTPUT = ROOT / "data" / "historical_discovered_events.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
FDA_URL = "https://api.fda.gov/drug/drugsfda.json"
DEFAULT_START_YEAR = 2015
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
    ("PHASE_ADVANCED", "POSITIVE", ("advanced to phase", "advances to phase", "progressed to phase")),
    ("DATE_ACCELERATED", "POSITIVE", ("accelerated timeline", "earlier than expected", "accelerated the timeline")),
    ("DATE_DELAYED", "NEGATIVE", ("delayed timeline", "delay in the timeline", "later than expected", "delayed submission")),
    ("REGULATORY_FILING", "POSITIVE", ("nda submission", "bla submission", "regulatory submission", "submitted the application", "filing accepted")),
]

# Narrow queries are used by the EFTS fallback.  They let the query itself
# provide the catalyst class even though we do not download the filing body.
EFTS_QUERIES = (
    ("NEGATIVE", '"complete response letter" OR "not approved" OR rejected OR rejection OR refused OR denied OR "failed to meet" OR "did not meet" OR "missed the primary endpoint" OR "failed the primary endpoint" OR futility OR "negative topline"'),
    ("HOLD_SAFETY", '"clinical hold" OR "placed on hold" OR "study hold" OR "boxed warning" OR "safety warning" OR "serious safety signal" OR "safety concern"'),
    ("POSITIVE_CLINICAL", '"met the primary endpoint" OR "met its primary endpoint" OR "positive topline" OR "positive results" OR "statistically significant" OR "clinical benefit" OR "topline results" OR "clinical trial results"'),
    ("REGULATORY", '"fda approves" OR "fda approved" OR "receives fda approval" OR "received fda approval" OR "full approval" OR "granted approval" OR "label expansion" OR "expanded indication" OR "new indication" OR "expanded use" OR "advanced to phase" OR "advances to phase" OR "progressed to phase" OR "nda submission" OR "bla submission" OR "regulatory submission" OR "submitted the application" OR "filing accepted"'),
    ("TIMING", '"accelerated timeline" OR "earlier than expected" OR "accelerated the timeline" OR "delayed timeline" OR "delay in the timeline" OR "later than expected" OR "delayed submission"'),
)


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
    # SEC requires automated clients to declare an identifying User-Agent with
    # a contact address. Keep it configurable so the workflow can override it.
    user_agent = os.getenv(
        "SEC_USER_AGENT",
        "Pharma Radar/1.0 (103763934+nickpero@users.noreply.github.com)",
    )
    return {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
    }


def _event_id(item: dict[str, Any]) -> str:
    raw = "|".join(str(item.get(k) or "") for k in ("ticker", "program", "subtype", "event_timestamp", "source", "url"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _classify(text: str) -> tuple[str, str] | None:
    normalized = text.lower()
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


def _sec_company_map(session: requests.Session | None = None) -> dict[str, dict[str, str]]:
    """Return the watchlist's local ticker→CIK map.

    We deliberately do not call SEC company_tickers.json here. GitHub Actions
    runners can receive 403 responses from that endpoint even with a valid
    identifying User-Agent. The watchlist is intentionally small and stable,
    so the CIK mapping is version-controlled locally in data/sec_cik_map.json.
    """
    payload = _load(SEC_CIK_MAP)
    if not isinstance(payload, dict):
        raise ValueError("data/sec_cik_map.json must contain a JSON object")
    result: dict[str, dict[str, str]] = {}
    for ticker, cik in payload.items():
        ticker_key = str(ticker).upper().strip()
        cik_value = str(cik).strip()
        if ticker_key and cik_value.isdigit():
            result[ticker_key] = {"cik": cik_value, "name": ticker_key}
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


def _efts_accession_document(hit: dict[str, Any]) -> tuple[str, str]:
    raw_id = str(hit.get("_id") or "")
    if ":" in raw_id:
        accession, document = raw_id.split(":", 1)
        return accession, document
    source = hit.get("_source") or {}
    accession = str(source.get("adsh") or source.get("accession_number") or "")
    document = str(source.get("file_name") or source.get("document") or "")
    return accession, document


def _efts_classification(category: str, title: str) -> tuple[str, str]:
    # Prefer the filing title when it explicitly identifies the event; otherwise
    # fall back to the query bucket that produced the hit.
    classified = _classify(title)
    if classified:
        return classified
    if category == "NEGATIVE":
        return "CLINICAL_RESULTS", "NEGATIVE"
    if category == "HOLD_SAFETY":
        lower = title.lower()
        if "safety" in lower or "warning" in lower:
            return "FDA_SAFETY_WARNING", "NEGATIVE"
        return "TRIAL_HOLD", "NEGATIVE"
    if category == "POSITIVE_CLINICAL":
        return "CLINICAL_RESULTS", "POSITIVE"
    if category == "REGULATORY":
        lower = title.lower()
        if "approval" in lower or "approves" in lower or "approved" in lower:
            return "FDA_APPROVAL", "POSITIVE"
        if "label" in lower or "indication" in lower:
            return "LABEL_EXPANSION", "POSITIVE"
        if "phase" in lower:
            return "PHASE_ADVANCED", "POSITIVE"
        return "REGULATORY_FILING", "POSITIVE"
    if "delay" in title.lower() or "delayed" in title.lower():
        return "DATE_DELAYED", "NEGATIVE"
    return "DATE_ACCELERATED", "POSITIVE"


def discover_sec_efts(
    session: requests.Session,
    ticker: str,
    company: str,
    programs: list[str],
    cik: str,
    start_date: date,
    max_pages_per_query: int = 5,
) -> list[dict[str, Any]]:
    """Discover catalysts from SEC's Full-Text Search index without archive downloads.

    This is the GitHub Actions-safe path when data.sec.gov/submissions is blocked.
    EFTS is a separate SEC host and returns filing metadata for matching full-text
    phrases, so we can build conservative catalyst events without downloading the
    filing HTML from www.sec.gov.
    """
    padded = str(cik).zfill(10)
    end_date = date.today()
    events: dict[str, dict[str, Any]] = {}

    for category, query in EFTS_QUERIES:
        offset = 0
        for _ in range(max_pages_per_query):
            params = {
                "q": f"({query})",
                "forms": "8-K,6-K",
                "dateRange": "custom",
                "startdt": start_date.isoformat(),
                "enddt": end_date.isoformat(),
                "ciks": padded,
                "from": offset,
                "size": 100,
            }
            response = session.get(SEC_EFTS_URL, params=params, headers=_headers("sec-efts"), timeout=30)
            response.raise_for_status()
            payload = response.json()
            hits = ((payload.get("hits") or {}).get("hits") or [])
            if not hits:
                break

            for hit in hits:
                source = hit.get("_source") or {}
                accession, document = _efts_accession_document(hit)
                file_date = str(source.get("file_date") or source.get("display_date_filed") or "")
                if not accession or not file_date:
                    continue
                if not document:
                    document = ""
                title = str(source.get("file_description") or source.get("file_type") or document or "SEC filing")
                subtype, direction = _efts_classification(category, title)
                program = _program_from_text(title, programs)
                accession_path = accession.replace("-", "")
                if document:
                    url = SEC_ARCHIVE_URL.format(cik=str(int(cik)), accession=accession_path, document=document)
                else:
                    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/"
                event = {
                    "event_id": None,
                    "ticker": ticker,
                    "company": company,
                    "program": program,
                    "subtype": subtype,
                    "direction": direction,
                    "event_timestamp": file_date,
                    "source": "SEC",
                    "source_type": "SEC_EFTS",
                    "url": url,
                    "accession_number": accession,
                    "form": source.get("form_type"),
                    "items": source.get("items"),
                    "title": title,
                }
                event["event_id"] = _event_id(event)
                events[event["event_id"]] = event

            offset += len(hits)
            total = ((payload.get("hits") or {}).get("total") or {}).get("value")
            if len(hits) < 100 or (isinstance(total, int) and offset >= total):
                break
            time.sleep(0.2)
        time.sleep(0.2)

    return list(events.values())


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
        url = SEC_ARCHIVE_URL.format(cik=str(int(cik)), accession=accession.replace("-", ""), document=document)
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
            "event_id": None, "ticker": ticker, "company": company, "program": program,
            "subtype": subtype, "direction": direction,
            "event_timestamp": row.get("acceptanceDateTime") or row.get("filingDate"),
            "source": "SEC", "source_type": "PRIMARY_CORPORATE", "url": url,
            "accession_number": accession, "form": row.get("form"), "items": row.get("items"), "title": title,
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
                "event_id": None, "ticker": ticker, "company": company, "program": program,
                "subtype": subtype, "direction": "POSITIVE", "event_timestamp": event_date.isoformat(),
                "source": "FDA", "source_type": "PRIMARY_REGULATORY",
                "url": f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app.replace('NDA','').replace('BLA','')}",
                "application_number": app, "brand_name": brand, "generic_name": generic,
            }
            event["event_id"] = _event_id(event)
            events.append(event)
    return events


def discover(start_year: int | None = None) -> dict[str, Any]:
    start_year = start_year or int(os.getenv("PHARMA_RADAR_HISTORICAL_START_YEAR", str(DEFAULT_START_YEAR)))
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
            cik = (sec_map.get(ticker) or {}).get("cik")
            if not cik:
                errors.append({"ticker": ticker, "source": "SEC", "error": "Missing local SEC CIK mapping"})
            else:
                try:
                    sec_events = discover_sec(session, ticker, company, programs, cik, start_date)
                except requests.HTTPError as exc:
                    if getattr(exc.response, "status_code", None) == 403:
                        # GitHub-hosted runners can be blocked by data.sec.gov even
                        # with a compliant User-Agent. Fall back to SEC EFTS, which
                        # searches the filing text on its separate search service.
                        sec_events = discover_sec_efts(session, ticker, company, programs, cik, start_date)
                    else:
                        raise
                for event in sec_events:
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
        "version": "1.2", "generated_at": datetime.now(timezone.utc).isoformat(), "start_year": start_year,
        "tickers": len(watchlist), "events": ordered, "events_count": len(ordered),
        "by_source": {source: sum(1 for x in ordered if x.get("source") == source) for source in ("SEC", "FDA")},
        "errors": errors[:200],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = discover()
    print(json.dumps({k: result[k] for k in ("start_year", "tickers", "events_count", "by_source", "errors")}, indent=2))
