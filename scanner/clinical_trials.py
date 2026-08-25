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

    sponsor = protocol.get(
        "sponsorCollaboratorsModule", {}
    )

    conditions = protocol.get(
        "conditionsModule", {}
    )

    arms = protocol.get(
        "armsInterventionsModule", {}
    )

    return {
        "nct_id": identification.get("nctId"),

        "title": identification.get(
            "briefTitle"
        ),

        "official_title": identification.get(
            "officialTitle"
        ),

        "status": status.get(
            "overallStatus"
        ),

        "last_update": status.get(
            "lastUpdatePostDateStruct", {}
        ).get("date"),

        "start_date": status.get(
            "startDateStruct", {}
        ).get("date"),

        "completion_date": status.get(
            "completionDateStruct", {}
        ).get("date"),

        "study_type": design.get(
            "studyType"
        ),

        "phases": design.get(
            "phases", []
        ),

        "enrollment": design.get(
            "enrollmentInfo", {}
        ).get("count"),

        "enrollment_type": design.get(
            "enrollmentInfo", {}
        ).get("type"),

        "sponsor": sponsor.get(
            "leadSponsor", {}
        ).get("name"),

        "conditions": conditions.get(
            "conditions", []
        ),

        "interventions": [
            intervention.get("name")
            for intervention in arms.get(
                "interventions", []
            )
            if intervention.get("name")
        ]
    }


def search_program(program):
    studies = search_trials(program)

    return [
        extract_trial_info(study)
        for study in studies
    ]
