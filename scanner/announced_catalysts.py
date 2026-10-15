"""Validation and alert-window helpers for company-announced clinical catalysts.

The JSON feed is source-backed and curated; no event is inferred from trial
completion dates. Dates retain their declared precision.
"""
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANNOUNCED_CATALYSTS_PATH = ROOT / "data" / "announced_catalysts.json"
READOUT, MILESTONE, REVIEW = "CLINICAL_READOUT", "TRIAL_MILESTONE", "CLINICAL_REVIEW"
VALID_TYPES = {READOUT, MILESTONE, REVIEW}


def classify_announced_event(event):
    item = dict(event)
    event_type = str(item.get("event_type") or "").upper().strip()
    if event_type not in VALID_TYPES:
        raise ValueError(f"Unsupported event_type: {event_type or 'MISSING'}")
    item["event_type"] = event_type
    item["ticker"] = str(item.get("ticker") or "").strip().upper()
    if not item["ticker"]:
        raise ValueError("ticker is required")
    if not (item.get("source_url") or item.get("source")):
        raise ValueError("source or source_url is required")
    if not (item.get("event_name") or item.get("title")):
        raise ValueError("event_name or title is required")
    if event_type == READOUT:
        item["clinical_outcome_available"] = bool(item.get("clinical_outcome_available", True))
        item["actionability"] = item.get("actionability") or "CATALYST"
    else:
        item["clinical_outcome_available"] = False
        item["actionability"] = "WATCH"
        item["direction"] = "UNKNOWN"
    return item


def event_fingerprint(event):
    explicit_id = str(event.get("event_id") or "").strip()
    if explicit_id:
        raw = explicit_id.lower()
    else:
        parts = (event.get("ticker"), event.get("program"), event.get("event_name") or event.get("title"),
                 event.get("event_type"), event.get("date") or event.get("window_start"))
        raw = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def deduplicate_events(events):
    unique = {}
    for raw in events:
        if raw.get("_schema") or raw.get("_instructions"):
            continue
        event = classify_announced_event(raw)
        event["event_fingerprint"] = event_fingerprint(event)
        unique.setdefault(event["event_fingerprint"], event)
    return list(unique.values())


def load_announced_events(path=None):
    target = Path(path) if path else ANNOUNCED_CATALYSTS_PATH
    if not target.exists():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("announced_catalysts.json must contain a JSON list")
    return deduplicate_events(data)


def _date(value):
    text = str(value or "").strip()
    if len(text) == 7 and text[4] == "-":
        try:
            return date.fromisoformat(text + "-01"), "MONTH"
        except ValueError:
            return None, None
    try:
        return date.fromisoformat(text[:10]), "DAY"
    except ValueError:
        return None, None


def upcoming_announced_events(events, days=90, today=None, watchlist=None):
    start = today or date.today()
    end = start + timedelta(days=days)
    rows = []
    for event in deduplicate_events(events):
        ticker = event["ticker"]
        if watchlist is not None and ticker not in watchlist:
            continue
        event_date, precision = _date(event.get("date"))
        window_start, start_precision = _date(event.get("window_start"))
        window_end, _ = _date(event.get("window_end"))
        if event_date is None:
            event_date, precision = window_start, "WINDOW" if window_start else None
        if event_date is None:
            continue
        effective_end = window_end or event_date
        if effective_end < start or event_date > end:
            continue
        row = dict(event)
        row["date"] = event_date.isoformat()
        row["date_precision"] = precision or start_precision or "UNKNOWN"
        row["window_end"] = effective_end.isoformat() if window_end else None
        row["company"] = (watchlist or {}).get(ticker, {}).get("company", event.get("company", ticker))
        rows.append(row)
    rows.sort(key=lambda item: (item["date"], item["ticker"], item.get("event_id", "")))
    return rows


def alerts_due(events, today=None, lead_days=(14, 7, 3, 0), sent_fingerprints=None):
    today = today or date.today()
    sent = set(sent_fingerprints or [])
    due = []
    for event in deduplicate_events(events):
        parsed, _ = _date(event.get("date") or event.get("window_start"))
        if parsed is None:
            continue
        days_left = (parsed - today).days
        fingerprint = event["event_fingerprint"]
        alert_fingerprint = f"{fingerprint}:{days_left}"
        if days_left in lead_days and alert_fingerprint not in sent:
            item = dict(event)
            item["days_until_event"] = days_left
            item["alert_fingerprint"] = alert_fingerprint
            due.append(item)
    return due
