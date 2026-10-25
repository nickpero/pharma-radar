"""Persistent delivery state for Pharma Radar Telegram alerts."""

import json
import os
import tempfile
from pathlib import Path

STATE_FILE = Path("data/telegram_alert_state.json")


def load_sent_alerts():
    """Load delivery history; fail closed on corruption to avoid duplicate alerts."""
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(
            f"Telegram alert state is unreadable ({STATE_FILE}); refusing to reset "
            "delivery history automatically"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Telegram alert state has invalid structure ({STATE_FILE}); "
            "refusing to reset delivery history automatically"
        )
    return data


def save_sent_alerts(state):
    """Atomically persist delivery history so a crash cannot leave partial JSON."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{STATE_FILE.name}.", suffix=".tmp", dir=str(STATE_FILE.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, STATE_FILE)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def filter_unsent(alerts, sent_state, key_fn):
    """Return alerts not previously delivered, without mutating state."""
    result = []
    for alert in alerts or []:
        key = key_fn(alert)
        if key not in sent_state:
            result.append(alert)
    return result


def mark_sent(alerts, sent_state, key_fn, timestamp):
    """Mark successfully delivered alerts as sent."""
    for alert in alerts or []:
        sent_state[key_fn(alert)] = timestamp
    return sent_state
