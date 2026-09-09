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


def discover_fda(
    session: requests.Session,
    ticker: str,
    company: str,
    start_date: date,
    max_pages_per_token: int = 3,
) -> list[dict[str, Any]]:
    """Return FDA approval/label events matching the watchlist company.

    Uses wildcard sponsor searches because sponsor names in Drugs@FDA often
    differ from the current public company name. Only approved NDA/BLA
    submissions are emitted; generic ANDA approvals are excluded because they
    are usually poor proxies for a biotech/company-specific trading catalyst.
    """
    events: dict[str, dict[str, Any]] = {}
    for token in _tokens(company):
        skip = 0
        for _ in range(max_pages_per_token):
            params = {
                "search": f'sponsor_name:*{token}* AND submissions.submission_status:AP',
                "limit": 99,
                "skip": skip,
            }
            response = session.get(API_URL, params=params, timeout=30)
            if response.status_code == 404:
                break
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results") or []
            if not results:
                break
            for result in results:
                application = str(result.get("application_number") or "")
                if not (application.startswith("NDA") or application.startswith("BLA")):
                    continue
                sponsor = str(result.get("sponsor_name") or "")
                if token not in _norm(sponsor):
                    continue
                generic, brand = _product(result)
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
                        "program": generic or brand or application,
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
                    }
                    event["event_id"] = _event_id(event)
                    events[event["event_id"]] = event
            if len(results) < 99:
                break
            skip += 99
    return sorted(events.values(), key=lambda x: str(x.get("event_timestamp") or ""))
