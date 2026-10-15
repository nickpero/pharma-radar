from datetime import date
import json

from scanner.catalyst_calendar_delivery import due_calendar_alerts, format_due_alert, run_delivery


def row(**overrides):
    item = {
        "ticker": "ABC",
        "company": "ABC Bio",
        "program": "Drug A",
        "phase": "PHASE3",
        "event_type": "CLINICAL_READOUT",
        "milestone": "Interim efficacy data",
        "date": "2026-10-22",
        "date_precision": "DAY",
        "source_url": "https://example.com/primary",
        "why_it_matters": "Could change the program's probability of success.",
    }
    item.update(overrides)
    return item


def test_due_alert_is_classified_and_deduplicated():
    item = row()
    due = due_calendar_alerts([item], today=date(2026, 10, 15))
    assert len(due) == 1
    assert due[0]["trigger"] == "D7"
    assert "1 — VERO CLINICAL READOUT" in format_due_alert(due[0])
    assert "Fonte primaria: https://example.com/primary" in format_due_alert(due[0])
    assert due_calendar_alerts([item], today=date(2026, 10, 15),
                               sent_state={due[0]["delivery_key"]: "sent"}) == []


def test_milestone_and_review_never_claim_efficacy():
    milestone = row(event_type="TRIAL_MILESTONE", source_url="https://clinicaltrials.gov/study/NCT123",
                    milestone="PRIMARY_COMPLETION")
    review = row(event_type="CLINICAL_REVIEW", milestone="Blinded DSMB review")
    assert "2 — MILESTONE PREVISTA, NON UN RISULTATO" in format_due_alert(milestone)
    assert "3 — REVIEW / SICUREZZA / CIECO" in format_due_alert(review)
    assert "non attribuire esito positivo o negativo" in format_due_alert(review)


def test_month_only_event_not_given_fake_day_countdown():
    item = row(date="2026-10-01", date_precision="MONTH")
    assert due_calendar_alerts([item], today=date(2026, 10, 15))[0]["trigger"] == "MONTH"
    assert due_calendar_alerts([item], today=date(2026, 9, 15)) == []


def test_delivery_persists_only_after_success(tmp_path):
    state_path = tmp_path / "state.json"
    calls = []
    result = run_delivery(
        today=date(2026, 10, 15),
        rows=[row()],
        state_path=state_path,
        send_fn=lambda message: calls.append(message) or {"ok": True},
    )
    assert result == {"due": 1, "sent": 1}
    state = json.loads(state_path.read_text())
    assert len(state) == 1
    assert len(calls) == 1
    again = run_delivery(
        today=date(2026, 10, 15),
        rows=[row()],
        state_path=state_path,
        send_fn=lambda message: calls.append(message) or {"ok": True},
    )
    assert again == {"due": 0, "sent": 0}
    assert len(calls) == 1


def test_failed_delivery_does_not_mark_as_sent(tmp_path):
    state_path = tmp_path / "state.json"
    def fail(_):
        raise RuntimeError("telegram unavailable")
    try:
        run_delivery(today=date(2026, 10, 15), rows=[row()], state_path=state_path, send_fn=fail)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected Telegram failure")
    assert not state_path.exists()



def test_partial_delivery_persists_first_alert_before_second_fails(tmp_path):
    state_path = tmp_path / "state.json"
    first = row(date="2026-10-22", milestone="Readout A")
    second = row(date="2026-10-22", milestone="Readout B")
    calls = {"count": 0}

    def fail_second(_):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("telegram unavailable")
        return {"ok": True}

    try:
        run_delivery(today=date(2026, 10, 15), rows=[first, second],
                     state_path=state_path, send_fn=fail_second)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected Telegram failure")
    state = json.loads(state_path.read_text())
    assert len(state) == 1
    retry_due = due_calendar_alerts([first, second], today=date(2026, 10, 15), sent_state=state)
    assert len(retry_due) == 1
    assert retry_due[0]["milestone"] == "Readout B"
