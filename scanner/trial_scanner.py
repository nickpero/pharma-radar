import json
from pathlib import Path

from scanner.clinical_trials import search_program
from scanner.state import load_state, save_state, detect_changes
from scanner.relevance import is_relevant
from scanner.catalyst import classify_trial_changes
from scanner.score import score_events
from scanner.alert_filter import filter_alerts, sort_alerts


WATCHLIST_FILE = Path("data/watchlist.json")


def load_watchlist():
    with open(
        WATCHLIST_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def make_trial_key(ticker, program, trial):
    return (
        f"{ticker}:"
        f"{program}:"
        f"{trial.get('nct_id')}"
    )


def scan(baseline=False):
    watchlist = load_watchlist()
    old_state = load_state()

    new_state = {}
    changes = []
    alerts = []
    errors = []
    relevant_details = []

    total_trials = 0
    relevant_trials = 0
    filtered_trials = 0

    for ticker, company in watchlist.items():

        programs = company.get(
            "programs",
            []
        )

        for program in programs:

            print(
                f"Searching {ticker} - {program}"
            )

            try:
                trials = search_program(
                    program
                )

            except Exception as error:

                print(
                    f"ERROR searching "
                    f"{ticker} - "
                    f"{program}: {error}"
                )

                errors.append({
                    "ticker": ticker,
                    "program": program,
                    "error": str(error)
                })

                continue

            for trial in trials:

                nct_id = trial.get(
                    "nct_id"
                )

                if not nct_id:
                    continue

                total_trials += 1

                if not is_relevant(
                    trial,
                    company,
                    ticker,
                    program
                ):
                    filtered_trials += 1
                    continue

                relevant_trials += 1

                relevant_details.append({
                    "ticker": ticker,
                    "program": program,
                    "nct_id": nct_id,
                    "status": trial.get(
                        "status"
                    ),
                    "title": trial.get(
                        "title"
                    )
                })

                key = make_trial_key(
                    ticker,
                    program,
                    trial
                )

                new_state[key] = trial

                old_trial = old_state.get(
                    key
                )

                # =================================
                # BASELINE MODE
                # =================================

                if baseline:
                    continue

                # =================================
                # EXISTING TRIAL
                # =================================

                if old_trial:

                    trial_changes = detect_changes(
                        old_trial,
                        trial
                    )

                    if trial_changes:

                        catalyst_events = (
                            classify_trial_changes(
                                trial_changes
                            )
                        )

                        scored_events = score_events(
                            catalyst_events
                        )

                        trial_alerts = filter_alerts(
                            scored_events
                        )

                        for event in trial_alerts:

                            alerts.append({
                                "ticker": ticker,
                                "company": company.get(
                                    "company",
                                    ticker
                                ),
                                "program": program,
                                "nct_id": nct_id,
                                "event": event,
                                "changes": trial_changes,
                                "trial": trial
                            })

                # =================================
                # NEW TRIAL
                # =================================

                else:

                    new_event = {
                        "type": "NEW_TRIAL",
                        "severity": "MEDIUM",
                        "direction": "UNKNOWN",
                        "field": None,
                        "old_value": None,
                        "new_value": None
                    }

                    scored_events = score_events(
                        [new_event]
                    )

                    trial_alerts = filter_alerts(
                        scored_events
                    )

                    for event in trial_alerts:

                        alerts.append({
                            "ticker": ticker,
                            "company": company.get(
                                "company",
                                ticker
                            ),
                            "program": program,
                            "nct_id": nct_id,
                            "event": event,
                            "changes": {},
                            "trial": trial
                        })

    # =================================
    # SORT ALERTS
    # =================================

    alerts = sort_alerts(
        alerts
    )

    # =================================
    # SAVE CURRENT STATE
    # =================================

    save_state(
        new_state
    )

    # =================================
    # SUMMARY
    # =================================

    print()

    print(
        "========== SCAN SUMMARY =========="
    )

    print(
        f"Companies: {len(watchlist)}"
    )

    print(
        f"Trials found: {total_trials}"
    )

    print(
        f"Relevant trials: {relevant_trials}"
    )

    print(
        f"Filtered trials: {filtered_trials}"
    )

    print(
        f"Changes detected: {len(alerts)}"
    )

    print(
        f"Errors: {len(errors)}"
    )

    print(
        "==================================="
    )

    return {
        "companies": len(watchlist),
        "total_trials": total_trials,
        "relevant_trials": relevant_trials,
        "filtered_trials": filtered_trials,
        "changes": alerts,
        "alerts": alerts,
        "errors": errors,
        "relevant_details": relevant_details,
        "baseline": baseline
                        }
