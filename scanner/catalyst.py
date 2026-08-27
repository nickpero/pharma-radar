from datetime import datetime


# ============================================================
# PHARMA RADAR — CATALYST ENGINE
# ============================================================


def normalize(value):
    if value is None:
        return None

    return str(value).strip().upper()


def parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    try:
        return datetime.strptime(
            str(value),
            "%Y-%m-%d",
        ).date()

    except (ValueError, TypeError):
        return None


# ============================================================
# STATUS
# ============================================================

def status_direction(old_status, new_status):

    old_status = normalize(old_status)
    new_status = normalize(new_status)

    if (
        new_status == "COMPLETED"
        and old_status != "COMPLETED"
    ):
        return "POSITIVE"

    if new_status in {
        "TERMINATED",
        "WITHDRAWN",
        "SUSPENDED",
    }:
        return "NEGATIVE"

    if (
        new_status == "RECRUITING"
        and old_status in {
            "NOT_YET_RECRUITING",
            "SUSPENDED",
        }
    ):
        return "POSITIVE"

    return "UNKNOWN"


def classify_status_change(
    old_status,
    new_status,
):

    old_status = normalize(old_status)
    new_status = normalize(new_status)

    direction = status_direction(
        old_status,
        new_status,
    )

    if new_status == "COMPLETED":
        subtype = "TRIAL_COMPLETED"

    elif new_status == "TERMINATED":
        subtype = "TRIAL_TERMINATED"

    elif new_status == "SUSPENDED":
        subtype = "TRIAL_SUSPENDED"

    elif new_status == "WITHDRAWN":
        subtype = "TRIAL_WITHDRAWN"

    elif new_status == "RECRUITING":
        subtype = "TRIAL_RECRUITING"

    else:
        subtype = "STATUS_CHANGE"

    if subtype in {
        "TRIAL_COMPLETED",
        "TRIAL_TERMINATED",
        "TRIAL_SUSPENDED",
        "TRIAL_WITHDRAWN",
    }:
        severity = "HIGH"
    else:
        severity = "MEDIUM"

    return {
        "type": "STATUS_CHANGE",
        "subtype": subtype,
        "old_value": old_status,
        "new_value": new_status,
        "direction": direction,
        "severity": severity,
    }


# ============================================================
# DATE CHANGES
# ============================================================

def classify_date_change(
    old_date,
    new_date,
):

    old = parse_date(old_date)
    new = parse_date(new_date)

    if not old or not new:
        return None

    if old == new:
        return None

    if new < old:
        subtype = "DATE_ACCELERATED"
        direction = "POSITIVE"
    else:
        subtype = "DATE_DELAYED"
        direction = "NEGATIVE"

    return {
        "type": "DATE_CHANGE",
        "subtype": subtype,
        "old_value": old_date,
        "new_value": new_date,
        "direction": direction,
        "event_date": new.isoformat(),
        "severity": "HIGH",
    }


# ============================================================
# ENROLLMENT
# ============================================================

def classify_enrollment_change(
    old_enrollment,
    new_enrollment,
):

    if (
        old_enrollment is None
        or new_enrollment is None
    ):
        return None

    try:
        old_value = int(old_enrollment)
        new_value = int(new_enrollment)

    except (ValueError, TypeError):
        return None

    if new_value <= old_value:
        return None

    return {
        "type": "ENROLLMENT_CHANGE",
        "subtype": "ENROLLMENT_INCREASED",
        "old_value": old_value,
        "new_value": new_value,
        "direction": "UNKNOWN",
        "severity": "MEDIUM",
    }


# ============================================================
# GENERIC FIELD CHANGE
# ============================================================

def classify_field_change(
    field,
    old_value,
    new_value,
):

    if old_value == new_value:
        return None

    return {
        "type": "FIELD_CHANGE",
        "subtype": field,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "direction": "UNKNOWN",
        "severity": "LOW",
    }


# ============================================================
# TRIAL CHANGE CLASSIFICATION
# ============================================================

def classify_trial_changes(changes):

    events = []

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = changes.get(
        "status",
        {},
    )

    old_status = status.get("old")
    new_status = status.get("new")

    if (
        old_status is not None
        and new_status is not None
        and old_status != new_status
    ):

        events.append(
            classify_status_change(
                old_status,
                new_status,
            )
        )

    # --------------------------------------------------------
    # PRIMARY COMPLETION DATE
    # --------------------------------------------------------

    primary_date = changes.get(
        "primary_completion_date",
        {},
    )

    date_event = classify_date_change(
        primary_date.get("old"),
        primary_date.get("new"),
    )

    if date_event:

        date_event["field"] = (
            "primary_completion_date"
        )

        events.append(date_event)

    # --------------------------------------------------------
    # STUDY COMPLETION DATE
    # --------------------------------------------------------

    study_date = changes.get(
        "study_completion_date",
        {},
    )

    date_event = classify_date_change(
        study_date.get("old"),
        study_date.get("new"),
    )

    if date_event:

        date_event["field"] = (
            "study_completion_date"
        )

        events.append(date_event)

    # --------------------------------------------------------
    # GENERIC COMPLETION DATE
    # --------------------------------------------------------
    #
    # Compatibility with older integration data.
    # --------------------------------------------------------

    completion_date = changes.get(
        "completion_date",
        {},
    )

    date_event = classify_date_change(
        completion_date.get("old"),
        completion_date.get("new"),
    )

    if date_event:

        date_event["field"] = (
            "completion_date"
        )

        events.append(date_event)

    # --------------------------------------------------------
    # ENROLLMENT
    # --------------------------------------------------------

    enrollment = changes.get(
        "enrollment",
        {},
    )

    enrollment_event = (
        classify_enrollment_change(
            enrollment.get("old"),
            enrollment.get("new"),
        )
    )

    if enrollment_event:
        events.append(enrollment_event)

    # --------------------------------------------------------
    # OTHER FIELDS
    # --------------------------------------------------------

    ignored_fields = {
        "status",
        "primary_completion_date",
        "study_completion_date",
        "completion_date",
        "enrollment",
    }

    for field, change in changes.items():

        if field in ignored_fields:
            continue

        if not isinstance(change, dict):
            continue

        old_value = change.get("old")
        new_value = change.get("new")

        event = classify_field_change(
            field,
            old_value,
            new_value,
        )

        if event:
            events.append(event)

    return events


# ============================================================
# EVENT ENRICHMENT
# ============================================================

def enrich_events(
    events,
    trial=None,
):

    trial = trial or {}

    phase = trial.get("phase")

    for event in events:

        event["phase"] = phase

        if event.get("event_date") is None:

            event["event_date"] = (
                trial.get(
                    "primary_completion_date"
                )
                or trial.get(
                    "completion_date"
                )
            )

    return events
