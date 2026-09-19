"""
Pharma Radar — Pharma Intelligence Email (5.8)

Knowledge-first Italian intelligence emails for material pharma development and regulatory events.
The email channel is independent of Trading Intelligence and market reaction.
"""

import os
import smtplib
from email.message import EmailMessage

from scanner.pharma_email_state import email_delivery_key, load_email_state, save_email_state


PHARMA_EVENT_TYPES = {
    "NEW_TRIAL", "STATUS_CHANGE", "DATE_CHANGE", "PHASE_CHANGE",
    "ENROLLMENT_CHANGE", "PROTOCOL_CHANGE",
}
PHARMA_SUBTYPE_PREFIXES = (
    "FDA_", "EMA_", "CLINICAL_RESULT", "SAFETY", "FILING",
    "REJECTION", "LABEL_EXPANSION", "APPROVAL",
)
MEANINGFUL_FIELD_NAMES = {
    "phase", "overall_phase", "intervention", "interventions",
    "brief_summary", "official_title", "eligibility_criteria",
    "primary_outcome_measures", "secondary_outcome_measures",
    "study_type", "design_info", "conditions",
}
IGNORED_FIELD_NAMES = {
    "last_update_posted", "last_update_submit_date", "version",
    "organization", "locations", "contacts", "central_contacts",
}
EMAIL_STATE_PATH = os.path.join("data", "pharma_email_state.json")


def _event(alert):
    return alert.get("event") if isinstance(alert.get("event"), dict) else {}


def _event_type(alert):
    event = _event(alert)
    return str(alert.get("event_type") or event.get("type") or "").upper()


def _subtype(alert):
    event = _event(alert)
    return str(alert.get("subtype") or event.get("subtype") or "").upper()


def _field_name(alert):
    event = _event(alert)
    return str(alert.get("field") or event.get("field") or "").lower()


def is_pharma_intelligence_event(alert):
    """Material knowledge event; never depends on TI score or market reaction."""
    if not isinstance(alert, dict):
        return False
    event_type = _event_type(alert)
    subtype = _subtype(alert)
    field = _field_name(alert)

    if event_type in PHARMA_EVENT_TYPES:
        return True
    if any(subtype.startswith(prefix) for prefix in PHARMA_SUBTYPE_PREFIXES):
        return True
    if event_type == "FIELD_CHANGE":
        if field in IGNORED_FIELD_NAMES:
            return False
        return (
            field in MEANINGFUL_FIELD_NAMES
            or field.startswith(("protocol", "outcome", "endpoint"))
        )
    source_type = str(alert.get("source_type") or "").upper()
    return source_type in {"PRIMARY_REGULATORY", "PRIMARY_CLINICAL"} and bool(
        alert.get("title") or alert.get("summary")
    )


def _category(alert):
    subtype = _subtype(alert)
    event_type = _event_type(alert)
    if subtype.startswith(("FDA_", "EMA_")) or event_type in {"FDA_EVENT", "EMA_EVENT"}:
        return "REGULATORY"
    if event_type == "NEW_TRIAL":
        return "DISCOVERY"
    if event_type in {
        "PHASE_CHANGE", "STATUS_CHANGE", "DATE_CHANGE",
        "ENROLLMENT_CHANGE", "PROTOCOL_CHANGE",
    } or subtype in {"PHASE_CHANGE", "TRIAL_COMPLETED", "TRIAL_RECRUITING"}:
        return "DEVELOPMENT"
    if subtype.startswith(("CLINICAL_RESULT", "SAFETY")) or subtype in {
        "FILING", "REJECTION", "LABEL_EXPANSION", "APPROVAL",
    }:
        return "MILESTONE"
    return "DEVELOPMENT"


def _trial(alert):
    return alert.get("trial") if isinstance(alert.get("trial"), dict) else {}


def _trial_value(alert, *keys):
    trial = _trial(alert)
    for key in keys:
        value = trial.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _journey_status(alert):
    event = _event(alert)
    status = _trial_value(alert, "status", "overall_status") or event.get("status")
    phase = _trial_value(alert, "phase", "overall_phase") or event.get("phase")
    parts = []
    if phase:
        parts.append(f"Fase: {phase}")
    if status:
        parts.append(f"Stato: {status}")
    return " | ".join(parts) or "Non disponibile"


def _next_step(alert):
    event = _event(alert)
    next_date = (
        _trial_value(alert, "primary_completion_date", "study_completion_date")
        or event.get("event_date")
    )
    return (
        f"Prossima milestone/data disponibile: {next_date}"
        if next_date else "Non disponibile nella fonte analizzata."
    )


def _knowledge_explainer(alert):
    event = _event(alert)
    explainer = alert.get("catalyst_explainer") or {}
    summary = (
        alert.get("summary") or event.get("summary")
        or _trial_value(alert, "brief_summary", "summary")
    )
    indication = explainer.get("indication") or _trial_value(alert, "conditions")
    stage = explainer.get("stage") or _trial_value(alert, "phase", "overall_phase")
    return {
        "what_is": explainer.get("what_is") or summary or "Descrizione non disponibile nella fonte analizzata.",
        "mechanism": explainer.get("mechanism") or event.get("mechanism"),
        "indication": indication or "Non disponibile nella fonte analizzata.",
        "stage": stage or "Non disponibile.",
        "why_it_matters": explainer.get("why_it_matters") or "Aggiornamento rilevante per seguire l'evoluzione del programma.",
        "company_impact": explainer.get("company_impact") or "Da valutare nel contesto della pipeline e dello sviluppo del programma.",
    }


def _reaction_line(alert):
    reaction = alert.get("market_reaction") or alert.get("reaction") or {}
    values = []
    for label, key in (
        ("1m", "reaction_1m_pct"), ("5m", "reaction_5m_pct"),
        ("15m", "reaction_15m_pct"), ("30m", "reaction_30m_pct"),
        ("60m", "reaction_60m_pct"),
    ):
        value = reaction.get(key)
        if value is not None:
            values.append(f"{label} {float(value):+.2f}%")
    if not values:
        return ""
    return " | ".join(values)


def format_pharma_intelligence_email(alert):
    """Build a knowledge-first Italian Pharma Intelligence email."""
    event = _event(alert)
    ticker = alert.get("ticker", "UNKNOWN")
    program = alert.get("program", "UNKNOWN")
    company = alert.get("company") or event.get("company")
    category = _category(alert)
    subtype = _subtype(alert) or "PHARMA_EVENT"
    event_type = _event_type(alert) or "PHARMA_EVENT"
    title = alert.get("title") or event.get("title") or "Aggiornamento Pharma"
    summary = alert.get("summary") or event.get("summary") or ""
    source = alert.get("source") or event.get("source") or "Non disponibile"
    source_url = alert.get("url") or alert.get("source_url") or event.get("url") or event.get("source_url")
    nct_id = alert.get("nct_id") or event.get("nct_id")
    changes = alert.get("changes") if isinstance(alert.get("changes"), dict) else {}
    explainer = _knowledge_explainer(alert)
    journey = _journey_status(alert)

    lines = [
        "PHARMA RADAR — PHARMA INTELLIGENCE",
        "",
        f"📚 {category} | {ticker} — {program}",
    ]
    if company:
        lines.append(f"🏢 Azienda: {company}")
    if nct_id:
        lines.append(f"🧪 Trial: {nct_id}")
    lines += [
        f"📍 Evento: {event_type} — {subtype}",
        f"🧭 Percorso: {journey}",
        "",
        f"📰 {title}",
    ]
    if summary:
        lines += ["", "SINTESI", " ".join(str(summary).split())[:1600]]

    lines += [
        "",
        "💊 COS'È / COSA FA",
        str(explainer["what_is"]),
        "",
        "🩺 INDICAZIONE",
        str(explainer["indication"]),
        "",
        "🧪 FASE / STATO",
        str(explainer["stage"]),
    ]
    if explainer.get("mechanism"):
        lines += ["", "⚙️ MECCANISMO", str(explainer["mechanism"])]

    if changes:
        lines += ["", "🔄 COSA È CAMBIATO"]
        for field, change in changes.items():
            if isinstance(change, dict):
                lines.append(f"• {field}: {change.get('old')} → {change.get('new')}")
            else:
                lines.append(f"• {field}: {change}")

    lines += [
        "",
        "🎯 PERCHÉ È INTERESSANTE",
        str(explainer["why_it_matters"]),
        "",
        "➡️ PROSSIMO PASSO / MILESTONE",
        _next_step(alert),
        "",
        "🏢 RUOLO NELLA PIPELINE",
        str(explainer["company_impact"]),
    ]

    reaction = _reaction_line(alert)
    if reaction:
        lines += ["", "📈 REAZIONE DEL MERCATO (solo contesto)", reaction]

    lines += [
        "",
        "ℹ️ CRITERIO DEL REPORT",
        "Questa email ha finalità esclusivamente conoscitiva: segue l'evoluzione di farmaci, trial e percorso regolatorio. I punteggi Trading Intelligence non determinano l'invio.",
        "",
        f"Fonte: {source}",
    ]
    if source_url:
        lines.append(f"Link fonte ufficiale: {source_url}")
    return "\n".join(lines)


def _smtp_config():
    host = os.getenv("PHARMA_SMTP_HOST") or os.getenv("SMTP_HOST")
    port = int(os.getenv("PHARMA_SMTP_PORT") or os.getenv("SMTP_PORT") or "465")
    username = os.getenv("PHARMA_SMTP_USERNAME") or os.getenv("SMTP_USERNAME")
    password = os.getenv("PHARMA_SMTP_PASSWORD") or os.getenv("SMTP_PASSWORD")
    sender = os.getenv("PHARMA_EMAIL_FROM") or os.getenv("EMAIL_FROM") or username
    recipient = os.getenv("PHARMA_EMAIL_TO") or os.getenv("EMAIL_TO")
    return host, port, username, password, sender, recipient


def email_is_configured():
    try:
        host, _port, username, password, sender, recipient = _smtp_config()
    except (TypeError, ValueError):
        return False
    return all((host, username, password, sender, recipient))


def send_pharma_intelligence_email(alert):
    """Send one knowledge-first intelligence email."""
    if not is_pharma_intelligence_event(alert) or not email_is_configured():
        return False

    host, port, username, password, sender, recipient = _smtp_config()
    key = email_delivery_key(alert)
    sent_keys = load_email_state(EMAIL_STATE_PATH)
    if key in sent_keys:
        return False

    ticker = alert.get("ticker", "UNKNOWN")
    program = alert.get("program", "UNKNOWN")
    subtype = _subtype(alert) or "PHARMA_EVENT"

    message = EmailMessage()
    message["Subject"] = f"Pharma Radar | {_category(alert)} | {ticker} — {program} | {subtype}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(format_pharma_intelligence_email(alert))

    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException, TimeoutError, ValueError) as exc:
        print(f"Pharma Intelligence email error for {ticker}: {exc}")
        return False

    sent_keys.add(key)
    save_email_state(sent_keys, EMAIL_STATE_PATH)
    return True


def send_pharma_intelligence_emails(alerts):
    """Send material Pharma Intelligence emails once per unique event."""
    if not email_is_configured():
        return 0
    sent = 0
    for alert in alerts or []:
        if send_pharma_intelligence_email(alert):
            sent += 1
    return sent
