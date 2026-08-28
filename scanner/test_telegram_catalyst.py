from scanner.telegram import (
    send_catalyst_alert,
)


def main():

    # ========================================
    # SIMULATED CRITICAL CATALYST
    # ========================================

    alert = {
        "ticker": "CAPR",
        "company": "Capricor Therapeutics",
        "program": "deramiocel",
        "nct_id": "NCT00000000",

        "event": {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "CATALYST",
            "subtype": "TRIAL_COMPLETED",
            "old_value": "RECRUITING",
            "new_value": "COMPLETED",
            "score": 100,
            "label": "CRITICAL",
        },

        "changes": {
            "status": {
                "old": "RECRUITING",
                "new": "COMPLETED",
            }
        },

        "trial": {
            "nct_id": "NCT00000000",
            "status": "COMPLETED",
            "title": "Simulated Deramiocel Trial",
        },
    }

    print(
        "Sending simulated Catalyst alert..."
    )

    result = send_catalyst_alert(
        alert
    )

    print(
        "Telegram API response:"
    )

    print(
        result
    )

    print()
    print(
        "🟢 CATALYST → TELEGRAM TEST PASSED"
    )


if __name__ == "__main__":

    main()
