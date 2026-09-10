from datetime import date

from scanner.historical_fda_crl import _date, _tokens


def test_date_parses_fda_format():
    assert _date("10/05/2018") == date(2018, 10, 5)


def test_tokens_remove_generic_words():
    assert _tokens("Acme Therapeutics, Inc.") == ["acme"]


if __name__ == "__main__":
    test_date_parses_fda_format()
    test_tokens_remove_generic_words()
    print("Historical FDA CRL tests passed")
