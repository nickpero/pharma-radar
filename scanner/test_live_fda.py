"""
Pharma Radar — LIVE FDA Test

Testa il feed FDA reale.

Obiettivo:
- collegarsi realmente a FDA;
- recuperare comunicazioni;
- verificare che non siano elementi
  di navigazione;
- verificare titolo, URL e struttura;
- stampare i risultati per controllo umano.

NON effettua:
- scoring;
- matching;
- Trading Intelligence;
- Telegram.
"""

from urllib.parse import urlparse

from scanner.fda_feed import (
    get_fda_news,
    is_fda_press_announcement_url,
    is_valid_news_title,
)


# ============================================
# SETTINGS
# ============================================

MAX_ITEMS = 10


# ============================================
# BLOCKED TITLES
# ============================================

BLOCKED_TITLES = {
    "press announcements",
    "skip to main content",
    "skip to fda search",
    "skip to footer links",
    "skip to in this section menu",
    "report a product problem",
    "contact fda",
    "fda guidance documents",
    "recalls, market withdrawals and safety alerts",
    "fda news",
    "newsroom",
}


# ============================================
# TEST LIVE FEED
# ============================================

def test_live_fda():

    news = get_fda_news(
        max_items=MAX_ITEMS
    )

    print()
    print(
        "========== LIVE FDA TEST =========="
    )

    print(
        f"News recuperate: {len(news)}"
    )

    # ----------------------------------------
    # DEVE ESSERCI ALMENO UNA NEWS
    # ----------------------------------------

    assert news, (
        "FDA feed returned no news"
    )

    # ----------------------------------------
    # VALIDAZIONE RISULTATI
    # ----------------------------------------

    seen_urls = set()

    for item in news:

        title = item.get(
            "title",
            ""
        )

        url = item.get(
            "url"
        )

        date = item.get(
            "published_at"
        )

        print()
        print(
            f"TITLE: {title}"
        )

        print(
            f"DATE: {date}"
        )

        print(
            f"URL: {url}"
        )

        print(
            "-----------------------------------"
        )

        # ------------------------------------
        # TITLE
        # ------------------------------------

        assert title, (
            "FDA news has empty title"
        )

        assert is_valid_news_title(
            title
        ), (
            f"Invalid/navigation title: {title}"
        )

        assert title.lower() not in (
            BLOCKED_TITLES
        ), (
            f"Navigation title detected: {title}"
        )

        # ------------------------------------
        # URL
        # ------------------------------------

        assert url, (
            f"FDA news has no URL: {title}"
        )

        assert is_fda_press_announcement_url(
            url
        ), (
            f"URL is not a Press Announcement: "
            f"{url}"
        )

        parsed = urlparse(
            url
        )

        assert not parsed.fragment, (
            f"Anchor URL detected: {url}"
        )

        # ------------------------------------
        # DUPLICATES
        # ------------------------------------

        assert url not in seen_urls, (
            f"Duplicate FDA URL: {url}"
        )

        seen_urls.add(
            url
        )

    print()
    print(
        "==================================="
    )

    print(
        "✅ LIVE FDA test passed"
    )


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    test_live_fda()