from scanner.fda_catalyst import build_fda_catalyst, classify_fda_catalyst


def classify(title, summary=""):
    return classify_fda_catalyst({"title": title, "summary": summary})


def test_approval_is_extreme_positive():
    result = classify("FDA approves new therapy")
    assert result["catalyst_type"] == "APPROVAL"
    assert result["direction"] == "POSITIVE"
    assert result["urgency"] == "EXTREME"


def test_rejection_is_extreme_negative():
    result = classify("FDA issues Complete Response Letter")
    assert result["catalyst_type"] == "REJECTION"
    assert result["direction"] == "NEGATIVE"
    assert result["urgency"] == "EXTREME"


def test_safety_is_extreme_negative():
    result = classify("FDA announces boxed warning")
    assert result["catalyst_type"] == "SAFETY"
    assert result["direction"] == "NEGATIVE"
    assert result["urgency"] == "EXTREME"


def test_label_expansion_is_high_positive():
    result = classify("FDA expands indication")
    assert result["catalyst_type"] == "LABEL_EXPANSION"
    assert result["direction"] == "POSITIVE"
    assert result["urgency"] == "HIGH"


def test_clinical_results_can_be_negative_or_positive():
    negative = classify("Phase 3 clinical trial results failed to meet the primary endpoint")
    positive = classify("Phase 3 clinical trial results met the primary endpoint")
    assert negative["catalyst_type"] == "CLINICAL_RESULT"
    assert negative["direction"] == "NEGATIVE"
    assert positive["catalyst_type"] == "CLINICAL_RESULT"
    assert positive["direction"] == "POSITIVE"


def test_hold_and_hold_lift_are_opposite():
    hold = classify("FDA places trial on clinical hold")
    lift = classify("FDA announces clinical hold lifted")
    assert hold["catalyst_type"] == "TRIAL_HOLD"
    assert hold["direction"] == "NEGATIVE"
    assert lift["catalyst_type"] == "TRIAL_HOLD_LIFTED"
    assert lift["direction"] == "POSITIVE"


def test_date_events_are_directional():
    accelerated = classify("FDA accelerated timeline")
    delayed = classify("FDA delayed submission")
    assert accelerated["catalyst_type"] == "DATE_ACCELERATED"
    assert accelerated["direction"] == "POSITIVE"
    assert delayed["catalyst_type"] == "DATE_DELAYED"
    assert delayed["direction"] == "NEGATIVE"


def test_phase_and_filing():
    phase = classify("Company advances to Phase 3")
    filing = classify("Company submits a new drug application")
    assert phase["catalyst_type"] == "PHASE_ADVANCEMENT"
    assert filing["catalyst_type"] == "FILING"


def test_negation_protection():
    result = classify("FDA does not approve the candidate")
    assert result["catalyst_type"] == "REJECTION"
    assert result["direction"] == "NEGATIVE"


def test_neutral_fallback():
    result = classify("FDA publishes general administrative update")
    assert result["catalyst_type"] == "NEUTRAL"
    assert result["direction"] == "UNKNOWN"
    assert result["urgency"] == "LOW"


def test_build_preserves_legacy_approval_subtype():
    event = build_fda_catalyst({
        "title": "FDA approves candidate",
        "summary": "Approval announcement",
        "categories": ["APPROVAL"],
    })
    assert event["subtype"] == "FDA_APPROVAL"
    assert event["catalyst_type"] == "APPROVAL"
    assert event["direction"] == "CATALYST"
    assert event["urgency"] == "EXTREME"


def test_sec_clinical_result_beats_regulatory_boilerplate():
    event = build_fda_catalyst({
        "source": "SEC",
        "source_type": "PRIMARY_CORPORATE",
        "title": "SEC 8-K — Summit Therapeutics (SMMT)",
        "summary": "Positive overall survival results from Phase 3 HARMONi-2; ivonescimab remains investigational and is not approved in the United States.",
        "content": "The Phase 3 study met its primary endpoint with positive overall survival results. Ivonescimab is investigational and is not approved by any regulatory authority in the United States.",
        "categories": ["APPROVAL"],
    })
    assert event["catalyst_type"] == "CLINICAL_RESULT"
    assert event["subtype"] == "CLINICAL_RESULTS"
    assert event["direction"] == "POSITIVE"


if __name__ == "__main__":
    test_approval_is_extreme_positive()
    test_rejection_is_extreme_negative()
    test_safety_is_extreme_negative()
    test_label_expansion_is_high_positive()
    test_clinical_results_can_be_negative_or_positive()
    test_hold_and_hold_lift_are_opposite()
    test_date_events_are_directional()
    test_phase_and_filing()
    test_negation_protection()
    test_neutral_fallback()
    test_build_preserves_legacy_approval_subtype()
    test_sec_clinical_result_beats_regulatory_boilerplate()
    print("P1.3 FDA CATALYST TESTS PASSED")
