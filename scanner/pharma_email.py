"""
Pharma Radar — Pharma Intelligence Email (5.7.3)

Plain-text Italian intelligence emails for CRITICAL/HIGH catalysts.
Email is optional: if SMTP settings are not configured, sending is skipped.
Delivery is persistent/deduplicated and SMTP failures are fail-safe.
"""

import os
import smtplib
from email.message import EmailMessage

from scanner.pharma_email_state import email_delivery_key, load_email_state, save_email_state


IMPORTANT_LABELS = {"CRITICAL", "HIGH"}


def _label(alert):
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    return str(alert.get("label") or event.get("label") or "LOW").upper()


def _reaction(alert):
    return alert.get("market_reaction") or alert.get("reaction") or {}


def _reaction_line(alert):
    reaction = _reaction(alert)
    values = []
    for label, key in (("1m", "reaction_1m_pct"), ("5m", "reaction_5m_pct"), ("15m", "reaction_15m_pct"), ("30m", "reaction_30m_pct"), ("60m", "reaction_60m_pct")):
        value = reaction.get(key)
        if value is not None:
            values.append(f"{label} {float(value):+.2f}%")
    strength = alert.get("reaction_strength", "UNKNOWN")
    interpretation = alert.get("reaction_interpretation", "UNKNOWN")
    return (" | ".join(values) if values else "Non ancora disponibile") + f" → {strength} / {interpretation}"


def format_pharma_intelligence_email(alert):
    """Build an Italian Pharma Intelligence email for one important alert."""
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    explainer = alert.get("catalyst_explainer") or {}
    ticker = alert.get("ticker", "UNKNOWN")
    program = alert.get("program", "UNKNOWN")
    company = alert.get("company") or event.get("company")
    label = _label(alert)
    priority = alert.get("alert_priority", event.get("alert_priority", 0))
    subtype = event.get("subtype", alert.get("subtype", "UNKNOWN"))
    event_type = event.get("type", alert.get("event_type", "UNKNOWN"))
    title = alert.get("title") or event.get("title") or "Catalyst pharma rilevante"
    summary = alert.get("summary") or event.get("summary") or ""
    source = alert.get("source") or event.get("source") or "Non disponibile"
    source_url = alert.get("url") or alert.get("source_url") or event.get("url") or event.get("source_url")

    lines = [
        "PHARMA RADAR — PHARMA INTELLIGENCE",
        "",
        f"🚨 {ticker} — {program}",
    ]
    if company:
        lines.append(f"🏢 Azienda: {company}")
    lines += [
        f"Priorità: {priority}/100 — {label}",
        f"Evento: {event_type} — {subtype}",
        "",
        f"📰 {title}",
    ]
    if summary:
        lines += ["", "SINTESI DELLA FONTE", " ".join(str(summary).split())[:1200]]

    lines += [
        "",
        "💊 COS'È / COSA FA",
        str(explainer.get("what_is") or "Informazioni sufficienti non disponibili nella fonte analizzata."),
    ]
    if explainer.get("mechanism"):
        lines += ["", "⚙️ MECCANISMO", str(explainer["mechanism"])]
    lines += [
        "",
        "🩺 INDICAZIONE",
        str(explainer.get("indication") or "Non disponibile nella fonte analizzata."),
        "",
        "🧪 FASE DI SVILUPPO",
        str(explainer.get("stage") or "Non disponibile."),
        "",
        "🎯 PERCHÉ CONTA",
        str(explainer.get("why_it_matters") or "Il catalyst merita attenzione per la rilevanza del programma."),
        "",
        "🏢 IMPATTO POTENZIALE SULL'AZIENDA",
        str(explainer.get("company_impact") or "Da valutare in funzione dei dati e del contesto aziendale."),
        "",
        "📈 REAZIONE DEL MERCATO",
        _reaction_line(alert),
        "",
        "⚠️ NOTA",
        "Questo report è uno strumento informativo per valutare il catalyst e non costituisce una raccomandazione automatica di acquisto o vendita.",
        "",
        f"Fonte: {source}",
    ]
    if source_url:
        lines += [f"Link fonte ufficiale: {source_url}"]
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
    """Send one intelligence email. Returns False when skipped or on delivery failure."""
    if _label(alert) not in IMPORTANT_LABELS or not email_is_configured():
        return False

    host, port, username, password, sender, recipient = _smtp_config()
    key = email_delivery_key(alert)
    sent_keys = load_email_state()
    if key in sent_keys:
        return False

    ticker = alert.get("ticker", "UNKNOWN")
    program = alert.get("program", "UNKNOWN")
    label = _label(alert)
    event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
    subtype = event.get("subtype", alert.get("subtype", "CATALYST"))

    message = EmailMessage()
    message["Subject"] = f"Pharma Radar | {label} | {ticker} — {program} | {subtype}"
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
    save_email_state(sent_keys)
    return True


def send_pharma_intelligence_emails(alerts):
    """Send CRITICAL/HIGH intelligence emails once per unique catalyst."""
    if not email_is_configured():
        return 0
    sent = 0
    for alert in alerts or []:
        if send_pharma_intelligence_email(alert):
            sent += 1
    return sent
