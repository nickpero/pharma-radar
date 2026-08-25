def normalize(text):
    if not text:
        return ""

    return (
        text.lower()
        .replace(",", " ")
        .replace(".", " ")
        .replace("-", " ")
        .strip()
    )


def sponsor_matches_company(trial, company):
    sponsor = normalize(trial.get("sponsor"))

    company_name = normalize(company.get("company"))

    if not sponsor or not company_name:
        return False

    company_words = [
        word
        for word in company_name.split()
        if len(word) >= 4
    ]

    return any(
        word in sponsor
        for word in company_words
    )


def program_matches_trial(trial, program):
    program = normalize(program)

    title = normalize(trial.get("title"))
    official_title = normalize(
        trial.get("official_title")
    )

    interventions = [
        normalize(name)
        for name in trial.get("interventions", [])
    ]

    if program in title:
        return True

    if program in official_title:
        return True

    if any(program in intervention for intervention in interventions):
        return True

    return False


def is_relevant(trial, company, program):
    sponsor_match = sponsor_matches_company(
        trial,
        company
    )

    program_match = program_matches_trial(
        trial,
        program
    )

    return sponsor_match or program_match
