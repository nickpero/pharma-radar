"""
Pharma Radar — Catalyst Scoring Engine

Trasforma gli eventi clinici classificati in un punteggio
di rilevanza per il trading.

Il punteggio NON è una raccomandazione di acquisto o vendita.
Serve a stabilire quali eventi meritano maggiore attenzione.

Il motore mantiene la compatibilità con gli eventi storici
del Pharma Radar e aggiunge una valutazione più raffinata
dei catalyst clinici.
"""


from datetime import datetime


# ============================================
# SCORE LIMIT
# ============================================

MAX_SCORE = 100


# ============================================
# BASE SCORES
# ============================================

SEVERITY_SCORE = {
    "HIGH": 70,
    "MEDIUM": 40,
    "LOW": 15,
}


# ============================================
# DIRECTION BONUS
# ============================================

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
# HIGH-VALUE CLINICAL EVENTS
# ============================================

SUBTYPE_BONUS = {

    # Major positive catalysts
    "TRIAL_COMPLETED": 5,
    "ENROLLMENT_COMPLETED": 10,
    "PRIMARY_ENDPOINT_MET": 20,
    "TOPLINE_RESULTS": 25,
    "FDA_APPROVAL": 30,
    "PRIMARY_ENDPOINT_MET": 25,
    "PRIMARY_ENDPOINT_FAILED": 25,
    "TOPLINE_RESULTS": 25,
    "MAINTENANCE_DATA": 20,
    "DOSE_RESPONSE": 15,
    "SECONDARY_ENDPOINT_MET": 10,
    "SECONDARY_ENDPOINT_FAILED": 15,
    "EFFICACY_SIGNAL": 15,
    "SAFETY_SIGNAL": 25,

    # Major negative catalysts
    "PRIMARY_ENDPOINT_FAILED": 25,
    "FDA_REJECTION": 30,
    "TRIAL_STOPPED_EFFICACY": 25,
    "TRIAL_STOPPED_SAFETY": 30,

    # Important but less decisive
    "SECONDARY_ENDPOINT_MET": 10,
    "SECONDARY_ENDPOINT_FAILED": 15,

    "PHASE_3_STARTED": 15,
    "PHASE_2_STARTED": 10,
    "PHASE_1_STARTED": 5,

    "DATE_ACCELERATED": 10,
    "DATE_DELAYED": 10,

    "TRIAL_TERMINATED": 20,
    "TRIAL_SUSPENDED": 15,
    "TRIAL_WITHDRAWN": 15,

    "TRIAL_RECRUITING": 0,
    "ENROLLMENT_INCREASED": 0,
}


# ============================================
# PHASE BONUS
# ============================================

PHASE_BONUS = {
    "PHASE3": 10,
    "PHASE 3": 10,

    "PHASE2": 5,
    "PHASE 2": 5,

    "PHASE1": 0,
    "PHASE 1": 0,
}


# ============================================
# TIMING BONUS
# ============================================

def parse_event_date(value):

    if not value:
        return None

    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            pass

    try:
        return datetime.strptime(
            str(value),
            "%Y-%m-%d",
        ).date()

    except (
        ValueError,
        TypeError,
    ):
        return None


def timing_bonus(event_date):

    date = parse_event_date(
        event_date
    )

    if date is None:
        return 0

    today = datetime.utcnow().date()

    days = (
        date - today
    ).days

    # Event already occurred or is imminent.
    if days <= 7:
        return 15

    # Event within approximately one month.
    if days <= 30:
        return 10

    # Event within approximately three months.
    if days <= 90:
        return 5

    return 0


# ============================================
# PHASE BONUS
# ============================================

def phase_bonus(phase):

    if not phase:
        return 0

    value = str(
        phase
    ).strip().upper()

    return PHASE_BONUS.get(
        value,
        0,
    )


# ============================================
# SCORE MAIN EVENT
# ============================================

def score_event(event):
    """
    Calcola il punteggio di un singolo evento.

    Il punteggio finale è compreso tra 0 e 100.
    """

    severity = str(
        event.get(
            "severity",
            "LOW",
        )
    ).upper()

    direction = str(
        event.get(
            "direction",
            "UNKNOWN",
        )
    ).upper()

    event_type = str(
        event.get(
            "type",
            "FIELD_CHANGE",
        )
    ).upper()

    subtype = str(
        event.get(
            "subtype",
            "",
        )
    ).upper()

    score = 0

    # ----------------------------------------
    # Severity
    # ----------------------------------------

    score += SEVERITY_SCORE.get(
        severity,
        0,
    )

    # ----------------------------------------
    # Direction
    # ----------------------------------------

    score += DIRECTION_BONUS.get(
        direction,
        0,
    )

    # ----------------------------------------
    # Event type
    # ----------------------------------------

    score += EVENT_TYPE_BONUS.get(
        event_type,
        0,
    )

    # ----------------------------------------
    # Clinical subtype
    # ----------------------------------------

    score += SUBTYPE_BONUS.get(
        subtype,
        0,
    )

    # ----------------------------------------
    # Phase
    # ----------------------------------------

    score += phase_bonus(
        event.get(
            "phase"
        )
    )

    # ----------------------------------------
    # Timing
    # ----------------------------------------

    score += timing_bonus(
        event.get(
            "event_date"
        )
    )

    # ----------------------------------------
    # Historical compatibility
    #
    # These conditions preserve the original
    # scoring behaviour expected by the
    # existing Radar tests.
    # ----------------------------------------

    if subtype == "DATE_ACCELERATED":
        score += 0

    if subtype == "DATE_DELAYED":
        score += 0

    # ----------------------------------------
    # Limit
    # ----------------------------------------

    score = min(
        score,
        MAX_SCORE,
    )

    return score


# ============================================
# SCORE LABEL
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

    result = dict(
        event
    )

    score = score_event(
        result
    )

    result["score"] = score

    result["label"] = score_label(
        score
    )

    try:
        from scanner.clinical_impact import enrich_clinical_impact
        result = enrich_clinical_impact(result)
    except Exception:
        pass

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
            enrich_event(
                event
            )
        )

    # Gli eventi più importanti vengono
    # restituiti per primi.
    scored.sort(
        key=lambda item: item.get(
            "score",
            0
        ),
        reverse=True,
    )

    return scored
