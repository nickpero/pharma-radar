from unittest.mock import Mock, patch

import requests

from scanner.italian_translation import alert_protected_terms, translate_to_italian
from scanner.telegram import _it_status


def test_source_text_is_translated_and_named_entity_is_preserved():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [[[ "Approvazione di ZYME per zanidatamab", "FDA approval of ZYME for zanidatamab", None, None ]], None, "en"]
    with patch("scanner.italian_translation.requests.get", return_value=response) as get:
        result = translate_to_italian("FDA approval of ZYME for zanidatamab", ["ZYME", "zanidatamab"])
    assert result == "Approvazione di ZYME per zanidatamab"
    assert get.called


def test_translation_failure_never_returns_untranslated_english():
    with patch("scanner.italian_translation.requests.get", side_effect=requests.Timeout):
        assert translate_to_italian("A newly announced clinical trial") == (
            "Traduzione non disponibile; consultare la fonte originale."
        )


def test_alert_protected_terms_include_company_ticker_and_program():
    alert = {"ticker": "ZYME", "company": "Zymeworks", "program": "zanidatamab"}
    assert alert_protected_terms(alert) == ["Zymeworks", "ZYME", "zanidatamab"]


def test_next_24_hours_window_is_italian():
    assert _it_status("NEXT_24H") == "PROSSIME 24 ORE"
