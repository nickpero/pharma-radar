from scanner.ema_feed import build_ema_news_item, classify_ema_text, parse_ema_rss
from scanner.sec_feed import DEFAULT_USER_AGENT, build_sec_item, get_ticker_cik_map
from scanner.regulatory_pipeline import process_regulatory_news
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
        "The committee adopted a positive opinion recommending a change to the marketing authorisation.",
    )
    assert "APPROVAL" in categories
    assert "LABEL" in categories


def test_primary_source_builders():
    ema = build_ema_news_item("EMA VYVGART update", "/en/news/vyvgart", "2026-09-01")
    sec = build_sec_item("ARGX", "argenx", "0001743812", "0000000000-26-000001", "8-K", "2026-09-01", "argx-8k.htm", ["8.01"], "argenx VYVGART clinical update")
    assert ema["source_type"] == "PRIMARY_REGULATORY"
    assert sec["source_type"] == "PRIMARY_CORPORATE"
    assert sec["form"] == "8-K"


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


def test_fda_score_preserves_label():
    event = {
        "type": "FDA_EVENT",
        "subtype": "FDA_APPROVAL",
        "severity": "HIGH",
        "direction": "CATALYST",
    }
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


if __name__ == "__main__":
    test_ema_rss_parser()
    test_ema_content_classification()
    test_primary_source_builders()
    test_sec_user_agent_is_declared()
    test_sec_watchlist_cik_map_avoids_runtime_ticker_lookup()
    test_fda_score_preserves_label()
    test_regulatory_pipeline_requires_program_match()
    test_regulatory_pipeline_rejects_generic_company_only_news()
    print("Regulatory source tests passed")
