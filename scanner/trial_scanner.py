import json
from pathlib import Path

from scanner.clinical_trials import search_program
from scanner.state import load_state, save_state, detect_changes
from scanner.relevance import is_relevant
from scanner.catalyst import classify_trial_changes
from scanner.score import score_events
from scanner.trading_intelligence import enrich_trading_events
from scanner.alert_filter import filter_alerts, sort_alerts

from scanner.fda_feed import get_fda_catalyst_news
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
    with open(
        WATCHLIST_FILE,
        "r",
        encoding="utf-8",
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
    trial,
):
    """
    Costruisce un alert standardizzato.
    """

    return {
        "ticker": ticker,
        "company": company.get(
            "company",
            ticker,
        ),
        "program": program,
        "nct_id": nct_id,
        "event": event,
        "changes": changes,
        "trial": trial,
        "score": event.get(
            "score",
            0,
        ),
        "label": event.get(
            "label",
            "LOW",
        ),
        "severity": event.get(
            "severity",
            "LOW",
        ),
        "direction": event.get(
            "direction",
            "UNKNOWN",
        ),
        "subtype": event.get(
            "subtype",
        ),
        "trading_impact": event.get(
            "trading_impact",
            "LOW",
        ),
        "trading_priority": event.get(
            "trading_priority",
            1,
        ),
        "urgency": event.get(
            "urgency",
            "LOW",
        ),
    }


# ============================================
# BUILD FDA ALERT
# ============================================

def build_fda_alert(event):
    """
    Converte un evento FDA Trading Intelligence
    nel formato alert del Radar.
    """

    return {
        "ticker": event.get(
            "ticker",
            "UNKNOWN",
        ),
        "company": event.get(
            "company",
            "UNKNOWN",
        ),
        "program": event.get(
            "program",
            "UNKNOWN",
        ),
        "nct_id": None,
        "event": event,
        "changes": {},
        "trial": {},
        "score": event.get(
            "score",
            0,
        ),
        "label": event.get(
            "label",
            "LOW",
        ),
        "severity": event.get(
            "severity",
            "LOW",
        ),
        "direction": event.get(
            "direction",
            "UNKNOWN",
        ),
        "subtype": event.get(
            "subtype",
        ),
        "trading_impact": event.get(
            "trading_impact",
            "LOW",
        ),
        "trading_priority": event.get(
            "trading_priority",
            1,
        ),
        "urgency": event.get(
            "urgency",
            "LOW",
        ),
        "source": "FDA",
        "title": event.get(
            "title",
            "",
        ),
        "summary": event.get(
            "summary",
            "",
        ),
        "url": event.get(
            "url",
        ),
        "published_at": event.get(
            "published_at",
        ),
    }


# ============================================
# PROCESS FDA
# ============================================

def scan_fda(
    watchlist,
    max_items=50,
):
    """
    Recupera e processa le news FDA.

    Gli errori FDA non interrompono la scansione
    Clinical Trials.