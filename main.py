from scanner.trial_scanner import scan
from scanner.telegram import send_telegram


def main():
    print("Starting Pharma Radar...")

    changes = scan()

    if changes:
        message = f"""🧬 PHARMA RADAR — TRIAL UPDATE

🚨 Changes detected: {len(changes)}

"""

        for change in changes[:10]:
            message += (
                f"🔴 {change['ticker']} — "
                f"{change['program']}\n"
                f"NCT: {change['nct_id']}\n"
            )

            for field, values in change["changes"].items():
                message += (
                    f"{field}: "
                    f"{values['old']} → "
                    f"{values['new']}\n"
                )

            message += "\n"

    else:
        message = """🧬 PHARMA RADAR — SCAN

🟢 ClinicalTrials.gov scanned
🟢 Watchlist checked
🟢 No changes detected

Status: CLEAN
"""

    send_telegram(message)

    print("Scan completed.")


if __name__ == "__main__":
    main()
