"""
Pharma Radar — FDA Catalyst Scoring

Trasforma un FDA Catalyst Event in un evento
compatibile con il Catalyst Scoring Engine.

Il modulo non modifica il motore di scoring
esistente: prepara semplicemente gli eventi FDA
nel formato corretto.
"""


from scanner.score import score_event


# ============================================
# FDA SCORE BOOST
# ============================================

FDA_SCORE_BONUS = {

    "FDA_APPROVAL": 25,
    "FDA_REJECTION": 25,
    "FDA_SAFETY_WARNING": 25,
    "CLINICAL_RESULTS": 20,
    "LABEL_EXPANSION": 15,
    "FDA_UPDATE": 0,
}


# ============================================
# ENRICH FDA EVENT
# ============================================

def enrich_fda_event(event):
    """
    Arricchisce un FDA event con il bonus
    specifico della categoria FDA.

    Il punteggio base viene calcolato dal
    Catalyst Scoring Engine esistente.
    """

    if not isinstance(event, dict):
        raise TypeError(
            "event must be a dictionary"
        )

    result = dict(event)

    subtype = str(
        result.get(
            "subtype",
            "FDA_UPDATE"
        )
    ).upper()

    bonus = FDA_SCORE_BONUS.get(
        subtype,
        0
    )

    result["fda_score_bonus"] = bonus

    return result


# ============================================
# SCORE FDA EVENT
# ============================================

def score_fda_event(event):
    """
    Calcola il punteggio di un FDA catalyst.

    Usa il motore di scoring esistente e applica
    successivamente il bonus FDA specifico.

    Il risultato finale è limitato a 100.
    """

    enriched = enrich_fda_event(
        event
    )

    base_score = score_event(
        enriched
    )

    if isinstance(base_score, dict):

        result = dict(
            base_score
        )

        current_score = result.get(
            "score",
            0
        )

    else:

        result = dict(
            enriched
        )

        current_score = base_score

    try:
        current_score = int(
            current_score
        )
    except (
        ValueError,
        TypeError
    ):
        current_score = 0

    bonus = enriched.get(
        "fda_score_bonus",
        0
    )

    try:
        bonus = int(
            bonus
        )
    except (
        ValueError,
        TypeError
    ):
        bonus = 0

    final_score = min(
        current_score + bonus,
        100
    )

    result["score"] = final_score

    return result


# ============================================
# SCORE MULTIPLE FDA EVENTS
# ============================================

def score_fda_events(events):
    """
    Calcola il punteggio di una lista di
    FDA catalyst events.
    """

    if not events:
        return []

    return [
        score_fda_event(
            event
        )
        for event in events
      ]
