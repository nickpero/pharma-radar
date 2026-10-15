"""Validation and alert-window helpers for company-announced clinical catalysts.

The JSON feed is intentionally source-backed and curated; no event is inferred
from a trial completion date. Dates retain their declared precision.
"""
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANNOUNCED_CATALYSTS_PATH = ROOT / "data" / "announced_catalysts.json"

READOUT = "CLINICAL_READOUT"
MILESTONE = "TRIAL_MILESTONE"
REVIEW = "CLINICAL_REVIEW"
VALID_TYPES = {READOUT, MILESTONE, REVIEW}


def classify_announced_event(event):
    """Normalize explicit event evidence without inferring clinical outcome."""
    item = dict(event)
    event_type = str(item.get("event_type") or "").upper().strip()
    if event_type not in VALID_TYPES:
        raise ValueError(f"Unsupported event_type: {event_type or 'MISSING'}")
    item["event_type"] = event_type
    if event_type == READOUT:
        item["clinical_outcome_available"] = bool(item.get("clinical_outcome_available", True))
        item["actionability"] = item.get("actionability") or "CATALYST"
    elif event_type == MILESTONE:
        item["clinical_outcome_available"] = False
        item["actionability"] = "WATCH"
        item["direction"] = "UNKNOWN"
    else:
        item["clinical_outcome_available"] = False
        item["actionability"] = "WATCH"
        item["direction"] = "UNKNOWN"
    item["ticker"] = str(item.get("ticker") or "").strip().upper()
    if not item["ticker"]:
        raise ValueError("ticker is required")
    if not (item.get("source_url") or item.get("source")):
        raise ValueError("source or source_url is required")
    if not (item.get("event_name") or item.get("title")):
        raise ValueError("event_name or title is required")
    return item


def event_fingerprint(event):
    """Stable identity for duplicate detection; explicit IDs take precedence."""
    explicit_id = str(event.get("event_id") or "").strip()
    if explicit_id:
        raw = explicit_id.lower()
    else:
        parts = (
            event.get("ticker"), event.get("program"), event.get("event_name") or event.get("title"),
            event.get("event_type"), event.get("date") or event.get("window_start"),
        )
        raw = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def deduplicate_events(events):
    """Keep first occurrence, but permit a materially changed event under a new ID."""
    unique = {}
    for raw in events:
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
        window_end, end_precision = _date(event.get("window_end"))
        if event_date is None:
            event_date = window_start
            precision = "WINDOW" if window_start else None
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
    """Return due event notices; caller persists sent_fingerprints across runs."""
    today = today or date.today()
    sent = set(sent_fingerprints or [])
    due = []
    for event in deduplicate_events(events):
        parsed, _ = _date(event.get("date") or event.get("window_start"))
        if parsed is None:
            continue
        days_left = (parsed - today).days
        fingerprint = event["event_fingerprint"]
        if days_left in lead_days and fingerprint not in sent:
            item = dict(event)
            item["days_until_event"] = days_left
            item["alert_fingerprint"] = f"{fingerprint}:{days_left}"
            due.append(item)
    return due
