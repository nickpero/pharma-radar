from scanner.clinical_trials import extract_trial_info
from scanner.state import detect_changes


def _study():
    return {
        "hasResults": True,
        "protocolSection": {
            "identificationModule": {"nctId": "NCT12345678", "briefTitle": "Example study"},
            "statusModule": {
                "overallStatus": "COMPLETED",
                "lastUpdatePostDateStruct": {"date": "2026-10-29"},
                "lastUpdateSubmitDate": "2026-10-27",
                "primaryCompletionDateStruct": {"date": "2026-09-30"},
                "completionDateStruct": {"date": "2026-10-15"},
            },
            "designModule": {"studyType": "INTERVENTIONAL", "phases": ["PHASE3"],
                             "enrollmentInfo": {"count": 240, "type": "ACTUAL"}},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Example Bio"}},
            "conditionsModule": {"conditions": ["Cancer"]},
            "armsInterventionsModule": {"interventions": [{"name": "Drug X"}]},
            "outcomesModule": {"primaryOutcomes": [
                {"measure": "Overall survival", "description": "OS", "timeFrame": "24 months"}
            ]},
        },
        "resultsSection": {"statusModule": {"resultsFirstPostDateStruct": {"date": "2026-10-28"}}},
    }


def test_extract_trial_info_includes_high_value_registry_fields():
    trial = extract_trial_info(_study())
    assert trial["nct_id"] == "NCT12345678"
    assert trial["primary_completion_date"] == "2026-09-30"
    assert trial["results_posted_date"] == "2026-10-28"
    assert trial["has_results"] is True
    assert trial["primary_outcomes"] == [{
        "measure": "Overall survival", "description": "OS", "time_frame": "24 months"
    }]


def test_detect_changes_captures_completion_results_and_endpoint_edits():
    old = extract_trial_info(_study())
    new_payload = _study()
    new_payload["protocolSection"]["statusModule"]["primaryCompletionDateStruct"]["date"] = "2026-12-31"
    new_payload["protocolSection"]["outcomesModule"]["primaryOutcomes"][0]["measure"] = "Progression-free survival"
    new_payload["hasResults"] = False
    new = extract_trial_info(new_payload)
    changes = detect_changes(old, new)
    assert changes["primary_completion_date"] == {
        "old": "2026-09-30", "new": "2026-12-31"
    }
    assert changes["primary_outcomes"]["new"][0]["measure"] == "Progression-free survival"
    assert changes["has_results"] == {"old": True, "new": False}
