"""
Pharma Radar — Daily Top 5
Ranks the active Pharma Radar universe by daily gain and attaches
same-day catalyst context when the Radar has recorded one.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scanner.market_data import get_market_snapshot
from scanner.telegram import send_telegram

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"
CATALYST_HISTORY_PATH = ROOT / "data" / "catalyst_history.json"


def load_watchlist(path=WATCHLIST_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_catalyst_history(path=CATALYST_HISTORY_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _today_utc():
    return datetime.now(timezone.utc).date().isoformat()


def _parse_event_timestamp(event):
    value = event.get("event_timestamp") or event.get("published_at")
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _catalyst_freshness(event, now=None):
    if not event:
        return "NONE"
    dt = _parse_event_timestamp(event)
    if dt is None:
        return "UNKNOWN_TIME"
    reference = now or datetime.now(timezone.utc)
    age_hours = max(0.0, (reference - dt).total_seconds() / 3600.0)
    if age_hours <= 24:
        return "NEW_0_24H"
    if age_hours <= 72:
        return "REACTION_24_72H"
    return "HISTORICAL_GT_72H"


def _source_is_primary(event):
    if not event:
        return False
    source = str(event.get("source") or "").upper()
    source_type = str(event.get("source_type") or "").upper()
    return source in {"SEC", "FDA", "FDA RSS", "CLINICALTRIALS", "COMPANY", "COMPANY IR", "COURT", "EMA", "EU CTIS"} or source_type.startswith("PRIMARY_")


def _program_is_verified(event, meta=None):
    if not event:
        return False
    program = str(event.get("program") or "").strip().lower()
    if not program:
        return False
    programs = [str(item).strip().lower() for item in (meta or {}).get("programs", [])]
    if not programs:
        return True
    return any(program == item or program in item or item in program for item in programs)


def _alert_quality_gate(event, now=None, meta=None):
    if not event:
        return {"eligible": False, "reason": "NO_EVENT", "freshness": "NONE",
                "primary_source": False, "program_verified": False}
    freshness = _catalyst_freshness(event, now)
    primary = _source_is_primary(event)
    program_verified = _program_is_verified(event, meta)
    if freshness == "UNKNOWN_TIME":
        return {"eligible": False, "reason": "EVENT_TIMESTAMP_MISSING", "freshness": freshness, "primary_source": primary}
    if freshness == "HISTORICAL_GT_72H":
        return {"eligible": False, "reason": "HISTORICAL_GT_72H", "freshness": freshness,
                "primary_source": primary, "program_verified": program_verified}
    if not primary:
        return {"eligible": False, "reason": "PRIMARY_SOURCE_NOT_VERIFIED", "freshness": freshness,
                "primary_source": False, "program_verified": program_verified}
    if not program_verified:
        return {"eligible": False, "reason": "PROGRAM_NOT_VERIFIED", "freshness": freshness,
                "primary_source": primary, "program_verified": False}
    return {"eligible": True, "reason": "QUALITY_GATE_PASS", "freshness": freshness,
            "primary_source": True, "program_verified": True}


def _reference_time(date_value=None, now=None):
    if now is not None:
        return now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    if date_value:
        return datetime.fromisoformat(f"{date_value}T23:59:59+00:00")
    return datetime.now(timezone.utc)


def _recent_catalysts(history, ticker, date_value=None, now=None, meta=None):
    """Return catalysts from the target day or the preceding 72h window."""
    reference = _reference_time(date_value, now).astimezone(timezone.utc)
    matches = []
    for event in history.values():
        if str(event.get("ticker", "")).upper() != ticker:
            continue
        dt = _parse_event_timestamp(event)
        if dt is None or dt > reference:
            continue
        age_hours = (reference - dt).total_seconds() / 3600.0
        if 0 <= age_hours <= 72:
            matches.append(event)
    def sort_key(item):
        primary = 1 if _source_is_primary(item) else 0
        program = 1 if _program_is_verified(item, meta) else 0
        return (
            program,
            primary,
            _parse_event_timestamp(item) or datetime.min.replace(tzinfo=timezone.utc),
            int(item.get("alert_priority") or 0),
        )

    return sorted(matches, key=sort_key, reverse=True)


def build_daily_top5(watchlist=None, history=None, snapshot_fn=get_market_snapshot, date_value=None):
    watchlist = watchlist if watchlist is not None else load_watchlist()
    history = history if history is not None else load_catalyst_history()
    rows = []
    reference_now = _reference_time(date_value)
    for ticker, meta in watchlist.items():
        snapshot = snapshot_fn(ticker)
        if not snapshot or snapshot.get("price_change_pct") is None:
            continue
        recent = _recent_catalysts(history, ticker.upper(), date_value, meta=meta)
        catalyst = recent[0] if recent else None
        rows.append({
            "ticker": ticker.upper(),
            "company": meta.get("company", ticker.upper()),
            "programs": meta.get("programs", []),
            "price_change_pct": snapshot.get("price_change_pct"),
            "volume": snapshot.get("volume"),
            "volume_ratio": snapshot.get("volume_ratio"),
            "price": snapshot.get("price"),
            "market_data_source": snapshot.get("market_data_source"),
            "catalyst_found": catalyst is not None,
            "catalyst_freshness": _catalyst_freshness(catalyst, reference_now),
            "catalyst_primary_source": _source_is_primary(catalyst),
            "alert_quality_gate": _alert_quality_gate(catalyst, now=reference_now, meta=meta),
            "catalyst_subtype": catalyst.get("subtype") if catalyst else None,
            "catalyst_program": catalyst.get("program") if catalyst else None,
            "catalyst_source": catalyst.get("source") if catalyst else None,
            "catalyst_priority": catalyst.get("alert_priority") if catalyst else None,
            "catalyst_url": catalyst.get("url") if catalyst else None,
            "classification": _classify_row(catalyst, meta),
            "catalyst_evidence": _catalyst_evidence(catalyst),
            "radar_inclusion": _radar_inclusion(
                catalyst,
                meta,
                _alert_quality_gate(catalyst, now=reference_now, meta=meta),
                _catalyst_freshness(catalyst, reference_now),
            ),
            "radar_reason": _radar_reason(
                catalyst,
                meta,
                _alert_quality_gate(catalyst, now=reference_now, meta=meta),
                _catalyst_freshness(catalyst, reference_now),
            ),
        })
    rows.sort(key=lambda item: item["price_change_pct"], reverse=True)
    return rows[:5]


FUNDAMENTAL_SUBTYPES = {
    "TOPLINE_RESULTS", "PRIMARY_ENDPOINT_MET", "PRIMARY_ENDPOINT_FAILED",
    "FDA_APPROVAL", "FDA_REJECTION", "FDA_SAFETY_WARNING",
    "PHASE_ADVANCED", "PHASE_DATA_UPDATE", "CLINICAL_RESULTS",
    "CLINICAL_DATA_RELEASE", "COMMERCIAL_CATALYST", "COMMERCIAL_PARTNERSHIP",
    "GUIDANCE_RAISED", "PATENT_RULING", "REGULATORY_RULING",
    "FDA_FILING_ACCEPTED",
}

DEVELOPMENT_WATCH_SUBTYPES = {
    "EXPLORATORY_DATA", "DEVELOPMENT_MILESTONE", "FORMULATION_MILESTONE",
    "CLINICAL_MILESTONE", "CATALYST_WATCH", "PHASE_1_STARTED", "PHASE_2_STARTED",
    "ENROLLMENT_INCREASED", "DATE_ACCELERATED", "DATE_DELAYED",
}


def _classify_row(catalyst, meta=None):
    if not catalyst:
        role = str((meta or {}).get("radar_role") or "").upper()
        if role == "MARKET_STRUCTURE_WATCH":
            return "TECHNICAL_OR_INDEX_FLOW"
        if role.endswith("_WATCH"):
            return "WATCHLIST_CONTEXT_NO_NEW_CATALYST"
        return "MARKET_MOVE_UNEXPLAINED"
    subtype = str(catalyst.get("subtype") or catalyst.get("type") or "").upper()
    if subtype in FUNDAMENTAL_SUBTYPES:
        return "FUNDAMENTAL_OR_CLINICAL_CATALYST"
    if subtype in DEVELOPMENT_WATCH_SUBTYPES:
        return "DEVELOPMENT_MILESTONE_WATCH"
    return "CATALYST_LINKED"


def _catalyst_evidence(catalyst):
    if not catalyst:
        return "NO_VERIFIED_SAME_DAY_CATALYST"
    return str(catalyst.get("catalyst_evidence") or catalyst.get("evidence_class")
               or "RADAR_RECORDED_EVENT").upper()

def _radar_inclusion(catalyst, meta, quality_gate=None, freshness=None):
    if not catalyst:
        return str((meta or {}).get("radar_role") or "WATCH_UNEXPLAINED_MOVE").upper()
    gate = quality_gate or {}
    if not gate.get("eligible", False):
        return "NO_NEW_ALERT"
    if freshness in {"REACTION_24_72H", "HISTORICAL_GT_72H"}:
        return "REACTION_ONLY_NO_NEW_ALERT"
    subtype = str(catalyst.get("subtype") or catalyst.get("type") or "").upper()
    if subtype in FUNDAMENTAL_SUBTYPES:
        return "INCLUDE_IF_MATERIAL"
    if subtype in DEVELOPMENT_WATCH_SUBTYPES:
        return "WATCH_ONLY"
    return "WATCH_ONLY"


def _radar_reason(catalyst, meta, quality_gate=None, freshness=None):
    if catalyst:
        gate = quality_gate or {}
        if not gate.get("eligible", False):
            return (
                "Catalyst linked to the move but blocked by the Quality Gate: "
                f"{gate.get('reason', 'UNVERIFIED')}."
            )
        if freshness in {"REACTION_24_72H", "HISTORICAL_GT_72H"}:
            return (
                "Existing catalyst is outside the new-event window; "
                "track the market reaction but do not emit a new catalyst alert."
            )
        subtype = str(catalyst.get("subtype") or catalyst.get("type") or "").upper()
        if subtype in FUNDAMENTAL_SUBTYPES:
            return (
                "Verified fundamental/clinical/regulatory catalyst; "
                "consider Radar inclusion if material and not already alerted."
            )
        if subtype in DEVELOPMENT_WATCH_SUBTYPES:
            return (
                "Development/timeline milestone without a new clinical outcome; "
                "retain as monitoring context, not as a new high-priority alert."
            )
        return (
            "Catalyst-linked move, but event type is not independently classified "
            "as a fundamental/clinical catalyst; retain as watch context."
        )
    role = str((meta or {}).get("radar_role") or "").upper()
    if role == "MARKET_STRUCTURE_WATCH":
        return (meta or {}).get("radar_reason") or (
            "Market-structure/index flow without a new Pharma catalyst; "
            "track separately and do not classify as clinical or regulatory."
        )
    if role.endswith("_WATCH"):
        return (meta or {}).get("radar_reason") or (
            "Watchlist context exists, but no verified same-day catalyst was recorded; "
            "do not label the price move itself as a catalyst."
        )
    return (meta or {}).get("radar_reason") or (
        "Price/volume move without a verified same-day fundamental catalyst; "
        "monitor separately and do not label as a catalyst."
    )


def format_daily_top5(rows, date_value=None):
    day = date_value or _today_utc()
    lines = [
        "🧬 PHARMA RADAR — DAILY TOP 5",
        "━━━━━━━━━━━━━━━━━━",
        f"📅 {day}",
        "",
    ]
    if not rows:
        lines.append("⚠️ No market data available.")
        return "\n".join(lines)
    for index, row in enumerate(rows, 1):
        pct = float(row["price_change_pct"])
        volume_ratio = row.get("volume_ratio")
        volume_text = f"{float(volume_ratio):.1f}x avg" if volume_ratio else "N/A"
        if row["catalyst_found"]:
            gate = row.get("alert_quality_gate") or {}
            freshness = row.get("catalyst_freshness", "UNKNOWN_TIME")
            reason = f'{row["catalyst_subtype"]} · {row["catalyst_source"] or "UNKNOWN"} · {freshness}'
            classification = row.get("classification", "CATALYST_LINKED")
            if freshness == "REACTION_24_72H":
                classification = "REACTION_CONTINUATION"
            elif freshness == "HISTORICAL_GT_72H":
                classification = "HISTORICAL_WATCH"
            if not gate.get("eligible"):
                classification = f'{classification}_QUALITY_GATED'
        else:
            reason = "No same-day Radar catalyst recorded"
            classification = row.get("classification", "MARKET_MOVE_UNEXPLAINED")
        lines.extend([
            f"{index}. 🧬 {row['ticker']} · {row['company']}",
            f"   📈 {pct:+.2f}% · Volume {volume_text}",
            f"   📰 {reason}",
            f"   💊 Program: {row.get('catalyst_program') or ', '.join(row.get('programs') or []) or 'N/A'}",
            f"   🔎 {classification}",
            f"   🧠 Evidence: {row.get('catalyst_evidence', 'N/A')}",
            f"   📚 Source: {row.get('catalyst_source') or 'N/A'}",
            f"   📡 Radar: {row.get('radar_inclusion', 'N/A')}",
            f"   🛡️ Quality Gate: {(row.get('alert_quality_gate') or {}).get('reason', 'N/A')}",
            f"   ℹ️ Why: {row.get('radar_reason', 'N/A')}",
            "",
        ])
    return "\n".join(lines).rstrip()


def run(send=True, watchlist=None, history=None, snapshot_fn=get_market_snapshot, date_value=None):
    rows = build_daily_top5(watchlist, history, snapshot_fn, date_value)
    message = format_daily_top5(rows, date_value)
    if send:
        send_telegram(message)
    return rows, message


if __name__ == "__main__":
    run(send=os.getenv("SEND_TELEGRAM", "1") == "1")
