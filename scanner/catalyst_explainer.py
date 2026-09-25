"""
Pharma Radar — Catalyst Explainer

Deterministic, source-grounded explainer for important pharma catalysts.
No scientific mechanism is invented: when the source does not provide enough
information, the explainer explicitly says so.
"""

import re


IMPORTANT_LABELS = {"CRITICAL", "HIGH"}


def _clean(value, limit=360):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:limit].rstrip(" .")


def _first_nonempty(*values):
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return ""


def _trial_text(alert):
    trial = alert.get("trial") if isinstance(alert.get("trial"), dict) else {}
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    return _first_nonempty(
        trial.get("brief_summary"), trial.get("summary"), trial.get("description"),
        event.get("summary"), alert.get("summary")
    )


def _indication(alert):
    trial = alert.get("trial") if isinstance(alert.get("trial"), dict) else {}
    conditions = trial.get("conditions")
    if isinstance(conditions, list):
        values = [_clean(item, 100) for item in conditions if _clean(item, 100)]
        if values:
            return ", ".join(values[:2])
    if isinstance(conditions, str) and conditions.strip():
        return _clean(conditions, 180)
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    return _first_nonempty(event.get("indication"), event.get("disease"))


def _stage(alert):
    trial = alert.get("trial") if isinstance(alert.get("trial"), dict) else {}
    return _first_nonempty(
        trial.get("phase"), trial.get("overall_phase"),
        alert.get("development_stage"), alert.get("stage")
    ) or "Non disponibile"


def _what_it_is(alert):
    text = _trial_text(alert)
    if text:
        return text
    return "La fonte disponibile non contiene una descrizione sufficiente del farmaco/program­ma."


def _why_it_matters(alert):
    subtype = str(alert.get("subtype") or "").upper()
    direction = str(alert.get("direction") or "").upper()
    mapping = {
        "FDA_APPROVAL": "L'approvazione FDA porta il programma a un passaggio regolatorio/commerciale decisivo.",
        "FDA_MEETING": "Interlocuzione con la FDA su sviluppo o percorso regolatorio; non equivale ad approvazione.",
        "FDA_PATHWAY": "Indicazione di un possibile percorso regolatorio; non equivale ad approvazione.",
        "EMA_APPROVAL": "Il parere/autorizzazione EMA rappresenta un passaggio regolatorio decisivo per il programma.",
        "CLINICAL_RESULTS": "I risultati clinici possono modificare la valutazione del programma e il rischio percepito dal mercato.",
        "CLINICAL_RESULT": "I risultati clinici possono modificare la valutazione del programma e il rischio percepito dal mercato.",
        "PHASE_ADVANCEMENT": "Il passaggio a una fase successiva indica avanzamento dello sviluppo clinico e riduzione di parte del rischio di sviluppo.",
        "FILING": "Il filing rappresenta un passaggio regolatorio formale verso una possibile decisione dell'autorità.",
        "TRIAL_COMPLETED": "Il completamento dello studio rende disponibili dati o un passaggio decisionale potenzialmente rilevante.",
        "SAFETY": "Un evento di sicurezza può modificare materialmente il profilo rischio/beneficio del programma.",
        "REJECTION": "Un rifiuto regolatorio aumenta il rischio sul programma e può avere un impatto rilevante sulla società.",
        "LABEL_EXPANSION": "L'espansione dell'indicazione può aumentare il mercato potenziale del farmaco.",
    }
    return mapping.get(subtype) or (
        "Il segnale è rilevante per la società perché è classificato come catalizzatore di sviluppo/regolatorio."
        if direction in {"POSITIVE", "CATALYST"} else
        "Il segnale merita attenzione perché può modificare la valutazione del programma."
    )


def _company_impact(alert):
    subtype = str(alert.get("subtype") or "").upper()
    if subtype in {"FDA_APPROVAL", "EMA_APPROVAL"}:
        return "Potenziale passaggio dalla fase di sviluppo alla commercializzazione, con possibile impatto su ricavi e valorizzazione; l'entità dipende dal mercato e dall'esecuzione commerciale."
    if subtype in {"REJECTION", "SAFETY"}:
        return "Possibile impatto negativo sul valore del programma e sulle aspettative della società."
    if subtype in {"PHASE_ADVANCEMENT", "CLINICAL_RESULT", "CLINICAL_RESULTS", "LABEL_EXPANSION", "FILING"}:
        return "Può modificare le aspettative sul valore del programma e sulla probabilità di successo regolatorio/commerciale."
    return "Impatto potenziale da valutare insieme alla qualità dei dati e alla reazione del mercato."


def _market_reaction(alert):
    reaction = alert.get("market_reaction") or {}
    values = []
    for label, key in (("1m", "reaction_1m_pct"), ("5m", "reaction_5m_pct"), ("15m", "reaction_15m_pct"), ("30m", "reaction_30m_pct"), ("60m", "reaction_60m_pct")):
        value = reaction.get(key)
        if value is not None:
            values.append(f"{label} {float(value):+.2f}%")
    strength = alert.get("reaction_strength", "UNKNOWN")
    interpretation = alert.get("reaction_interpretation", "UNKNOWN")
    if values:
        return " | ".join(values) + f" → {strength} / {interpretation}"
    return f"Non ancora disponibile → {strength} / {interpretation}"


def enrich_catalyst_explainer(alert):
    """Add a concise Italian, source-grounded explainer to Pharma alerts."""
    if not isinstance(alert, dict):
        return alert
    explainer = {
        "what_is": _what_it_is(alert),
        "indication": _indication(alert) or "Non disponibile nella fonte analizzata",
        "stage": _stage(alert),
        "why_it_matters": _why_it_matters(alert),
        "company_impact": _company_impact(alert),
        "market_reaction": _market_reaction(alert),
        "language": "it",
        "source_grounded": True,
    }
    enriched = dict(alert)
    enriched["catalyst_explainer"] = explainer
    return enriched


def enrich_catalyst_explainers(alerts):
    return [enrich_catalyst_explainer(alert) for alert in (alerts or [])]
