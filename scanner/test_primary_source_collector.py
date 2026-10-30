from pathlib import Path

from scanner import primary_source_collector as collector


SOURCE = {
    "ticker": "TST",
    "company": "Test Bio",
    "listing_url": "https://investors.testbio.com/press-releases",
    "allowed_host": "investors.testbio.com",
}


def test_parser_keeps_clinical_candidate_and_source_domain():
    html = """
    <html><body><div>
      <p>October 15, 2026</p>
      <a href="/news/phase-3-topline">Test Bio announces Phase 3 topline results in rare disease</a>
      <a href="https://other.example/clinical">Clinical trial results</a>
      <a href="/privacy">Clinical trial privacy policy</a>
    </div></body></html>
    """
    rows = collector.parse_listing_page(html, SOURCE, discovered_at="2026-10-15T00:00:00+00:00")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "TST"
    assert rows[0]["source_url"] == "https://investors.testbio.com/news/phase-3-topline"
    assert rows[0]["review_status"] == "PENDING_REVIEW"
    assert rows[0]["event_type"] is None
    assert rows[0]["event_date"] is None
    assert rows[0]["publication_date_candidate"] == "October 15, 2026"


class Response:
    text = '<a href="/news/phase-2-data">Company reports Phase 2 clinical data in trial</a>'

    def raise_for_status(self):
        pass


class Session:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return Response()


def test_collector_persists_new_candidates_and_deduplicates(tmp_path):
    state = tmp_path / "state.json"
    candidates = tmp_path / "candidates.json"
    session = Session()
    first = collector.collect_candidates([SOURCE], state, candidates, session)
    assert first["sources_ok"] == 1
    assert len(first["new_candidates"]) == 1
    assert first["pending_total"] == 1

    second = collector.collect_candidates([SOURCE], state, candidates, session)
    assert second["new_candidates"] == []
    assert second["pending_total"] == 1


def test_collector_does_not_overwrite_reviewed_candidate(tmp_path):
    state = tmp_path / "state.json"
    candidates = tmp_path / "candidates.json"
    url = "https://investors.testbio.com/news/phase-2-data"
    candidates.write_text(
        '[{"source_url":"' + url + '","review_status":"APPROVED","event_date":"2026-12-01"}]',
        encoding="utf-8",
    )
    result = collector.collect_candidates([SOURCE], state, candidates, Session())
    assert result["new_candidates"] == []
    assert result["pending_total"] == 1
    assert '"review_status": "APPROVED"' in candidates.read_text(encoding="utf-8")


def test_all_sources_failure_is_reported(tmp_path):
    class FailedSession:
        def get(self, *args, **kwargs):
            raise OSError("offline")

    import pytest
    with pytest.raises(RuntimeError, match="All official"):
        collector.collect_candidates([SOURCE], tmp_path / "state.json",
                                     tmp_path / "candidates.json", FailedSession())


def test_configured_primary_sources_cover_priority_watchlist_and_match_hosts():
    sources = collector.load_json(collector.SOURCES_PATH, [])
    by_ticker = {row["ticker"]: row for row in sources}
    assert {"ALNY", "MRK", "REGN", "KOD", "LFCR", "ONCO", "SCYX", "LXRX"} <= set(by_ticker)
    for row in sources:
        from urllib.parse import urlparse
        parsed = urlparse(row["listing_url"])
        assert parsed.scheme == "https"
        assert parsed.hostname == row["allowed_host"]
