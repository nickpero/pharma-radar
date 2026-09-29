"""
Pharma Radar — Clinical Catalyst Calendar
Builds an upcoming clinical milestone calendar from the Radar's trial state.
Dates are treated with their source precision; month-only dates are never
presented as exact days.
"""

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"
TRIALS_PATH = ROOT / "data" / "trials_state.json"


def _parse_date(value):
    text = str(value or "").strip()
    if len(text) == 7 and text[4] == "-":
        try:
            return date.fromisoformat(text + "-01"), "MONTH"
        except ValueError:
            return None, None
    try:
        return date.fromisoformat(text[:10]), "DAY"
    except ValueError:
        return None, None


def build_upcoming_calendar(days=90, watchlist=None, trials=None, today=None):
    if watchlist is None:
        watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    if trials is None:
        trials = json.loads(TRIALS_PATH.read_text(encoding="utf-8"))
    start = today or date.today()
    end = start + timedelta(days=days)
    rows = []
    for key, trial in trials.items():
        ticker = str(key).split(":", 1)[0].upper()
        if ticker not in watchlist:
            continue
        status = str(trial.get("status") or "").upper()
        if status in {"COMPLETED", "TERMINATED", "WITHDRAWN"}:
            continue
        for field, label in (
            ("primary_completion_date", "PRIMARY_COMPLETION"),
            ("completion_date", "STUDY_COMPLETION"),
        ):
            raw = trial.get(field)
            parsed, precision = _parse_date(raw)
            if parsed is None or parsed < start or parsed > end:
                continue
            rows.append({
                "ticker": ticker,
                "company": watchlist[ticker].get("company", ticker),
                "programs": watchlist[ticker].get("programs", []),
                "nct_id": trial.get("nct_id"),
                "title": trial.get("title"),
                "phase": (trial.get("phases") or [None])[0],
                "status": status,
                "milestone": label,
                "date": parsed.isoformat(),
                "date_precision": precision,
                "source": "ClinicalTrials.gov/Radar state",
            })
    rows.sort(key=lambda item: (item["date"], item["ticker"], item["nct_id"] or ""))
    return rows


def format_calendar(rows, days=90):
    lines = [
        "🧬 PHARMA RADAR — CATALYST CALENDAR",
        "━━━━━━━━━━━━━━━━━━",
        f"📅 Next {days} days",
        "",
    ]
    if not rows:
        lines.append("🟢 No upcoming monitored clinical milestones.")
        return "\n".join(lines)
    for row in rows:
        date_text = row["date"] if row["date_precision"] == "DAY" else row["date"][:7] + " (month)"
        lines.extend([
            f"📅 {date_text} · {row['ticker']} · {row['milestone']}",
            f"💊 {row['programs'][0] if row['programs'] else row['title'] or 'UNKNOWN'} · {row['phase'] or 'PHASE UNKNOWN'}",
            f"🔬 {row['nct_id'] or 'N/A'} · {row['status']}",
            "",
        ])
    return "\n".join(lines).rstrip()
