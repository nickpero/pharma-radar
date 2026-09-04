"""
Pharma Radar — FDA Matcher Controlled Tests

Test controllati del collegamento:

FDA News → Watchlist → Ticker / Program

Questi test verificano sia i match positivi
sia i falsi positivi più pericolosi.
"""

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


def make_news(title):
    return {
        "title": title,
        "summary": "",
        "description": "",
        "content": "",
        "body": "",
        "text": "",
        "article_text": "",
        "full_text": "",
        "drug": "",
        "drug_name": "",
        "program": "",
        "program_name": "",
        "company": "",
        "company_name": "",
        "sponsor": "",
        "manufacturer": "",
        "applicant": "",
        "raw_text": "",
    }


def assert_match(title, expected_ticker, expected_program):
    news = make_news(title)

    result = identify_fda_target(
        news,
        WATCHLIST,
    )

    assert result is not None, (
        f"Expected match for {expected_ticker}, "
        f"but matcher returned None.\n"
        f"Title: {title}"
    )

    assert result.get("ticker") == expected_ticker, (
        f"Wrong ticker.\n"
        f"Expected: {expected_ticker}\n"
        f"Got: {result.get('ticker')}\n"
        f"Title: {title}"
    )

    assert result.get("program") == expected_program, (
        f"Wrong program.\n"
        f"Expected: {expected_program}\n"
        f"Got: {result.get('program')}\n"
        f"Title: {title}"
    )

    return result


def assert_no_match(title):
    news = make_news(title)

    result = identify_fda_target(
        news,
        WATCHLIST,
    )

    assert result is None, (
        f"Unexpected FDA match.\n"
        f"Got: {result}\n"
        f"Title: {title}"
    )


def test_known_program_matches():
    """
    Programmi canonici presenti nella watchlist.
    """

    cases = [
        (
            "FDA approves VYVGART for a new indication",
            "ARGX",
            "VYVGART",
        ),
        (
            "FDA approves zidesamtinib for ROS1-positive cancer",
            "NUVL",
            "zidesamtinib",
        ),
        (
            "FDA decision announced for AMT-130",
            "QURE",
            "AMT-130",
        ),
        (
            "FDA provides regulatory update on zorevunersen",
            "STOK",
            "zorevunersen",
        ),
        (
            "FDA decision on ivonescimab",
            "SMMT",
            "ivonescimab",
        ),
        (
            "FDA update on deramiocel",
            "CAPR",
            "deramiocel",
        ),
        (
            "FDA announces decision concerning molgramostim",
            "SVRA",
            "molgramostim",
        ),
        (
            "FDA update regarding zanidatamab",
            "ZYME",
            "zanidatamab",
        ),
        (
            "FDA regulatory update on deucrictibant",
            "PHVS",
            "deucrictibant",
        ),
        (
            "FDA update on delpacibart",
            "RNA",
            "delpacibart",
        ),
    ]

    for title, ticker, program in cases:
        result = assert_match(
            title,
            ticker,
            program,
        )

        print(
            f"✅ {ticker} — {program} "
            f"(match_type={result.get('match_type')}, "
            f"confidence={result.get('confidence')})"
        )


def test_alias_matches():
    """
    Verifica alcuni alias farmacologici importanti.
    """

    cases = [
        (
            "FDA update on efgartigimod",
            "ARGX",
            "VYVGART",
        ),
        (
            "FDA update on efgartigimod alfa",
            "ARGX",
            "VYVGART",
        ),
        (
            "FDA update on CAP-1002",
            "CAPR",
            "deramiocel",
        ),
        (
            "FDA update on CAP1002",
            "CAPR",
            "deramiocel",
        ),
        (
            "FDA update on STK-001",
            "STOK",
            "zorevunersen",
        ),
        (
            "FDA update on AMT130",
            "QURE",
            "AMT-130",
        ),
        (
            "FDA update on AK112",
            "SMMT",
            "ivonescimab",
        ),
    ]

    for title, ticker, program in cases:
        result = assert_match(
            title,
            ticker,
            program,
        )

        print(
            f"✅ ALIAS {ticker} — {program} "
            f"(match_type={result.get('match_type')}, "
            f"confidence={result.get('confidence')})"
        )


def test_no_false_positive_from_ticker_only():
    """
    Un ticker scritto casualmente nel testo non deve
    generare automaticamente un match di programma.

    Questo protegge in particolare il caso RARE / UX111
    che aveva generato un falso positivo.
    """

    cases = [
        "Market update: RARE sector activity increases today",
        "Analyst commentary mentions RARE biotechnology stocks",
        "Trading volume increased for RARE",
        "General biotech market news mentioning RARE",
    ]

    for title in cases:
        assert_no_match(title)
        print(f"✅ NO FALSE POSITIVE — {title}")


def test_generic_fda_news_does_not_match():
    """
    Una FDA news generica, senza riferimenti alla watchlist,
    non deve essere associata a nessun ticker.
    """

    cases = [
        "FDA announces new regulatory initiative",
        "FDA updates general drug development guidance",
        "FDA announces public health initiative",
        "FDA publishes new regulatory framework",
    ]

    for title in cases:
        assert_no_match(title)
        print(f"✅ GENERIC NEWS IGNORED — {title}")


def test_wrong_program_does_not_match():
    """
    Un programma non presente nella watchlist non deve
    essere attribuito arbitrariamente a un'azienda.
    """

    cases = [
        "FDA approves completelyunknowncompound",
        "FDA decision announced for UNKNOWN-999",
        "FDA update on hypothetical-drug-123",
    ]

    for title in cases:
        assert_no_match(title)
        print(f"✅ UNKNOWN PROGRAM IGNORED — {title}")


def main():
    print("=" * 60)
    print("========== FDA MATCHER CONTROLLED TEST ==========")
    print("=" * 60)

    print("\n[1] Known program matches")
    test_known_program_matches()

    print("\n[2] Alias matches")
    test_alias_matches()

    print("\n[3] False-positive protection")
    test_no_false_positive_from_ticker_only()

    print("\n[4] Generic FDA news")
    test_generic_fda_news_does_not_match()

    print("\n[5] Unknown programs")
    test_wrong_program_does_not_match()

    print("\n" + "=" * 60)
    print("✅ FDA MATCHER CONTROLLED TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()