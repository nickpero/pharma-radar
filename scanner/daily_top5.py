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


def _same_day_catalysts(history, ticker, date_value=None):
    day = date_value or _today_utc()
    matches = []
    for event in history.values():
        if str(event.get("ticker", "")).upper() != ticker:
            continue
        timestamp = str(event.get("event_timestamp") or event.get("published_at") or "")
        if timestamp[:10] == day:
            matches.append(event)
    return sorted(
        matches,
        key=lambda item: int(item.get("alert_priority") or 0),
        reverse=True,
    )


def build_daily_top5(watchlist=None, history=None, snapshot_fn=get_market_snapshot, date_value=None):
    watchlist = watchlist if watchlist is not None else load_watchlist()
    history = history if history is not None else load_catalyst_history()
    rows = []
    for ticker, meta in watchlist.items():
        snapshot = snapshot_fn(ticker)
        if not snapshot or snapshot.get("price_change_pct") is None:
            continue
        same_day = _same_day_catalysts(history, ticker.upper(), date_value)
        catalyst = same_day[0] if same_day else None
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
            "catalyst_subtype": catalyst.get("subtype") if catalyst else None,
            "catalyst_program": catalyst.get("program") if catalyst else None,
            "catalyst_source": catalyst.get("source") if catalyst else None,
            "catalyst_priority": catalyst.get("alert_priority") if catalyst else None,
            "catalyst_url": catalyst.get("url") if catalyst else None,
            "classification": _classify_row(catalyst),
            "catalyst_evidence": _catalyst_evidence(catalyst),
            "radar_inclusion": _radar_inclusion(catalyst, meta),
            "radar_reason": _radar_reason(catalyst, meta),
        })
    rows.sort(key=lambda item: item["price_change_pct"], reverse=True)
    return rows[:5]


def _classify_row(catalyst):
    if not catalyst:
        return "MARKET_MOVE_UNEXPLAINED"
    subtype = str(catalyst.get("subtype") or catalyst.get("type") or "").upper()
    fundamental = {
        "TOPLINE_RESULTS", "PRIMARY_ENDPOINT_MET", "PRIMARY_ENDPOINT_FAILED",
        "FDA_APPROVAL", "FDA_REJECTION", "FDA_SAFETY_WARNING",
        "PHASE_ADVANCED", "PHASE_DATA_UPDATE", "CLINICAL_RESULTS",
        "COMMERCIAL_CATALYST", "COMMERCIAL_PARTNERSHIP", "GUIDANCE_RAISED",
    }
    if subtype in fundamental:
        return "FUNDAMENTAL_OR_CLINICAL_CATALYST"
    if subtype in {"EXPLORATORY_DATA", "DEVELOPMENT_MILESTONE", "FORMULATION_MILESTONE",
                    "PHASE_1_STARTED", "PHASE_2_STARTED"}:
        return "DEVELOPMENT_MILESTONE_WATCH"
    return "CATALYST_LINKED"

def _catalyst_evidence(catalyst):
    if not catalyst:
        return "NO_VERIFIED_SAME_DAY_CATALYST"
    return str(catalyst.get("catalyst_evidence") or catalyst.get("evidence_class")
               or "RADAR_RECORDED_EVENT").upper()

def _radar_inclusion(catalyst, meta):
    if catalyst:
        return str(catalyst.get("radar_inclusion") or "YES_IF_MATERIAL").upper()
    return str((meta or {}).get("radar_role") or "WATCH_UNEXPLAINED_MOVE").upper()

def _radar_reason(catalyst, meta):
    if catalyst:
        return catalyst.get("radar_reason") or (
            "Same-day catalyst recorded by Pharma Radar; retain for monitoring based on event materiality."
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
            reason = f'{row["catalyst_subtype"]} · {row["catalyst_source"] or "PRIMARY"}'
            classification = row.get("classification", "CATALYST_LINKED")
        else:
            reason = "No same-day Radar catalyst recorded"
            classification = row.get("classification", "MARKET_MOVE_UNEXPLAINED")
        lines.extend([
            f"{index}. 🧬 {row['ticker']} · {row['company']}",
            f"   📈 {pct:+.2f}% · Volume {volume_text}",
            f"   📰 {reason}",
            f"   🔎 {classification}",
            f"   🧠 Evidence: {row.get('catalyst_evidence', 'N/A')}",
            f"   📡 Radar: {row.get('radar_inclusion', 'N/A')}",
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
