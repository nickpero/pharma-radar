"""Pharma Radar — Clinical catalyst novelty and market-impact enrichment.

Descriptive/operational only: this layer does not produce a buy/sell signal.
"""

NOVELTY_PATTERNS = [
    (30, ("unexpected", "surprise", "first time", "new data", "new finding", "newly reported")),
    (25, ("primary endpoint", "statistically significant", "met the primary endpoint", "failed the primary endpoint")),
    (20, ("topline", "top-line", "phase 3 results", "phase 2 results")),
    (20, ("maintenance", "weight maintenance", "every two weeks", "every 2 weeks", "monthly dosing", "once monthly")),
    (15, ("dose response", "dose-response", "dose dependent", "dose-dependent")),
    (15, ("secondary endpoint", "secondary endpoints")),
    (15, ("safety signal", "safety concern", "adverse event", "tolerability")),
]

IMPACT_PATTERNS = [
    (35, ("primary endpoint", "topline results", "top-line results")),
    (30, ("met the primary endpoint", "positive topline", "positive top-line")),
    (30, ("failed the primary endpoint", "negative topline", "negative top-line", "futility")),
    (25, ("maintenance", "every two weeks", "every 2 weeks", "monthly dosing", "once monthly")),
    (25, ("statistically significant", "clinical benefit", "overall survival")),
    (20, ("safety signal", "serious safety", "safety concern")),
    (15, ("secondary endpoint", "dose response", "dose-response")),
]

CLINICAL_SUBTYPE_RULES = [
    ("SAFETY_SIGNAL", ("safety signal", "serious safety", "safety concern", "unexpected safety", "tolerability issue")),
    ("PRIMARY_ENDPOINT_FAILED", ("failed to meet the primary endpoint", "failed the primary endpoint", "missed the primary endpoint", "negative topline", "futility")),
    ("PRIMARY_ENDPOINT_MET", ("met the primary endpoint", "met its primary endpoint", "primary endpoint was met")),
    ("TOPLINE_RESULTS", ("topline results", "top-line results", "positive topline", "negative topline")),
    ("MAINTENANCE_DATA", ("maintenance", "weight maintenance", "maintain weight", "every two weeks", "every 2 weeks", "monthly dosing", "once monthly")),
    ("DOSE_RESPONSE", ("dose response", "dose-response", "dose dependent", "dose-dependent")),
    ("SECONDARY_ENDPOINT_MET", ("secondary endpoint met", "met a secondary endpoint", "secondary endpoints were met")),
    ("SECONDARY_ENDPOINT_FAILED", ("secondary endpoint failed", "failed a secondary endpoint", "secondary endpoints failed")),
    ("EFFICACY_SIGNAL", ("clinical benefit", "efficacy signal", "efficacy data", "weight loss", "overall survival")),
]

def _text(event):
    return " ".join(str(event.get(k) or "") for k in ("title", "summary", "article_text", "content", "body", "text", "new_value")).lower()

def _score(patterns, text):
    score = 0
    matched = []
    for points, phrases in patterns:
        if any(p.lower() in text for p in phrases):
            score += points
            matched.append(phrases[0])
    return min(score, 100), matched

def classify_clinical_subtype(event):
    text = _text(event)
    for subtype, phrases in CLINICAL_SUBTYPE_RULES:
        if any(p.lower() in text for p in phrases):
            return subtype
    return None

def enrich_clinical_impact(event):
    result = dict(event or {})
    text = _text(result)
    subtype = str(result.get("subtype") or "").upper()
    clinical = (
        result.get("catalyst_category") == "CLINICAL_DATA_RELEASE"
        or subtype in {"CLINICAL_RESULTS", "TOPLINE_RESULTS", "PRIMARY_ENDPOINT_MET", "PRIMARY_ENDPOINT_FAILED",
                       "SECONDARY_ENDPOINT_MET", "SECONDARY_ENDPOINT_FAILED", "MAINTENANCE_DATA", "EFFICACY_SIGNAL", "SAFETY_SIGNAL"}
        or "clinical result" in text or "topline" in text or "primary endpoint" in text
    )
    if not clinical:
        result.setdefault("novelty_score", 0)
        result.setdefault("market_impact_score", 0)
        result.setdefault("market_impact_label", "N/A")
        return result
    specific = classify_clinical_subtype(result)
    if specific:
        result["subtype"] = specific
    novelty, novelty_matches = _score(NOVELTY_PATTERNS, text)
    impact, impact_matches = _score(IMPACT_PATTERNS, text)
    if result.get("subtype") in {"PRIMARY_ENDPOINT_MET", "PRIMARY_ENDPOINT_FAILED", "TOPLINE_RESULTS"}:
        impact = max(impact, 80)
    if result.get("subtype") == "MAINTENANCE_DATA":
        impact = max(impact, 75)
    result["catalyst_category"] = "CLINICAL_DATA_RELEASE"
    result["clinical_data_release"] = True
    result["novelty_score"] = novelty
    result["novelty_matches"] = novelty_matches
    result["market_impact_score"] = impact
    result["market_impact_matches"] = impact_matches
    result["market_impact_label"] = "CRITICAL" if impact >= 80 else "HIGH" if impact >= 60 else "MEDIUM" if impact >= 35 else "LOW"
    return result
