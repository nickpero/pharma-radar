"""Pharma Radar — Operational Catalyst Qualification Gate.

Separates genuine fundamental/clinical/regulatory catalysts from technical,
speculative, or unexplained market moves. This layer is descriptive only and
does not generate buy/sell recommendations.
"""
from __future__ import annotations

from datetime import datetime, timezone


PRIMARY_SOURCE_TYPES = {
    "PRIMARY_CLINICAL",
    "PRIMARY_REGULATORY",
    "PRIMARY_CORPORATE",
}
RELIABLE_SOURCE_TYPES = PRIMARY_SOURCE_TYPES | {"RELIABLE_REGULATORY"}

CLINICAL_SUBTYPES = {
    "PRIMARY_ENDPOINT_MET",
    "PRIMARY_ENDPOINT_FAILED",
    "TOPLINE_RESULTS",
    "TRIAL_STOPPED_EFFICACY",
    "TRIAL_STOPPED_SAFETY",
    "ENROLLMENT_COMPLETED",
    "PHASE_3_STARTED",
    "PHASE_2_STARTED",
    "PHASE_1_STARTED",
    "SECONDARY_ENDPOINT_MET",
    "SECONDARY_ENDPOINT_FAILED",
    "TRIAL_COMPLETED",
}
REGULATORY_SUBTYPES = {
    "FDA_APPROVAL",
    "FDA_REJECTION",
    "IND_CLEARANCE",
    "PRIORITY_REVIEW",
    "FAST_TRACK",
    "BREAKTHROUGH_THERAPY",
}
CORPORATE_SUBTYPES = {
    "LICENSING",
    "PARTNERSHIP",
    "ACQUISITION",
    "MILESTONE_PAYMENT",
}

SPECULATIVE_WORDS = (
    "short squeeze",
    "squeeze",
    "meme",
    "social",
    "reddit",
    "stocktwits",
    "crypto",
    "blockchain",
    "nft",
    "ai platform",
)
TECHNICAL_WORDS = (
    "technical",
    "momentum",
    "volume spike",
    "unusual volume",
    "price action",
    "breakout",
)


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(event):
    return " ".join(
        str(event.get(key) or "")
        for key in ("title", "summary", "why_it_matters", "catalyst_category")
    ).strip().lower()


def _parse_timestamp(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def freshness_bucket(event, now=None):
    dt = _parse_timestamp(event.get("published_at") or event.get("event_timestamp"))
    if dt is None:
        return "UNKNOWN"
    reference = now or datetime.now(timezone.utc)
    age_hours = max(0.0, (reference - dt).total_seconds() / 3600)
    if age_hours < 2:
        return "BREAKING"
    if age_hours < 24:
        return "FRESH"
    if age_hours <= 72:
        return "RECENT"
    return "BACKGROUND"


def _source_class(event):
    source_type = str(event.get("source_type") or "").upper()
    source = str(event.get("source") or "").upper()
    if source_type in PRIMARY_SOURCE_TYPES:
        return "PRIMARY"
    if source_type in RELIABLE_SOURCE_TYPES or source in {"FDA", "FDA RSS", "EMA", "SEC"}:
        return "RELIABLE"
    if source_type:
        return "SECONDARY"
    return "UNKNOWN"


def _market_strength(event):
    price = _num(event.get("price_change_pct"))
    if price is None:
        price = _num((event.get("market_data") or {}).get("price_change_pct"))
    volume = _num(event.get("volume_ratio"))
    if volume is None:
        volume = _num((event.get("market_data") or {}).get("volume_ratio"))
    price_abs = abs(price) if price is not None else 0
    if price_abs >= 50 or (volume is not None and volume >= 5):
        return "EXTREME"
    if price_abs >= 20 or (volume is not None and volume >= 3):
        return "HIGH"
    if price_abs >= 10 or (volume is not None and volume >= 2):
        return "MEDIUM"
    return "LOW"


def qualify_catalyst(event, now=None):
    """Add an operational classification without suppressing the underlying event."""
    result = dict(event or {})
    subtype = str(result.get("subtype") or result.get("type") or "").upper()
    source_class = _source_class(result)
    text = _text(result)
    score = _num(result.get("score")) or 0

    if any(word in text for word in SPECULATIVE_WORDS) and subtype not in (
        CLINICAL_SUBTYPES | REGULATORY_SUBTYPES
    ):
        catalyst_class = "SPECULATIVE"
    elif any(word in text for word in TECHNICAL_WORDS) and subtype not in (
        CLINICAL_SUBTYPES | REGULATORY_SUBTYPES | CORPORATE_SUBTYPES
    ):
        catalyst_class = "TECHNICAL"
    elif subtype in CLINICAL_SUBTYPES:
        catalyst_class = "FUNDAMENTAL_CLINICAL"
    elif subtype in REGULATORY_SUBTYPES:
        catalyst_class = "FUNDAMENTAL_REGULATORY"
    elif subtype in CORPORATE_SUBTYPES or "partnership" in text or "acquisition" in text or "licensing" in text:
        catalyst_class = "FUNDAMENTAL_CORPORATE"
    else:
        catalyst_class = "UNCLEAR"

    market_strength = _market_strength(result)
    freshness = freshness_bucket(result, now=now)

    genuine = catalyst_class.startswith("FUNDAMENTAL_")
    primary = source_class == "PRIMARY"
    reliable = source_class in {"PRIMARY", "RELIABLE"}

    # Entry into the operational Catalyst Radar requires a genuine event and
    # reliable evidence. A primary clinical/regulatory event can qualify on
    # event strength alone; corporate events also require materiality.
    entry_criteria = {
        "genuine_catalyst": genuine,
        "reliable_source": reliable,
        "primary_source": primary,
        "material_event": score >= 60 or subtype in CLINICAL_SUBTYPES | REGULATORY_SUBTYPES,
    }
    entry_count = sum(bool(value) for value in entry_criteria.values())

    if genuine and reliable and entry_criteria["material_event"]:
        radar_inclusion = "INCLUDE"
        if primary and market_strength in {"HIGH", "EXTREME"}:
            radar_priority = "P0"
        elif primary:
            radar_priority = "P1"
        else:
            radar_priority = "P2"
    elif genuine and (reliable or market_strength in {"HIGH", "EXTREME"}):
        radar_inclusion = "WATCH"
        radar_priority = "P2"
    elif catalyst_class in {"SPECULATIVE", "TECHNICAL"} or not reliable:
        radar_inclusion = "WATCH"
        radar_priority = "P3"
    else:
        radar_inclusion = "UNCONFIRMED"
        radar_priority = "P3"

    # Do not let a huge price/volume move upgrade a non-catalyst into P0/P1.
    if not genuine:
        radar_priority = "P2" if radar_inclusion == "WATCH" and market_strength == "EXTREME" else "P3"

    result.update({
        "catalyst_quality_version": "1.0",
        "catalyst_class": catalyst_class,
        "catalyst_source_class": source_class,
        "catalyst_primary_source": primary,
        "catalyst_reliable_source": reliable,
        "catalyst_market_strength": market_strength,
        "catalyst_freshness": freshness,
        "catalyst_entry_criteria": entry_criteria,
        "catalyst_entry_count": entry_count,
        "radar_inclusion": radar_inclusion,
        "radar_priority": radar_priority,
        "radar_operational_reason": _reason(catalyst_class, source_class, freshness, market_strength),
    })
    return result


def _reason(catalyst_class, source_class, freshness, market_strength):
    if catalyst_class == "FUNDAMENTAL_CLINICAL":
        return f"Verified clinical catalyst; source={source_class}; freshness={freshness}; market_activity={market_strength}."
    if catalyst_class == "FUNDAMENTAL_REGULATORY":
        return f"Verified regulatory catalyst; source={source_class}; freshness={freshness}; market_activity={market_strength}."
    if catalyst_class == "FUNDAMENTAL_CORPORATE":
        return f"Verified corporate catalyst; source={source_class}; freshness={freshness}; market_activity={market_strength}."
    if catalyst_class == "SPECULATIVE":
        return "Market activity may be speculative; no clinical/regulatory catalyst established."
    if catalyst_class == "TECHNICAL":
        return "Price/volume behavior is technical; no qualifying fundamental catalyst established."
    return "Catalyst remains unclear or insufficiently verified."


def enrich_catalyst_quality(events):
    return [qualify_catalyst(event) for event in (events or [])]
