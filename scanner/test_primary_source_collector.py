import json
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
    assert rows[0]["published_at"] is None
    assert rows[0]["publication_time_precision"] == "DATE_ONLY"
    assert rows[0]["publication_timestamp_source"] == "CARD_TEXT"


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
    first_state = json.loads(state.read_text(encoding="utf-8"))

    second = collector.collect_candidates([SOURCE], state, candidates, session)
    assert second["new_candidates"] == []
    assert second["pending_total"] == 1
    second_state = json.loads(state.read_text(encoding="utf-8"))
    assert second_state == first_state
    assert "last_checked_at" not in second_state


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
    with pytest.raises(RuntimeError, match="All enabled official"):
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



def test_parser_extracts_timezone_aware_original_publication_timestamp():
    html = """
    <html><body><article>
      <time datetime="2026-10-15T09:30:00-04:00">October 15, 2026</time>
      <a href="/news/phase-3-topline">Test Bio announces Phase 3 topline results</a>
    </article></body></html>
    """
    rows = collector.parse_listing_page(
        html, SOURCE, discovered_at="2026-10-15T15:00:00+00:00"
    )
    assert len(rows) == 1
    assert rows[0]["published_at"] == "2026-10-15T13:30:00+00:00"
    assert rows[0]["published_at_raw"] == "2026-10-15T09:30:00-04:00"
    assert rows[0]["publication_time_precision"] == "TIMESTAMP"
    assert rows[0]["publication_timezone_known"] is True
    assert rows[0]["publication_timestamp_source"] == "TIME_TAG"


def test_parser_does_not_invent_timezone_for_unzoned_timestamp():
    html = """
    <html><body><article>
      <time datetime="2026-10-15T09:30:00">October 15, 2026</time>
      <a href="/news/phase-3-topline">Test Bio announces Phase 3 topline results</a>
    </article></body></html>
    """
    rows = collector.parse_listing_page(html, SOURCE)
    assert len(rows) == 1
    assert rows[0]["published_at"] is None
    assert rows[0]["publication_time_precision"] == "TIMEZONE_UNKNOWN"
    assert rows[0]["publication_timezone_known"] is False



def test_configured_sources_are_official_https_pages():
    sources = collector.load_json(collector.SOURCES_PATH, [])
    assert {item["ticker"] for item in sources} == {
        "ALNY", "MRK", "REGN", "KOD", "LFCR", "ONCO", "SCYX", "LXRX",
        "CAPR", "SVRA", "ZYME", "MIRM", "PHVS", "TENX", "NUVL", "ARGX", "QURE", "STOK",
    }
    for item in sources:
        parsed = collector.urlparse(item["listing_url"])
        assert parsed.scheme == "https"
        assert parsed.hostname == item["allowed_host"]
    by_ticker = {item["ticker"]: item for item in sources}
    assert {ticker for ticker, item in by_ticker.items() if item.get("enabled", True)} == {
        "ALNY", "MRK", "ONCO", "SCYX", "CAPR", "SVRA", "ZYME", "MIRM",
        "NUVL", "ARGX", "QURE", "STOK", "KOD", "LFCR", "LXRX",
    }
    assert {ticker for ticker, item in by_ticker.items() if item.get("enabled") is False} == {
        "PHVS", "TENX", "REGN",
    }


def test_disabled_source_is_not_requested(tmp_path):
    session = Session()
    disabled = dict(SOURCE, enabled=False)
    result = collector.collect_candidates(
        [disabled],
        tmp_path / "state.json",
        tmp_path / "candidates.json",
        session,
    )
    assert session.calls == 0
    assert result["sources_enabled"] == 0
    assert result["sources_disabled"] == 1
    assert result["sources_ok"] == 0



def test_rss_parser_extracts_original_publication_timestamp():
    source = dict(
        SOURCE,
        listing_url="https://company.example/rss/news.xml",
        allowed_host="company.example",
    )
    rss = """
    <rss><channel><item>
      <title>Company announces Phase 3 clinical results from its pivotal study</title>
      <link>https://company.example/news/phase-3-results</link>
      <pubDate>Thu, 30 Oct 2026 09:00:00 -0400</pubDate>
      <description>Topline clinical results from the pivotal Phase 3 study.</description>
    </item></channel></rss>
    """
    rows = collector.parse_listing_page(rss, source)
    assert len(rows) == 1
    assert rows[0]["source_url"] == "https://company.example/news/phase-3-results"
    assert rows[0]["published_at"] == "2026-10-30T13:00:00+00:00"
    assert rows[0]["publication_time_precision"] == "TIMESTAMP"
    assert rows[0]["publication_timezone_known"] is True
    assert rows[0]["publication_timestamp_source"] == "RSS_PUBDATE"


def test_restored_priority_ir_sources_use_verified_official_hosts():
    sources = collector.load_json(collector.SOURCES_PATH, [])
    by_ticker = {item["ticker"]: item for item in sources}
    expected = {
        "KOD": ("https://ir.kodiak.com/investor-relations/", "ir.kodiak.com"),
        "LFCR": ("https://ir.lifecore.com/press-releases", "ir.lifecore.com"),
        "LXRX": ("https://investors.lexpharma.com/news-events/news-releases", "investors.lexpharma.com"),
    }
    for ticker, (url, host) in expected.items():
        assert by_ticker[ticker]["enabled"] is True
        assert by_ticker[ticker]["listing_url"] == url
        assert by_ticker[ticker]["allowed_host"] == host
