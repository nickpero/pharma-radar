"""
Pharma Radar — Trading Intelligence

Trasforma un evento clinico già classificato e
scorato in una valutazione orientata al trading.

IMPORTANTE:
Non è una raccomandazione di acquisto o vendita.
Serve a stabilire la priorità operativa dell'evento.
"""


# ============================================
# TRADING IMPACT LEVELS
# ============================================

IMPACT_LEVELS = {
    "EXTREME": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}


# ============================================
# EVENT PRIORITY
# ============================================

EVENT_PRIORITY = {

    # ----------------------------------------
    # EXTREME
    # ----------------------------------------

    "TRIAL_POSITIVE": "EXTREME",
    "ENDPOINT_REACHED": "EXTREME",
    "TRIAL_NEGATIVE": "EXTREME",
    "ENDPOINT_FAILED": "EXTREME",
    "TRIAL_STOPPED_SAFETY": "EXTREME",
    "TRIAL_STOPPED_EFFICACY": "EXTREME",

    "FDA_APPROVAL": "EXTREME",
    "EMA_APPROVAL": "EXTREME",
    "FDA_REJECTION": "EXTREME",
    "EMA_REJECTION": "EXTREME",
    "COMPLETE_RESPONSE_LETTER": "EXTREME",

    "CLINICAL_RESULTS": "EXTREME",

    # ----------------------------------------
    # HIGH
    # ----------------------------------------

    "DATE_ACCELERATED": "HIGH",
    "PHASE_ADVANCED": "HIGH",
    "PHASE_CHANGE": "HIGH",
    "SIGNIFICANT_ENROLLMENT_CHANGE": "HIGH",
    "DATE_DELAYED": "HIGH",

    # ----------------------------------------
    # MEDIUM
    # ----------------------------------------

    "ENROLLMENT_UPDATED": "MEDIUM",
    "PROTOCOL_UPDATED": "MEDIUM",
    "SITE_CHANGE": "MEDIUM",

    # ----------------------------------------
    # LOW
    # ----------------------------------------

    "FIELD_UPDATED": "LOW",
    "CONTACT_UPDATED": "LOW",
    "ADMINISTRATIVE_UPDATE": "LOW",
}


# ============================================
# DEFAULT PRIORITY
# ============================================

DEFAULT_PRIORITY = "LOW"


# ============================================
# GET TRADING IMPACT
# ============================================

def get_trading_impact(event):
    """
    Determina il livello di impatto potenziale
    dell'evento sul titolo.

    La valutazione combina:

    - subtype
    - event type
    - score
    - direction
    """

    subtype = str(
        event.get(
            "subtype",
            ""
        )
    ).upper()

    event_type = str(
        event.get(
            "type",
            ""
        )
    ).upper()

    direction = str(
        event.get(
            "direction",
            "UNKNOWN"
        )
    ).upper()

    score = event.get(
        "score",
        0
    )

    try:
        score = int(score)

    except (
        ValueError,
        TypeError
    ):
        score = 0

    # ========================================
    # EXTREME SUBTYPES
    # ========================================

    if subtype in {
        "TRIAL_POSITIVE",
        "ENDPOINT_REACHED",
        "TRIAL_NEGATIVE",
        "ENDPOINT_FAILED",
        "TRIAL_STOPPED_SAFETY",
        "TRIAL_STOPPED_EFFICACY",
        "FDA_APPROVAL",
        "EMA_APPROVAL",
        "FDA_REJECTION",
        "EMA_REJECTION",
        "COMPLETE_RESPONSE_LETTER",
        "CLINICAL_RESULTS",
    }:

        return "EXTREME"

    # ========================================
    # CRITICAL SCORE
    # ========================================

    if score >= 80:

        if direction in {
            "POSITIVE",
            "NEGATIVE",
            "CATALYST",
        }:

            return "EXTREME"

    # ========================================
    # HIGH SCORE
    # ========================================

    if score >= 60:
        return "HIGH"

    # ========================================
    # EVENT TYPE
    # ========================================

    if event_type == "PHASE_CHANGE":
        return "HIGH"

    if event_type == "DATE_CHANGE":

        if subtype in {
            "DATE_ACCELERATED",
            "DATE_DELAYED",
        }:

            return "HIGH"

        return "MEDIUM"

    if event_type == "STATUS_CHANGE":

        if direction == "CATALYST":
            return "EXTREME"

        if direction in {
            "POSITIVE",
            "NEGATIVE",
        }:

            return "HIGH"

    if event_type == "ENROLLMENT_CHANGE":
        return "MEDIUM"

    if event_type == "PROTOCOL_CHANGE":
        return "MEDIUM"

    if event_type == "FIELD_CHANGE":
        return "LOW"

    return DEFAULT_PRIORITY


# ============================================
# PRIORITY SCORE
# ============================================

def trading_priority_score(event):
    """
    Converte il Trading Impact in un valore 1-4.
    """

    impact = get_trading_impact(
        event
    )

    return IMPACT_LEVELS.get(
        impact,
        IMPACT_LEVELS[
            DEFAULT_PRIORITY
        ]
    )


# ============================================
# URGENCY
# ============================================

def get_urgency(event):
    """
    Determina la velocità con cui l'evento
    dovrebbe essere analizzato.
    """

    impact = get_trading_impact(
        event
    )

    score = event.get(
        "score",
        0
    )

    try:
        score = int(score)

    except (
        ValueError,
        TypeError
    ):
        score = 0

    # ========================================
    # EXTREME
    # ========================================

    if impact == "EXTREME":
        return "IMMEDIATE"

    # ========================================
    # HIGH
    # ========================================

    if impact == "HIGH" and score >= 60:
        return "FAST"

    # ========================================
    # MEDIUM
    # ========================================

    if impact == "MEDIUM":
        return "NORMAL"

    # ========================================
    # LOW
    # ========================================

    return "LOW"


# ============================================
# ENRICH EVENT
# ============================================

def enrich_trading_event(event):
    """
    Aggiunge le informazioni Trading Intelligence
    all'evento senza modificarne i dati originali.
    """

    result = dict(
        event
    )

    impact = get_trading_impact(
        result
    )

    result["trading_impact"] = impact

    result["trading_priority"] = (
        trading_priority_score(
            result
        )
    )

    result["urgency"] = get_urgency(
        result
    )

    return result


# ============================================
# MULTIPLE EVENTS
# ============================================

def enrich_trading_events(events):
    """
    Arricchisce una lista di eventi.
    """

    return [
        enrich_trading_event(event)
        for event in events
    ]
