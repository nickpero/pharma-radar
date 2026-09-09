"""Persistent delivery state for Pharma Radar Telegram alerts."""

import json
from pathlib import Path

STATE_FILE = Path("data/telegram_alert_state.json")


def load_sent_alerts():
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_sent_alerts(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2, sort_keys=True)


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
