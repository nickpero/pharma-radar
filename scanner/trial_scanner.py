import json
from pathlib import Path

from scanner.clinical_trials import search_program
from scanner.state import load_state, save_state, detect_changes


WATCHLIST_FILE = Path("data/watchlist.json")


def load_watchlist():
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def make_trial_key(ticker, program, trial):
    return f"{ticker}:{program}:{trial.get('nct_id')}"


def scan():
    watchlist = load_watchlist()
    old_state = load_state()

    new_state = {}
    changes = []
    errors = []
    total_trials = 0

    for ticker, company in watchlist.items():

        programs = company.get("programs", [])

        for program in programs:

            print(f"Searching {ticker} - {program}")

            try:
                trials = search_program(program)

            except Exception as error:
                print(
                    f"ERROR searching {ticker} - "
                    f"{program}: {error}"
                )

                errors.append({
                    "ticker": ticker,
                    "program": program,
                    "error": str(error)
                })

                continue

            for trial in trials:

                nct_id = trial.get("nct_id")

                if not nct_id:
                    continue

                total_trials += 1

                key = make_trial_key(
                    ticker,
                    program,
                    trial
                )

                new_state[key] = trial

                old_trial = old_state.get(key)

                if old_trial:
                    trial_changes = detect_changes(
                        old_trial,
                        trial
                    )

                    if trial_changes:
                        changes.append({
                            "ticker": ticker,
                            "company": company["company"],
                            "program": program,
                            "nct_id": nct_id,
                            "changes": trial_changes,
                            "trial": trial
                        })

    save_state(new_state)

    print()
    print("========== SCAN SUMMARY ==========")
    print(f"Companies: {len(watchlist)}")
    print(f"Trials found: {total_trials}")
    print(f"Changes detected: {len(changes)}")
    print(f"Errors: {len(errors)}")
    print("===================================")

    return {
        "companies": len(watchlist),
        "total_trials": total_trials,
        "changes": changes,
        "errors": errors
                        }
