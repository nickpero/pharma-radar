"""Multi-sector opportunity scoring — isolated prototype, no orders or alerts.

Missing data never earns points. Hard risk gates prevent an actionable rating.
"""
from math import isfinite

WEIGHTS = {
    "catalyst": 25,
    "relative_volume": 20,
    "momentum": 20,
    "financial_quality": 15,
    "liquidity": 10,
    "risk_reward": 10,
}
SECTORS = {"pharma", "biotech", "ai", "robotics", "energy", "semiconductors", "industrial"}


def score_candidate(candidate):
    """Return a transparent screening score; never a trade recommendation.

    Each factor must be a verified number between 0 and 100.
    Risk flags block eligibility regardless of the aggregate score.
    """
    sector = str(candidate.get("sector", "")).lower()
    if sector not in SECTORS:
        raise ValueError("Unsupported sector")
    factors = candidate.get("factors") or {}
    points = 0.0
    missing = []
    for name, weight in WEIGHTS.items():
        value = factors.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 100:
            missing.append(name)
            continue
        points += value * weight / 100
    flags = [name for name in ("unverified_news", "dilution_risk", "illiquid", "binary_event", "stale_data") if candidate.get(name) is True]
    eligible = not missing and not flags and points >= 70
    return {
        "ticker": str(candidate.get("ticker", "")).strip().upper(),
        "sector": sector,
        "opportunity_score": round(points, 2),
        "missing_factors": missing,
        "risk_flags": flags,
        "eligible_for_review": eligible,
        "status": "REVIEW" if eligible else "WATCH_ONLY",
    }
