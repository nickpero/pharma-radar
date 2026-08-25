import json
from pathlib import Path


STATE_FILE = Path("data/trials_state.json")


def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2
        )


def detect_changes(old_trial, new_trial):
    changes = {}

    fields_to_monitor = [
        "status",
        "last_update",
        "start_date",
        "completion_date",
        "study_type",
        "phases",
        "enrollment",
        "enrollment_type",
        "sponsor",
        "conditions",
        "interventions",
        "title",
        "official_title"
    ]

    for field in fields_to_monitor:

        old_value = old_trial.get(field)
        new_value = new_trial.get(field)

        if old_value != new_value:
            changes[field] = {
                "old": old_value,
                "new": new_value
            }

    return changes
