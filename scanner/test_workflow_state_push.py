from pathlib import Path


def test_production_state_commit_rebases_and_retries_without_force_push():
    workflow = Path(".github/workflows/radar.yml").read_text(encoding="utf-8")
    assert "group: pharma-radar-production" in workflow
    assert "git fetch origin main" in workflow
    assert "git rebase origin/main" in workflow
    assert "for attempt in 1 2 3" in workflow
    assert "git push origin HEAD:main" in workflow
    assert "git push --force" not in workflow
