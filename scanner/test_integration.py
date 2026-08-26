from scanner.catalyst import classify_trial_changes
from scanner.trial_scanner import make_trial_key


def test_catalyst_integration():

    changes = {
        "status": {
            "old": "RECRUITING",
            "new": "COMPLETED"
        },
        "completion_date": {
            "old": "2027-06-30",
            "new": "2027-03-31"
        }
    }

    events = classify_trial_changes(
        changes
    )

    assert len(events) == 2

    status_event = events[0]
    date_event = events[1]

    assert status_event["type"] == "STATUS_CHANGE"
    assert status_event["severity"] == "HIGH"

    assert date_event["type"] == "DATE_CHANGE"
    assert date_event["direction"] == "POSITIVE"


def test_trial_key():

    trial = {
        "nct_id": "NCT12345678"
    }

    key = make_trial_key(
        "CAPR",
        "deramiocel",
        trial
    )

    assert key == (
        "CAPR:"
        "deramiocel:"
        "NCT12345678"
    )


if __name__ == "__main__":

    test_catalyst_integration()
    test_trial_key()

    print(
        "✅ Integration tests passed"
    )
