import json
from pathlib import Path

from scanner import universe_expansion


def test_reconcile_adds_only_verified_candidates(tmp_path, monkeypatch):
    watch = tmp_path / "watchlist.json"
    cik = tmp_path / "sec_cik_map.json"
    candidates = tmp_path / "universe_candidates.json"
    watch.write_text(json.dumps({"OLD": {"company": "Old", "programs": ["old"], "priority": "ORANGE"}}))
    cik.write_text(json.dumps({"NEW": "123"}))
    candidates.write_text(json.dumps({"candidates": {
        "NEW": {"company": "New Pharma", "programs": ["Drug"], "priority": "RED", "cik": "123"},
        "BAD": {"company": "Bad Pharma", "programs": ["Drug"], "priority": "RED"}
    }}))
    monkeypatch.setattr(universe_expansion, "WATCHLIST_FILE", watch)
    monkeypatch.setattr(universe_expansion, "CIK_FILE", cik)
    monkeypatch.setattr(universe_expansion, "CANDIDATE_FILE", candidates)

    result = universe_expansion.reconcile_watchlist()

    assert result["added"] == ["NEW"]
    assert any(row["ticker"] == "BAD" and row["reason"] == "MISSING_SEC_CIK" for row in result["rejected"])
    assert json.loads(watch.read_text())["NEW"]["company"] == "New Pharma"


def test_reconcile_is_idempotent(tmp_path, monkeypatch):
    watch = tmp_path / "watchlist.json"
    cik = tmp_path / "sec_cik_map.json"
    candidates = tmp_path / "universe_candidates.json"
    watch.write_text("{}")
    cik.write_text(json.dumps({"NEW": "123"}))
    candidates.write_text(json.dumps({"candidates": {
        "NEW": {"company": "New Pharma", "programs": ["Drug"], "priority": "RED", "cik": "123"}
    }}))
    monkeypatch.setattr(universe_expansion, "WATCHLIST_FILE", watch)
    monkeypatch.setattr(universe_expansion, "CIK_FILE", cik)
    monkeypatch.setattr(universe_expansion, "CANDIDATE_FILE", candidates)

    first = universe_expansion.reconcile_watchlist()
    second = universe_expansion.reconcile_watchlist()

    assert first["added"] == ["NEW"]
    assert second["added"] == []
