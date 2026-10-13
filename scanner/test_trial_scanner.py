from datetime import datetime, timedelta, timezone

from scanner.trial_scanner import (
    make_trial_key, build_alert, _parse_fda_event_timestamp,
    _is_recent_fda_event, _has_parseable_fda_timestamp,
)


def test_make_trial_key():
    trial = {"nct_id": "NCT04428476"}
    key = make_trial_key("CAPR", "deramiocel", trial)
    assert key == "CAPR:deramiocel:NCT04428476"


def test_make_trial_key_unique():
    trial_1 = {"nct_id": "NCT11111111"}
    trial_2 = {"nct_id": "NCT22222222"}
    key_1 = make_trial_key("CAPR", "deramiocel", trial_1)
    key_2 = make_trial_key("CAPR", "deramiocel", trial_2)
    assert key_1 != key_2


def test_make_trial_key_program_difference():
    trial = {"nct_id": "NCT12345678"}
    key_1 = make_trial_key("CAPR", "deramiocel", trial)
    key_2 = make_trial_key("CAPR", "other_program", trial)
    assert key_1 != key_2


def test_build_alert_carries_catalyst_confirmation():
    event = {
        "score": 100,
        "label": "CRITICAL",
        "severity": "HIGH",
        "direction": "CATALYST",
        "subtype": "FDA_APPROVAL",
        "catalyst_confirmation_score": 82,
        "catalyst_confirmation": "CONFIRMED",
    }
    alert = build_alert(
        "IONS",
        {"company": "Ionis Pharmaceuticals"},
        "zilganersen",
        None,
        event,
        {},
        {},
    )
    assert alert["catalyst_confirmation_score"] == 82
    assert alert["catalyst_confirmation"] == "CONFIRMED"






def test_fda_timestamp_skips_invalid_primary_and_uses_valid_fallback():
    fallback = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    event = {
        "published_at": "date unavailable",
        "first_published_at": fallback,
        "event_date": "also invalid",
    }
    parsed, field, raw = _parse_fda_event_timestamp(event)
    assert parsed is not None
    assert field == "first_published_at"
    assert raw == fallback
    assert _has_parseable_fda_timestamp(event)
    assert _is_recent_fda_event(event)


def test_fda_timestamp_does_not_invent_date_when_all_candidates_invalid():
    event = {
        "published_at": "unknown",
        "first_published_at": None,
        "event_date": "not-a-date",
    }
    assert _parse_fda_event_timestamp(event) == (None, None, None)
    assert not _has_parseable_fda_timestamp(event)
    assert not _is_recent_fda_event(event)


if __name__ == "__main__":
    test_make_trial_key()
    test_make_trial_key_unique()
    test_make_trial_key_program_difference()
    test_build_alert_carries_catalyst_confirmation()
    test_fda_timestamp_skips_invalid_primary_and_uses_valid_fallback()
    test_fda_timestamp_does_not_invent_date_when_all_candidates_invalid()
    print("✅ Trial Scanner tests passed")
