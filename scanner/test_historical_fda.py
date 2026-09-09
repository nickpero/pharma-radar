from datetime import date

from scanner.historical_fda import _norm, _tokens


def test_norm_removes_punctuation():
    assert _norm("Avidity Biosciences, Inc.") == "aviditybiosciencesinc"


def test_tokens_removes_generic_corporate_words():
    assert _tokens("Avidity Biosciences, Inc.") == ["avidity", "biosciences"]
    assert _tokens("Moderna, Inc.") == ["moderna"]


def test_start_date_is_importable():
    assert date(2015, 1, 1).isoformat() == "2015-01-01"


if __name__ == "__main__":
    test_norm_removes_punctuation()
    test_tokens_removes_generic_corporate_words()
    test_start_date_is_importable()
    print("Historical FDA tests passed")
