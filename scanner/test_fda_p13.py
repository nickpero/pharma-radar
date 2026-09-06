"""P1.3 regression tests for advanced FDA catalyst classification."""

from scanner.fda_catalyst import build_fda_catalyst, classify_fda_catalyst


def classify(title, content=""):
    return classify_fda_catalyst({"title": title, "content": content})


def test_approval_is_extreme_positive():
    result = classify("FDA approves zidesamtinib for ROS1-positive NSCLC")
    assert result["catalyst_type"] == "APPROVAL"
    assert result["direction"] == "POSITIVE"
    assert result["urgency"] == "EXTREME"


def test_rejection_is_extreme_negative():
    result = classify("FDA issues Complete Response Letter for candidate")
    assert result["catalyst_type"] == "REJECTION"
    assert result["direction"] == "NEGATIVE"
    assert result["urgency"] == "EXTREME"


def test_safety_is_extreme_negative():
    result = classify("FDA announces boxed warning for drug")
    assert result["catalyst_type"] == "SAFETY"
    assert result["direction"] == "NEGATIVE"
    assert result["urgency"] == "EXTREME"


def test_label_expansion_is_high_positive():
    result = classify("FDA grants expanded indication")
    assert result["catalyst_type"] == "LABEL_EXPANSION"
    assert result["direction"] == "POSITIVE"
    assert result["urgency"] == "HIGH"


def test_clinical_results_can_be_negative_or_positive():
    negative = classify("Clinical study failed to meet the primary endpoint")
    positive = classify("Clinical study met the primary endpoint")
    assert negative["catalyst_type"] == "CLINICAL_RESULT"
    assert negative["direction"] == "NEGATIVE"
    assert positive["catalyst_type"] == "CLINICAL_RESULT"
    assert positive["direction"] == "POSITIVE"


def test_hold_and_hold_lift_are_opposite():
    hold = classify("FDA places the program on clinical hold")
    lifted = classify("FDA announces clinical hold lifted")
    assert hold["catalyst_type"] == "TRIAL_HOLD"
    assert hold["direction"] == "NEGATIVE"
    assert lifted["catalyst_type"] == "TRIAL_HOLD_LIFTED"
    assert lifted["direction"] == "POSITIVE"


def test_date_events_are_directional():
    accelerated = classify("FDA update: accelerated timeline")
    delayed = classify("FDA update: delayed timeline")
    assert accelerated["catalyst_type"] == "DATE_ACCELERATED"
    assert accelerated["direction"] == "POSITIVE"
    assert delayed["catalyst_type"] == "DATE_DELAYED"
    assert delayed["direction"] == "NEGATIVE"


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
    assert event["direction"] == "POSITIVE"
    assert event["urgency"] == "EXTREME"


if __name__ == "__main__":
    test_approval_is_extreme_positive()
    test_rejection_is_extreme_negative()
    test_safety_is_extreme_negative()
    test_label_expansion_is_high_positive()
    test_clinical_results_can_be_negative_or_positive()
    test_hold_and_hold_lift_are_opposite()
    test_date_events_are_directional()
    test_neutral_fallback()
    test_build_preserves_legacy_approval_subtype()
    print("P1.3 FDA CATALYST TESTS PASSED")
