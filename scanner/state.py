import json
from pathlib import Path


STATE_FILE = Path("state/trials.json")


def load_state():
    if not STATE_FILE.exists():
        return {}

    with open(STATE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False
        )


def detect_changes(old_data, new_data):
    changes = {}

    for key, new_value in new_data.items():
        old_value = old_data.get(key)

        if old_value != new_value:
            changes[key] = {
                "old": old_value,
                "new": new_value
            }

    return changes
