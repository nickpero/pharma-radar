"""
Pharma Radar — FDA Live Matching Diagnostic

Diagnostica:

FDA News → Matcher → Watchlist → Ticker / Program

NON modifica il comportamento del Radar.
NON invia Telegram.
NON genera alert.

Serve esclusivamente a capire quante FDA news
reali vengono riconosciute dalla watchlist.
"""

from scanner.fda_news import get_fda_news
from scanner.fda_matcher import identify_fda_target
from scanner.trial_scanner import load_watchlist


def main():
    print("=" * 70)
    print("========== FDA LIVE MATCHING DIAGNOSTIC ==========")
    print("=" * 70)

    watchlist = load_watchlist()

    news = get_fda_news(
        max_news=50
    )

    print()
    print(f"FDA news recuperate: {len(news)}")
    print(f"Watchlist companies: {len(watchlist)}")
    print()

    matched = []
    unmatched = []

    for index, news_item in enumerate(
        news,
        start=1,
    ):
        title = news_item.get(
            "title",
            "",
        )

        url = news_item.get(
            "url",
            "",
        )

        target = identify_fda_target(
            news_item,
            watchlist,
        )

        print("=" * 70)
        print(f"NEWS #{index}")
        print(f"TITLE: {title}")
        print(f"URL:   {url}")

        if target is None:
            print("MATCH: ❌ NONE")
            unmatched.append(
                news_item
            )
            continue

        ticker = target.get(
            "ticker"
        )

        company = target.get(
            "company"
        )

        program = target.get(
            "program"
        )

        match_type = target.get(
            "match_type"
        )

        confidence = target.get(
            "confidence"
        )

        company_matches = target.get(
            "company_matches",
            [],
        )

        program_matches = target.get(
            "program_matches",
            [],
        )

        print("MATCH: ✅")
        print(f"Ticker:            {ticker}")
        print(f"Company:           {company}")
        print(f"Program:           {program}")
        print(f"Match type:        {match_type}")
        print(f"Confidence:        {confidence}")
        print(f"Company matches:   {company_matches}")
        print(f"Program matches:   {program_matches}")

        matched.append(
            {
                "news": news_item,
                "target": target,
            }
        )

    print()
    print("=" * 70)
    print("========== DIAGNOSTIC SUMMARY ==========")
    print("=" * 70)

    print(f"News:               {len(news)}")
    print(f"Matched:            {len(matched)}")
    print(f"Unmatched:          {len(unmatched)}")

    if news:
        match_rate = (
            len(matched)
            / len(news)
            * 100
        )
    else:
        match_rate = 0

    print(
        f"Match rate:         {match_rate:.1f}%"
    )

    print()
    print("========== MATCHED NEWS ==========")

    if not matched:
        print("Nessun match.")
    else:
        for item in matched:
            target = item["target"]
            news_item = item["news"]

            print(
                f"✅ {target.get('ticker')} "
                f"| {target.get('program')} "
                f"| {target.get('match_type')} "
                f"| {news_item.get('title')}"
            )

    print()
    print("========== UNMATCHED NEWS ==========")

    if not unmatched:
        print("Tutte le news sono state associate.")
    else:
        for news_item in unmatched:
            print(
                f"❌ {news_item.get('title')}"
            )

    print()
    print("=" * 70)
    print("FDA LIVE MATCHING DIAGNOSTIC COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()