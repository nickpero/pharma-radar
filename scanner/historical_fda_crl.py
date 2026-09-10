"""Historical FDA Complete Response Letter (CRL) catalyst discovery."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any

import requests

API_URL = "https://api.fda.gov/transparency/crl.json"
GENERIC_TOKENS = {
    "therapeutics", "pharmaceuticals", "pharmaceutical", "pharma", "sciences",
    "biopharma", "biosciences", "inc", "ltd", "corp", "corporation",
    "company", "holdings", "group", "limited", "plc", "laboratories", "lab",
}


def _tokens(company: str) -> list[str]:
    out: list[str] = []
    for raw in re.findall(r"[A-Za-z0-9]+", company):
        token = raw.lower()
        if len(token) >= 5 and token not in GENERIC_TOKENS and token not in out:
            out.append(token)
    return out[:3]


def _date(value: Any) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    return None


def _event_id(event: dict[str, Any]) -> str:
    raw = "|".join(str(event.get(k) or "") for k in (
        "ticker", "application_number", "letter_date", "company_name", "subtype"
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _query(session: requests.Session, search: str, limit: int = 100) -> list[dict[str, Any]]:
    response = session.get(API_URL, params={"search": search, "limit": limit}, timeout=30)
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json().get("results") or []


def discover_fda_crl(
    session: requests.Session,
    ticker: str,
    company: str,
    start_date: date,
) -> list[dict[str, Any]]:
    """Return historical CRLs associated with the current watchlist company name."""
    events: dict[str, dict[str, Any]] = {}
    for token in _tokens(company):
        search = f'company_name:*{token}* AND letter_type:"COMPLETE RESPONSE"'
        for result in _query(session, search):
            letter_date = _date(result.get("letter_date"))
            if letter_date is None or letter_date < start_date:
                continue
            company_name = str(result.get("company_name") or "")
            event = {
                "event_id": None,
                "ticker": ticker,
                "company": company,
                "program": str(result.get("approval_name") or "") or None,
                "subtype": "FDA_REJECTION",
                "direction": "NEGATIVE",
                "event_timestamp": letter_date.isoformat(),
                "source": "FDA_CRL",
                "source_type": "PRIMARY_REGULATORY",
                "url": "https://open.fda.gov/crltable/",
                "application_number": result.get("application_number"),
                "company_name": company_name,
                "letter_type": result.get("letter_type"),
                "letter_file": result.get("file_name"),
            }
            event["event_id"] = _event_id(event)
            events[event["event_id"]] = event
    return sorted(events.values(), key=lambda x: str(x.get("event_timestamp") or ""))
