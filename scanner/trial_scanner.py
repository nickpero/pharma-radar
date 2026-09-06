import json
from pathlib import Path

from scanner.clinical_trials import search_program
from scanner.state import load_state, save_state, detect_changes
from scanner.relevance import is_relevant
from scanner.catalyst import classify_trial_changes
from scanner.score import score_events
from scanner.trading_intelligence import enrich_trading_events
from scanner.alert_filter import filter_alerts, sort_alerts

from scanner.fda_enrichment import get_enriched_fda_news
from scanner.fda_pipeline import (
    process_fda_news,
    filter_fda_trading_alerts,
    sort_fda_events,
)


WATCHLIST_FILE = Path("data/watchlist.json")


# ============================================
# WATCHLIST
# ============================================

def load_watchlist():
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# ============================================
# TRIAL KEY
# ============================================

def make_trial_key(ticker, program, trial):
    """Crea una chiave stabile per identificare un trial."""
    return f"{ticker}:{program}:{trial.get('nct_id')}"


# ============================================
# BUILD ALERT
# ============================================

def build_alert(ticker, company, program, nct_id, event, changes, trial):
    """Costruisce un alert standardizzato."""
    return {
        "ticker": ticker,
        "company": company.get("company", ticker),
        "program": program,
        "nct_id": nct_id,
        "event": event,
        "changes": changes,
        "trial": trial,
        "score": event.get("score", 0),
        "label": event.get("label", "LOW"),
        "severity": event.get("severity", "LOW"),
        "direction": event.get("direction", "UNKNOWN"),
        "subtype": event.get("subtype"),
        "trading_impact": event.get("trading_impact", "LOW"),
        "trading_priority": event.get("trading_priority", 1),
        "urgency": event.get("urgency", "LOW"),
    }


# ============================================
# BUILD FDA ALERT
# ============================================

def build_fda_alert(event):
    """Converte un evento FDA Trading Intelligence nel formato Radar."""
    return {
        "ticker": event.get("ticker", "UNKNOWN"),
        "company": event.get("company", "UNKNOWN"),
        "program": event.get("program", "UNKNOWN"),
        "nct_id": None,
        "event": event,
        "changes": {},
        "trial": {},
        "score": event.get("score", 0),
        "label": event.get("label", "LOW"),
        "severity": event.get("severity", "LOW"),
        "direction": event.get("direction", "UNKNOWN"),
        "subtype": event.get("subtype"),
        "trading_impact": event.get("trading_impact", "LOW"),
        "trading_priority": event.get("trading_priority", 1),
        "urgency": event.get("urgency", "LOW"),
        "source": "FDA",
        "title": event.get("title", ""),
        "summary": event.get("summary", ""),
        "url": event.get("url"),
        "published_at": event.get("published_at"),
    }


# ============================================
# PROCESS FDA
# ============================================

def scan_fda(watchlist, max_items=50):
    """
    Recupera le FDA News, arricchisce gli articoli FDA ufficiali
    prima del matching e passa quindi alla pipeline catalyst.
    """
    try:
        # PRODUCTION P0 PATH:
        # FDA feed -> official article enrichment -> matcher -> catalyst
        news = get_enriched_fda_news(max_news=max_items, max_pages=5)

        events = process_fda_news(news, watchlist)
        trading_events = filter_fda_trading_alerts(events)
        trading_events = sort_fda_events(trading_events)

        alerts = [build_fda_alert(event) for event in trading_events]

        return {
            "news": news,
            "events": events,
            "alerts": alerts,
            "error": None,
        }

    except Exception as error:
        return {
            "news": [],
            "events": [],
            "alerts": [],
            "error": str(error),
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
    # CLINICAL TRIALS
    # ========================================
    for ticker, company in watchlist.items():
        programs = company.get("programs", [])

        for program in programs:
            print(f"Searching {ticker} - {program}")

            try:
                trials = search_program(program)
            except Exception as error:
                print(f"ERROR searching {ticker} - {program}: {error}")
                errors.append({"ticker": ticker, "program": program, "error": str(error)})
                continue

            for trial in trials:
                nct_id = trial.get("nct_id")
                if not nct_id:
                    continue

                total_trials += 1

                if not is_relevant(trial, company, ticker, program):
                    filtered_trials += 1
                    continue

                relevant_trials += 1
                relevant_details.append({
                    "ticker": ticker,
                    "program": program,
                    "nct_id": nct_id,
                    "status": trial.get("status"),
                    "title": trial.get("title"),
                })

                key = make_trial_key(ticker, program, trial)
                new_state[key] = trial
                old_trial = old_state.get(key)

                if baseline:
                    continue

                if old_trial:
                    trial_changes = detect_changes(old_trial, trial)
                    if not trial_changes:
                        continue

                    detected_changes.append({
                        "ticker": ticker,
                        "program": program,
                        "nct_id": nct_id,
                        "changes": trial_changes,
                    })

                    catalyst_events = classify_trial_changes(trial_changes)
                    if not catalyst_events:
                        continue

                    scored_events = score_events(catalyst_events)
                    enriched_events = enrich_trading_events(scored_events)
                    trial_alerts = filter_alerts(enriched_events)

                    for event in trial_alerts:
                        alerts.append(build_alert(
                            ticker, company, program, nct_id,
                            event, trial_changes, trial,
                        ))

                else:
                    new_event = {
                        "type": "NEW_TRIAL",
                        "severity": "MEDIUM",
                        "direction": "UNKNOWN",
                        "subtype": "NEW_TRIAL",
                        "field": None,
                        "old_value": None,
                        "new_value": None,
                    }
                    scored_events = score_events([new_event])
                    enriched_events = enrich_trading_events(scored_events)
                    trial_alerts = filter_alerts(enriched_events)

                    for event in trial_alerts:
                        alerts.append(build_alert(
                            ticker, company, program, nct_id,
                            event, {}, trial,
                        ))

    # ========================================
    # FDA FEED
    # ========================================
    print()
    print("Searching FDA catalyst news...")

    fda_result = scan_fda(watchlist)

    if fda_result["error"]:
        errors.append({
            "ticker": "FDA",
            "program": "FDA_FEED",
            "error": fda_result["error"],
        })
    else:
        alerts.extend(fda_result["alerts"])

    alerts = sort_alerts(alerts)
    save_state(new_state)

    print()
    print("========== SCAN SUMMARY ==========")
    print(f"Companies: {len(watchlist)}")
    print(f"Trials found: {total_trials}")
    print(f"Relevant trials: {relevant_trials}")
    print(f"Filtered trials: {filtered_trials}")
    print(f"Changes detected: {len(detected_changes)}")
    print(f"FDA news: {len(fda_result['news'])}")
    print(f"FDA events: {len(fda_result['events'])}")
    print(f"Alerts: {len(alerts)}")
    print(f"Errors: {len(errors)}")
    print("===================================")

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
        "fda_news": fda_result["news"],
        "fda_events": fda_result["events"],
        "fda_alerts": fda_result["alerts"],
        "baseline": baseline,
    }
