from scanner.fda_matcher import (
    normalize,
    contains_alias,
    get_match_confidence,
    match_company,
    match_program,
    match_fda_news,
    get_best_match,
    identify_fda_target,
    match_fda_news_batch,
    filter_matched_fda_news,
)


# ============================================
# TEST NORMALIZATION
# ============================================

def test_normalize():

    assert normalize(
        "Capricor Therapeutics, Inc."
    ) == "capricor therapeutics inc"

    assert normalize(
        "CAP-1002"
    ) == "cap 1002"


# ============================================
# TEST ALIAS
# ============================================

def test_contains_alias():

    text = (
        "The study of deramiocel "
        "was announced today."
    )

    assert contains_alias(
        text,
        "deramiocel"
    )

    assert not contains_alias(
        text,
        "molgramostim"
    )


# ============================================
# TEST CONFIDENCE
# ============================================

def test_match_confidence():

    assert (
        get_match_confidence(
            "COMPANY_AND_PROGRAM"
        )
        == "HIGH"
    )

    assert (
        get_match_confidence(
            "PROGRAM"
        )
        == "HIGH"
    )

    assert (
        get_match_confidence(
            "COMPANY"
        )
        == "MEDIUM"
    )

    assert (
        get_match_confidence(
            "UNKNOWN"
        )
        == "LOW"
    )


# ============================================
# TEST COMPANY MATCH
# ============================================

def test_company_match():

    news = {
        "title": (
            "FDA reviews Capricor Therapeutics "
            "treatment"
        ),
        "summary": "",
    }

    company = {
        "company": "Capricor Therapeutics"
    }

    matches = match_company(
        news,
        "CAPR",
        company
    )

    assert matches


# ============================================
# TEST PROGRAM MATCH
# ============================================

def test_program_match():

    news = {
        "title": (
            "FDA updates review of deramiocel"
        ),
        "summary": (
            "The treatment is also known "
            "as CAP-1002."
        ),
    }

    matches = match_program(
        news,
        "CAPR",
        "deramiocel"
    )

    assert matches

    assert (
        "deramiocel"
        in matches
        or "CAP-1002"
        in matches
    )


# ============================================
# TEST COMPANY + PROGRAM
# ============================================

def test_company_and_program_match():

    watchlist = {

        "CAPR": {

            "company": (
                "Capricor Therapeutics"
            ),

            "programs": [
                "deramiocel",
            ],
        },
    }

    news = {
        "source": "FDA",
        "title": (
            "FDA updates review of "
            "Capricor Therapeutics "
            "deramiocel"
        ),
        "summary": (
            "The treatment is also known "
            "as CAP-1002."
        ),
    }

    matches = match_fda_news(
        news,
        watchlist
    )

    assert len(matches) == 1

    match = matches[0]

    assert match["ticker"] == "CAPR"
    assert (
        match["program"]
        == "deramiocel"
    )

    assert (
        match["match_type"]
        == "COMPANY_AND_PROGRAM"
    )

    assert (
        match["confidence"]
        == "HIGH"
    )


# ============================================
# TEST PROGRAM-ONLY MATCH
# ============================================

def test_program_only_match():

    watchlist = {

        "CAPR": {

            "company": (
                "Capricor Therapeutics"
            ),

            "programs": [
                "deramiocel",
            ],
        },
    }

    news = {
        "source": "FDA",
        "title": (
            "FDA announces update "
            "for deramiocel"
        ),
        "summary": "",
    }

    matches = match_fda_news(
        news,
        watchlist
    )

    assert len(matches) == 1

    assert (
        matches[0]["match_type"]
        == "PROGRAM"
    )

    assert (
        matches[0]["confidence"]
        == "HIGH"
    )


# ============================================
# TEST COMPANY-ONLY MATCH
# ============================================

def test_company_only_match():

    watchlist = {

        "CAPR": {

            "company": (
                "Capricor Therapeutics"
            ),

            "programs": [
                "deramiocel",
            ],
        },
    }

    news = {
        "source": "FDA",
        "title": (
            "FDA updates Capricor Therapeutics"
        ),
        "summary": (
            "The agency issued a new update."
        ),
    }

    matches = match_fda_news(
        news,
        watchlist
    )

    assert len(matches) == 1

    assert (
        matches[0]["match_type"]
        == "COMPANY"
    )

    assert (
        matches[0]["confidence"]
        == "MEDIUM"
    )


# ============================================
# TEST NO MATCH
# ============================================

def test_no_match():

    watchlist = {

        "CAPR": {

            "company": (
                "Capricor Therapeutics"
            ),

            "programs": [
                "deramiocel",
            ],
        },
    }

    news = {
        "source": "FDA",
        "title": (
            "FDA approves unrelated treatment"
        ),
        "summary": "",
    }

    matches = match_fda_news(
        news,
        watchlist
    )

    assert matches == []


# ============================================
# TEST BEST MATCH
# ============================================

def test_best_match():

    matches = [

        {
            "match_type": "COMPANY",
            "ticker": "CAPR",
        },

        {
            "match_type": "PROGRAM",
            "ticker": "CAPR",
        },

        {
            "match_type": (
                "COMPANY_AND_PROGRAM"
            ),
            "ticker": "CAPR",
        },
    ]

    best = get_best_match(
        matches
    )

    assert best is not None

    assert (
        best["match_type"]
        == "COMPANY_AND_PROGRAM"
    )


# ============================================
# TEST IDENTIFY TARGET
# ============================================

def test_identify_fda_target():

    watchlist = {

        "CAPR": {

            "company": (
                "Capricor Therapeutics"
            ),

            "programs": [
                "deramiocel",
            ],
        },
    }

    news = {
        "source": "FDA",
        "title": (
            "FDA updates Capricor "
            "deramiocel"
        ),
        "summary": "",
    }

    target = identify_fda_target(
        news,
        watchlist
    )

    assert target is not None
    assert target["ticker"] == "CAPR"
    assert target["program"] == "deramiocel"
    assert target["confidence"] == "HIGH"


# ============================================
# TEST BATCH
# ============================================

def test_batch():

    watchlist = {

        "CAPR": {

            "company": (
                "Capricor Therapeutics"
            ),

            "programs": [
                "deramiocel",
            ],
        },
    }

    news = [

        {
            "source": "FDA",
            "title": (
                "FDA updates deramiocel"
            ),
            "summary": "",
        },

        {
            "source": "FDA",
            "title": (
                "FDA publishes unrelated news"
            ),
            "summary": "",
        },
    ]

    results = match_fda_news_batch(
        news,
        watchlist
    )

    assert len(results) == 2

    assert results[0]["matched"] is True
    assert results[1]["matched"] is False


# ============================================
# TEST FILTER
# ============================================

def test_filter_matched():

    watchlist = {

        "CAPR": {

            "company": (
                "Capricor Therapeutics"
            ),

            "programs": [
                "deramiocel",
            ],
        },
    }

    news = [

        {
            "source": "FDA",
            "title": (
                "FDA updates deramiocel"
            ),
            "summary": "",
        },

        {
            "source": "FDA",
            "title": (
                "FDA publishes unrelated news"
            ),
            "summary": "",
        },
    ]

    filtered = filter_matched_fda_news(
        news,
        watchlist
    )

    assert len(filtered) == 1

    assert (
        filtered[0]["best_match"]["ticker"]
        == "CAPR"
    )


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":

    test_normalize()
    test_contains_alias()
    test_match_confidence()
    test_company_match()
    test_program_match()
    test_company_and_program_match()
    test_program_only_match()
    test_company_only_match()
    test_no_match()
    test_best_match()
    test_identify_fda_target()
    test_batch()
    test_filter_matched()

    print(
        "✅ FDA Matcher tests passed"
    )