from scanner.telegram_delivery_audit import append_delivery_audit


def test_delivery_audit_records_publication_seen_qualification_and_telegram_confirmation(tmp_path):
    path = tmp_path / "telegram_delivery_audit.json"
    alert = {
        "ticker": "ACME",
        "program": "drug-x",
        "published_at": "2026-10-31T08:00:00+00:00",
        "first_seen_at": "2026-10-31T08:02:00+00:00",
        "qualified_at": "2026-10-31T08:03:00+00:00",
        "event": {"subtype": "FDA_APPROVAL"},
    }

    append_delivery_audit(
        [alert], lambda item: "event-key", "ATTEMPTED",
        attempted_at="2026-10-31T08:04:00+00:00", path=path,
    )
    append_delivery_audit(
        [alert], lambda item: "event-key", "CONFIRMED",
        attempted_at="2026-10-31T08:04:00+00:00",
        confirmed_at="2026-10-31T08:04:01+00:00",
        message_id=987, path=path,
    )

    import json
    records = json.loads(path.read_text(encoding="utf-8"))
    assert len(records) == 2
    confirmed = records[-1]
    assert confirmed["dedup_key"] == "event-key"
    assert confirmed["ticker"] == "ACME"
    assert confirmed["event_type"] == "FDA_APPROVAL"
    assert confirmed["first_published_at"] == alert["published_at"]
    assert confirmed["first_seen_at"] == alert["first_seen_at"]
    assert confirmed["qualified_at"] == alert["qualified_at"]
    assert confirmed["telegram_attempted_at"] == "2026-10-31T08:04:00+00:00"
    assert confirmed["telegram_confirmed_at"] == "2026-10-31T08:04:01+00:00"
    assert confirmed["telegram_message_id"] == 987
    assert confirmed["delivery_status"] == "CONFIRMED"


def test_delivery_audit_preserves_failed_attempts(tmp_path):
    path = tmp_path / "telegram_delivery_audit.json"
    append_delivery_audit(
        [{"ticker": "ACME", "program": "drug-x"}],
        lambda item: "event-key",
        "FAILED",
        attempted_at="2026-10-31T08:04:00+00:00",
        error="Telegram timeout",
        path=path,
    )

    import json
    record = json.loads(path.read_text(encoding="utf-8"))[0]
    assert record["delivery_status"] == "FAILED"
    assert record["telegram_confirmed_at"] is None
    assert record["telegram_message_id"] is None
    assert record["error"] == "Telegram timeout"
