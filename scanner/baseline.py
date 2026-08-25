from scanner.trial_scanner import scan


def create_baseline():
    print("===================================")
    print("PHARMA RADAR — BASELINE")
    print("===================================")

    result = scan(baseline=True)

    print()
    print("Baseline completed.")
    print(
        f"Companies: {result['companies']}"
    )
    print(
        f"Trials found: {result['total_trials']}"
    )
    print(
        f"Relevant trials: "
        f"{result['relevant_trials']}"
    )
    print(
        f"Filtered trials: "
        f"{result['filtered_trials']}"
    )
    print(
        f"Errors: {len(result['errors'])}"
    )

    print()
    print(
        "No alerts generated."
    )


if __name__ == "__main__":
    create_baseline()
