import json
from pathlib import Path


ALIASES_FILE = Path("data/aliases.json")


def load_aliases():
    if not ALIASES_FILE.exists():
        return {}

    with open(ALIASES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize(text):
    if not text:
        return ""

    return (
        text.lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )


def contains_alias(text, aliases):
    normalized_text = normalize(text)

    for alias in aliases:
        normalized_alias = normalize(alias)

        if normalized_alias and normalized_alias in normalized_text:
            return True

    return False


def sponsor_matches_company(
    trial,
    company,
    company_aliases
):
    sponsor = trial.get("sponsor", "")

    aliases = [
        company.get("company", "")
    ]

    aliases.extend(company_aliases)

    return contains_alias(
        sponsor,
        aliases
    )


def program_matches_trial(
    trial,
    program,
    program_aliases
):
    aliases = [
        program
    ]

    aliases.extend(program_aliases)

    title = trial.get("title", "")
    official_title = trial.get(
        "official_title",
        ""
    )

    interventions = trial.get(
        "interventions",
        []
    )

    if contains_alias(title, aliases):
        return True

    if contains_alias(
        official_title,
        aliases
    ):
        return True

    for intervention in interventions:
        if contains_alias(
            intervention,
            aliases
        ):
            return True

    return False


def is_relevant(
    trial,
    company,
    ticker,
    program
):
    aliases = load_aliases()

    company_config = aliases.get(
        ticker,
        {}
    )

    company_aliases = company_config.get(
        "company_aliases",
        []
    )

    program_config = company_config.get(
        "program_aliases",
        {}
    )

    program_aliases = program_config.get(
        program,
        []
    )

    sponsor_match = sponsor_matches_company(
        trial,
        company,
        company_aliases
    )

    program_match = program_matches_trial(
        trial,
        program,
        program_aliases
    )

    return sponsor_match or program_match
