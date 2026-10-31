"""Pharma Opportunity Board: separates fresh catalysts from reactions and history.

This is a decision-support view, not a buy/sell signal. Missing data stays unknown.
"""

import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from scanner.catalyst_calendar import build_upcoming_calendar
from scanner.catalyst_memory import history_records

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"
BOARD_PATH = ROOT / "data" / "opportunity_board.json"

PRIMARY_SOURCES = {
    "FDA", "FDA RSS", "EMA", "SEC", "CLINICALTRIALS", "CLINICALTRIALS.GOV",
    "COMPANY", "COMPANY IR", "EU CTIS",
}
COMPANY_LEVEL_SUBTYPES = {
    "COMPANY_FINANCIAL_RESULTS", "COMPANY_BUSINESS_UPDATE",
    "COMPANY_ACQUISITION", "COMPANY_GUIDANCE",
}


def _parse_event_time(value):
    raw = str(value or "").strip()
    if not raw:
        return None, "MISSING"
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        try:
            return date.fromisoformat(raw), "DATE_ONLY"
        except ValueError:
            return None, "INVALID"
    if "T" not in raw and " " not in raw:
        return None, "DATE_ONLY"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None, "INVALID"
    if parsed.tzinfo is None:
        return parsed, "TIMEZONE_UNKNOWN"
    return parsed.astimezone(timezone.utc), "TIMESTAMP"


def _freshness(event, now):
    raw = event.get("event_timestamp") or event.get("published_at")
    parsed, precision = _parse_event_time(raw)
    if precision == "TIMESTAMP":
        age_hours = (now - parsed).total_seconds() / 3600.0
        if age_hours < 0:
            return "FUTURE_TIMESTAMP", precision
        if age_hours <= 24:
            return "LIVE_0_24H", precision
        if age_hours <= 72:
            return "LATE_24_72H", precision
        return "HISTORICAL_GT_72H", precision
    if precision == "DATE_ONLY":
        try:
            event_date = parsed if isinstance(parsed, date) else date.fromisoformat(str(raw)[:10])
        except (TypeError, ValueError):
            return "UNKNOWN_TIME", "INVALID"
        days_old = (now.date() - event_date).days
        if days_old == 0:
            return "DATE_ONLY_TODAY", precision
        if 0 < days_old <= 3:
            return "DATE_ONLY_RECENT", precision
        if days_old < 0:
            return "FUTURE_DATE", precision
        return "HISTORICAL", precision
    if precision == "TIMEZONE_UNKNOWN":
        return "UNKNOWN_TIMEZONE", precision
    return "UNKNOWN_TIME", precision


def _is_primary(event):
    source = str(event.get("source") or "").strip().upper()
    source_type = str(event.get("source_type") or "").strip().upper()
    return source in PRIMARY_SOURCES or source_type.startswith("PRIMARY_")


def _program_status(event, company_meta):
    subtype = str(event.get("subtype") or "").upper()
    program = str(event.get("program") or "").strip().lower()
    if not program and subtype in COMPANY_LEVEL_SUBTYPES:
        return True, "COMPANY_LEVEL"
    if not program:
        return False, "MISSING_PROGRAM"
    configured = [str(item).strip().lower() for item in company_meta.get("programs", [])]
    if not configured:
        return False, "NO_WATCHLIST_PROGRAMS"
    matched = any(program == item or program in item or item in program for item in configured)
    return matched, "VERIFIED" if matched else "PROGRAM_MISMATCH"


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _opportunity_score(event, primary, program_verified, freshness):
    components = []
    catalyst = _number(event.get("score"))
    priority = _number(event.get("alert_priority"))
    if catalyst is not None:
        components.append((catalyst, 0.35))
    if priority is not None:
        components.append((priority, 0.20))
    components.append((100.0 if primary else 0.0, 0.20))
    components.append((100.0 if program_verified else 0.0, 0.15))
    freshness_score = {
        "LIVE_0_24H": 100.0,
        "DATE_ONLY_TODAY": 70.0,
        "LATE_24_72H": 35.0,
        "DATE_ONLY_RECENT": 25.0,
    }.get(freshness)
    if freshness_score is not None:
        components.append((freshness_score, 0.10))
    if not components:
        return None
    total_weight = sum(weight for _, weight in components)
    return round(sum(value * weight for value, weight in components) / total_weight, 1)


def _market_snapshot(event):
    market = event.get("market_data") if isinstance(event.get("market_data"), dict) else {}
    price = _number(event.get("price") if event.get("price") is not None else market.get("price"))
    average_volume = _number(
        event.get("average_volume_20d")
        if event.get("average_volume_20d") is not None
        else market.get("average_volume_20d")
    )
    volume_ratio = _number(
        event.get("volume_ratio")
        if event.get("volume_ratio") is not None
        else market.get("volume_ratio")
    )
    price_change = _number(
        event.get("price_change_pct")
        if event.get("price_change_pct") is not None
        else market.get("price_change_pct")
    )
    market_cap = _number(event.get("market_cap") if event.get("market_cap") is not None else market.get("market_cap"))
    dollar_volume = price * average_volume if price is not None and average_volume is not None else None
    return {
        "price": price,
        "price_change_pct": price_change,
        "volume_ratio": volume_ratio,
        "average_volume_20d": average_volume,
        "market_cap": market_cap,
        "estimated_average_dollar_volume_20d": round(dollar_volume, 2) if dollar_volume is not None else None,
        "source": event.get("market_data_source") or market.get("market_data_source"),
        "status": "AVAILABLE" if any(value is not None for value in (price, price_change, volume_ratio, market_cap, dollar_volume)) else "UNKNOWN",
    }


def _event_row(event, watchlist, now):
    ticker = str(event.get("ticker") or "UNKNOWN").upper()
    company_meta = watchlist.get(ticker, {})
    primary = _is_primary(event)
    program_verified, program_status = _program_status(event, company_meta)
    freshness, precision = _freshness(event, now)
    subtype = str(event.get("subtype") or "UNKNOWN").upper()
    if not primary:
        status, reason = "EXCLUDED", "PRIMARY_SOURCE_NOT_VERIFIED"
    elif freshness in {"HISTORICAL_GT_72H", "HISTORICAL", "LATE_24_72H", "DATE_ONLY_RECENT"}:
        status, reason = "LATE", freshness
    elif freshness in {"UNKNOWN_TIME", "UNKNOWN_TIMEZONE", "FUTURE_TIMESTAMP", "FUTURE_DATE"}:
        status, reason = "EXCLUDED", freshness
    elif freshness == "LIVE_0_24H" and (program_verified or program_status == "COMPANY_LEVEL"):
        status, reason = "LIVE", "FRESH_PRIMARY_CATALYST"
    elif freshness in {"LIVE_0_24H", "DATE_ONLY_TODAY"}:
        status, reason = "WATCH", program_status if not program_verified else "DATE_PRECISION_INSUFFICIENT"
    else:
        status, reason = "EXCLUDED", freshness

    score = _opportunity_score(event, primary, program_verified, freshness)
    market = _market_snapshot(event)
    return {
        "status": status,
        "reason": reason,
        "ticker": ticker,
        "company": event.get("company") or company_meta.get("company") or ticker,
        "program": event.get("program"),
        "program_status": program_status,
        "event_type": subtype,
        "title": event.get("title"),
        "source": event.get("source"),
        "source_type": event.get("source_type"),
        "source_url": event.get("url"),
        "published_at": event.get("event_timestamp") or event.get("published_at"),
        "publication_precision": precision,
        "first_seen_at": event.get("first_seen_at") or event.get("detected_at"),
        "catalyst_score": _number(event.get("score")),
        "priority_score": _number(event.get("alert_priority")),
        "trading_intelligence_score": _number(event.get("trading_intelligence_score")),
        "opportunity_score": score,
        "market": market,
        "nct_id": event.get("nct_id"),
    }


def build_opportunity_board(events=None, watchlist=None, upcoming=None, now=None):
    """Build a transparent board from recent catalyst memory and estimated milestones."""
    if watchlist is None:
        watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    if events is None:
        events = history_records()
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    reference = reference.astimezone(timezone.utc)

    rows = [_event_row(event, watchlist, reference) for event in (events or []) if isinstance(event, dict)]
    live = [row for row in rows if row["status"] == "LIVE"]
    watch = [row for row in rows if row["status"] == "WATCH"]
    late = [row for row in rows if row["status"] == "LATE"]
    excluded = [row for row in rows if row["status"] == "EXCLUDED"]

    def sort_rows(items):
        items.sort(key=lambda row: (
            row.get("opportunity_score") if row.get("opportunity_score") is not None else -1,
            row.get("published_at") or "",
        ), reverse=True)
    for group in (live, watch, late):
        sort_rows(group)

    if upcoming is None:
        try:
            upcoming = build_upcoming_calendar(days=90, watchlist=watchlist, today=reference.astimezone(ZoneInfo('Europe/Rome')).date())
        except (OSError, ValueError, json.JSONDecodeError):
            upcoming = []

    return {
        "generated_at": reference.isoformat(),
        "methodology": {
            "live": "Timestamped primary-source catalyst published within 24 hours, with a verified program or recognized company-level event.",
            "watch": "Fresh primary-source item with date-only precision or incomplete program verification.",
            "late": "24-72 hour reactions and older historical events; never a new Telegram alert.",
            "upcoming": "Estimated ClinicalTrials.gov registry completion milestones, not confirmed readout dates.",
            "missing_data": "Unknown values remain null; scores use only available components.",
        },
        "counts": {
            "live": len(live), "watch": len(watch), "late": len(late),
            "upcoming": len(upcoming), "excluded": len(excluded),
        },
        "live": live[:25],
        "watch": watch[:50],
        "upcoming": upcoming[:100],
        "late": late[:50],
        "excluded": excluded[:50],
    }


def save_opportunity_board(board, path=BOARD_PATH):
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = None
        if isinstance(previous, dict):
            previous_compare = dict(previous)
            current_compare = dict(board)
            previous_compare.pop("generated_at", None)
            current_compare.pop("generated_at", None)
            if previous_compare == current_compare:
                return path
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(board, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise
    return path


def format_board_summary(board):
    counts = board.get("counts", {})
    return (
        "PHARMA OPPORTUNITY BOARD: "
        f"LIVE={counts.get('live', 0)} | WATCH={counts.get('watch', 0)} | "
        f"UPCOMING={counts.get('upcoming', 0)} | LATE={counts.get('late', 0)} | "
        f"EXCLUDED={counts.get('excluded', 0)}"
    )
