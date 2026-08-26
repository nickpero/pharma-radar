"""
Pharma Radar — Catalyst Classification

Classifica le modifiche rilevate nei trial clinici.
Non assegna ancora un investment score.
"""


HIGH_IMPACT_FIELDS = {
    "status",
    "start_date",
    "completion_date",
    "primary_completion_date",
    "enrollment",
    "enrollment_type",
    "phases",
    "official_title",
    "title",
}


def classify_change(field, old_value, new_value):
    """
    Classifica una singola modifica di un trial.
    """

    field = field.lower()

    # -----------------------------
    # STATUS
    # -----------------------------

    if field == "status":
        return classify_status_change(
            old_value,
            new_value
        )

    # -----------------------------
    # DATE
    # -----------------------------

    if field in {
        "start_date",
        "completion_date",
        "primary_completion_date",
    }:
        return {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # -----------------------------
    # ENROLLMENT
    # -----------------------------

    if field in {
        "enrollment",
        "enrollment_type",
    }:
        return {
            "type": "ENROLLMENT_CHANGE",
            "severity": "MEDIUM",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # -----------------------------
    # PHASE
    # -----------------------------

    if field == "phases":
        return {
            "type": "PHASE_CHANGE",
            "severity": "HIGH",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # -----------------------------
    # TITLE / PROTOCOL
    # -----------------------------

    if field in {
        "title",
        "official_title",
    }:
        return {
            "type": "PROTOCOL_CHANGE",
            "severity": "HIGH",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # -----------------------------
    # GENERIC CHANGE
    # -----------------------------

    return {
        "type": "FIELD_CHANGE",
        "severity": "LOW",
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
    }


def classify_status_change(old_status, new_status):
    """
    Classifica il passaggio da uno status ClinicalTrials.gov
    ad un altro.
    """

    old_status = str(
        old_status or ""
    ).upper()

    new_status = str(
        new_status or ""
    ).upper()

    # -----------------------------
    # POSITIVE / POTENTIALLY POSITIVE
    # -----------------------------

    positive_transitions = {
        (
            "NOT_YET_RECRUITING",
            "RECRUITING",
        ),
        (
            "NOT_YET_RECRUITING",
            "ENROLLING_BY_INVITATION",
        ),
        (
            "RECRUITING",
            "ENROLLING_BY_INVITATION",
        ),
    }

    if (
        old_status,
        new_status
    ) in positive_transitions:

        return {
            "type": "STATUS_CHANGE",
            "severity": "MEDIUM",
            "direction": "POSITIVE",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # -----------------------------
    # TRIAL COMPLETION
    # -----------------------------

    completion_statuses = {
        "COMPLETED"
    }

    if new_status in completion_statuses:

        return {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "CATALYST",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # -----------------------------
    # TERMINATED / SUSPENDED
    # -----------------------------

    negative_statuses = {
        "TERMINATED",
        "SUSPENDED",
        "WITHDRAWN",
    }

    if new_status in negative_statuses:

        return {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "NEGATIVE",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # -----------------------------
    # ACTIVE NOT RECRUITING
    # -----------------------------

    if new_status == "ACTIVE_NOT_RECRUITING":

        return {
            "type": "STATUS_CHANGE",
            "severity": "MEDIUM",
            "direction": "NEUTRAL",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # -----------------------------
    # GENERIC STATUS CHANGE
    # -----------------------------

    return {
        "type": "STATUS_CHANGE",
        "severity": "MEDIUM",
        "direction": "UNKNOWN",
        "field": "status",
        "old_value": old_status,
        "new_value": new_status,
    }


def classify_trial_changes(changes):
    """
    Trasforma il dizionario prodotto da detect_changes()
    in una lista di eventi Catalyst.
    """

    events = []

    for field, values in changes.items():

        old_value = values.get("old")
        new_value = values.get("new")

        event = classify_change(
            field,
            old_value,
            new_value
        )

        events.append(event)

    return events
