"""Pharma Radar — persistent email delivery state (5.7.3 hardening)."""

import hashlib
import json
import os
import tempfile


DEFAULT_PATH = os.path.join("data", "pharma_email_state.json")
MAX_KEYS = 5000


def _normalise(value):
    return " ".join(str(value or "").strip().lower().split())


def email_delivery_key(alert):
    """Return a stable key for one catalyst email, independent of source name."""
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    parts = (
        alert.get("ticker") or event.get("ticker"),
        alert.get("program") or event.get("program"),
        alert.get("subtype") or event.get("subtype"),
        alert.get("event_timestamp") or event.get("event_timestamp") or event.get("timestamp"),
        alert.get("title") or event.get("title"),
        alert.get("url") or alert.get("source_url") or event.get("url") or event.get("source_url"),
    )
    payload = "|".join(_normalise(item) for item in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


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
    fd, temp_path = tempfile.mkstemp(prefix="pharma_email_state_", suffix=".json", dir=directory or None)
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
