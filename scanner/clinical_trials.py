import requests

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def search_trials(query: str, page_size: int = 20):
    response = requests.get(
        BASE_URL,
        params={"query.term": query, "pageSize": page_size, "format": "json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("studies", [])


def extract_trial_info(study):
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})
    conditions = protocol.get("conditionsModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    outcomes = protocol.get("outcomesModule", {})

    primary_outcomes = []
    for outcome in outcomes.get("primaryOutcomes", []) or []:
        if isinstance(outcome, dict):
            primary_outcomes.append({
                "measure": outcome.get("measure"),
                "description": outcome.get("description"),
                "time_frame": outcome.get("timeFrame"),
            })

    return {
        "nct_id": identification.get("nctId"),
        "title": identification.get("briefTitle"),
        "official_title": identification.get("officialTitle"),
        "status": status.get("overallStatus"),
        "last_update": (status.get("lastUpdatePostDateStruct") or {}).get("date"),
        "last_update_submitted": status.get("lastUpdateSubmitDate"),
        "start_date": (status.get("startDateStruct") or {}).get("date"),
        "primary_completion_date": (status.get("primaryCompletionDateStruct") or {}).get("date"),
        "completion_date": (status.get("completionDateStruct") or {}).get("date"),
        "results_posted_date": (((study.get("resultsSection") or {}).get("statusModule") or {})
                                .get("resultsFirstPostDateStruct") or {}).get("date"),
        "has_results": bool(study.get("hasResults", False)),
        "primary_outcomes": primary_outcomes,
        "study_type": design.get("studyType"),
        "phases": design.get("phases", []),
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "enrollment_type": (design.get("enrollmentInfo") or {}).get("type"),
        "sponsor": (sponsor.get("leadSponsor") or {}).get("name"),
        "conditions": conditions.get("conditions", []),
        "interventions": [
            intervention.get("name")
            for intervention in arms.get("interventions", [])
            if intervention.get("name")
        ],
    }


def search_program(program):
    return [extract_trial_info(study) for study in search_trials(program)]
