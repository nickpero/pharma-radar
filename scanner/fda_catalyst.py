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

PHASE_ADVANCEMENT_PATTERNS = ("phase advancement","advanced to phase","advances to phase","progressed to phase","progresses to phase","moved to phase","moves to phase","moved into phase","moves into phase","transitioned to phase","initiated phase 1","initiated phase 2","initiated phase 3","started phase 1","started phase 2","started phase 3","began phase 1","began phase 2","began phase 3","begins phase 1","begins phase 2","begins phase 3","entered phase 1","entered phase 2","entered phase 3")
EXPLORATORY_PATTERNS = ("exploratory analysis","exploratory analyses","exploratory data","exploratory endpoint","exploratory endpoints","post-hoc analysis","post hoc analysis","post-hoc analyses","post hoc analyses","subgroup analysis","subgroup analyses","subgroup data")
CORPORATE_TRANSACTION_PATTERNS = ("agreement and plan of merger", "merger agreement", "definitive agreement to acquire", "agrees to acquire", "agreed to acquire", "acquisition of", "acquire all of the outstanding shares", "tender offer", "merger with", "acquired by", "to be acquired")
IP_CATALYST_PATTERNS = ("notice of allowance", "patent allowance", "patent granted", "patent issued", "patent approval", "intellectual property protection", "patent ruling")
DEVELOPMENT_MILESTONE_PATTERNS = ("successfully formulate", "successful completion of formulation", "completed formulation work", "formulation milestone", "development milestone", "program milestone", "advances the program", "advances development", "program advances", "initiates study", "initiates a study", "begins study", "starts study", "study initiation", "enrollment begins", "begins enrollment", "first patient dosed", "first patient enrolled", "dosing begins", "dosing initiated")
PHASE_DATA_UPDATE_PATTERNS = ("phase 1 results","phase 2 results","phase 3 results","phase 1 data","phase 2 data","phase 3 data","phase i results","phase ii results","phase iii results","phase i data","phase ii data","phase iii data","phase 1 clinical trial","phase 2 clinical trial","phase 3 clinical trial","phase 1 study","phase 2 study","phase 3 study","phase i study","phase ii study","phase iii study","open-label extension","open label extension")
CLINICAL_REVIEW_PATTERNS = (
    "dsmb review", "dsmb safety review", "data safety monitoring board",
    "safety review completed", "safety review found no concerns",
    "remains blinded", "study remains blinded", "trial remains blinded",
    "blinded interim review", "blinded review", "without unblinding",
    "enrollment completed", "closed enrollment",
)

ADVANCED_RULES = [
    ("CORPORATE_TRANSACTION", "POSITIVE", "EXTREME", CORPORATE_TRANSACTION_PATTERNS),
    ("IP_CATALYST", "POSITIVE", "HIGH", IP_CATALYST_PATTERNS),
    ("DEVELOPMENT_MILESTONE", "POSITIVE", "HIGH", DEVELOPMENT_MILESTONE_PATTERNS),
    ("TRIAL_HOLD_LIFTED", "POSITIVE", "HIGH", ("clinical hold lifted", "hold lifted", "lifted the clinical hold", "hold is lifted")),
    ("TRIAL_HOLD", "NEGATIVE", "EXTREME", ("clinical hold", "placed on clinical hold", "trial hold", "study hold")),
    ("REJECTION", "NEGATIVE", "EXTREME", ("complete response letter", r"\bcrl\b", "not approved", "does not approve", "did not approve", "will not approve", "won't approve", "rejected", "rejection", "refused", "refusal", "denied", "denial")),
    ("SAFETY", "NEGATIVE", "EXTREME", ("boxed warning", "safety warning", "drug safety communication", "recall", "serious safety", "safety concern", "contamination")),
    ("REGULATORY_APPROVAL", "POSITIVE", "EXTREME", ("health canada approved", "health canada approval", "health canada has approved", "approved by health canada", "ema approved", "ema approval", "ema has approved", "approved by ema", "european commission approved", "european commission approval", "european commission has approved", "approved by the european commission", "mhra approved", "mhra approval", "mhra has approved", "approved by the mhra", "tga approved", "tga approval", "tga has approved", "approved by the tga")),
    ("APPROVAL", "POSITIVE", "EXTREME", ("__EXPLICIT_FDA_APPROVAL__")),
    ("LABEL_EXPANSION", "POSITIVE", "HIGH", ("label expansion", "expanded indication", "expands indication", "expanded use", "expands use", "expanded the indication", "expands the indication", "new indication")),
    ("FILING", "POSITIVE", "HIGH", ("new drug application", "biologics license application", "nda submission", "bla submission", "regulatory submission", "submitted the application", "filing accepted")),
    ("CLINICAL_RESULT", "NEGATIVE", "HIGH", ("failed to meet", "did not meet", "missed the primary endpoint", "failed the primary endpoint", "futility", "negative topline", "not statistically significant", "no significant benefit")),
    ("CLINICAL_RESULT", "POSITIVE", "HIGH", ("met the primary endpoint", "met its primary endpoint", "positive topline", "positive results", "statistically significant", "clinical benefit")),
    ("EXPLORATORY_DATA", "POSITIVE", "MEDIUM", EXPLORATORY_PATTERNS),
    ("PHASE_DATA_UPDATE", "POSITIVE", "HIGH", PHASE_DATA_UPDATE_PATTERNS),
    ("CLINICAL_RESULT", "POSITIVE", "HIGH", ("clinical trial results", "clinical study results", "clinical results", "topline results", "trial results")),
    ("CLINICAL_REVIEW_UPDATE", "UNKNOWN", "MEDIUM", CLINICAL_REVIEW_PATTERNS),
    ("PHASE_ADVANCEMENT", "POSITIVE", "HIGH", PHASE_ADVANCEMENT_PATTERNS),
    ("DATE_ACCELERATED", "POSITIVE", "HIGH", ("accelerated timeline", "date accelerated", "accelerated the timeline", "earlier than expected")),
    ("DATE_DELAYED", "NEGATIVE", "HIGH", ("delayed timeline", "date delayed", "delay in the timeline", "later than expected", "delayed submission")),
]

EXPLORATORY_RULES = [rule for rule in ADVANCED_RULES if rule[0] == "EXPLORATORY_DATA"]
PHASE_DATA_RULES = [rule for rule in ADVANCED_RULES if rule[0] == "PHASE_DATA_UPDATE"]
CLINICAL_RULES = [rule for rule in ADVANCED_RULES if rule[0] == "CLINICAL_RESULT"]

APPROVAL_POSITIVE_PATTERNS = (
    r"\bfda\s+(?:has\s+)?approved\b",
    r"\bfda\s+approves\b",
    r"\breceives?\s+(?:full\s+|accelerated\s+)?fda\s+approval\b",
    r"\bfda\s+grants?\s+(?:full\s+|accelerated\s+)?approval\b",
    r"\bfda\s+authorizes\b",
)

APPROVAL_NEGATION_PATTERNS = (
    r"\bnot\s+(?:yet\s+)?approved\b",
    r"\bnot\s+approved\s+in\s+the\s+(?:united\s+states|us)\b",
    r"\bremains?\s+investigational\b",
    r"\bpotential\s+(?:regulatory\s+)?pathway\b",
    r"\bprepar(?:ing|es)\s+to\s+meet\s+(?:with\s+)?the?\s*fda\b",
    r"\bplans?\s+to\s+meet\s+(?:with\s+)?the?\s*fda\b",
    r"\bseek(?:s|ing)?\s+(?:fda\s+)?approval\b",
    r"\bapplication\s+(?:for|seeking)\s+approval\b",
    r"\bcould\s+support\s+(?:a\s+)?new\s+drug\s+application\b",
)

REGULATORY_RULES = [
    ("FDA_MEETING", "NEUTRAL", "HIGH", (
        "meet with the fda", "meeting with the fda", "fda meeting",
        "discuss with the fda", "discussion with the fda",
    )),
    ("FDA_PATHWAY", "NEUTRAL", "HIGH", (
        "regulatory pathway", "registrational pathway", "pathway with the fda",
        "potential pathway", "regulatory path forward",
    )),
]



def _text(news_item):
    return "\n".join(str(news_item.get(k) or "") for k in ("title", "summary", "article_text", "content", "body", "text")).lower()


def _matches(text, pattern):
    if pattern == "__EXPLICIT_FDA_APPROVAL__":
        return bool(
            any(re.search(rule, text, re.IGNORECASE) for rule in APPROVAL_POSITIVE_PATTERNS)
            and not any(re.search(rule, text, re.IGNORECASE) for rule in APPROVAL_NEGATION_PATTERNS)
        )
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

    approval_blocked = any(
        re.search(rule, text, re.IGNORECASE)
        for rule in APPROVAL_NEGATION_PATTERNS
    )

    # Explicit FDA approval is the highest-specificity positive regulatory
    # signal. Resolve it before generic phase/clinical rules. Keep this check
    # deliberately direct so the core approval contract cannot regress when
    # ADVANCED_RULES is reordered.
    if not approval_blocked:
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in APPROVAL_POSITIVE_PATTERNS):
            return {
                "catalyst_type": "APPROVAL",
                "direction": "POSITIVE",
                "urgency": "EXTREME",
                "classification_source": "explicit_fda_approval",
            }

    # Separate a blinded/DSMB/interim safety review from an actual clinical
    # readout. A review can be market-relevant, but it does not disclose
    # efficacy/top-line outcomes and must not be scored as clinical results.
    review_hit = any(_matches(text, p) for p in CLINICAL_REVIEW_PATTERNS)
    efficacy_disclosure = any(
        _matches(text, p) for p in (
            "interim efficacy results", "interim efficacy data",
            "interim clinical results", "interim topline", "interim top-line",
            "unblinded results", "unblinded data", "primary endpoint",
            "met the primary endpoint", "failed to meet the primary endpoint",
        )
    )
    if review_hit and not efficacy_disclosure:
        return {
            "catalyst_type": "CLINICAL_REVIEW_UPDATE",
            "direction": "UNKNOWN",
            "urgency": "MEDIUM",
            "classification_source": "clinical_review",
        }

    # Classify the most specific clinical event first. Phase numbers alone
    # never imply a phase advancement. For primary corporate/SEC material,
    # explicit clinical results outrank generic phase-data wording.
    for source_text, source_name in ((title, "title"), (text, "content")):
        result = _classify(source_text, source_name, EXPLORATORY_RULES)
        if result:
            return result
    if source_type == "PRIMARY_CORPORATE":
        for source_text, source_name in ((title, "title"), (text, "content")):
            result = _classify(source_text, source_name, CLINICAL_RULES)
            if result:
                return result
    # Explicit regulatory pathway/meeting is not an approval and, when
    # present, outranks generic phase-data wording.
    for source_text, source_name in ((title, "title"), (text, "content")):
        result = _classify(source_text, source_name, REGULATORY_RULES)
        if result:
            return result

    for source_text, source_name in ((title, "title"), (text, "content")):
        result = _classify(source_text, source_name, PHASE_DATA_RULES)
        if result:
            if any(phrase in source_text for phrase in (
                "failed to meet", "did not meet", "missed the primary endpoint",
                "failed the primary endpoint", "negative topline", "futility",
                "not statistically significant", "no significant benefit",
            )):
                result["direction"] = "NEGATIVE"
            return result

    # Explicit regulatory pathway/meeting is not an approval.
    for source_text, source_name in ((title, "title"), (text, "content")):
        result = _classify(source_text, source_name, REGULATORY_RULES)
        if result:
            return result

    # Remaining non-approval catalysts.
    remaining_rules = [
        rule for rule in ADVANCED_RULES
        if rule[0] != "APPROVAL"
    ]
    for source_text, source_name in ((title, "title"), (text, "content")):
        result = _classify(source_text, source_name, remaining_rules)
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

    # Never trust a broad category keyword for FDA approval. The advanced
    # classifier is the source of truth for this subtype.
    if selected_category == "APPROVAL" and advanced["catalyst_type"] == "NEUTRAL":
        # Preserve the legacy APPROVAL category only when the source contains
        # explicit FDA approval evidence.
        explicit_approval = bool(
            any(re.search(rule, text, re.IGNORECASE) for rule in APPROVAL_POSITIVE_PATTERNS)
            and not any(re.search(rule, text, re.IGNORECASE) for rule in APPROVAL_NEGATION_PATTERNS)
        )
        if explicit_approval:
            event["catalyst_type"] = "APPROVAL"
            event["subtype"] = "FDA_APPROVAL"
            event["severity"] = "HIGH"
            event["direction"] = "CATALYST"
            event["urgency"] = "EXTREME"
        else:
            event["subtype"] = "FDA_UPDATE"
            event["severity"] = "LOW"
            event["direction"] = "UNKNOWN"

    if selected_category == "APPROVAL" and advanced["catalyst_type"] == "APPROVAL":
        event["direction"] = FDA_CATALYST_MAP["APPROVAL"]["direction"]
    if selected_category == "LABEL" and advanced["catalyst_type"] == "LABEL_EXPANSION":
        event["direction"] = FDA_CATALYST_MAP["LABEL"]["direction"]

    subtype_map = {
        "CLINICAL_RESULT": "CLINICAL_RESULTS", "PHASE_DATA_UPDATE": "PHASE_DATA_UPDATE", "EXPLORATORY_DATA": "EXPLORATORY_DATA", "LABEL_EXPANSION": "LABEL_EXPANSION",
        "REJECTION": "FDA_REJECTION", "SAFETY": "FDA_SAFETY_WARNING", "APPROVAL": "FDA_APPROVAL",
        "REGULATORY_APPROVAL": "REGULATORY_APPROVAL", "CORPORATE_TRANSACTION": "CORPORATE_TRANSACTION", "IP_CATALYST": "IP_CATALYST",
        "TRIAL_HOLD": "TRIAL_HOLD", "TRIAL_HOLD_LIFTED": "TRIAL_HOLD_LIFTED",
        "PHASE_ADVANCEMENT": "PHASE_ADVANCED", "DEVELOPMENT_MILESTONE": "DEVELOPMENT_MILESTONE", "DATE_ACCELERATED": "DATE_ACCELERATED",
        "DATE_DELAYED": "DATE_DELAYED", "FILING": "REGULATORY_FILING", "FDA_MEETING": "FDA_MEETING", "FDA_PATHWAY": "FDA_PATHWAY",
    }
    if advanced["catalyst_type"] in subtype_map:
        event["subtype"] = subtype_map[advanced["catalyst_type"]]
    if selected_category == "CLINICAL" and advanced["catalyst_type"] == "PHASE_DATA_UPDATE":
        event["catalyst_type"] = "CLINICAL_RESULT"
        event["subtype"] = "CLINICAL_RESULTS"
        event["direction"] = FDA_CATALYST_MAP["CLINICAL"]["direction"]
    if advanced["urgency"] == "EXTREME":
        event["severity"] = "HIGH"
    elif advanced["urgency"] == "HIGH" and event.get("severity") == "LOW":
        event["severity"] = "MEDIUM"
    # Normalize positive clinical-result direction defensively. This protects
    # the legacy FDA CLINICAL category from unrelated category boilerplate.
    if advanced["catalyst_type"] == "CLINICAL_RESULT":
        clinical_text = _text(news_item)
        if any(p in clinical_text for p in (
            "met the primary endpoint", "met its primary endpoint",
            "positive topline", "positive results", "statistically significant",
            "clinical benefit",
        )):
            advanced["direction"] = "POSITIVE"
        elif any(p in clinical_text for p in (
            "failed to meet", "did not meet", "missed the primary endpoint",
            "failed the primary endpoint", "futility", "negative topline",
            "not statistically significant", "no significant benefit",
        )):
            advanced["direction"] = "NEGATIVE"

    # Defense-in-depth: an SEC 8-K must contain explicit FDA approval evidence.
    # Generic references to approved products, future authorization, or pathways
    # must never produce FDA_APPROVAL.
    source = str(news_item.get("source") or "").upper()
    form = str(news_item.get("form") or "").upper()
    if source == "SEC" and form in {"8-K", "8-K/A"} and event.get("subtype") == "FDA_APPROVAL":
        text = _text(news_item)
        explicit = bool(
            any(re.search(rule, text, re.IGNORECASE) for rule in APPROVAL_POSITIVE_PATTERNS)
            and not any(re.search(rule, text, re.IGNORECASE) for rule in APPROVAL_NEGATION_PATTERNS)
        )
        if not explicit:
            event["subtype"] = "FDA_UPDATE"
            event["catalyst_type"] = "NEUTRAL"
            event["severity"] = "LOW"
            event["direction"] = "UNKNOWN"
            event["urgency"] = "LOW"
            event["classification_source"] = "sec_8k_approval_guard"

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
