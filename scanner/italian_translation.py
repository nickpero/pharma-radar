"""Traduzione dei contenuti esterni in italiano per le notifiche Pharma Radar.

Le etichette interne sono tradotte localmente; i testi provenienti da fonti esterne
vengono tradotti prima della visualizzazione. I nomi propri indicati dal chiamante
sono protetti. In caso di indisponibilità del servizio non viene mostrato testo
inglese non tradotto: si visualizza un messaggio esplicito e resta disponibile il link
alla fonte primaria.
"""
import re
from functools import lru_cache

import requests

TRANSLATION_URL = "https://translate.googleapis.com/translate_a/single"
_TRANSLATION_FAILURE = "Traduzione non disponibile; consultare la fonte originale."


def _protect_terms(text, protected_terms):
    result = str(text or "")
    replacements = {}
    # Replace longer terms first so a company/program name is not partially changed.
    terms = sorted({str(term).strip() for term in (protected_terms or []) if str(term or "").strip()},
                   key=len, reverse=True)
    for index, term in enumerate(terms):
        token = f"ZXQPHARMANAME{index}QXZ"
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if pattern.search(result):
            result = pattern.sub(token, result)
            replacements[token] = term
    return result, replacements


@lru_cache(maxsize=512)
def _translate_cached(text):
    response = requests.get(
        TRANSLATION_URL,
        params={"client": "gtx", "sl": "auto", "tl": "it", "dt": "t", "q": text},
        timeout=6,
    )
    response.raise_for_status()
    payload = response.json()
    translated = "".join(
        segment[0] for segment in (payload[0] or [])
        if isinstance(segment, list) and segment and segment[0]
    )
    if not translated.strip():
        raise ValueError("Il servizio di traduzione ha restituito un testo vuoto")
    return translated


def translate_to_italian(value, protected_terms=None):
    """Translate arbitrary source text to Italian, preserving named entities.

    If translation is unavailable, return an Italian fallback rather than silently
    emitting untranslated English text. Empty values remain empty.
    """
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    protected_text, replacements = _protect_terms(text, protected_terms)
    try:
        translated = _translate_cached(protected_text)
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError):
        return _TRANSLATION_FAILURE
    for token, term in replacements.items():
        translated = translated.replace(token, term)
        translated = translated.replace(token.lower(), term)
    return translated


def alert_protected_terms(alert):
    """Return known company, ticker and drug/program names to preserve verbatim."""
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    terms = [
        alert.get("company"), event.get("company"),
        alert.get("ticker"), alert.get("drug_name"), alert.get("drug"),
        alert.get("program"), event.get("program"),
    ]
    trial = alert.get("trial") if isinstance(alert.get("trial"), dict) else {}
    for key in ("intervention", "interventions", "drug_name", "drug"):
        value = trial.get(key)
        if isinstance(value, str):
            terms.append(value)
        elif isinstance(value, list):
            terms.extend(value)
    return [str(term).strip() for term in terms if isinstance(term, str) and term.strip()]
