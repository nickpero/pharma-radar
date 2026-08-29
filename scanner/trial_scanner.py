import json
from pathlib import Path

from scanner.clinical_trials import search_program
from scanner.state import load_state, save_state, detect_changes
from scanner.relevance import is_relevant
from scanner.catalyst import classify_trial_changes
from scanner.score import score_events
from scanner.trading_intelligence import enrich_trading_events
from scanner.alert_filter import filter_alerts, sort_alerts


WATCHLIST_FILE = Path("data/watchlist.json")


# ============================================
# WATCHLIST
# ============================================

def load_watchlist():
    with open(
        WATCHLIST_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


# ============================================
# TRIAL KEY
# ============================================

def make_trial_key(ticker, program, trial):
    """
    Crea una chiave stabile per identificare
    un trial all'interno della watchlist.
    """

    return (
        f"{ticker}:"
        f"{program}:"
        f"{trial.get('nct_id')}"
    )


# ============================================
# BUILD ALERT
# ============================================

def build_alert(
    ticker,
    company,
    program,
    nct_id,
    event,
    changes,
    trial
):
    """
    Costruisce un alert standardizzato.
    """

    return {
        "ticker": ticker,
        "company": company.get(
            "company",
            ticker
        ),
        "program": program,
        "nct_id": nct_id,
        "event": event,
        "changes": changes,
        "trial": trial,
        "score": event.get(
            "score",
            0
        ),
        "label": event.get(
            "label",
            "LOW"
        ),
        "severity": event.get(
            "severity",
            "LOW"
        ),
        "direction": event.get(
            "direction",
            "UNKNOWN"
        ),
        "subtype": event.get(
            "subtype"
        ),
        "trading_impact": event.get(
            "trading_impact",
            "LOW"
        ),
        "trading_priority": event.get(
            "trading_priority",
            1
        ),
        "urgency": event.get(
            "urgency",
            "LOW"
        )
    }


# ============================================
# SCAN
# ============================================

def scan(baseline=False):

    watchlist = load_watchlist()

    old_state = load_state()

    new_state = {}

    detected_changes = []

    alerts = []

    errors = []

    relevant_details = []

    total_trials = 0
    relevant_trials = 0
    filtered_trials = 0

    # ========================================
    # COMPANIES
    # ========================================

    for ticker, company in watchlist.items():

        programs = company.get(
            "programs",
            []
        )

        for program in programs:

            print(
                f"Searching {ticker} - {program}"
            )

            # =================================
            # SEARCH
            # =================================

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

            # =================================
            # TRIALS
            # =================================

            for trial in trials:

                nct_id = trial.get(
                    "nct_id"
                )

                if not nct_id:
                    continue

                total_trials += 1

                # =================================
                # RELEVANCE
                # =================================

                if not is_relevant(
                    trial,
                    company,
                    ticker,
                    program
                ):

                    filtered_trials += 1

                    continue

                relevant_trials += 1

                # =================================
                # RELEVANT DETAILS
                # =================================

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

                # =================================
                # TRIAL KEY
                # =================================

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
                # BASELINE
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

                    if not trial_changes:
                        continue

                    # ---------------------------------
                    # Count actual detected changes
                    # ---------------------------------

                    detected_changes.append({
                        "ticker": ticker,
                        "program": program,
                        "nct_id": nct_id,
                        "changes": trial_changes
                    })

                    # ---------------------------------
                    # Catalyst classification
                    # ---------------------------------

                    catalyst_events = (
                        classify_trial_changes(
                            trial_changes
                        )
                    )

                    if not catalyst_events:
                        continue

                    # ---------------------------------
                    # Score
                    # ---------------------------------

                    scored_events = score_events(
                        catalyst_events
                    )

                    # ---------------------------------
                    # Trading Intelligence
                    # ---------------------------------

                    enriched_events = (
                        enrich_trading_events(
                            scored_events
                        )
                    )

                    # ---------------------------------
                    # Alert filter
                    # ---------------------------------

                    trial_alerts = filter_alerts(
                        enriched_events
                    )

                    # ---------------------------------
                    # Build alerts
                    # ---------------------------------

                    for event in trial_alerts:

                        alerts.append(
                            build_alert(
                                ticker,
                                company,
                                program,
                                nct_id,
                                event,
                                trial_changes,
                                trial
                            )
                        )

                # =================================
                # NEW TRIAL
                # =================================

                else:

                    new_event = {
                        "type": "NEW_TRIAL",
                        "severity": "MEDIUM",
                        "direction": "UNKNOWN",
                        "subtype": "NEW_TRIAL",
                        "field": None,
                        "old_value": None,
                        "new_value": None
                    }

                    scored_events = score_events(
                        [new_event]
                    )

                    enriched_events = (
                        enrich_trading_events(
                            scored_events
                        )
                    )

                    trial_alerts = filter_alerts(
                        enriched_events
                    )

                    for event in trial_alerts:

                        alerts.append(
                            build_alert(
                                ticker,
                                company,
                                program,
                                nct_id,
                                event,
                                {},
                                trial
                            )
                        )

    # ========================================
    # SORT ALERTS
    # ========================================

    alerts = sort_alerts(
        alerts
    )

    # ========================================
    # SAVE STATE
    # ========================================

    save_state(
        new_state
    )

    # ========================================
    # SUMMARY
    # ========================================

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
        f"Changes detected: {len(detected_changes)}"
    )

    print(
        f"Alerts: {len(alerts)}"
    )

    print(
        f"Errors: {len(errors)}"
    )

    print(
        "==================================="
    )

    # ========================================
    # RETURN
    # ========================================

    return {
        "companies": len(watchlist),
        "total_trials": total_trials,
        "relevant_trials": relevant_trials,
        "filtered_trials": filtered_trials,
        "detected_changes": detected_changes,
        "changes": alerts,
        "alerts": alerts,
        "errors": errors,
        "relevant_details": relevant_details,
        "baseline": baseline
                }
