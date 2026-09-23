"""Catalyst-level deduplication for Pharma Radar.

Separates a newly published source document from a genuinely new underlying
catalyst. Regulatory filings frequently restate an earlier FDA decision.
Those restatements should remain useful as context but must not create a new
CRITICAL catalyst alert.

Policy:
- default equivalence window: 30 days;
- identity: ticker + program + catalyst subtype;
- when available, anchor the catalyst to the substantive regulatory date;
- SEC/FDA documents published later that only restate the same approval are
  suppressed as duplicates;
- material new indications/regimens/safety findings/results are preserved.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from scanner.catalyst_memory import find_similar_events

DEDUP_WINDOW_DAYS = 30

_MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)

_DATE_RE = re.compile(
    rf"\b({_MONTHS})\s+(\d{{1,2}}),\s+(\d{{4}})\b",
    re.I,
)

_MATERIAL_PATTERNS = (
    r"new indication",
    r"expanded indication",
    r"additional indication",
    r"new regimen",
    r"new dosing",
    r"label expansion",
    r"label update",
    r"safety warning",
    r"boxed warning",
    r"complete response letter",
    r"clinical hold",
    r"new clinical results",
    r"topline results",
    r"phase [123] results",
    r"statistically significant",
    r"primary endpoint",
    r"new efficacy",
    r"new milestone",
    r"milestone payment",
)

_APPROVAL_PATTERNS = (
    r"fda\s+(?:has\s+)?approved",
    r"fda\s+approval",
    r"granted\s+(?:standard\s+)?(?:full\s+)?approval",
    r"approval\s+of\s+",
)


def _text(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    fields = (
        alert.get("title"),
        alert.get("summary"),
        alert.get("content"),
        event.get("title"),
        event.get("summary"),
        event.get("content"),
    )
    return " ".join(str(value or "") for value in fields).strip()


def _parse_date(value):
    if not value:
        return None
    value = str(value).strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _anchor_date(alert):
    """Find the substantive catalyst date, not merely the filing date."""
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}

    for key in ("catalyst_date", "approval_date", "decision_date", "event_date"):
        parsed = _parse_date(alert.get(key) or event.get(key))
        if parsed:
            return parsed

    subtype = str(alert.get("subtype") or event.get("subtype") or "").upper()
    text = _text(alert)
    if subtype == "FDA_APPROVAL" and re.search("|".join(_APPROVAL_PATTERNS), text, re.I):
        matches = list(_DATE_RE.finditer(text))
        if matches:
            # Prefer a date in the same sentence as an approval phrase.
            for match in matches:
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end]
                if re.search("|".join(_APPROVAL_PATTERNS), context, re.I):
                    return date(int(match.group(3)), datetime.strptime(match.group(1).title(), "%B").month, int(match.group(2)))
            match = matches[0]
            return date(int(match.group(3)), datetime.strptime(match.group(1).title(), "%B").month, int(match.group(2)))

    return _parse_date(
        alert.get("event_timestamp")
        or alert.get("published_at")
        or event.get("published_at")
    )


def _published_date(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    return _parse_date(alert.get("published_at") or alert.get("event_timestamp") or event.get("published_at"))


def _identity(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    return (
        str(alert.get("ticker") or event.get("ticker") or "").upper().strip(),
        str(alert.get("program") or event.get("program") or "").lower().strip(),
        str(alert.get("subtype") or event.get("subtype") or "").upper().strip(),
    )


def _material_update(alert):
    text = _text(alert).lower()
    return any(re.search(pattern, text, re.I) for pattern in _MATERIAL_PATTERNS)


def _same_catalyst(alert, prior):
    if _identity(alert) != _identity(prior):
        return False

    current_anchor = _anchor_date(alert)
    prior_anchor = _anchor_date(prior)
    if current_anchor and prior_anchor:
        distance = abs((current_anchor - prior_anchor).days)
        if distance == 0:
            return True
        if distance > DEDUP_WINDOW_DAYS:
            return False
    elif current_anchor or prior_anchor:
        # One side lacks an anchor: fall back to publication/event dates.
        current_anchor = current_anchor or _published_date(alert)
        prior_anchor = prior_anchor or _published_date(prior)

    if current_anchor and prior_anchor:
        return abs((current_anchor - prior_anchor).days) <= DEDUP_WINDOW_DAYS

    return True


def is_restatement(alert, prior):
    """True when a newly published document repeats the same catalyst."""
    if _material_update(alert):
        return False
    if not _same_catalyst(alert, prior):
        return False

    current_pub = _published_date(alert)
    current_anchor = _anchor_date(alert)
    prior_anchor = _anchor_date(prior)

    # Strongest case: the new document is published after the original
    # substantive event and carries the same catalyst date.
    if current_anchor and prior_anchor and current_anchor == prior_anchor:
        return True

    # SEC filings that explicitly describe an older approval are restatements.
    source = str(alert.get("source") or "").upper()
    if source == "SEC" and current_pub and current_anchor and current_anchor < current_pub:
        if prior_anchor and abs((current_anchor - prior_anchor).days) <= DEDUP_WINDOW_DAYS:
            return True

    return False


def filter_known_catalysts(alerts, limit=50):
    """Suppress already-recorded catalysts while retaining material updates.

    Returns (fresh_alerts, suppressed_alerts).
    """
    fresh = []
    suppressed = []

    for alert in alerts or []:
        try:
            prior_events = find_similar_events(alert, limit=limit)
        except Exception:
            prior_events = []

        duplicate = any(is_restatement(alert, prior) for prior in prior_events)
        if duplicate:
            item = dict(alert)
            item["dedup_status"] = "RESTATEMENT_DUPLICATE"
            item["dedup_reason"] = "Same underlying catalyst already recorded"
            suppressed.append(item)
        else:
            fresh.append(alert)

    return fresh, suppressed
