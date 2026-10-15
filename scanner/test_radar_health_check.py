from datetime import datetime, timezone, timedelta

from scanner import radar_health_check as health


def test_recent_success_is_healthy(monkeypatch):
    now = datetime.now(timezone.utc)
    run = {
        "created_at": (now - timedelta(minutes=10)).isoformat(),
        "updated_at": (now - timedelta(minutes=9)).isoformat(),
        "status": "completed",
        "conclusion": "success",
        "html_url": "https://github.com/example/repo/actions/runs/1",
    }
    monkeypatch.setattr(health, "request", lambda url: {"workflow_runs": [run]})
    healthy, detail = health.inspect_latest_run()
    assert healthy is True
    assert "completato correttamente" in detail


def test_failed_latest_run_is_unhealthy(monkeypatch):
    now = datetime.now(timezone.utc)
    run = {
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "status": "completed",
        "conclusion": "failure",
        "html_url": "https://github.com/example/repo/actions/runs/2",
    }
    monkeypatch.setattr(health, "request", lambda url: {"workflow_runs": [run]})
    healthy, detail = health.inspect_latest_run()
    assert healthy is False
    assert "failure" in detail


def test_stale_success_is_unhealthy(monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(minutes=70)
    run = {
        "created_at": old.isoformat(),
        "updated_at": old.isoformat(),
        "status": "completed",
        "conclusion": "success",
        "html_url": "https://github.com/example/repo/actions/runs/3",
    }
    monkeypatch.setattr(health, "request", lambda url: {"workflow_runs": [run]})
    healthy, detail = health.inspect_latest_run()
    assert healthy is False
    assert "45 minuti" in detail


def test_recent_in_progress_run_is_not_false_alarm(monkeypatch):
    now = datetime.now(timezone.utc)
    run = {
        "created_at": (now - timedelta(minutes=5)).isoformat(),
        "updated_at": now.isoformat(),
        "status": "in_progress",
        "conclusion": None,
        "html_url": "https://github.com/example/repo/actions/runs/4",
    }
    monkeypatch.setattr(health, "request", lambda url: {"workflow_runs": [run]})
    healthy, detail = health.inspect_latest_run()
    assert healthy is True
    assert "in corso" in detail


def test_no_runs_is_unhealthy(monkeypatch):
    monkeypatch.setattr(health, "request", lambda url: {"workflow_runs": []})
    healthy, detail = health.inspect_latest_run()
    assert healthy is False
    assert "Nessuna esecuzione" in detail
