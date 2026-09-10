"""Tests for ClinicalTrials.gov historical pagination."""
from datetime import date

from scanner.historical_clinical_trials import _fetch_studies


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []
        self.payloads = [
            {
                "studies": [
                    {"protocolSection": {"identificationModule": {"nctId": "NCT00000001"}}},
                    {"protocolSection": {"identificationModule": {"nctId": "NCT00000002"}}},
                ],
                "nextPageToken": "PAGE_2",
            },
            {
                "studies": [
                    {"protocolSection": {"identificationModule": {"nctId": "NCT00000003"}}},
                    {"protocolSection": {"identificationModule": {"nctId": "NCT00000004"}}},
                ],
            },
        ]

    def get(self, url, params, timeout):
        self.calls.append((url, dict(params), timeout))
        return FakeResponse(self.payloads[len(self.calls) - 1])


def test_fetch_studies_follows_next_page_token():
    session = FakeSession()
    studies = _fetch_studies(session, "example", 10)

    ids = [
        study["protocolSection"]["identificationModule"]["nctId"]
        for study in studies
    ]
    assert ids == [
        "NCT00000001",
        "NCT00000002",
        "NCT00000003",
        "NCT00000004",
    ]
    assert len(session.calls) == 2
    assert session.calls[0][1]["pageSize"] == 10
    assert "pageToken" not in session.calls[0][1]
    assert session.calls[1][1]["pageToken"] == "PAGE_2"


def test_fetch_studies_respects_cap():
    session = FakeSession()
    studies = _fetch_studies(session, "example", 3)

    assert len(studies) == 3
    assert len(session.calls) == 2


if __name__ == "__main__":
    test_fetch_studies_follows_next_page_token()
    test_fetch_studies_respects_cap()
    print("Historical ClinicalTrials.gov pagination tests passed")
