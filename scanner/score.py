"""
Pharma Radar — Catalyst Scoring Engine

Trasforma gli eventi clinici classificati in un punteggio
di rilevanza per il trading.

IMPORTANTE:
Il punteggio NON è una raccomandazione di acquisto o vendita.
Serve a stabilire quali eventi meritano maggiore attenzione.
"""


# ============================================
# BASE SCORES
# ============================================

SEVERITY_SCORE = {
    "HIGH": 70,
    "MEDIUM": 40,
    "LOW": 15,
}


DIRECTION_BONUS = {
    "CATALYST": 25,
    "POSITIVE": 20,
    "NEGATIVE": 20,
    "NEUTRAL": 0,
    "UNKNOWN": 0,
}


# ============================================
# EVENT TYPE WEIGHTS
# ============================================

EVENT_TYPE_BONUS = {
    "STATUS_CHANGE": 5,
    "DATE_CHANGE": 10,
    "PHASE_CHANGE": 15,
    "ENROLLMENT_CHANGE": 5,
    "PROTOCOL_CHANGE": 5,
    "NEW_TRIAL": 10,
    "FIELD_CHANGE": 0,
}


# ============================================
# SCORE LIMIT
# ============================================

MAX_SCORE = 100


# ============================================
# MAIN SCORING FUNCTION
# ============================================

def score_event(event):
    """
    Calcola il punteggio di un singolo evento.
    """

    severity = event.get(
        "severity",
        "LOW"
    ).upper()

    direction = event.get(
        "direction",
        "UNKNOWN"
    ).upper()

    event_type = event.get(
        "type",
        "FIELD_CHANGE"
    ).upper()

    score = 0

    # ----------------------------------------
    # Severity
    # ----------------------------------------

    score += SEVERITY_SCORE.get(
        severity,
        0
    )

    # ----------------------------------------
    # Direction
    # ----------------------------------------

    score += DIRECTION_BONUS.get(
        direction,
        0
    )

    # ----------------------------------------
    # Event type
    # ----------------------------------------

    score += EVENT_TYPE_BONUS.get(
        event_type,
        0
    )

    # ----------------------------------------
    # Date acceleration
    # ----------------------------------------

    if event.get(
        "subtype"
    ) == "DATE_ACCELERATED":

        score += 10

    # ----------------------------------------
    # Date delay
    # ----------------------------------------

    if event.get(
        "subtype"
    ) == "DATE_DELAYED":

        score += 10

    # ----------------------------------------
    # Limit
    # ----------------------------------------

    score = min(
        score,
        MAX_SCORE
    )

    return score


# ============================================
# EVENT LABEL
# ============================================

def score_label(score):
    """
    Converte il punteggio in una categoria.
    """

    if score >= 80:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 35:
        return "MEDIUM"

    return "LOW"


# ============================================
# EVENT ENRICHMENT
# ============================================

def enrich_event(event):
    """
    Aggiunge score e label all'evento.
    """

    result = dict(event)

    score = score_event(
        result
    )

    result["score"] = score

    result["label"] = score_label(
        score
    )

    return result


# ============================================
# MULTIPLE EVENTS
# ============================================

def score_events(events):
    """
    Calcola score per una lista di eventi.
    """

    scored = []

    for event in events:

        scored.append(
            enrich_event(event)
        )

    return scored
