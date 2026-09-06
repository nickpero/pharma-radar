"""
Pharma Radar — FDA Catalyst Engine

Trasforma una FDA News Item in un evento Catalyst
standardizzato, distinguendo il tipo di catalyst,
direzione e urgenza.

Questo modulo NON effettua raccomandazioni di acquisto o vendita.
"""

import re

FDA_CATALYST_MAP = {
    "APPROVAL": {"type": "FDA_EVENT", "subtype": "FDA_APPROVAL", "severity": "HIGH", "direction": "CATALYST"},
    "REJECTION": {"type": "FDA_EVENT", "subtype": "FDA_REJECTION", "severity": "HIGH", "direction": "NEGATIVE"},
    "SAFETY": {"type": "FDA_EVENT", "subtype": "FDA_SAFETY_WARNING", "severity": "HIGH", "direction": "NEGATIVE"},
    "CLINICAL": {"type": "FDA_EVENT", "subtype": "CLINICAL_RESULTS", "severity": "HIGH", "direction": "POSITIVE"},
    "LABEL": {"type": "FDA_EVENT", "subtype": "LABEL_EXPANSION", "severity": "HIGH", "direction": "CATALYST"},
}

DEFAULT_EVENT = {"type": "FDA_EVENT", "subtype": "FDA_UPDATE", "severity": "LOW", "direction": "UNKNOWN"}

CATEGORY_PRIORITY = ["APPROVAL", "REJECTION", "SAFETY", "CLINICAL", "LABEL"]

ADVANCED_RULES = [
    ("TRIAL_HOLD_LIFTED", "POSITIVE", "HIGH", ("clinical hold lifted", "hold lifted", "lifted the clinical hold", "hold is lifted")),
    ("TRIAL_HOLD", "NEGATIVE", "EXTREME", ("clinical hold", "placed on clinical hold", "trial hold", "study hold")),
    ("DATE_ACCELERATED", "POSITIVE", "HIGH", ("accelerated timeline", "date accelerated", "accelerated the timeline", "earlier than expected")),
    ("DATE_DELAYED", "NEGATIVE", "HIGH", ("delayed timeline", "date delayed", "delay in the timeline", "later than expected", "delayed submission")),
    ("REJECTION", "NEGATIVE", "EXTREME", ("complete response letter", "\bcrl\b", "not approved", "rejected", "rejection", "refused", "refusal", "denied", "denial")),
    ("SAFETY", "NEGATIVE", "EXTREME", ("boxed warning", "safety warning", "drug safety communication", "recall", "serious safety", "safety concern", "contamination")),
    ("APPROVAL", "POSITIVE", "EXTREME", ("approved", "approval", "authorizes", "authorized", "authorization", "cleared", "clearance")),
    ("LABEL_EXPANSION", "POSITIVE", "HIGH", ("label expansion", "expanded indication", "expanded use", "expanded the indication", "new indication")),
    ("CLINICAL_RESULT", "NEGATIVE", "HIGH", ("failed to meet", "did not meet", "missed the primary endpoint", "failed the primary endpoint", "futility", "negative topline")),
    ("CLINICAL_RESULT", "POSITIVE", "HIGH", ("met the primary endpoint", "met its primary endpoint", "positive topline", "positive results", "statistically significant", "clinical benefit")),
]


def _text(news_item):
    parts = []
    for key in ("title", "summary", "article_text", "content", "body", "text"):
        value = news_item.get(key)
        if value:
            parts.append(str(value))
    return "\n".join(parts).lower()


def _matches(text, pattern):
    if "\\b" in pattern or pattern.startswith("\\b"):
        return bool(re.search(pattern, text, re.IGNORECASE))
    return pattern in text


def classify_fda_catalyst(news_item):
    """Classifica una news FDA in catalyst_type, direction e urgency."""
    if not isinstance(news_item, dict):
        raise TypeError("news_item must be a dictionary")

    text = _text(news_item)
    title = str(news_item.get("title") or "").lower()

    # Il titolo ha precedenza per gli eventi regulatorily decisive.
    for catalyst_type, direction, urgency, patterns in ADVANCED_RULES:
        if any(_matches(title, p) for p in patterns):
            return {"catalyst_type": catalyst_type, "direction": direction, "urgency": urgency, "classification_source": "title"}

    for catalyst_type, direction, urgency, patterns in ADVANCED_RULES:
        if any(_matches(text, p) for p in patterns):
            return {"catalyst_type": catalyst_type, "direction": direction, "urgency": urgency, "classification_source": "content"}

    return {"catalyst_type": "NEUTRAL", "direction": "UNKNOWN", "urgency": "LOW", "classification_source": "fallback"}


def build_fda_catalyst(news_item):
    if not isinstance(news_item, dict):
        raise TypeError("news_item must be a dictionary")

    categories = news_item.get("categories", [])
    if not isinstance(categories, list):
        categories = list(categories or [])
    normalized_categories = {str(category).upper() for category in categories}

    selected_category = next((c for c in CATEGORY_PRIORITY if c in normalized_categories), None)
    event = dict(FDA_CATALYST_MAP.get(selected_category, DEFAULT_EVENT))

    advanced = classify_fda_catalyst(news_item)
    event.update(advanced)

    # Manteniamo la compatibilità con il vecchio schema: CLINICAL/SAFETY/etc.
    if advanced["catalyst_type"] == "CLINICAL_RESULT":
        event["subtype"] = "CLINICAL_RESULTS"
    elif advanced["catalyst_type"] == "LABEL_EXPANSION":
        event["subtype"] = "LABEL_EXPANSION"
    elif advanced["catalyst_type"] == "REJECTION":
        event["subtype"] = "FDA_REJECTION"
    elif advanced["catalyst_type"] == "SAFETY":
        event["subtype"] = "FDA_SAFETY_WARNING"
    elif advanced["catalyst_type"] == "APPROVAL":
        event["subtype"] = "FDA_APPROVAL"

    # L'urgenza avanzata diventa anche severity per il motore di scoring.
    if advanced["urgency"] == "EXTREME":
        event["severity"] = "HIGH"
    elif advanced["urgency"] == "HIGH" and event.get("severity") == "LOW":
        event["severity"] = "MEDIUM"

    event["source"] = news_item.get("source", "FDA")
    event["title"] = news_item.get("title", "")
    event["summary"] = news_item.get("summary", "")
    event["url"] = news_item.get("url")
    event["published_at"] = news_item.get("published_at")
    event["categories"] = list(normalized_categories)
    event["field"] = None
    event["old_value"] = None
    event["new_value"] = news_item.get("title", "")
    return event


def build_fda_catalysts(news_items):
    if not news_items:
        return []
    return [build_fda_catalyst(item) for item in news_items]


def build_relevant_fda_catalysts(news_items):
    catalysts = []
    for item in news_items:
        priority = str(item.get("priority", "LOW")).upper()
        if priority not in {"EXTREME", "HIGH"}:
            continue
        catalysts.append(build_fda_catalyst(item))
    return catalysts
