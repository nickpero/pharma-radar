import json
import re
from pathlib import Path

from scanner.clinical_trials import search_program
from scanner.state import load_state, save_state, detect_changes
from scanner.relevance import is_relevant
from scanner.catalyst import classify_trial_changes
from scanner.score import score_events
from scanner.trading_intelligence import enrich_trading_events
from scanner.trading_setup_41 import enrich_trading_setup
from scanner.trading_setup_2 import enrich_trading_setup_2
from scanner.reaction import enrich_reaction_classification
from scanner.historical_stats import enrich_historical_stats_batch
from scanner.historical_edge_score import enrich_historical_edges
from scanner.priority import enrich_alert_priorities, sort_by_alert_priority
from scanner.alert_filter import filter_alerts
from scanner.fda_enrichment import get_enriched_fda_news
from scanner.fda_pipeline import process_fda_news, filter_fda_trading_alerts
from scanner.regulatory_pipeline import scan_regulatory_sources
from scanner.market_data import enrich_market_data, enrich_market_reactions
from scanner.catalyst_memory import record_events, memory_summary
from scanner.catalyst_explainer import enrich_catalyst_explainers
from scanner.catalyst_confirmation import enrich_catalyst_confirmation
from scanner.catalyst_dedup import filter_known_catalysts
from scanner.catalyst_dedup import filter_known_catalysts

WATCHLIST_FILE = Path("data/watchlist.json")


def load_watchlist():
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def make_trial_key(ticker, program, trial):
    return f"{ticker}:{program}:{trial.get('nct_id')}"


def _reaction_fields(event):
    reaction = event.get("market_reaction") or {}
    return {
        "market_reaction": reaction, "reaction_status": reaction.get("reaction_status", "UNAVAILABLE"),
        "reaction_pct": reaction.get("reaction_pct"), "reaction_direction": reaction.get("reaction_direction", "UNKNOWN"),
        "reaction_1m_pct": reaction.get("reaction_1m_pct"), "reaction_5m_pct": reaction.get("reaction_5m_pct"),
        "reaction_15m_pct": reaction.get("reaction_15m_pct"), "reaction_30m_pct": reaction.get("reaction_30m_pct"),
        "reaction_60m_pct": reaction.get("reaction_60m_pct"), "post_catalyst_high": reaction.get("post_catalyst_high"),
        "post_catalyst_low": reaction.get("post_catalyst_low"), "gap_pct": reaction.get("gap_pct"),
        "pre_event_15m_pct": reaction.get("pre_event_15m_pct"), "event_price": reaction.get("event_price"),
        "current_price": reaction.get("current_price"),
    }


def _normalise_text(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _dedup_key(alert):
    """Identify the same catalyst reported more than once upstream."""
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    timestamp = _normalise_text(alert.get("event_timestamp") or event.get("published_at"))
    title = _normalise_text(alert.get("title") or event.get("title"))
    identity = timestamp or title or _normalise_text(alert.get("url") or event.get("url"))
    return (
        _normalise_text(alert.get("ticker", "UNKNOWN")).upper(),
        _normalise_text(alert.get("program", "UNKNOWN")),
        _normalise_text(alert.get("subtype") or event.get("subtype")),
        identity,
    )


def _dedup_rank(alert):
    reaction = alert.get("market_reaction") or {}
    available_reaction = any(reaction.get(key) is not None for key in ("reaction_pct", "reaction_5m_pct", "reaction_15m_pct", "reaction_30m_pct", "reaction_60m_pct"))
    return (float(alert.get("alert_priority") or 0), float(alert.get("trading_setup_score") or 0), int(available_reaction))


def deduplicate_alerts(alerts):
    """Collapse duplicate upstream reports while retaining the richest alert."""
    unique = {}
    for alert in alerts or []:
        key = _dedup_key(alert)
        current = unique.get(key)
        if current is None or _dedup_rank(alert) > _dedup_rank(current):
            unique[key] = alert
    return sort_by_alert_priority(list(unique.values()))


def build_alert(ticker, company, program, nct_id, event, changes, trial):
    alert = {
        "ticker": ticker, "company": company.get("company", ticker), "program": program, "nct_id": nct_id,
        "event": event, "changes": changes, "trial": trial, "score": event.get("score", 0),
        "label": event.get("label", "LOW"), "severity": event.get("severity", "LOW"), "direction": event.get("direction", "UNKNOWN"),
        "subtype": event.get("subtype"), "trading_impact": event.get("trading_impact", "LOW"),
        "trading_priority": event.get("trading_priority", 1), "urgency": event.get("urgency", "LOW"),
        "alert_priority": event.get("alert_priority", 0), "alert_tier": event.get("alert_tier", "LOW"),
        "trading_setup_score": event.get("trading_setup_score", 0), "trading_window": event.get("trading_window", "UNKNOWN"),
        "market_awareness": event.get("market_awareness", "UNKNOWN"), "price_change_pct": event.get("price_change_pct"),
        "volume_ratio": event.get("volume_ratio"), "event_surprise": event.get("event_surprise", "UNKNOWN"),
        "market_cap": event.get("market_cap"), "short_interest_pct": event.get("short_interest_pct"),
        "data_quality": event.get("data_quality", "LOW"), "event_timestamp": event.get("event_timestamp"),
        "source": event.get("source", "CLINICALTRIALS"), "source_type": event.get("source_type", "PRIMARY_CLINICAL"),
        "reaction_strength": event.get("reaction_strength", "UNKNOWN"), "reaction_interpretation": event.get("reaction_interpretation", "UNKNOWN"),
        "reaction_classification": event.get("reaction_classification", "UNKNOWN"), "trading_setup_version": event.get("trading_setup_version", "4"),
        "catalyst_confirmation_score": event.get("catalyst_confirmation_score", 0), "catalyst_confirmation": event.get("catalyst_confirmation", "UNCONFIRMED"),
        "historical_edge_version": event.get("historical_edge_version"), "historical_edge_score": event.get("historical_edge_score"),
        "historical_edge_label": event.get("historical_edge_label"), "historical_edge_confidence": event.get("historical_edge_confidence"),
        "historical_edge_sample": event.get("historical_edge_sample"), "historical_edge_median_1d_pct": event.get("historical_edge_median_1d_pct"),
        "historical_edge_win_rate_1d": event.get("historical_edge_win_rate_1d"), "historical_edge_direction_adjustment": event.get("historical_edge_direction_adjustment"),
        "historical_edge_ticker_sample": event.get("historical_edge_ticker_sample"),
        "catalyst_category": event.get("catalyst_category"),
        "clinical_data_release": event.get("clinical_data_release", False),
        "novelty_score": event.get("novelty_score", 0),
        "novelty_matches": event.get("novelty_matches", []),
        "market_impact_score": event.get("market_impact_score", 0),
        "market_impact_label": event.get("market_impact_label", "N/A"), "historical_edge_ticker_adjustment": event.get("historical_edge_ticker_adjustment"),
    }
    alert.update(_reaction_fields(event))
    return alert


def build_fda_alert(event):
    alert = {
        "ticker": event.get("ticker", "UNKNOWN"), "company": event.get("company", "UNKNOWN"), "program": event.get("program", "UNKNOWN"),
        "nct_id": None, "event": event, "changes": {}, "trial": {}, "score": event.get("score", 0), "label": event.get("label", "LOW"),
        "severity": event.get("severity", "LOW"), "direction": event.get("direction", "UNKNOWN"), "subtype": event.get("subtype"),
        "trading_impact": event.get("trading_impact", "LOW"), "trading_priority": event.get("trading_priority", 1), "urgency": event.get("urgency", "LOW"),
        "alert_priority": event.get("alert_priority", 0), "alert_tier": event.get("alert_tier", "LOW"), "trading_setup_score": event.get("trading_setup_score", 0),
        "trading_window": event.get("trading_window", "UNKNOWN"), "market_awareness": event.get("market_awareness", "UNKNOWN"),
        "price_change_pct": event.get("price_change_pct"), "volume_ratio": event.get("volume_ratio"), "event_surprise": event.get("event_surprise", "UNKNOWN"),
        "market_cap": event.get("market_cap"), "short_interest_pct": event.get("short_interest_pct"), "data_quality": event.get("data_quality", "LOW"),
        "event_timestamp": event.get("published_at"), "source": event.get("source", "FDA"), "source_type": event.get("source_type", "PRIMARY_REGULATORY"),
        "title": event.get("title", ""), "summary": event.get("summary", ""), "url": event.get("url"), "published_at": event.get("published_at"),
        "reaction_strength": event.get("reaction_strength", "UNKNOWN"), "reaction_interpretation": event.get("reaction_interpretation", "UNKNOWN"),
        "reaction_classification": event.get("reaction_classification", "UNKNOWN"), "trading_setup_version": event.get("trading_setup_version", "4"),
        "catalyst_confirmation_score": event.get("catalyst_confirmation_score", 0), "catalyst_confirmation": event.get("catalyst_confirmation", "UNCONFIRMED"),
        "historical_edge_version": event.get("historical_edge_version"), "historical_edge_score": event.get("historical_edge_score"),
        "historical_edge_label": event.get("historical_edge_label"), "historical_edge_confidence": event.get("historical_edge_confidence"),
        "historical_edge_sample": event.get("historical_edge_sample"), "historical_edge_median_1d_pct": event.get("historical_edge_median_1d_pct"),
        "historical_edge_win_rate_1d": event.get("historical_edge_win_rate_1d"), "historical_edge_direction_adjustment": event.get("historical_edge_direction_adjustment"),
        "historical_edge_ticker_sample": event.get("historical_edge_ticker_sample"), "historical_edge_ticker_adjustment": event.get("historical_edge_ticker_adjustment"),
    }
    alert.update(_reaction_fields(event))
    return alert


def scan_fda(watchlist, max_items=50):
    try:
        news = get_enriched_fda_news(max_news=max_items, max_pages=5)
        events = process_fda_news(news, watchlist)
        trading_events = sort_by_alert_priority(filter_fda_trading_alerts(events))
        alerts = [build_fda_alert(event) for event in trading_events]
        return {"news": news, "events": events, "alerts": alerts, "error": None}
    except Exception as error:
        return {"news": [], "events": [], "alerts": [], "error": str(error)}


def scan(baseline=False):
    watchlist = load_watchlist()
    old_state = load_state()
    new_state, detected_changes, alerts, errors, relevant_details = {}, [], [], [], []
    total_trials = relevant_trials = filtered_trials = 0
    for ticker, company in watchlist.items():
        for program in company.get("programs", []):
            print(f"Searching {ticker} - {program}")
            try:
                trials = search_program(program)
            except Exception as error:
                print(f"ERROR searching {ticker} - {program}: {error}")
                errors.append({"ticker": ticker, "program": program, "error": str(error)})
                continue
            for trial in trials:
                nct_id = trial.get("nct_id")
                if not nct_id: continue
                total_trials += 1
                if not is_relevant(trial, company, ticker, program): filtered_trials += 1; continue
                relevant_trials += 1
                relevant_details.append({"ticker": ticker, "program": program, "nct_id": nct_id, "status": trial.get("status"), "title": trial.get("title")})
                key = make_trial_key(ticker, program, trial); new_state[key] = trial; old_trial = old_state.get(key)
                if baseline: continue
                if old_trial:
                    trial_changes = detect_changes(old_trial, trial)
                    if not trial_changes: continue
                    detected_changes.append({"ticker": ticker, "program": program, "nct_id": nct_id, "changes": trial_changes})
                    catalyst_events = classify_trial_changes(trial_changes)
                    if not catalyst_events: continue
                    scored_events = score_events(catalyst_events)
                    enriched_events = enrich_alert_priorities(enrich_trading_events(scored_events))
                    for event in filter_alerts(enriched_events): alerts.append(build_alert(ticker, company, program, nct_id, event, trial_changes, trial))
                else:
                    new_event = {"type": "NEW_TRIAL", "severity": "MEDIUM", "direction": "UNKNOWN", "subtype": "NEW_TRIAL", "field": None, "old_value": None, "new_value": None}
                    scored_events = score_events([new_event]); enriched_events = enrich_alert_priorities(enrich_trading_events(scored_events))
                    for event in filter_alerts(enriched_events): alerts.append(build_alert(ticker, company, program, nct_id, event, {}, trial))

    print("\nSearching FDA catalyst news...")
    fda_result = scan_fda(watchlist)
    if fda_result["error"]: errors.append({"ticker": "FDA", "program": "FDA_FEED", "error": fda_result["error"]})
    else: alerts.extend(fda_result["alerts"])
    print("\nSearching EMA + SEC catalyst news...")
    try:
        regulatory_result = scan_regulatory_sources(watchlist)
        alerts.extend([build_fda_alert(event) for event in regulatory_result["alerts"]])
    except Exception as error:
        regulatory_result = {"ema_news": [], "sec_news": [], "news": [], "events": [], "alerts": []}
        errors.append({"ticker": "REGULATORY", "program": "EMA_SEC", "error": str(error)})

    alerts = enrich_market_data(alerts)
    alerts = enrich_market_reactions(alerts)
    alerts = [enrich_reaction_classification(alert) for alert in alerts]
    alerts = enrich_historical_stats_batch(alerts)
    alerts = enrich_historical_edges(alerts)
    alerts = [enrich_trading_setup_2(alert, market_data=alert.get("market_data")) for alert in alerts]
    alerts = [enrich_catalyst_confirmation(alert) for alert in alerts]
    alerts = deduplicate_alerts(alerts)
    alerts, suppressed_duplicates = filter_known_catalysts(alerts)
    alerts = enrich_catalyst_explainers(alerts)
    monitoring_alerts = alerts + suppressed_duplicates
    memory_added = record_events(alerts); memory_info = memory_summary()
    print(f"Catalyst memory: +{memory_added} records, total={memory_info['records']}")
    save_state(new_state)
    print("\n========== SCAN SUMMARY ==========")
    print(f"Companies: {len(watchlist)}"); print(f"Trials found: {total_trials}"); print(f"Relevant trials: {relevant_trials}"); print(f"Filtered trials: {filtered_trials}")
    print(f"Changes detected: {len(detected_changes)}"); print(f"FDA news: {len(fda_result['news'])}"); print(f"FDA events: {len(fda_result['events'])}")
    print(f"EMA news: {len(regulatory_result['ema_news'])}"); print(f"SEC filings: {len(regulatory_result['sec_news'])}"); print(f"EMA/SEC events: {len(regulatory_result['events'])}")
    print(f"Alerts: {len(alerts)}"); print(f"Errors: {len(errors)}"); print("===================================")
    return {"companies": len(watchlist), "total_trials": total_trials, "relevant_trials": relevant_trials, "filtered_trials": filtered_trials,
            "detected_changes": detected_changes, "changes": alerts, "alerts": alerts, "monitoring_alerts": monitoring_alerts, "suppressed_duplicates": suppressed_duplicates, "errors": errors, "relevant_details": relevant_details,
            "fda_news": fda_result["news"], "fda_events": fda_result["events"], "fda_alerts": fda_result["alerts"],
            "ema_news": regulatory_result["ema_news"], "sec_news": regulatory_result["sec_news"], "regulatory_events": regulatory_result["events"],
            "regulatory_alerts": regulatory_result["alerts"], "memory_added": memory_added, "memory": memory_info, "baseline": baseline}
