"""Deliver due clinical-catalyst calendar alerts with persistent deduplication.

Only source-backed announced events and ClinicalTrials.gov trial milestones are
eligible. A completion date is never described as an efficacy result.
"""
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from scanner.catalyst_calendar import build_upcoming_calendar
from scanner.telegram import send_telegram

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "catalyst_calendar_alert_state.json"
LEAD_DAYS = (14, 7, 3, 1, 0)


def _fingerprint(row):
    identity = "|".join(str(value or "").strip().lower() for value in (
        row.get("ticker"), row.get("program"), row.get("event_type"),
        row.get("milestone"), row.get("nct_id"), row.get("date"),
        row.get("window_end"),
    ))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _due_trigger(row, today):
    precision = row.get("date_precision", "DAY")
    try:
        event_date = date.fromisoformat(str(row.get("date", ""))[:10])
    except ValueError:
        return None
    if precision == "MONTH":
        # Month-only dates have no exact day. Notify once in the named month,
        # not on an invented day-countdown.
        if event_date.year == today.year and event_date.month == today.month:
            return "MONTH"
        return None
    days_left = (event_date - today).days
    if days_left in LEAD_DAYS:
        return f"D{days_left}"
    if precision == "WINDOW":
        try:
            end = date.fromisoformat(str(row.get("window_end", ""))[:10])
        except ValueError:
            end = event_date
        if event_date <= today <= end:
            return "WINDOW_OPEN"
    return None


def due_calendar_alerts(rows, today=None, sent_state=None):
    today = today or date.today()
    sent_state = sent_state or {}
    due = []
    for row in rows or []:
        event_type = str(row.get("event_type") or "TRIAL_MILESTONE").upper()
        if event_type not in {"CLINICAL_READOUT", "TRIAL_MILESTONE", "CLINICAL_REVIEW"}:
            continue
        if event_type in {"CLINICAL_READOUT", "CLINICAL_REVIEW"} and not (
            row.get("source_url") or row.get("source")
        ):
            continue
        trigger = _due_trigger(row, today)
        if trigger is None:
            continue
        key = f"{_fingerprint(row)}:{trigger}"
        if key in sent_state:
            continue
        item = dict(row)
        item["delivery_key"] = key
        item["trigger"] = trigger
        due.append(item)
    return due


def format_due_alert(row):
    event_type = str(row.get("event_type") or "TRIAL_MILESTONE").upper()
    classification = {
        "CLINICAL_READOUT": "1 — VERO CLINICAL READOUT / DATI DI EFFICACIA",
        "TRIAL_MILESTONE": "2 — MILESTONE PREVISTA, NON UN RISULTATO",
        "CLINICAL_REVIEW": "3 — REVIEW / SICUREZZA / CIECO, SENZA EFFICACIA UNBLINDED",
    }[event_type]
    date_text = str(row.get("date") or "DATA NON DISPONIBILE")
    if row.get("date_precision") == "MONTH":
        date_text = date_text[:7] + " (finestra mensile)"
    elif row.get("date_precision") == "WINDOW" and row.get("window_end"):
        date_text += " → " + str(row["window_end"])
    lines = [
        "🧬 PHARMA RADAR — CATALYST CLINICO IN AVVICINAMENTO",
        "━━━━━━━━━━━━━━━━━━",
        f"🏢 {row.get('company') or row.get('ticker') or 'AZIENDA N/D'} · {row.get('ticker') or 'TICKER N/D'}",
        f"💊 {row.get('program') or row.get('title') or 'Programma N/D'} · {row.get('phase') or 'Fase N/D'}",
        f"📌 {row.get('milestone') or row.get('event_name') or 'Evento clinico'}",
        f"📅 Data/finestra: {date_text}",
        f"🏷️ Classificazione: {classification}",
    ]
    if row.get("source_published_at") or row.get("published_at"):
        lines.append(f"🗞 Pubblicazione fonte: {row.get('source_published_at') or row.get('published_at')}")
    source_url = row.get("source_url") or row.get("source")
    if source_url:
        lines.append(f"🔗 Fonte primaria: {source_url}")
    if event_type == "TRIAL_MILESTONE":
        lines.append("💡 Rilevanza: segnala la tempistica del trial; non dimostra che i risultati siano disponibili.")
        if row.get("why_it_matters"):
            lines.append(f"Contesto: {row['why_it_matters']}")
    elif event_type == "CLINICAL_REVIEW":
        lines.append("💡 Rilevanza: aggiornamento di processo/sicurezza; non attribuire esito positivo o negativo senza dati unblinded.")
        if row.get("why_it_matters"):
            lines.append(f"Contesto: {row['why_it_matters']}")
    elif row.get("why_it_matters"):
        lines.append(f"💡 Rilevanza: {row['why_it_matters']}")
    else:
        lines.append("💡 Rilevanza: i dati possono modificare la valutazione del programma; nessuna direzione è inferita prima di leggerli.")
    lines.extend([
        f"🕒 Generato: {datetime.now(timezone.utc).isoformat()}",
        "⚠️ Informativo: nessun segnale automatico di acquisto/vendita.",
        "━━━━━━━━━━━━━━━━━━",
    ])
    return "\n".join(lines)


def run_delivery(today=None, rows=None, state_path=None, send_fn=None):
    today = today or date.today()
    state_path = Path(state_path) if state_path else STATE_PATH
    send_fn = send_fn or send_telegram
    if rows is None:
        rows = build_upcoming_calendar(days=90, today=today)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        state = {}
    due = due_calendar_alerts(rows, today=today, sent_state=state)
    if not due:
        return {"due": 0, "sent": 0}
    # Mark only after the delivery succeeds, so transient Telegram errors retry.
    sent_keys = []
    for row in due:
        send_fn(format_due_alert(row))
        sent_keys.append(row["delivery_key"])
    timestamp = datetime.now(timezone.utc).isoformat()
    for key in sent_keys:
        state[key] = timestamp
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(state_path)
    return {"due": len(due), "sent": len(sent_keys)}


if __name__ == "__main__":
    result = run_delivery()
    print(f"Clinical catalyst calendar delivery: due={result['due']} sent={result['sent']}")
