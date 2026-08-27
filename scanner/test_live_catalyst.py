from scanner.state import load_state, detect_changes
from scanner.catalyst import classify_trial_changes
from scanner.score import score_events
from scanner.alert_filter import filter_alerts


def main():

    state = load_state()

    if not state:
        raise RuntimeError(
            "State is empty. Run a normal scan first."
        )

    # ========================================
    # FIND A TRIAL
    # ========================================

    selected_key = None
    selected_trial = None

    for key, trial in state.items():

        if trial.get("nct_id"):

            selected_key = key
            selected_trial = trial

            break

    if not selected_trial:
        raise RuntimeError(
            "No trial found in state."
        )

    # ========================================
    # SIMULATE CHANGE
    # ========================================

    old_trial = dict(
        selected_trial
    )

    new_trial = dict(
        selected_trial
    )

    old_trial["status"] = "RECRUITING"
    new_trial["status"] = "COMPLETED"

    # ========================================
    # DETECT CHANGES
    # ========================================

    changes = detect_changes(
        old_trial,
        new_trial
    )

    assert "status" in changes

    print()
    print("========== LIVE CATALYST TEST ==========")

    print(
        f"Trial: {selected_key}"
    )

    print(
        f"Old status: {changes['status']['old']}"
    )

    print(
        f"New status: {changes['status']['new']}"
    )

    # ========================================
    # CATALYST
    # ========================================

    events = classify_trial_changes(
        changes
    )

    assert events

    print()
    print("Catalyst events:")

    for event in events:

        print(
            f"- {event}"
        )

    # ========================================
    # SCORE
    # ========================================

    scored = score_events(
        events
    )

    assert scored

    print()
    print("Scored events:")

    for event in scored:

        print(
            f"- score={event.get('score')} "
            f"label={event.get('label')} "
            f"type={event.get('type')} "
            f"subtype={event.get('subtype')}"
        )

    # ========================================
    # ALERT FILTER
    # ========================================

    alerts = filter_alerts(
        scored
    )

    assert alerts

    critical = alerts[0]

    assert critical["score"] == 100
    assert critical["label"] == "CRITICAL"

    print()
    print("Alerts:")

    for alert in alerts:

        print(
            f"- score={alert.get('score')} "
            f"label={alert.get('label')} "
            f"direction={alert.get('direction')}"
        )

    print()
    print(
        "✅ LIVE CATALYST TEST PASSED"
    )

    print(
        "State file was NOT modified."
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
