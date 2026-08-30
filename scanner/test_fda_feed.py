from scanner.fda_feed import (
    normalize_text,
    get_item_id,
    normalize_date,
    extract_title,
    extract_link,
    extract_summary,
    extract_date,
    parse_fda_page,
    sort_fda_news,
)


# ============================================
# TEST NORMALIZE
# ============================================

def test_normalize_text():

    assert normalize_text(
        "  FDA   approves   drug  "
    ) == "FDA approves drug"

    assert normalize_text(
        None
    ) == ""

    assert normalize_text(
        ""
    ) == ""


# ============================================
# TEST DATE
# ============================================

def test_normalize_date():

    assert normalize_date(
        "2026-08-30"
    ).startswith(
        "2026-08-30"
    )

    assert normalize_date(
        "August 30, 2026"
    ).startswith(
        "2026-08-30"
    )


# ============================================
# TEST ITEM ID
# ============================================

def test_item_id():

    item = {
        "title": "FDA approves new drug",
        "url": "https://www.fda.gov/test",
        "published_at": "2026-08-30",
    }

    first = get_item_id(item)
    second = get_item_id(item)

    assert first == second
    assert len(first) == 64


# ============================================
# TEST HTML EXTRACTION
# ============================================

def test_html_extraction():

    html = """
    <article>
        <h2>
            FDA approves new cancer treatment
        </h2>

        <time datetime="2026-08-30">
            August 30, 2026
        </time>

        <p>
            The FDA announced approval today.
        </p>

        <a href="/news-events/press-announcements/test">
            Read more
        </a>
    </article>
    """

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    article = soup.find(
        "article"
    )

    title = extract_title(
        article
    )

    link = extract_link(
        article
    )

    summary = extract_summary(
        article
    )

    date = extract_date(
        article
    )

    assert title == (
        "FDA approves new cancer treatment"
    )

    assert link == (
        "https://www.fda.gov/"
        "news-events/press-announcements/test"
    )

    assert (
        "FDA announced approval"
        in summary
    )

    assert date.startswith(
        "2026-08-30"
    )


# ============================================
# TEST PARSER
# ============================================

def test_parse_fda_page():

    html = """
    <html>
        <body>

            <article>

                <h2>
                    FDA approves new cancer drug
                </h2>

                <time datetime="2026-08-30">
                    August 30, 2026
                </time>

                <p>
                    The FDA announced approval today.
                </p>

                <a href="/news-events/press-announcements/test">
                    Read more
                </a>

            </article>

            <article>

                <h2>
                    FDA publishes general information
                </h2>

                <time datetime="2026-08-29">
                    August 29, 2026
                </time>

                <p>
                    General regulatory information.
                </p>

                <a href="/news-events/press-announcements/general">
                    Read more
                </a>

            </article>

        </body>
    </html>
    """

    news = parse_fda_page(
        html,
        max_items=10,
    )

    assert len(news) == 2

    assert news[0]["source"] == "FDA"

    titles = {
        item["title"]
        for item in news
    }

    assert (
        "FDA approves new cancer drug"
        in titles
    )

    assert (
        "FDA publishes general information"
        in titles
    )


# ============================================
# TEST DUPLICATES
# ============================================

def test_duplicate_removal():

    html = """
    <html>
        <body>

            <article>

                <h2>
                    FDA approves new drug
                </h2>

                <time datetime="2026-08-30">
                    August 30, 2026
                </time>

                <p>
                    FDA approval announced.
                </p>

                <a href="/test">
                    Read more
                </a>

            </article>

            <article>

                <h2>
                    FDA approves new drug
                </h2>

                <time datetime="2026-08-30">
                    August 30, 2026
                </time>

                <p>
                    FDA approval announced.
                </p>

                <a href="/test">
                    Read more
                </a>

            </article>

        </body>
    </html>
    """

    news = parse_fda_page(
        html,
        max_items=10,
    )

    assert len(news) == 1


# ============================================
# TEST MAX ITEMS
# ============================================

def test_max_items():

    html = """
    <html>
        <body>

            <article>
                <h2>FDA approves drug one</h2>
                <a href="/one">Read more</a>
            </article>

            <article>
                <h2>FDA approves drug two</h2>
                <a href="/two">Read more</a>
            </article>

            <article>
                <h2>FDA approves drug three</h2>
                <a href="/three">Read more</a>
            </article>

        </body>
    </html>
    """

    news = parse_fda_page(
        html,
        max_items=2,
    )

    assert len(news) == 2


# ============================================
# TEST SORT
# ============================================

def test_sort_fda_news():

    news = [

        {
            "title": "Low",
            "priority": "LOW",
        },

        {
            "title": "Extreme",
            "priority": "EXTREME",
        },

        {
            "title": "High",
            "priority": "HIGH",
        },
    ]

    ordered = sort_fda_news(
        news
    )

    assert ordered[0]["title"] == (
        "Extreme"
    )

    assert ordered[1]["title"] == (
        "High"
    )

    assert ordered[2]["title"] == (
        "Low"
    )


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    test_normalize_text()
    test_normalize_date()
    test_item_id()
    test_html_extraction()
    test_parse_fda_page()
    test_duplicate_removal()
    test_max_items()
    test_sort_fda_news()

    print(
        "✅ FDA Feed tests passed"
    )