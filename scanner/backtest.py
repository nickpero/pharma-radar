"""Pharma Radar — Phase 5.7 lightweight backtest dataset.

This module deliberately does not optimize thresholds or place trades. It turns
historical catalyst-memory records into point-in-time observations and exposes
only reaction horizons that were actually recorded by the live scanner.
"""

from statistics import mean, median

HORIZONS = (1, 5, 15, 30, 60)


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reaction(row):
    return row.get("reaction") or row.get("market_reaction") or {}


def _point_in_time(row):
    """Return fields that were known at alert time, without recalculating them."""
    return {
        "memory_key": row.get("memory_key"),
        "ticker": row.get("ticker"),
        "company": row.get("company"),
        "program": row.get("program"),
        "subtype": row.get("subtype"),
        "direction": row.get("direction"),
        "severity": row.get("severity"),
        "score": _number(row.get("score")),
        "alert_priority": _number(row.get("alert_priority")),
        "event_surprise": row.get("event_surprise"),
        "trading_setup_score": _number(row.get("trading_setup_score")),
        "reaction_strength": row.get("reaction_strength"),
        "reaction_interpretation": row.get("reaction_interpretation"),
        "price_change_pct": _number(row.get("price_change_pct")),
        "volume_ratio": _number(row.get("volume_ratio")),
        "market_cap": _number(row.get("market_cap")),
        "short_interest_pct": _number(row.get("short_interest_pct")),
        "event_timestamp": row.get("event_timestamp"),
    }


def build_dataset(rows):
    """Build a small, deterministic dataset from catalyst memory records."""
    dataset = []
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        observation = _point_in_time(row)
        reaction = _reaction(row)
        observation["outcomes"] = {
            f"{minutes}m": _number(reaction.get(f"reaction_{minutes}m_pct"))
            for minutes in HORIZONS
        }
        observation["outcomes_available"] = sum(
            value is not None for value in observation["outcomes"].values()
        )
        dataset.append(observation)
    return dataset


def summarize_outcomes(dataset, horizon="15m"):
    """Return transparent descriptive statistics; no optimization is performed."""
    values = [
        _number(row.get("outcomes", {}).get(horizon))
        for row in dataset or []
    ]
    values = [value for value in values if value is not None]
    if not values:
        return {
            "horizon": horizon,
            "observations": 0,
            "win_rate": None,
            "average_return_pct": None,
            "median_return_pct": None,
        }
    return {
        "horizon": horizon,
        "observations": len(values),
        "win_rate": sum(value > 0 for value in values) / len(values),
        "average_return_pct": mean(values),
        "median_return_pct": median(values),
    }


def summarize_all_horizons(dataset):
    return {f"{minutes}m": summarize_outcomes(dataset, f"{minutes}m") for minutes in HORIZONS}
