"""Pharma Radar — persistent Pharma Intelligence email state.

Deduplication is event-based, not drug-based: the same medicine can generate
multiple emails as its development evolves, while the same underlying event
is sent only once. Material updates can intentionally create a new event
version when a source is corrected or materially expanded.
"""

import hashlib
import json
import os
import re
import tempfile

DEFAULT_PATH = os.path.join("data", "pharma_email_state.json")
MAX_KEYS = 5000

_MATERIAL_UPDATE_PATTERNS = {
    "CORRECTION": r"\b(correct(?:ion|ed)?|erratum|clarif(?:ication|ied)|revised)\b",
    "NEW_RESULTS": r"\b(new|updated|additional|top[- ]line|follow[- ]up|interim|final)\b.{0,60}\b(results?|data|findings?)\b",
    "INDICATION_CHANGE": r"\b(new|additional|expanded|change(?:d)?|broadened)\b.{0,60}\b(indication|indications|population)\b",
    "REGULATORY_UPDATE": r"\b(accepted|acceptance|filed|filing|pdufa|complete response|crl|approved|approval|rejected|rejection|label expansion|regulatory decision)\b",
}


def _normalise(value):
    return " ".join(str(value or "").strip().lower().split())


def _hash(parts):
    payload = "|".join(_normalise(item) for item in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _material_update_type(alert):
    """Return a small exception class only for clearly material updates."""
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    explicit = (
        alert.get("material_update_type")
        or event.get("material_update_type")
        or alert.get("update_type")
        or event.get("update_type")
    )
    if explicit:
        return _normalise(explicit).upper()

    text = " ".join(
        _normalise(alert.get(key) or event.get(key))
        for key in ("title", "summary", "subtype")
    )
    for kind, pattern in _MATERIAL_UPDATE_PATTERNS.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            return kind
    return ""


def _content_fingerprint(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    title = alert.get("title") or event.get("title") or ""
    summary = alert.get("summary") or event.get("summary") or ""
    result = alert.get("results") or event.get("results") or ""
    status = alert.get("regulatory_status") or event.get("regulatory_status") or ""
    return _hash((title, summary, result, status))


def email_delivery_key(alert):
    """Stable V2.1 identity for one Pharma event plus simple material-update exceptions."""
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    ticker = alert.get("ticker") or event.get("ticker") or "UNKNOWN"
    program = alert.get("program") or event.get("program") or "UNKNOWN"
    nct_id = alert.get("nct_id") or event.get("nct_id") or ""
    event_type = alert.get("event_type") or event.get("type") or ""
    subtype = alert.get("subtype") or event.get("subtype") or ""
    material_update = _material_update_type(alert)

    source_id = (
        alert.get("source_item_id") or alert.get("item_id")
        or event.get("source_item_id") or event.get("item_id")
    )
    url = (
        alert.get("url") or alert.get("source_url")
        or event.get("url") or event.get("source_url")
    )

    # Trial/state evolution: every distinct old->new transition is a new event.
    if nct_id or event_type in {
        "STATUS_CHANGE", "DATE_CHANGE", "PHASE_CHANGE",
        "ENROLLMENT_CHANGE", "PROTOCOL_CHANGE", "NEW_TRIAL",
    }:
        old_value = alert.get("old_value") or event.get("old_value")
        new_value = alert.get("new_value") or event.get("new_value")
        field = alert.get("field") or event.get("field")
        # Explicit material protocol/result updates get a content version.
        version = _content_fingerprint(alert) if material_update else ""
        return "V2.1:" + _hash((
            "TRIAL_EVENT", ticker, program, nct_id, event_type, subtype,
            field, old_value, new_value, material_update, version,
        ))

    # Regulatory/news: source identity suppresses simple republishing.
    # A material update deliberately adds a content fingerprint, so a corrected
    # or expanded version of the same source can generate a new email.
    title = alert.get("title") or event.get("title") or ""
    summary = alert.get("summary") or event.get("summary") or ""
    if source_id:
        identity = ("SOURCE_ID", source_id)
    elif url:
        identity = ("URL", url)
    else:
        identity = ("CONTENT", title, summary)

    version = _content_fingerprint(alert) if material_update else ""
    return "V2.1:" + _hash((
        "NEWS_EVENT", ticker, program, event_type, subtype,
        identity, material_update, version,
    ))


def load_email_state(path=DEFAULT_PATH):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        sent = data.get("sent", []) if isinstance(data, dict) else []
        if isinstance(sent, list):
            return {str(item) for item in sent}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return set()


def save_email_state(sent_keys, path=DEFAULT_PATH):
    keys = list(dict.fromkeys(str(item) for item in sent_keys))[-MAX_KEYS:]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix="pharma_email_state_", suffix=".json", dir=directory or None
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"sent": keys}, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def mark_email_sent(alert, path=DEFAULT_PATH):
    sent = load_email_state(path)
    key = email_delivery_key(alert)
    if key in sent:
        return False
    sent.add(key)
    save_email_state(sent, path)
    return True
