import json
from pathlib import Path

STATE_FILE = Path("data/trials_state.json")


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("trial state must be a JSON object")
        return data
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        # A corrupt baseline must not silently become an empty baseline:
        # doing so would hide changes accumulated before the failed read.
        raise RuntimeError(
            f"Clinical-trial state is unreadable ({STATE_FILE}); refusing to reset baseline"
        ) from exc


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.write("\n")
        file.flush()
    temporary.replace(STATE_FILE)


def detect_changes(old_trial, new_trial):
    changes = {}
    fields_to_monitor = [
        "status", "last_update", "last_update_submitted", "start_date",
        "primary_completion_date", "completion_date", "results_posted_date",
        "has_results", "primary_outcomes", "study_type", "phases",
        "enrollment", "enrollment_type", "sponsor", "conditions",
        "interventions", "title", "official_title",
    ]
    for field in fields_to_monitor:
        old_value = old_trial.get(field)
        new_value = new_trial.get(field)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}
    return changes
