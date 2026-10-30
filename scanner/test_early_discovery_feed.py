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
