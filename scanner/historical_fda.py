"""Historical FDA catalyst discovery from the public Drugs@FDA/openFDA dataset."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any

import requests

API_URL = "https://api.fda.gov/drug/drugsfda.json"
GENERIC_TOKENS = {
    "therapeutics", "pharmaceuticals", "pharmaceutical", "pharma", "sciences",
    "biopharma", "biosciences", "inc", "inc.", "ltd", "corp", "corporation",
    "company", "holdings", "group", "limited", "plc",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _tokens(company: str) -> list[str]:
    out: list[str] = []
    for raw in re.findall(r"[A-Za-z0-9]+", company):
        token = raw.lower()
        if len(token) >= 5 and token not in GENERIC_TOKENS and token not in out:
            out.append(token)
    return out[:3]


def _program_tokens(programs: list[str]) -> list[str]:
    """Return conservative searchable tokens for watchlist drug/program names."""
    out: list[str] = []
    for program in programs:
        for raw in re.findall(r"[A-Za-z0-9]+", str(program or "")):
            token = raw.lower()
            if len(token) >= 4 and token not in out and token not in GENERIC_TOKENS:
                out.append(token)
    return out[:12]


def _event_id(event: dict[str, Any]) -> str:
    raw = "|".join(str(event.get(k) or "") for k in (
        "ticker", "application_number", "submission_number", "subtype", "event_timestamp"
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _submission_date(value: Any) -> date | None:
    text = str(value or "")
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _product(result: dict[str, Any]) -> tuple[str, str]:
    products = result.get("products") or []
    product = products[0] if products else {}
    brand = str(product.get("brand_name") or "")
    ingredients = product.get("active_ingredients") or []
    generic = str((ingredients[0] or {}).get("name") or "") if ingredients else ""
    return generic, brand


def _program_match(result: dict[str, Any], programs: list[str]) -> str | None:
    """Match a returned FDA product to a watchlist program by brand/ingredient."""
    if not programs:
        return None
    haystack = " ".join(
        [
            str(result.get("sponsor_name") or ""),
            *[
                str(x.get("brand_name") or "")
                for x in (result.get("products") or [])
                if isinstance(x, dict)
            ],
            *[
                str(ingredient.get("name") or "")
                for product in (result.get("products") or [])
                if isinstance(product, dict)
                for ingredient in (product.get("active_ingredients") or [])
                if isinstance(ingredient, dict)
            ],
        ]
    ).lower()
    for program in programs:
        if program and str(program).lower() in haystack:
            return program
    return None


def _query_pages(
    session: requests.Session,
    search: str,
    max_pages: int,
) -> list[dict[str, Any]]:
    """Page through an openFDA search, whose maximum limit is 99 per call."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    skip = 0
    for _ in range(max_pages):
        params = {"search": search, "limit": 99, "skip": skip}
        response = session.get(API_URL, params=params, timeout=30)
        if response.status_code == 404:
            break
        response.raise_for_status()
        payload = response.json()
        page = payload.get("results") or []
        if not page:
            break
        for result in page:
            key = str(result.get("application_number") or repr(result))
            if key not in seen:
                seen.add(key)
                results.append(result)
        if len(page) < 99:
            break
        skip += 99
    return results


def _build_events(
    ticker: str,
    company: str,
    result: dict[str, Any],
    start_date: date,
    matched_program: str | None,
) -> list[dict[str, Any]]:
    application = str(result.get("application_number") or "")
    if not (application.startswith("NDA") or application.startswith("BLA")):
        return []

    generic, brand = _product(result)
    sponsor = str(result.get("sponsor_name") or "")
    events: list[dict[str, Any]] = []
    for submission in result.get("submissions") or []:
        if str(submission.get("submission_status") or "").upper() != "AP":
            continue
        event_date = _submission_date(submission.get("submission_status_date"))
        if event_date is None or event_date < start_date:
            continue
        submission_type = str(submission.get("submission_type") or "").upper()
        subtype = "FDA_APPROVAL" if submission_type == "ORIG" else "LABEL_EXPANSION"
        event = {
            "event_id": None,
            "ticker": ticker,
            "company": company,
            "program": matched_program or generic or brand or application,
            "subtype": subtype,
            "direction": "POSITIVE",
            "event_timestamp": event_date.isoformat(),
            "source": "FDA",
            "source_type": "PRIMARY_REGULATORY",
            "url": "https://www.accessdata.fda.gov/scripts/cder/daf/",
            "application_number": application,
            "submission_number": str(submission.get("submission_number") or ""),
            "submission_type": submission_type,
            "sponsor_name": sponsor,
            "brand_name": brand,
            "generic_name": generic,
            "association": "PROGRAM_MATCH" if matched_program else "SPONSOR_MATCH",
        }
        event["event_id"] = _event_id(event)
        events.append(event)
    return events


def discover_fda(
    session: requests.Session,
    ticker: str,
    company: str,
    start_date: date,
    programs: list[str] | None = None,
    max_pages_per_token: int = 5,
) -> list[dict[str, Any]]:
    """Return historical NDA/BLA approval and label catalysts.

    Discovery uses two complementary paths:
    1. sponsor-name searches for the current/known company name;
    2. program/brand/active-ingredient searches for watchlist programs.

    The second path is important for historical records where the FDA sponsor
    name differs from the company's current public name (renaming, acquisition,
    subsidiary, licensing, etc.). Generic ANDA applications remain excluded.
    """
    programs = programs or []
    events: dict[str, dict[str, Any]] = {}

    for token in _tokens(company):
        search = f'sponsor_name:*{token}* AND submissions.submission_status:AP'
        for result in _query_pages(session, search, max_pages_per_token):
            for event in _build_events(ticker, company, result, start_date, None):
                events[event["event_id"]] = event

    for token in _program_tokens(programs):
        queries = (
            f'products.brand_name:*{token}* AND submissions.submission_status:AP',
            f'products.active_ingredients.name:*{token}* AND submissions.submission_status:AP',
        )
        for search in queries:
            for result in _query_pages(session, search, max_pages_per_token):
                matched = _program_match(result, programs)
                if not matched:
                    continue
                for event in _build_events(ticker, company, result, start_date, matched):
                    events[event["event_id"]] = event

    return sorted(events.values(), key=lambda x: str(x.get("event_timestamp") or ""))
