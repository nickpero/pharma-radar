"""
Pharma Radar — Unified Alert Priority

P2.1: combina catalyst score, trading impact,
urgency e match confidence in un singolo valore
operativo per ordinare gli alert.

Non è una previsione del movimento del titolo e
non costituisce una raccomandazione finanziaria.
"""

IMPACT_SCORE = {
    "EXTREME": 40,
    "HIGH": 30,
    "MEDIUM": 18,
    "LOW": 8,
}

URGENCY_SCORE = {
    "IMMEDIATE": 25,
    "FAST": 18,
    "NORMAL": 10,
    "LOW": 4,
}

CONFIDENCE_SCORE = {
    "HIGH": 15,
    "MEDIUM": 8,
    "LOW": 3,
}


def _bounded_int(value, default=0):
    try:
        return max(0, min(100, int(value)))
    except (ValueError, TypeError):
        return default


def get_alert_priority(event):
    """Calcola una priorità operativa 0-100."""
    if not isinstance(event, dict):
        raise TypeError("event must be a dictionary")

    score = _bounded_int(event.get("score", 0))
    impact = str(event.get("trading_impact", "LOW")).upper()
    urgency = str(event.get("urgency", "LOW")).upper()
    confidence = str(event.get("match_confidence", "LOW")).upper()

    # Il catalyst score pesa fino a 20 punti.
    catalyst_component = round(score * 0.20)
    impact_component = IMPACT_SCORE.get(impact, 8)
    urgency_component = URGENCY_SCORE.get(urgency, 4)
    confidence_component = CONFIDENCE_SCORE.get(confidence, 3)

    return min(
        100,
        catalyst_component
        + impact_component
        + urgency_component
        + confidence_component,
    )


def enrich_alert_priority(event):
    """Aggiunge alert_priority senza alterare i dati originali."""
    result = dict(event)
    result["alert_priority"] = get_alert_priority(result)
    return result


def enrich_alert_priorities(events):
    """Arricchisce una lista di eventi con la priorità unificata."""
    if not events:
        return []
    return [enrich_alert_priority(event) for event in events]


def sort_by_alert_priority(events):
    """Ordina per priorità operativa, poi per catalyst score."""
    return sorted(
        events or [],
        key=lambda event: (
            _bounded_int(event.get("alert_priority", 0)),
            _bounded_int(event.get("score", 0)),
        ),
        reverse=True,
    )
