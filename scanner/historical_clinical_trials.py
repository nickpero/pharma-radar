"""Discover historical clinical-trial milestones from ClinicalTrials.gov API v2.

This module intentionally avoids SEC and uses public trial records as a second
historical source. Current study records expose dated milestones that can be
converted into conservative catalyst events for the Historical Edge engine.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

import requests

API_URL = "https://clinicaltrials.gov/api/v2/studies"


def _date(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            return None
    return None


def _event_id(event: dict[str, Any]) -> str:
    raw = "|".join(str(event.get(k) or "") for k in ("ticker", "nct_id", "program", "subtype", "event_timestamp"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _program_match(text: str, programs: list[str]) -> str | None:
    lower = text.lower()
    for program in programs:
        if program and program.lower() in lower:
            return program
    return None


def _make_event(
    ticker: str,
    company: str,
    programs: list[str],
    study: dict[str, Any],
    subtype: str,
    direction: str,
    event_date: str,
) -> dict[str, Any] | None:
    protocol = study.get("protocolSection") or {}
    ident = protocol.get("identificationModule") or {}
    nct_id = str(ident.get("nctId") or "")
    title = str(ident.get("briefTitle") or ident.get("officialTitle") or "Clinical trial")
    program = _program_match(f"{title} {ident.get('officialTitle') or ''}", programs)
    if not nct_id or not event_date:
        return None
    event = {
        "event_id": None,
        "ticker": ticker,
        "company": company,
        "program": program,
        "nct_id": nct_id,
        "subtype": subtype,
        "direction": direction,
        "event_timestamp": event_date,
        "source": "ClinicalTrials.gov",
        "source_type": "CLINICALTRIALS_GOV",
        "url": f"https://clinicaltrials.gov/study/{nct_id}",
        "title": title,
        "study_status": ((protocol.get("statusModule") or {}).get("overallStatus")),
        "phase": ",".join((protocol.get("designModule") or {}).get("phases") or []),
    }
    event["event_id"] = _event_id(event)
    return event


def _milestones(study: dict[str, Any]) -> list[tuple[str, str, str]]:
    protocol = study.get("protocolSection") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    out: list[tuple[str, str, str]] = []

    start = _date((status.get("startDateStruct") or {}).get("date"))
    primary = _date((status.get("primaryCompletionDateStruct") or {}).get("date"))
    completion = _date((status.get("completionDateStruct") or {}).get("date"))
    results = _date(((study.get("resultsSection") or {}).get("statusModule") or {}).get("resultsFirstPostDateStruct", {}).get("date"))
    last_update = _date((status.get("lastUpdatePostDateStruct") or {}).get("date"))

    if start:
        out.append(("TRIAL_STARTED", "POSITIVE", start))
    if primary:
        out.append(("PRIMARY_COMPLETION", "POSITIVE", primary))
    if completion:
        out.append(("TRIAL_COMPLETED", "POSITIVE", completion))
    if results:
        out.append(("TRIAL_RESULTS_POSTED", "POSITIVE", results))
    if last_update and not any(last_update == x[2] for x in out):
        # Last update is useful only when no stronger dated milestone exists.
        out.append(("TRIAL_UPDATED", "NEUTRAL", last_update))
    phases = [str(x).upper() for x in (design.get("phases") or [])]
    if phases and primary:
        out.append(("PHASE_MILESTONE", "POSITIVE", primary))
    return out


def discover_clinical_trials(
    session: requests.Session,
    ticker: str,
    company: str,
    programs: list[str],
    start_date: date,
    max_studies: int = 100,
) -> list[dict[str, Any]]:
    """Return conservative dated milestones for trials matching company/programs.

    Searches by company and by program. Results are deduplicated by NCT ID and
    milestone date. We do not infer positive/negative efficacy from a trial's
    existence or completion; the generated events are informational milestones.
    """
    studies: dict[str, dict[str, Any]] = {}
    queries = [company] + [p for p in programs if p]
    for query in queries:
        params = {
            "query.term": query,
            "pageSize": min(max_studies, 100),
            "format": "json",
        }
        response = session.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        for study in payload.get("studies") or []:
            protocol = study.get("protocolSection") or {}
            nct_id = str((protocol.get("identificationModule") or {}).get("nctId") or "")
            if nct_id:
                studies[nct_id] = study

    events: dict[str, dict[str, Any]] = {}
    for study in studies.values():
        protocol = study.get("protocolSection") or {}
        ident = protocol.get("identificationModule") or {}
        title = str(ident.get("briefTitle") or ident.get("officialTitle") or "")
        sponsor = str(((protocol.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}).get("name") or "")
        haystack = f"{title} {sponsor} {ident.get('nctId') or ''}"
        # Keep company/program matching strict enough to avoid unrelated studies.
        if company.lower() not in haystack.lower() and not _program_match(haystack, programs):
            continue
        for subtype, direction, event_date in _milestones(study):
            if date.fromisoformat(event_date) < start_date:
                continue
            event = _make_event(ticker, company, programs, study, subtype, direction, event_date)
            if event:
                events[event["event_id"]] = event
    return sorted(events.values(), key=lambda x: str(x.get("event_timestamp") or ""))
