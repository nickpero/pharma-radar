from main import build_summary


def test_clean_summary():

    result = {
        "companies": 20,
        "total_trials": 174,
        "relevant_trials": 137,
        "filtered_trials": 37,
        "alerts": [],
        "errors": [],
    }

    message = build_summary(result)

    assert "🧬 PHARMA RADAR — SCAN" in message
    assert "Companies: 20" in message
    assert "Trials found: 174" in message
    assert "Relevant trials: 137" in message
    assert "Filtered out: 37" in message
    assert "Alerts: 0" in message

    assert "🟢 No catalyst alerts" in message
    assert "Status: CLEAN" in message

    assert "%0A" not in message
    assert "\n" in message


def test_alert_summary():

    result = {
        "companies": 20,
        "total_trials": 174,
        "relevant_trials": 137,
        "filtered_trials": 37,
        "alerts": [
            {
                "ticker": "CAPR",
                "program": "deramiocel",
                "nct_id": "NCT05126758",
                "event": {
                    "type": "STATUS_CHANGE",
                    "subtype": "TRIAL_COMPLETED",
                    "score": 95,
                    "label": "CRITICAL",
                },
            }
        ],
        "errors": [],
    }

    message = build_summary(result)

    assert "🚨 CATALYST ALERTS" in message
    assert "CAPR — deramiocel" in message
    assert "NCT05126758" in message
    assert "STATUS_CHANGE" in message
    assert "TRIAL_COMPLETED" in message
    assert "Score: 95/100" in message
    assert "CRITICAL" in message
    assert "Status: REVIEW" in message

    assert "%0A" not in message


def test_error_summary():

    result = {
        "companies": 20,
        "total_trials": 174,
        "relevant_trials": 137,
        "filtered_trials": 37,
        "alerts": [],
        "errors": [
            {
                "ticker": "CAPR",
                "program": "deramiocel",
                "error": "Test error",
            }
        ],
    }

    message = build_summary(result)

    assert "❌ ERRORS" in message
    assert "CAPR — deramiocel" in message
    assert "Status: WARNING" in message


if __name__ == "__main__":

    test_clean_summary()
    test_alert_summary()
    test_error_summary()

    print(
        "✅ Main integration tests passed"
  )
