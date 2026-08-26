"""
Pharma Radar — Catalyst Classification Engine

Classifica le modifiche dei trial clinici in base a:
- tipo di evento
- severità clinica
- direzione potenziale
- anticipo/ritardo delle date
"""

from datetime import date


# ============================================
# STATUS TRANSITIONS
# ============================================

POSITIVE_STATUS_TRANSITIONS = {
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


NEGATIVE_STATUS_TRANSITIONS = {
    "TERMINATED",
    "SUSPENDED",
    "WITHDRAWN",
}


# ============================================
# DATE HELPERS
# ============================================

def parse_date(value):
    """
    Converte una data YYYY-MM-DD in un oggetto date.

    Restituisce None se il valore non è valido.
    """

    if not value:
        return None

    try:
        return date.fromisoformat(
            str(value)
        )
    except (
        ValueError,
        TypeError
    ):
        return None


def classify_date_change(
    field,
    old_value,
    new_value
):
    """
    Determina se una modifica di data
    rappresenta un anticipo o un ritardo.
    """

    old_date = parse_date(
        old_value
    )

    new_date = parse_date(
        new_value
    )

    # ----------------------------------------
    # Data non interpretabile
    # ----------------------------------------

    if not old_date or not new_date:

        return {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "UNKNOWN",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # ----------------------------------------
    # Anticipo
    # ----------------------------------------

    if new_date < old_date:

        days = (
            old_date - new_date
        ).days

        return {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "POSITIVE",
            "subtype": "DATE_ACCELERATED",
            "days_changed": days,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # ----------------------------------------
    # Ritardo
    # ----------------------------------------

    if new_date > old_date:

        days = (
            new_date - old_date
        ).days

        return {
            "type": "DATE_CHANGE",
            "severity": "HIGH",
            "direction": "NEGATIVE",
            "subtype": "DATE_DELAYED",
            "days_changed": days,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # ----------------------------------------
    # Nessuna variazione reale
    # ----------------------------------------

    return {
        "type": "DATE_CHANGE",
        "severity": "LOW",
        "direction": "NEUTRAL",
        "subtype": "DATE_UNCHANGED",
        "days_changed": 0,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
    }


# ============================================
# STATUS CLASSIFICATION
# ============================================

def classify_status_change(
    old_status,
    new_status
):
    """
    Classifica un cambio di status.
    """

    old_status = str(
        old_status or ""
    ).upper()

    new_status = str(
        new_status or ""
    ).upper()

    # ----------------------------------------
    # Positive transition
    # ----------------------------------------

    if (
        old_status,
        new_status
    ) in POSITIVE_STATUS_TRANSITIONS:

        return {
            "type": "STATUS_CHANGE",
            "severity": "MEDIUM",
            "direction": "POSITIVE",
            "subtype": "TRIAL_PROGRESS",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # ----------------------------------------
    # Trial completed
    # ----------------------------------------

    if new_status == "COMPLETED":

        return {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "CATALYST",
            "subtype": "TRIAL_COMPLETED",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # ----------------------------------------
    # Negative status
    # ----------------------------------------

    if new_status in NEGATIVE_STATUS_TRANSITIONS:

        return {
            "type": "STATUS_CHANGE",
            "severity": "HIGH",
            "direction": "NEGATIVE",
            "subtype": "TRIAL_STOPPED",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # ----------------------------------------
    # Active not recruiting
    # ----------------------------------------

    if new_status == "ACTIVE_NOT_RECRUITING":

        return {
            "type": "STATUS_CHANGE",
            "severity": "MEDIUM",
            "direction": "NEUTRAL",
            "subtype": "RECRUITMENT_CLOSED",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # ----------------------------------------
    # Recruiting
    # ----------------------------------------

    if new_status == "RECRUITING":

        return {
            "type": "STATUS_CHANGE",
            "severity": "MEDIUM",
            "direction": "POSITIVE",
            "subtype": "RECRUITING_STARTED",
            "field": "status",
            "old_value": old_status,
            "new_value": new_status,
        }

    # ----------------------------------------
    # Generic status change
    # ----------------------------------------

    return {
        "type": "STATUS_CHANGE",
        "severity": "MEDIUM",
        "direction": "UNKNOWN",
        "subtype": "STATUS_UPDATED",
        "field": "status",
        "old_value": old_status,
        "new_value": new_status,
    }


# ============================================
# GENERIC FIELD CLASSIFICATION
# ============================================

def classify_change(
    field,
    old_value,
    new_value
):
    """
    Classifica una singola modifica.
    """

    field = str(
        field or ""
    ).lower()

    # ----------------------------------------
    # STATUS
    # ----------------------------------------

    if field == "status":

        return classify_status_change(
            old_value,
            new_value
        )

    # ----------------------------------------
    # DATES
    # ----------------------------------------

    if field in {
        "start_date",
        "completion_date",
        "primary_completion_date",
    }:

        return classify_date_change(
            field,
            old_value,
            new_value
        )

    # ----------------------------------------
    # ENROLLMENT
    # ----------------------------------------

    if field == "enrollment":

        return {
            "type": "ENROLLMENT_CHANGE",
            "severity": "MEDIUM",
            "direction": "UNKNOWN",
            "subtype": "ENROLLMENT_UPDATED",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # ----------------------------------------
    # ENROLLMENT TYPE
    # ----------------------------------------

    if field == "enrollment_type":

        return {
            "type": "ENROLLMENT_CHANGE",
            "severity": "LOW",
            "direction": "UNKNOWN",
            "subtype": "ENROLLMENT_TYPE_UPDATED",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # ----------------------------------------
    # PHASE
    # ----------------------------------------

    if field == "phases":

        return {
            "type": "PHASE_CHANGE",
            "severity": "HIGH",
            "direction": "POSITIVE",
            "subtype": "PHASE_UPDATED",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # ----------------------------------------
    # PROTOCOL / TITLE
    # ----------------------------------------

    if field in {
        "title",
        "official_title",
    }:

        return {
            "type": "PROTOCOL_CHANGE",
            "severity": "HIGH",
            "direction": "UNKNOWN",
            "subtype": "PROTOCOL_UPDATED",
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }

    # ----------------------------------------
    # GENERIC
    # ----------------------------------------

    return {
        "type": "FIELD_CHANGE",
        "severity": "LOW",
        "direction": "UNKNOWN",
        "subtype": "FIELD_UPDATED",
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
    }


# ============================================
# MULTIPLE CHANGES
# ============================================

def classify_trial_changes(changes):
    """
    Trasforma tutte le modifiche di un trial
    in eventi Catalyst.
    """

    events = []

    for field, values in changes.items():

        if not isinstance(
            values,
            dict
        ):
            continue

        old_value = values.get(
            "old"
        )

        new_value = values.get(
            "new"
        )

        event = classify_change(
            field,
            old_value,
            new_value
        )

        events.append(
            event
        )

    return events
