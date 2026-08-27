from scanner.state import detect_changes
from scanner.catalyst import classify_trial_changes
from scanner.score import score_events
from scanner.alert_filter import filter_alerts
from scanner.telegram import format_catalyst_alert


def main():

    # ========================================
    # SIMULATE REAL TRIAL
    # ========================================

    old_trial = {
        "nct_id": "NCT00000000",
        "status": "RECRUITING",
        "completion_date": "2027-06-30",
        "title": "Test Deramiocel Trial",
    }

    new_trial = {
        "nct_id": "NCT00000000",
        "status": "COMPLETED",
        "completion_date": "2027-03-31",
        "title": "Test Deramiocel Trial",
    }

    # ========================================
    # 1 — DETECT CHANGES
    # ========================================

    changes = detect_changes(
        old_trial,
        new_trial
    )

    assert "status" in changes
    assert "completion_date" in changes

    print("✅ Changes detected")

    # ========================================
    # 2 — CATALYST CLASSIFICATION
    # ========================================

    events = classify_trial_changes(
        changes
    )

    assert len(events) >= 1

    print("✅ Catalyst classification passed")

    for event in events:
        print(
            f"   {event}"
        )

    # ========================================
    # 3 — SCORE
    # ========================================

    scored = score_events(
        events
    )

    assert scored

    print("✅ Scoring passed")

    for event in scored:
        print(
            f"   score={event.get('score')} "
            f"label={event.get('label')}"
        )

    # ========================================
    # 4 — ALERT FILTER
    # ========================================

    alerts = filter_alerts(
        scored
    )

    assert alerts

    print("✅ Alert filter passed")

    # ========================================
    # 5 — FIND CRITICAL EVENT
    # ========================================

    critical = None

    for event in alerts:

        if event.get("score") >= 80:

            critical = event
            break

    assert critical is not None

    print(
        "✅ Critical catalyst detected"
    )

    print(
        f"   Score: {critical['score']}"
    )

    print(
        f"   Label: {critical['label']}"
    )

    # ========================================
    # 6 — BUILD TELEGRAM ALERT
    # ========================================

    alert = {
        "ticker": "CAPR",
        "company": "Capricor Therapeutics",
        "program": "deramiocel",
        "nct_id": "NCT00000000",
        "event": critical,
        "changes": changes,
        "trial": new_trial,
    }

    message = format_catalyst_alert(
        alert
    )

    assert "🚨 PHARMA RADAR — CATALYST" in message
    assert "CAPR — deramiocel" in message
    assert "NCT00000000" in message
    assert "Score:" in message
    assert "Severity:" in message
    assert "Direction:" in message

    print("✅ Telegram format passed")

    # ========================================
    # SHOW FINAL MESSAGE
    # ========================================

    print()
    print("========== SIMULATED TELEGRAM ==========")
    print()
    print(message)
    print()
    print("=========================================")

    print()
    print(
        "🟢 END-TO-END CATALYST TEST PASSED"
    )

    print(
        "No Telegram message was sent."
    )

    print(
        "No production state was modified."
    )


if __name__ == "__main__":

    main()
