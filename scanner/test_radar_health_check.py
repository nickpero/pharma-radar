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



def _write_source_state(tmp_path, now, successful, total=8, source_errors=None):
    import json
    state_path = tmp_path / "primary_source_discovery_state.json"
    sources_path = tmp_path / "primary_source_pages.json"
    state_path.write_text(json.dumps({
        "last_checked_at": now.isoformat(),
        "successful_sources": successful,
        "source_errors": source_errors or [],
    }), encoding="utf-8")
    sources_path.write_text(json.dumps([
        {"ticker": f"T{i}", "listing_url": f"https://ir.example{i}.com/news",
         "allowed_host": f"ir.example{i}.com"}
        for i in range(total)
    ]), encoding="utf-8")
    return state_path, sources_path


def test_source_coverage_is_healthy_when_most_sources_work(tmp_path):
    now = datetime.now(timezone.utc)
    state, sources = _write_source_state(tmp_path, now, successful=7, total=8,
                                         source_errors=["one source temporarily unavailable"])
    healthy, detail = health.inspect_source_coverage(state, sources, now)
    assert healthy is True
    assert "7/8" in detail


def test_source_coverage_is_unhealthy_when_too_many_sources_fail(tmp_path):
    now = datetime.now(timezone.utc)
    state, sources = _write_source_state(tmp_path, now, successful=4, total=8,
                                         source_errors=["KOD: timeout", "LXRX: 502"])
    healthy, detail = health.inspect_source_coverage(state, sources, now)
    assert healthy is False
    assert "4/8" in detail
    assert "KOD: timeout" in detail


def test_stale_source_coverage_is_unhealthy(tmp_path):
    now = datetime.now(timezone.utc)
    state, sources = _write_source_state(
        tmp_path, now - timedelta(minutes=40), successful=8, total=8
    )
    healthy, detail = health.inspect_source_coverage(state, sources, now)
    assert healthy is False
    assert "non aggiornata" in detail


def test_missing_source_state_is_allowed_on_first_deployment(tmp_path):
    healthy, detail = health.inspect_source_coverage(
        tmp_path / "not-created.json", tmp_path / "sources.json",
        datetime.now(timezone.utc)
    )
    assert healthy is True
    assert "non ancora inizializzata" in detail
