# CI verification: explicit EMA label signal; no production behavior change.
from scanner.ema_feed import build_ema_news_item, classify_ema_text, parse_ema_rss
import scanner.sec_feed as sec_feed
from scanner.sec_feed import (
    DEFAULT_USER_AGENT,
    DISCOVERY_MAX_TICKERS,
    _browse_company_url,
    _extract_accessions,
    _extract_filing_date,
    _pick_document,
    build_sec_item,
    get_ticker_cik_map,
)
from scanner.regulatory_pipeline import process_regulatory_news, is_regulatory_alert_candidate
from scanner.fda_score import score_fda_event


def test_ema_rss_parser():
    xml = """<rss><channel><item><title>EMA recommends new medicine VYVGART</title><link>/en/news/new-vyvgart</link><pubDate>Mon, 01 Sep 2026 10:00:00 +0000</pubDate><description>argenx announces important regulatory news for VYVGART.</description></item></channel></rss>"""
    items = parse_ema_rss(xml)
    assert len(items) == 1
    assert items[0]["source"] == "EMA"
    assert items[0]["source_type"] == "PRIMARY_REGULATORY"
    assert "VYVGART" in items[0]["title"]


def test_ema_content_classification():
    categories = classify_ema_text(
        "Committee recommends medicine",
        "",
        "The committee adopted a positive opinion recommending an extension of the therapeutic indication and a variation to the marketing authorisation.",
    )
    assert "APPROVAL" in categories
    assert "LABEL" in categories


def test_primary_source_builders():
    ema = build_ema_news_item("EMA VYVGART update", "/en/news/vyvgart", "2026-09-01")
    sec = build_sec_item("ARGX", "argenx", "0001743812", "0000000000-26-000001", "8-K", "2026-09-01", "argx-8k.htm", ["8.01"], "argenx VYVGART clinical update")
    assert ema["source_type"] == "PRIMARY_REGULATORY"
    assert sec["source_type"] == "PRIMARY_CORPORATE"
    assert sec["form"] == "8-K"


def test_sec_body_enrichment_preserves_program_text():
    text = (
        "Ionis Pharmaceuticals announced that the U.S. Food and Drug Administration "
        "has approved ZANVASTRO (zilganersen) for the treatment of Alexander disease."
    )
    sec = build_sec_item(
        "IONS", "Ionis Pharmaceuticals", "0000874015", "0001140361-26-035657", "8-K", "2026-09-04",
        items=["7.01", "8.01"], text=text,
    )
    assert sec["provider"] == "SEC_EDGAR_VIA_JINA"
    assert "zilganersen" in sec["content"].lower()
    assert "ZANVASTRO" in sec["content"]


def test_sec_primary_document_nonstandard_issuer_date_names():
    assert _pick_document([
        "0001937653-26-000051-index-headers.html", "finalgeapr.htm", "R1.htm", "zyme-20260825.htm"
    ]) == "zyme-20260825.htm"
    assert _pick_document([
        "0001599298-26-000001-index-headers.html", "a2026_prx0902xharmoni-2o.htm", "R1.htm", "smmt-20260902.htm"
    ]) == "smmt-20260902.htm"


def test_sec_primary_document_prefers_8k_over_exhibit():
    assert _pick_document(["ex991q22026_earningsxrelea.htm", "R1.htm", "zyme-20260806.htm", "issuer_8k.htm"]) == "issuer_8k.htm"


def test_sec_primary_document_fallback_ignores_exhibits_and_r_files():
    assert _pick_document(["R1.htm", "ex99-1.htm", "issuer-material-event.htm"]) == "issuer-material-event.htm"


def test_sec_user_agent_is_declared():
    assert "PharmaRadar" in DEFAULT_USER_AGENT
    assert "@" in DEFAULT_USER_AGENT


def test_sec_watchlist_cik_map_avoids_runtime_ticker_lookup():
    mapping = get_ticker_cik_map()
    assert mapping["CAPR"] == "0001133869"
    assert mapping["NUVL"] == "0001861560"
    assert mapping["IONS"] == "0000874015"
    assert mapping["SMMT"] == "0001599298"
    assert "ARGX" not in mapping


def test_sec_company_discovery_helpers():
    browse_url = _browse_company_url("0000874015", count=10)
    assert "CIK=0000874015" in browse_url
    assert "type=8-K" in browse_url

    browse_text = """
        Filing Date 2026-09-04
        0001140361-26-035657
        0001140361-26-035802
        0001140361-26-035657
    """
    accessions = _extract_accessions(browse_text, max_filings=2)
    assert accessions == ["0001140361-26-035657", "0001140361-26-035802"]
    assert _extract_filing_date(browse_text) == "2026-09-04"


def test_sec_discovery_rotates_each_production_scan():
    # Production runs every 10 minutes, so a new batch should be selected each scan.
    assert sec_feed.DISCOVERY_ROTATION_SECONDS == 600


def test_sec_discovery_is_bounded(monkeypatch):
    watchlist = {ticker: {"company": ticker} for ticker in sec_feed.WATCHLIST_CIK}
    calls = []

    def fake_discover(ticker, company, cik, max_filings=2):
        calls.append(ticker)
        return []

    monkeypatch.setattr(sec_feed, "_discover_company_filings", fake_discover)
    monkeypatch.setattr(sec_feed, "_JINA_RATE_LIMITED", False)
    sec_feed._discover_missing_companies(watchlist, set())
    assert len(calls) == DISCOVERY_MAX_TICKERS
    assert len(calls) < len(watchlist)


def test_sec_discovery_stops_after_rate_limit(monkeypatch):
    watchlist = {ticker: {"company": ticker} for ticker in list(sec_feed.WATCHLIST_CIK)[:6]}
    calls = []

    def fake_discover(ticker, company, cik, max_filings=2):
        calls.append(ticker)
        sec_feed._JINA_RATE_LIMITED = True
        return []

    monkeypatch.setattr(sec_feed, "_discover_company_filings", fake_discover)
    monkeypatch.setattr(sec_feed, "_JINA_RATE_LIMITED", False)
    sec_feed._discover_missing_companies(watchlist, set())
    assert len(calls) == 1
    monkeypatch.setattr(sec_feed, "_JINA_RATE_LIMITED", False)


def test_fda_score_preserves_label():
    event = {"type": "FDA_EVENT", "subtype": "FDA_APPROVAL", "severity": "HIGH", "direction": "CATALYST"}
    scored = score_fda_event(event)
    assert scored["score"] == 100
    assert scored["label"] == "CRITICAL"


def test_regulatory_pipeline_requires_program_match():
    watchlist = {"ARGX": {"company": "argenx", "programs": ["VYVGART"]}}
    items = [build_ema_news_item("argenx reports VYVGART regulatory update", "/en/news/vyvgart", "2026-09-01")]
    items[0]["content"] = "argenx VYVGART update"
    events = process_regulatory_news(items, watchlist)
    assert len(events) == 1
    assert events[0]["ticker"] == "ARGX"
    assert events[0]["program"] == "VYVGART"
    assert events[0]["source"] == "EMA"


def test_regulatory_pipeline_rejects_generic_company_only_news():
    watchlist = {"ARGX": {"company": "argenx", "programs": ["VYVGART"]}}
    items = [build_ema_news_item("argenx corporate update", "/en/news/corporate", "2026-09-01")]
    events = process_regulatory_news(items, watchlist)
    assert events == []


def test_ema_program_alias_without_matching_company_is_rejected():
    watchlist = {
        "RVMD": {"company": "Revolution Medicines", "programs": ["RMC-6236", "daraxonrasib"]},
    }
    items = [
        build_ema_news_item(
            "EMA recommends authorisation of Rasonque for metastatic pancreatic cancer",
            "/en/news/rasonque", "2026-10-15",
        )
    ]
    events = process_regulatory_news(items, watchlist)
    assert events == []


def test_sec_issuer_ticker_cannot_be_remapped_to_another_watchlist_company():
    watchlist = {
        "EYPT": {"company": "EyePoint Pharmaceuticals", "programs": ["DURAVYU"]},
        "LFCR": {"company": "Lifecore Biomedical", "programs": ["pilavapadin"]},
    }
    item = build_sec_item(
        "EYPT", "EyePoint Pharmaceuticals", "0001314102",
        "0000000000-26-000001", "8-K", "2026-10-19",
        items=["8.01"], text="EyePoint Pharmaceuticals filing mentions pilavapadin.",
    )
    events = process_regulatory_news([item], watchlist)
    # A program alias belonging to LFCR must not cause an EYPT SEC filing
    # to be attributed to LFCR. With no matching EYPT program, suppress it.
    assert events == []



def test_sec_direct_failure_isolated_per_ticker_and_preserves_successes(monkeypatch):
    watchlist = {
        "CAPR": {"company": "Capricor Therapeutics"},
        "NUVL": {"company": "Nuvalent"},
    }
    good = build_sec_item(
        "CAPR", "Capricor Therapeutics", "0001133869",
        "0000000000-26-000001", "8-K", "2026-10-28",
        items=["8.01"], text="Capricor material event",
    )
    calls = []
    def fake_direct(ticker, company, cik, max_filings=3):
        calls.append(ticker)
        if ticker == "CAPR":
            return [good]
        raise sec_feed.requests.HTTPError("403 forbidden")
    monkeypatch.setattr(sec_feed, "_fetch_sec_direct", fake_direct)
    monkeypatch.setattr(sec_feed, "_fetch_proxy", lambda max_filings=50: [])
    monkeypatch.setattr(sec_feed, "_discover_missing_companies", lambda *_: [])
    result = sec_feed.get_sec_news(watchlist)
    assert calls == ["CAPR", "NUVL"]
    assert len(result) == 1
    assert result[0]["ticker"] == "CAPR"
    assert sec_feed.LAST_FETCH_STATUS["status"] == "DEGRADED_FALLBACK"
    assert sec_feed.LAST_FETCH_STATUS["path"] == "direct_plus_proxy"
    assert sec_feed.LAST_FETCH_STATUS["failed_tickers"] == ["NUVL"]


def test_sec_uses_browse_fallback_after_proxy_failure(monkeypatch):
    watchlist = {"CAPR": {"company": "Capricor Therapeutics"}}
    expected = [{"ticker": "CAPR", "source": "SEC", "title": "Browse fallback"}]

    def fail_direct(*args, **kwargs):
        raise sec_feed.requests.RequestException("direct unavailable")

    def fail_proxy(*args, **kwargs):
        raise sec_feed.requests.Timeout("proxy timeout")

    monkeypatch.setattr(sec_feed, "_fetch_sec_direct", fail_direct)
    monkeypatch.setattr(sec_feed, "_fetch_proxy", fail_proxy)
    monkeypatch.setattr(sec_feed, "_discover_missing_companies", lambda *_: expected)

    result = sec_feed.get_sec_news(watchlist)
    assert result == expected
    assert sec_feed.LAST_FETCH_STATUS["status"] == "DEGRADED_FALLBACK"
    assert sec_feed.LAST_FETCH_STATUS["path"] == "direct_plus_discovery"
    assert sec_feed.LAST_FETCH_STATUS["count"] == 1


def test_medium_impact_regulatory_events_reach_final_delivery_gate():
    assert is_regulatory_alert_candidate({"trading_impact": "MEDIUM"}) is True
    assert is_regulatory_alert_candidate({"trading_impact": "HIGH"}) is True
    assert is_regulatory_alert_candidate({"trading_impact": "EXTREME"}) is True
    assert is_regulatory_alert_candidate({"trading_impact": "LOW"}) is False
    assert is_regulatory_alert_candidate({}) is False

if __name__ == "__main__":
    test_ema_rss_parser()
    test_ema_content_classification()
    test_primary_source_builders()
    test_sec_body_enrichment_preserves_program_text()
    test_sec_primary_document_nonstandard_issuer_date_names()
    test_sec_primary_document_prefers_8k_over_exhibit()
    test_sec_primary_document_fallback_ignores_exhibits_and_r_files()
    test_sec_user_agent_is_declared()
    test_sec_watchlist_cik_map_avoids_runtime_ticker_lookup()
    test_sec_company_discovery_helpers()
    test_fda_score_preserves_label()
    test_regulatory_pipeline_requires_program_match()
    test_regulatory_pipeline_rejects_generic_company_only_news()
    print("Regulatory source tests passed")
