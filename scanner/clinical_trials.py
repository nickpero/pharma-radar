import requests


BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def search_trials(query: str, page_size: int = 20):
    params = {
        "query.term": query,
        "pageSize": page_size,
        "format": "json"
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    return data.get("studies", [])


def extract_trial_info(study):
    protocol = study.get("protocolSection", {})

    identification = protocol.get(
        "identificationModule", {}
    )

    status = protocol.get(
        "statusModule", {}
    )

    design = protocol.get(
        "designModule", {}
    )

    return {
        "nct_id": identification.get("nctId"),
        "title": identification.get("briefTitle"),
        "status": status.get("overallStatus"),
        "start_date": (
            status.get("startDateStruct", {})
            .get("date")
        ),
        "completion_date": (
            status.get("completionDateStruct", {})
            .get("date")
        ),
        "study_type": design.get("studyType")
    }


def search_program(program):
    studies = search_trials(program)

    return [
        extract_trial_info(study)
        for study in studies
    ]
