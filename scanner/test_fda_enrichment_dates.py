from scanner.fda_enrichment import _extract_article_published_at, _is_parseable_date


def test_fda_enrichment_rejects_unparseable_nonempty_dates():
    assert not _is_parseable_date("not a date")
    assert not _is_parseable_date("")


def test_fda_enrichment_accepts_iso_and_human_readable_dates():
    assert _is_parseable_date("2026-10-13")
    assert _is_parseable_date("October 13, 2026")
    assert _is_parseable_date("2026-10-13T19:00:00+00:00")


def test_fda_article_date_extracts_official_publication_metadata():
    html = """
    <html><head>
      <meta property="article:published_time" content="2026-10-13T18:45:00Z">
    </head><body><main><h1>FDA announcement</h1></main></body></html>
    """
    assert _extract_article_published_at(html) == "2026-10-13T18:45:00+00:00"


def test_fda_article_date_does_not_return_unparseable_metadata():
    html = """
    <html><head><meta property="article:published_time" content="unknown"></head>
    <body><main>No date is shown here.</main></body></html>
    """
    assert _extract_article_published_at(html) is None
