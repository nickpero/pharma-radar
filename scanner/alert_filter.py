"""
Pharma Radar — Alert Filter

Seleziona gli eventi che meritano un alert Telegram.

Lo scoring determina la rilevanza numerica.
Questo modulo determina se l'evento deve
effettivamente generare un alert.
"""


# ============================================
# DEFAULT THRESHOLDS
# ============================================

DEFAULT_ALERT_SCORE = 60
DEFAULT_CRITICAL_SCORE = 80


# ============================================
# CLINICAL EVENT TYPES
# ============================================

HIGH_VALUE_SUBTYPES = {
    "PRIMARY_ENDPOINT_MET",
    "PRIMARY_ENDPOINT_FAILED",
    "TOPLINE_RESULTS",
    "FDA_APPROVAL",
    "FDA_REJECTION",
    "TRIAL_STOPPED_EFFICACY",
    "TRIAL_STOPPED_SAFETY",
    "TRIAL_COMPLETED",
    "TRIAL_TERMINATED",
    "TRIAL_SUSPENDED",
    "TRIAL_WITHDRAWN",
    "DATE_ACCELERATED",
    "DATE_DELAYED",
    "PHASE_3_STARTED",
    "PHASE_2_STARTED",
    "ENROLLMENT_COMPLETED",
}


# ============================================
# EVENTS THAT SHOULD NOT ALERT BY DEFAULT
# ============================================

IGNORED_SUBTYPES = {
    "FIELD_UPDATED",
    "FIELD_CHANGE",
    "ENROLLMENT_INCREASED",
    "TRIAL_RECRUITING",
}


# ============================================
# SCORE CONVERSION
# ============================================

def get_score(event):

    score = event.get(
        "score",
        0
    )

    try:
        return int(score)

    except (
        ValueError,
        TypeError
    ):
        return 0


# ============================================
# SINGLE EVENT
# ============================================

def is_alert_worthy(
    event,
    minimum_score=DEFAULT_ALERT_SCORE
):
    """
    Restituisce True se l'evento supera
    la soglia di alert.

    Gli eventi esplicitamente ignorati
    vengono esclusi anche se hanno uno
    score elevato.
    """

    score = get_score(
        event
    )

    if score < minimum_score:
        return False

    subtype = str(
        event.get(
            "subtype",
            ""
        )
    ).upper()

    # ----------------------------------------
    # Explicitly ignored events
    # ----------------------------------------

    if subtype in IGNORED_SUBTYPES:
        return False

    # ----------------------------------------
    # Score threshold
    #
    # Qualsiasi evento che supera la soglia
    # è potenzialmente rilevante.
    #
    # Questo mantiene la compatibilità con
    # eventi Catalyst futuri non ancora
    # presenti nella lista HIGH_VALUE_SUBTYPES.
    # ----------------------------------------

    return True


# ============================================
# CRITICAL EVENT
# ============================================

def is_critical(
    event,
    critical_score=DEFAULT_CRITICAL_SCORE
):
    """
    Identifica gli eventi critici.
    """

    score = get_score(
        event
    )

    return score >= critical_score


# ============================================
# FILTER EVENTS
# ============================================

def filter_alerts(
    events,
    minimum_score=DEFAULT_ALERT_SCORE
):
    """
    Restituisce soltanto gli eventi
    che devono generare un alert.
    """

    alerts = []

    for event in events:

        if is_alert_worthy(
            event,
            minimum_score
        ):

            alerts.append(
                event
            )

    return sort_alerts(
        alerts
    )


# ============================================
# FILTER CRITICAL EVENTS
# ============================================

def filter_critical(
    events,
    critical_score=DEFAULT_CRITICAL_SCORE
):
    """
    Restituisce soltanto gli eventi critici.
    """

    critical = []

    for event in events:

        if is_critical(
            event,
            critical_score
        ):

            critical.append(
                event
            )

    return sort_alerts(
        critical
    )


# ============================================
# SORT ALERTS
# ============================================

def sort_alerts(events):
    """
    Ordina gli eventi dal punteggio più alto
    al più basso.
    """

    return sorted(
        events,
        key=lambda event: get_score(
            event
        ),
        reverse=True
    )
