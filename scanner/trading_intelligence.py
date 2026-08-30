"""
Pharma Radar — Trading Intelligence

Trasforma un evento clinico o regolatorio già
classificato e scorato in una valutazione
orientata al trading.

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
    # EXTREME — CLINICAL
    # ----------------------------------------

    "TRIAL_POSITIVE": "EXTREME",
    "ENDPOINT_REACHED": "EXTREME",
    "TRIAL_NEGATIVE": "EXTREME",
    "ENDPOINT_FAILED": "EXTREME",
    "TRIAL_STOPPED_SAFETY": "EXTREME",
    "TRIAL_STOPPED_EFFICACY": "EXTREME",
    "CLINICAL_RESULTS": "EXTREME",

    # ----------------------------------------
    # EXTREME — FDA / REGULATORY
    # ----------------------------------------

    "FDA_APPROVAL": "EXTREME",
    "FDA_REJECTION": "EXTREME",
    "FDA_SAFETY_WARNING": "EXTREME",
    "FDA_SAFETY_SIGNAL": "EXTREME",
    "FDA_RECALL": "EXTREME",
    "EMA_APPROVAL": "EXTREME",
    "EMA_REJECTION": "EXTREME",
    "COMPLETE_RESPONSE_LETTER": "EXTREME",

    # ----------------------------------------
    # HIGH
    # ----------------------------------------

    "DATE_ACCELERATED": "HIGH",
    "DATE_DELAYED": "HIGH",
    "PHASE_ADVANCED": "HIGH",
    "PHASE_CHANGE": "HIGH",
    "SIGNIFICANT_ENROLLMENT_CHANGE": "HIGH",

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
    """

    if not isinstance(event, dict):
        return DEFAULT_PRIORITY

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

    # ----------------------------------------
    # Exact subtype match
    # ----------------------------------------

    if subtype in EVENT_PRIORITY:

        return EVENT_PRIORITY[
            subtype
        ]

    # ----------------------------------------
    # Generic event type
    # ----------------------------------------

    if event_type == "FDA_EVENT":

        # FDA events not explicitly mapped
        # are still treated as important.

        priority = str(
            event.get(
                "priority",
                ""
            )
        ).upper()

        if priority == "EXTREME":
            return "EXTREME"

        if priority == "HIGH":
            return "HIGH"

        if priority == "MEDIUM":
            return "MEDIUM"

        return DEFAULT_PRIORITY

    if event_type == "PHASE_CHANGE":
        return "HIGH"

    if event_type == "DATE_CHANGE":
        return "HIGH"

    if event_type == "STATUS_CHANGE":

        direction = str(
            event.get(
                "direction",
                "UNKNOWN"
            )
        ).upper()

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
    Converte l'impatto Trading in un valore 1-4.
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

    # ----------------------------------------
    # EXTREME
    # ----------------------------------------

    if impact == "EXTREME":
        return "IMMEDIATE"

    # ----------------------------------------
    # HIGH
    # ----------------------------------------

    if impact == "HIGH" and score >= 60:
        return "FAST"

    # ----------------------------------------
    # MEDIUM
    # ----------------------------------------

    if impact == "MEDIUM":
        return "NORMAL"

    # ----------------------------------------
    # LOW
    # ----------------------------------------

    return "LOW"


# ============================================
# ENRICH EVENT
# ============================================

def enrich_trading_event(event):
    """
    Aggiunge le informazioni Trading Intelligence
    all'evento senza modificare i dati originali.
    """

    if not isinstance(event, dict):
        return {}

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

    if not events:
        return []

    return [
        enrich_trading_event(event)
        for event in events
    ]