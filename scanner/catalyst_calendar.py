"""
Pharma Radar — Clinical Catalyst Calendar.
Combines ClinicalTrials.gov completion milestones with source-backed announced
catalysts. A milestone is never promoted to a clinical result by date alone.
"""
import json
from datetime import date, timedelta
from pathlib import Path

from scanner.announced_catalysts import load_announced_events, upcoming_announced_events

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


def _trial_program(key, trial, watch_entry):
    """Resolve the program from the trial key/intervention, not watchlist[0]."""
    parts = str(key).split(":")
    key_program = parts[1].strip() if len(parts) > 1 else ""
    candidates = watch_entry.get("programs", [])
    for program in candidates:
        if key_program and key_program.casefold() == str(program).casefold():
            return program
    interventions = trial.get("interventions") or []
    haystack = " ".join(str(value) for value in interventions + [key_program, trial.get("title", "")]).casefold()
    for program in candidates:
        if str(program).casefold() in haystack:
            return program
    return key_program or (interventions[0] if interventions else trial.get("title") or "UNKNOWN")


def build_upcoming_calendar(days=90, watchlist=None, trials=None, today=None, announced_events=None):
    if watchlist is None:
        watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    if trials is None:
        trials = json.loads(TRIALS_PATH.read_text(encoding="utf-8"))
    if announced_events is None:
        # When tests/callers inject a watchlist or trial snapshot, do not mix
        # in the repository's live announced feed unless explicitly requested.
        announced_events = load_announced_events() if watchlist is None and trials is None else []
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
        watch_entry = watchlist[ticker]
        program = _trial_program(key, trial, watch_entry)
        for field, label in (
            ("primary_completion_date", "PRIMARY_COMPLETION"),
            ("completion_date", "STUDY_COMPLETION"),
        ):
            parsed, precision = _parse_date(trial.get(field))
            if parsed is None or parsed < start or parsed > end:
                continue
            rows.append({
                "ticker": ticker,
                "company": watch_entry.get("company", ticker),
                "program": program,
                "programs": [program] if program != "UNKNOWN" else [],
                "nct_id": trial.get("nct_id"),
                "title": trial.get("title"),
                "phase": (trial.get("phases") or [None])[0],
                "status": status,
                "milestone": label,
                "event_type": "TRIAL_MILESTONE",
                "milestone_type": "EXPECTED_TRIAL_COMPLETION",
                "actionability": "WATCH",
                "direction": "UNKNOWN",
                "clinical_outcome_available": False,
                "date": parsed.isoformat(),
                "date_precision": precision,
                "source": "ClinicalTrials.gov",
                "source_url": f"https://clinicaltrials.gov/study/{trial.get('nct_id')}" if trial.get("nct_id") else "https://clinicaltrials.gov/",
            })
    for event in upcoming_announced_events(announced_events, days=days, today=start, watchlist=watchlist):
        rows.append({
            **event,
            "program": event.get("program") or event.get("drug_program") or "UNKNOWN",
            "programs": [event.get("program") or event.get("drug_program") or "UNKNOWN"],
            "milestone": event.get("event_name") or event.get("title") or event["event_type"],
            "milestone_type": event["event_type"],
            "nct_id": event.get("nct_id"),
            "status": event.get("status", "ANNOUNCED"),
            "source": event.get("source_url") or event.get("source"),
        })
    rows.sort(key=lambda item: (item["date"], item["ticker"], item.get("nct_id") or "", item.get("event_id") or ""))
    return rows


def format_calendar(rows, days=90):
    lines = [
        "🧬 PHARMA RADAR — CATALYST CALENDAR",
        "━━━━━━━━━━━━━━━━━━",
        f"📅 Next {days} days",
        "",
    ]
    if not rows:
        lines.append("🟢 No upcoming monitored clinical catalysts.")
        return "\n".join(lines)
    for row in rows:
        precision = row.get("date_precision", "DAY")
        date_text = row["date"] if precision == "DAY" else (
            row["date"][:7] + " (month)" if precision == "MONTH" else
            f"{row['date']} (window)" if precision == "WINDOW" else row["date"]
        )
        event_type = row.get("event_type", "TRIAL_MILESTONE")
        if event_type == "CLINICAL_READOUT":
            classification = "🧬 Clinical readout/data — not a confirmed positive or negative result until data are reviewed."
        elif event_type == "CLINICAL_REVIEW":
            classification = "⚪ Clinical review — no unblinded efficacy outcome inferred."
        else:
            classification = "ℹ️ Expected trial milestone — not itself a clinical readout."
        program = row.get("program") or ((row.get("programs") or [None])[0]) or row.get("title") or "UNKNOWN"
        lines.extend([
            f"📅 {date_text} · {row.get('company') or row['ticker']} ({row['ticker']}) · {row.get('milestone', 'CLINICAL_CATALYST')}",
            f"💊 {program} · {row.get('phase') or 'PHASE UNKNOWN'}",
            classification,
            f"🔬 {row.get('nct_id') or 'N/A'} · {row.get('status') or 'STATUS UNKNOWN'}",
            f"🔗 {row.get('source_url') or row.get('source') or 'Source unavailable'}",
            *([f"🗞 Pubblicazione fonte: {row.get('source_published_at') or row.get('published_at')}"] if row.get('source_published_at') or row.get('published_at') else []),
            *([f"💡 Rilevanza: {row.get('why_it_matters')}"] if row.get('why_it_matters') else []),
            "",
        ])
    return "\n".join(lines).rstrip()
