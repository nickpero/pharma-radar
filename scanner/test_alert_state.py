"""Regression tests for persistent Telegram delivery state."""

import json

import pytest

import scanner.alert_state as alert_state


def test_missing_state_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(alert_state, "STATE_FILE", tmp_path / "state.json")
    assert alert_state.load_sent_alerts() == {}


def test_state_round_trip_is_persistent_and_valid_json(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(alert_state, "STATE_FILE", path)
    expected = {"('FDA', 'NUVL', 'zidesamtinib')": "2026-10-25T12:00:00+00:00"}

    alert_state.save_sent_alerts(expected)

    assert alert_state.load_sent_alerts() == expected
    assert json.loads(path.read_text(encoding="utf-8")) == expected
    assert not list(tmp_path.glob(".state.json.*.tmp"))


@pytest.mark.parametrize("raw", ["{broken", "[]", '"not-a-dict"', "null"])
def test_corrupt_or_wrong_shape_state_fails_closed(tmp_path, monkeypatch, raw):
    path = tmp_path / "state.json"
    path.write_text(raw, encoding="utf-8")
    monkeypatch.setattr(alert_state, "STATE_FILE", path)

    with pytest.raises(RuntimeError, match="refusing to reset delivery history"):
        alert_state.load_sent_alerts()


def test_atomic_write_failure_preserves_previous_state(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text('{"old": "timestamp"}\n', encoding="utf-8")
    monkeypatch.setattr(alert_state, "STATE_FILE", path)

    def fail_replace(_src, _dst):
        raise OSError("simulated crash before replace")

    monkeypatch.setattr(alert_state.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated crash"):
        alert_state.save_sent_alerts({"new": "timestamp"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"old": "timestamp"}
    assert not list(tmp_path.glob(".state.json.*.tmp"))
