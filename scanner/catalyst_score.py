from datetime import datetime


# ============================================================
# PHARMA RADAR — CATALYST SCORING ENGINE
# ============================================================

# Score base per tipo di evento.
EVENT_SCORES = {
    "PRIMARY_ENDPOINT_MET": 100,
    "PRIMARY_ENDPOINT_FAILED": 100,
    "TOPLINE_RESULTS": 100,
    "FDA_APPROVAL": 100,
    "FDA_REJECTION": 100,
    "TRIAL_STOPPED_EFFICACY": 100,
    "TRIAL_STOPPED_SAFETY": 100,

    "TRIAL_COMPLETED": 90,
    "ENROLLMENT_COMPLETED": 85,
    "PHASE_3_STARTED": 85,

    "DATE_ACCELERATED": 80,
    "DATE_DELAYED": 80,

    "PHASE_2_STARTED": 70,
    "PHASE_1_STARTED": 60,

    "SECONDARY_ENDPOINT_MET": 65,
    "SECONDARY_ENDPOINT_FAILED": 75,

    "STATUS_CHANGE": 60,
    "OTHER": 20,
}


# ============================================================
# CLINICAL PHASE WEIGHT
# ============================================================

PHASE_BONUS = {
    "PHASE3": 10,
    "PHASE 3": 10,
    "PHASE2": 5,
    "PHASE 2": 5,
    "PHASE1": 0,
    "PHASE 1": 0,
}


# ============================================================
# LABEL
# ============================================================

def score_label(score):

    if score >= 95:
        return "CRITICAL"

    if score >= 85:
        return "VERY HIGH"

    if score >= 70:
        return "HIGH"

    if score >= 60:
        return "MEDIUM"

    return "LOW"


# ============================================================
# DIRECTION
# ============================================================

POSITIVE_EVENTS = {
    "PRIMARY_ENDPOINT_MET",
    "TOPLINE_RESULTS",
    "FDA_APPROVAL",
    "TRIAL_COMPLETED",
    "ENROLLMENT_COMPLETED",
    "PHASE_3_STARTED",
    "PHASE_2_STARTED",
    "PHASE_1_STARTED",
    "SECONDARY_ENDPOINT_MET",
    "DATE_ACCELERATED",
}


NEGATIVE_EVENTS = {
    "PRIMARY_ENDPOINT_FAILED",
    "FDA_REJECTION",
    "TRIAL_STOPPED_EFFICACY",
    "TRIAL_STOPPED_SAFETY",
    "SECONDARY_ENDPOINT_FAILED",
    "DATE_DELAYED",
}


def event_direction(event_type):

    if event_type in POSITIVE_EVENTS:
        return "POSITIVE"

    if event_type in NEGATIVE_EVENTS:
        return "NEGATIVE"

    return "UNKNOWN"


# ============================================================
# PHASE NORMALIZATION
# ============================================================

def normalize_phase(phase):

    if not phase:
        return ""

    value = str(phase).upper().strip()

    return value


# ============================================================
# PHASE BONUS
# ============================================================

def phase_bonus(phase):

    phase = normalize_phase(
        phase
    )

    return PHASE_BONUS.get(
        phase,
        0
    )


# ============================================================
# TIME PROXIMITY
# ============================================================

def days_until(date_value):

    if not date_value:
        return None

    try:

        date = datetime.strptime(
            str(date_value),
            "%Y-%m-%d"
        ).date()

        today = datetime.utcnow().date()

        return (
            date - today
        ).days

    except (
        ValueError,
        TypeError
    ):

        return None


def timing_bonus(date_value):

    days = days_until(
        date_value
    )

    if days is None:
        return 0

    # Event already occurred / imminent
    if days <= 7:
        return 15

    if days <= 30:
        return 10

    if days <= 90:
        return 5

    return 0


# ============================================================
# SCORE SINGLE EVENT
# ============================================================

def calculate_catalyst_score(
    event_type,
    phase=None,
    event_date=None,
    direction=None,
):

    event_type = (
        str(event_type)
        .upper()
        .strip()
    )

    base_score = EVENT_SCORES.get(
        event_type,
        EVENT_SCORES["OTHER"]
    )

    score = base_score

    # ----------------------------------------
    # PHASE
    # ----------------------------------------

    score += phase_bonus(
        phase
    )

    # ----------------------------------------
    # TIMING
    # ----------------------------------------

    score += timing_bonus(
        event_date
    )

    # ----------------------------------------
    # DIRECTION
    # ----------------------------------------

    if direction is None:

        direction = event_direction(
            event_type
        )

    # Negative events receive a
    # slightly stronger urgency weight.
    if direction == "NEGATIVE":
        score += 5

    # ----------------------------------------
    # CAP
    # ----------------------------------------

    score = min(
        score,
        100
    )

    return {
        "score": score,
        "label": score_label(
            score
        ),
        "direction": direction,
        "event_type": event_type,
    }


# ============================================================
# SCORE CATALYST EVENT OBJECT
# ============================================================

def score_catalyst_event(event):

    event_type = event.get(
        "type",
        "OTHER"
    )

    phase = event.get(
        "phase"
    )

    event_date = event.get(
        "event_date"
    )

    direction = event.get(
        "direction"
    )

    result = calculate_catalyst_score(
        event_type=event_type,
        phase=phase,
        event_date=event_date,
        direction=direction,
    )

    scored = dict(
        event
    )

    scored.update(
        result
    )

    return scored


# ============================================================
# SCORE MULTIPLE EVENTS
# ============================================================

def score_catalyst_events(events):

    scored = []

    for event in events:

        scored.append(
            score_catalyst_event(
                event
            )
        )

    return scored
