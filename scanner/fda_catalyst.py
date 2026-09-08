"""Pharma Radar — FDA Catalyst Engine."""

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
    ("REJECTION", "NEGATIVE", "EXTREME", ("complete response letter", r"\bcrl\b", "not approved", "does not approve", "did not approve", "will not approve", "won't approve", "rejected", "rejection", "refused", "refusal", "denied", "denial")),
    ("SAFETY", "NEGATIVE", "EXTREME", ("boxed warning", "safety warning", "drug safety communication", "recall", "serious safety", "safety concern", "contamination")),
    ("APPROVAL", "POSITIVE", "EXTREME", ("approves", "approved", "approval", "authorizes", "authorized", "authorization", "cleared", "clearance")),
    ("LABEL_EXPANSION", "POSITIVE", "HIGH", ("label expansion", "expanded indication", "expands indication", "expanded use", "expands use", "expanded the indication", "expands the indication", "new indication")),
    ("FILING", "POSITIVE", "HIGH", ("new drug application", "biologics license application", "nda submission", "bla submission", "regulatory submission", "submitted the application", "filing accepted")),
    ("CLINICAL_RESULT", "NEGATIVE", "HIGH", ("failed to meet", "did not meet", "missed the primary endpoint", "failed the primary endpoint", "futility", "negative topline", "not statistically significant", "no significant benefit")),
    ("CLINICAL_RESULT", "POSITIVE", "HIGH", ("met the primary endpoint", "met its primary endpoint", "positive topline", "positive results", "statistically significant", "clinical benefit")),
    ("CLINICAL_RESULT", "POSITIVE", "HIGH", ("clinical trial results", "clinical study results", "clinical results", "topline results", "trial results", "phase 2 results", "phase 3 results")),
    ("PHASE_ADVANCEMENT", "POSITIVE", "HIGH", ("phase advancement", "advanced to phase", "advances to phase", "phase 2", "phase 3")),
    ("DATE_ACCELERATED", "POSITIVE", "HIGH", ("accelerated timeline", "date accelerated", "accelerated the timeline", "earlier than expected")),
    ("DATE_DELAYED", "NEGATIVE", "HIGH", ("delayed timeline", "date delayed", "delay in the timeline", "later than expected", "delayed submission")),
]

CLINICAL_RULES = [rule for rule in ADVANCED_RULES if rule[0] == "CLINICAL_RESULT"]


def _text(news_item):
    return "\n".join(str(news_item.get(k) or "") for k in ("title", "summary", "article_text", "content", "body", "text")).lower()


def _matches(text, pattern):
    return bool(re.search(pattern, text, re.IGNORECASE)) if pattern.startswith(r"\b") else pattern in text


def _classify(text, source_name, rules=ADVANCED_RULES):
    for catalyst_type, direction, urgency, patterns in rules:
        if any(_matches(text, p) for p in patterns):
            return {"catalyst_type": catalyst_type, "direction": direction, "urgency": urgency, "classification_source": source_name}
    return None


def classify_fda_catalyst(news_item):
    if not isinstance(news_item, dict):
        raise TypeError("news_item must be a dictionary")
    text = _text(news_item)
    title = str(news_item.get("title") or "").lower()
    source_type = str(news_item.get("source_type") or "").upper()

    # SEC/corporate releases often contain boilerplate such as "not approved".
    # Resolve explicit clinical evidence first for primary-corporate sources.
    if source_type == "PRIMARY_CORPORATE":
        for source_text, source_name in ((title, "title"), (text, "content")):
            result = _classify(source_text, source_name, CLINICAL_RULES)
            if result:
                return result

    for source_text, source_name in ((title, "title"), (text, "content")):
        result = _classify(source_text, source_name)
        if result:
            return result
    return {"catalyst_type": "NEUTRAL", "direction": "UNKNOWN", "urgency": "LOW", "classification_source": "fallback"}


def build_fda_catalyst(news_item):
    if not isinstance(news_item, dict):
        raise TypeError("news_item must be a dictionary")
    categories = news_item.get("categories", [])
    if not isinstance(categories, list):
        categories = list(categories or [])
    normalized_categories = {str(c).upper() for c in categories}
    selected_category = next((c for c in CATEGORY_PRIORITY if c in normalized_categories), None)
    event = dict(FDA_CATALYST_MAP.get(selected_category, DEFAULT_EVENT))
    advanced = classify_fda_catalyst(news_item)
    if advanced["catalyst_type"] != "NEUTRAL":
        event.update(advanced)
    else:
        event.update({"catalyst_type": "NEUTRAL", "classification_source": "category" if selected_category else "fallback"})

    if selected_category == "APPROVAL" and advanced["catalyst_type"] == "APPROVAL":
        event["direction"] = FDA_CATALYST_MAP["APPROVAL"]["direction"]
    if selected_category == "LABEL" and advanced["catalyst_type"] == "LABEL_EXPANSION":
        event["direction"] = FDA_CATALYST_MAP["LABEL"]["direction"]

    subtype_map = {
        "CLINICAL_RESULT": "CLINICAL_RESULTS", "LABEL_EXPANSION": "LABEL_EXPANSION",
        "REJECTION": "FDA_REJECTION", "SAFETY": "FDA_SAFETY_WARNING", "APPROVAL": "FDA_APPROVAL",
        "TRIAL_HOLD": "TRIAL_HOLD", "TRIAL_HOLD_LIFTED": "TRIAL_HOLD_LIFTED",
        "PHASE_ADVANCEMENT": "PHASE_ADVANCED", "DATE_ACCELERATED": "DATE_ACCELERATED",
        "DATE_DELAYED": "DATE_DELAYED", "FILING": "REGULATORY_FILING",
    }
    if advanced["catalyst_type"] in subtype_map:
        event["subtype"] = subtype_map[advanced["catalyst_type"]]
    if advanced["urgency"] == "EXTREME":
        event["severity"] = "HIGH"
    elif advanced["urgency"] == "HIGH" and event.get("severity") == "LOW":
        event["severity"] = "MEDIUM"
    event.update({
        "source": news_item.get("source", "FDA"), "title": news_item.get("title", ""),
        "summary": news_item.get("summary", ""), "url": news_item.get("url"),
        "published_at": news_item.get("published_at"), "categories": list(normalized_categories),
        "field": None, "old_value": None, "new_value": news_item.get("title", ""),
    })
    return event


def build_fda_catalysts(news_items):
    return [build_fda_catalyst(item) for item in (news_items or [])]


def build_relevant_fda_catalysts(news_items):
    return [build_fda_catalyst(item) for item in (news_items or []) if str(item.get("priority", "LOW")).upper() in {"EXTREME", "HIGH"}]
