"""
Pharma Radar — FDA Matcher Diagnostic Test

Test diagnostico del matching FDA su notizie reali.

NON modifica il motore FDA Matcher.
Serve esclusivamente a capire:
FDA News → company/program → ticker
"""

from scanner.fda_feed import get_fda_news
from scanner.fda_matcher import identify_fda_target


WATCHLIST = {
    "CAPR": {
        "company": "Capricor Therapeutics",
        "programs": ["deramiocel"],
        "priority": "RED",
    },
    "SVRA": {
        "company": "Savara",
        "programs": ["molgramostim", "MOLBREEVI"],
        "priority": "RED",
    },
    "ZYME": {
        "company": "Zymeworks",
        "programs": ["zanidatamab"],
        "priority": "RED",
    },
    "MIRM": {
        "company": "Mirum Pharmaceuticals",
        "programs": [
            "maralixibat",
            "zilurgisertib",
            "brelovitug",
        ],
        "priority": "RED",
    },
    "PHVS": {
        "company": "Pharvaris",
        "programs": ["deucrictibant"],
        "priority": "RED",
    },
    "TENX": {
        "company": "Tenax Therapeutics",
        "programs": ["TNX-103"],
        "priority": "RED",
    },
    "NUVL": {
        "company": "Nuvalent",
        "programs": ["zidesamtinib"],
        "priority": "RED",
    },
    "RARE": {
        "company": "Ultragenyx",
        "programs": ["UX111"],
        "priority": "ORANGE",
    },
    "TLX": {
        "company": "Telix Pharmaceuticals",
        "programs": ["TLX101", "Pixclara"],
        "priority": "ORANGE",
    },
    "IONS": {
        "company": "Ionis Pharmaceuticals",
        "programs": ["zilganersen"],
        "priority": "ORANGE",
    },
    "ARGX": {
        "company": "argenx",
        "programs": ["VYVGART"],
        "priority": "RED",
    },
    "QURE": {
        "company": "uniQure",
        "programs": ["AMT-130"],
        "priority": "RED",
    },
    "STOK": {
        "company": "Stoke Therapeutics",
        "programs": ["zorevunersen"],
        "priority": "RED",
    },
    "ANNX": {
        "company": "Annexon",
        "programs": ["ANX007"],
        "priority": "ORANGE",
    },
    "IMMX": {
        "company": "Immix Biopharma",
        "programs": ["NXC-201"],
        "priority": "ORANGE",
    },
    "ALMS": {
        "company": "Alumis",
        "programs": ["ESK-001"],
        "priority": "ORANGE",
    },
    "RNA": {
        "company": "Avidity Biosciences",
        "programs": ["delpacibart"],
        "priority": "ORANGE",
    },
    "RGNX": {
        "company": "REGENXBIO",
        "programs": ["surabgene"],
        "priority": "ORANGE",
    },
    "EYPT": {
        "company": "EyePoint Pharmaceuticals",
        "programs": ["vorolanib"],
        "priority": "ORANGE",
    },
    "SMMT": {
        "company": "Summit Therapeutics",
        "programs": ["ivonescimab"],
        "priority": "RED",
    },
}


def main():
    print()
    print("=" * 60)
    print("========== FDA REAL NEWS → MATCHER DIAGNOSTIC ==========")
    print("=" * 60)

    news = get_fda_news(max_items=10)

    print()
    print(f"FDA news recuperate: {len(news)}")
    print()

    if not news:
        raise AssertionError(
            "Nessuna FDA news recuperata"
        )

    matched = 0
    unmatched = 0

    for index, item in enumerate(news, start=1):

        title = item.get("title", "")
        summary = item.get("summary", "")
        url = item.get("url", "")

        print("-" * 60)
        print(f"NEWS #{index}")
        print(f"TITLE: {title}")
        print(f"URL:   {url}")

        try:
            target = identify_fda_target(
                item,
                WATCHLIST,
            )

        except Exception as error:

            print(
                f"MATCHER ERROR: {error}"
            )

            raise

        if target is None:

            unmatched += 1

            print("MATCH: ❌ NONE")

        else:

            matched += 1

            print("MATCH: ✅ FOUND")
            print(
                f"TICKER: {target.get('ticker')}"
            )
            print(
                f"COMPANY: {target.get('company')}"
            )
            print(
                f"PROGRAM: {target.get('program')}"
            )
            print(
                f"MATCH TYPE: {target.get('match_type')}"
            )
            print(
                f"CONFIDENCE: {target.get('confidence')}"
            )
            print(
                f"COMPANY MATCHES: "
                f"{target.get('company_matches', [])}"
            )
            print(
                f"PROGRAM MATCHES: "
                f"{target.get('program_matches', [])}"
            )

    print()
    print("=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"News:       {len(news)}")
    print(f"Matched:    {matched}")
    print(f"Unmatched:  {unmatched}")
    print("=" * 60)

    print()

    if matched > 0:

        print(
            "✅ FDA Matcher ha trovato almeno "
            "un target reale."
        )

    else:

        print(
            "⚠️ Nessuna FDA news reale è stata "
            "associata alla watchlist."
        )

    print()
    print(
        "Questo test è diagnostico: "
        "non modifica il comportamento del Radar."
    )


if __name__ == "__main__":
    main()