"""Unit tests for historical catalyst discovery helpers."""
from scanner.historical_discovery import _classify, _program_from_text


def test_positive_clinical_result():
    result = _classify("The Phase 3 trial met the primary endpoint with statistically significant results")
    assert result == ("CLINICAL_RESULTS", "POSITIVE")


def test_negative_clinical_result():
    result = _classify("The Phase 3 trial failed to meet the primary endpoint")
    assert result == ("CLINICAL_RESULTS", "NEGATIVE")


def test_fda_approval():
    result = _classify("FDA approves the company's new therapy")
    assert result == ("FDA_APPROVAL", "POSITIVE")


def test_program_resolution():
    assert _program_from_text("positive results for zorevunersen", ["zorevunersen", "other"]) == "zorevunersen"


if __name__ == "__main__":
    test_positive_clinical_result()
    test_negative_clinical_result()
    test_fda_approval()
    test_program_resolution()
    print("Historical discovery tests passed")
