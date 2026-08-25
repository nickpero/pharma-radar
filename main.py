from scanner.trial_scanner import scan
from scanner.telegram import send_telegram
from scanner.report import build_scan_report


def main():
    print("Starting Pharma Radar...")

    result = scan()

    message = build_scan_report(
        companies=result["companies"],
        total_trials=result["total_trials"],
        changes=result["changes"],
        errors=result["errors"]
    )

    send_telegram(message)

    print("Scan completed.")


if __name__ == "__main__":
    main()
