from scanner.early_discovery_feed import _query, _source_info, _is_catalyst_like


def test_query_includes_trusted_distribution_and_specialist_domains():
    query = _query([("VBIO", "Valion Bio")])
    assert "site:globenewswire.com" in query
    assert "site:businesswire.com" in query
    assert "site:prnewswire.com" in query
    assert "site:biospace.com" in query
    assert "site:fiercebiotech.com" in query
    assert "site:fiercepharma.com" in query
    assert "site:endpts.com" in query
    assert "site:statnews.com" in query
    assert "site:biopharmadive.com" in query
    assert "site:pharmaphorum.com" in query


def test_source_info_classifies_globenewswire():
    class Node:
        text = "GlobeNewswire"
        def get(self, key):
            return "https://www.globenewswire.com/news-release/example"
    class Entry:
        def find(self, tag):
            return Node() if tag == "source" else None
    provider, source_type = _source_info(Entry(), "https://news.google.com/example")
    assert provider == "GlobeNewswire"
    assert source_type == "TRUSTED_DISTRIBUTION"


def test_source_info_classifies_biospace():
    class Node:
        text = "BioSpace"
        def get(self, key):
            return "https://www.biospace.com/article/example"
    class Entry:
        def find(self, tag):
            return Node() if tag == "source" else None
    provider, source_type = _source_info(Entry(), "https://news.google.com/example")
    assert provider == "BioSpace"
    assert source_type == "SPECIALIST"


def test_source_info_classifies_endpoints_news():
    class Node:
        text = "Endpoints News"
        def get(self, key):
            return "https://endpts.com/example"
    class Entry:
        def find(self, tag):
            return Node() if tag == "source" else None
    provider, source_type = _source_info(Entry(), "https://news.google.com/example")
    assert provider == "Endpoints News"
    assert source_type == "SPECIALIST"


def test_discovery_detects_corporate_and_clinical_risk_events():
    assert _is_catalyst_like("Quarterly earnings and revenue guidance", "")
    assert _is_catalyst_like("Company announces strategic review and cash runway update", "")
    assert _is_catalyst_like("Phase 3 futility and clinical hold", "")
    assert not _is_catalyst_like("Company appoints a new board observer", "")



def test_request_batch_splits_oversized_query(monkeypatch):
    from types import SimpleNamespace
    from scanner import early_discovery_feed as feed

    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return SimpleNamespace(status_code=414, headers={}, text="", raise_for_status=lambda: None)
        return SimpleNamespace(
            status_code=200,
            headers={},
            text="<rss><channel></channel></rss>",
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(feed.requests, "get", fake_get)
    rows = feed._request_batch([("AAA", "Alpha Bio"), ("BBB", "Beta Bio")], 1)
    assert rows == []
    assert len(calls) == 3


def test_request_batch_retries_transient_server_error(monkeypatch):
    from types import SimpleNamespace
    from scanner import early_discovery_feed as feed
    import requests

    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            response = requests.Response()
            response.status_code = 503
            response.url = url
            return response
        return SimpleNamespace(
            status_code=200,
            headers={},
            text="<rss><channel></channel></rss>",
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr(feed.requests, "get", fake_get)
    monkeypatch.setattr(feed.time, "sleep", lambda _delay: None)
    rows = feed._request_batch([("AAA", "Alpha Bio")], 1)
    assert rows == []
    assert len(calls) == 2


def test_early_discovery_diagnostics_include_source_path(monkeypatch):
    from scanner import early_discovery_feed as feed

    monkeypatch.setattr(feed.requests, "get", lambda *args, **kwargs: None)
    assert feed.get_early_news({}) == []
    assert feed.LAST_FETCH_STATUS["path"] == "google_news_rss"
    assert feed.LAST_FETCH_STATUS["companies_queried"] == 0
