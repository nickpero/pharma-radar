"""
Pharma Radar — Alert Filter

Seleziona gli eventi che meritano un alert Telegram.

Lo scoring determina la rilevanza.
Questo modulo determina se l'evento supera
la soglia necessaria per generare un alert.
"""


# ============================================
# DEFAULT THRESHOLDS
# ============================================

DEFAULT_ALERT_SCORE = 60
DEFAULT_CRITICAL_SCORE = 80


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
    """

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
        return False

    return score >= minimum_score


# ============================================
# CRITICAL EVENT
# ============================================

def is_critical(
    event,
    critical_score=DEFAULT_CRITICAL_SCORE
):
    """
    Identifica gli eventi CRITICAL.
    """

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
        return False

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
    che superano la soglia.
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

    return alerts


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

    return critical


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
        key=lambda event: event.get(
            "score",
            0
        ),
        reverse=True
  )
