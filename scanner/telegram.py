"""
Pharma Radar — Telegram Alerts

Gestisce l'invio degli alert Pharma Radar tramite Telegram Bot API.
"""

import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import requests
from scanner.priority import get_alert_tier, enrich_alert_priority
from scanner.italian_translation import translate_to_italian, alert_protected_terms

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


# Display-only aliases. The underlying entity/program identity remains unchanged.
DRUG_DISPLAY_NAMES = {
    "zilganersen": "Zilganersen (Zanvastro)",
}

EVENT_DISPLAY_NAMES = {
    "FDA_APPROVAL": "APPROVAZIONE FDA",
    "FDA_MEETING": "INCONTRO FDA",
    "FDA_PATHWAY": "PERCORSO REGOLATORIO FDA",
    "FDA_REJECTION": "RIFIUTO FDA",
    "FDA_SAFETY_WARNING": "AVVISO DI SICUREZZA FDA",
    "CLINICAL_RESULTS": "RISULTATI CLINICI",
    "TOPLINE_RESULTS": "RISULTATI PRINCIPALI",
    "PRIMARY_ENDPOINT_MET": "OBIETTIVO PRIMARIO RAGGIUNTO",
    "PRIMARY_ENDPOINT_FAILED": "OBIETTIVO PRIMARIO NON RAGGIUNTO",
    "MAINTENANCE_DATA": "DATI DI MANTENIMENTO",
    "DOSE_RESPONSE": "RISPOSTA ALLA DOSE",
    "SECONDARY_ENDPOINT_MET": "OBIETTIVO SECONDARIO RAGGIUNTO",
    "SECONDARY_ENDPOINT_FAILED": "OBIETTIVO SECONDARIO NON RAGGIUNTO",
    "EFFICACY_SIGNAL": "SEGNALE DI EFFICACIA",
    "SAFETY_SIGNAL": "SEGNALE DI SICUREZZA",
    "LABEL_EXPANSION": "ESTENSIONE DELL'INDICAZIONE",
    "REGULATORY_FILING": "DEPOSITO REGOLATORIO",
    "TRIAL_HOLD": "SOSPENSIONE DELLO STUDIO",
    "TRIAL_HOLD_LIFTED": "RIPRESA DELLO STUDIO",
    "PHASE_ADVANCED": "AVANZAMENTO DI FASE",
    "PHASE_DATA_UPDATE": "AGGIORNAMENTO DEI DATI DI FASE",
    "EXPLORATORY_DATA": "DATI ESPLORATIVI",
    "DATE_ACCELERATED": "DATA ANTICIPATA",
    "DATE_DELAYED": "DATA POSTICIPATA",
    "CLINICAL_REVIEW_UPDATE": "AGGIORNAMENTO DELLA REVISIONE CLINICA",
    "TRIAL_COMPLETED": "STUDIO COMPLETATO",
    "TRIAL_STOPPED": "STUDIO INTERROTTO",
    "TRIAL_STATUS_UNKNOWN": "STATO DELLO STUDIO NON NOTO",
}


def send_telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID is not configured")
    if not isinstance(message, str):
        message = str(message)
    if not message.strip():
        raise ValueError("Telegram message is empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH - 20] + "\n\n[TRUNCATED]"
    response = requests.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_direction_icon(direction):
    direction = str(direction or "UNKNOWN").upper()
    if direction in {"POSITIVE", "CATALYST"}:
        return "📈"
    if direction == "NEGATIVE":
        return "📉"
    return "⚪"


def get_severity_icon(label):
    return {"CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "🟠"}.get(
        str(label or "LOW").upper(), "⚪"
    )


def _clean_text(value, limit=None):
    text = " ".join(str(value or "").split())
    return text[:limit] if limit else text


def _num(value, digits=2):
    try:
        return f"{float(value):+.{digits}f}"
    except (TypeError, ValueError):
        return None


def _known(value):
    text = _clean_text(value)
    return text if text and text.upper() not in {"UNKNOWN", "N/A", "NONE", "NULL", "UNAVAILABLE"} else None


def _drug_name(alert, program):
    """Use a real short drug name when available; never use the article body."""
    for key in ("drug_name", "drug"):
        value = _clean_text(alert.get(key), 100)
        if value and len(value) <= 100:
            return value
    return DRUG_DISPLAY_NAMES.get(str(program).strip().lower(), program)


def _it_status(value):
    """Traduce etichette interne comuni nelle notifiche rivolte all'utente."""
    raw = _clean_text(value, 100)
    key = raw.upper()
    labels = {
        "CRITICAL": "CRITICO", "HIGH": "ALTO", "MEDIUM": "MEDIO", "LOW": "BASSO",
        "POSITIVE": "POSITIVA", "NEGATIVE": "NEGATIVA", "UNKNOWN": "NON DISPONIBILE",
        "UNAVAILABLE": "NON DISPONIBILE", "IMMEDIATE": "IMMEDIATA",
        "DIVERGENT": "DIVERGENTE", "STRONG POSITIVE": "FORTEMENTE POSITIVA",
        "STRONG NEGATIVE": "FORTEMENTE NEGATIVA", "CONFIRMED": "CONFERMATA",
        "UNCONFIRMED": "NON CONFERMATA", "FDA_UPDATE": "AGGIORNAMENTO FDA",
        "1-7D": "1–7 giorni", "1-3D": "1–3 giorni", "1D": "1 giorno", "2-4W": "2–4 settimane", "1-4W": "1–4 settimane",
        "NEXT_24H": "PROSSIME 24 ORE", "NEXT 24H": "PROSSIME 24 ORE", "NEXT_48H": "PROSSIME 48 ORE", "NEXT 7D": "PROSSIMI 7 GIORNI", "UNKNOWN_TIME": "ORA NON DISPONIBILE", "N/A": "NON DISPONIBILE", "NONE": "NON DISPONIBILE", 
        "EMA_UPDATE": "AGGIORNAMENTO EMA", "WATCH": "DA MONITORARE",
    }
    if key in labels:
        return labels[key]
    if key.endswith("D") and key[:-1].isdigit():
        return f"{key[:-1]} giorni"
    return raw.replace("_", " ") if raw else "NON DISPONIBILE"


def _event_display_name(subtype, event_type):
    raw = _clean_text(subtype or event_type, 100).upper()
    if raw in EVENT_DISPLAY_NAMES:
        return EVENT_DISPLAY_NAMES[raw]
    return _it_status(raw) if raw else "EVENTO"


def _parse_iso_date(value):
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None



def _format_timestamp(value):
    """Format a source timestamp in Italian local time without inventing missing data."""
    if not value:
        return "NON DISPONIBILE"
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed_date = _parse_iso_date(text)
        return f"{parsed_date.strftime('%d/%m/%Y')} (ora non disponibile)" if parsed_date else "NON DISPONIBILE"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(ZoneInfo("Europe/Rome"))
    return local.strftime("%d/%m/%Y %H:%M %Z")


def _timeline_details(alert, event, subtype):
    """Return trader-readable details for clinical-trial timeline changes."""
    if str(subtype or "").upper() not in {"DATE_ACCELERATED", "DATE_DELAYED"}:
        return None

    old_value = event.get("old_value")
    new_value = event.get("new_value")
    old_date = _parse_iso_date(old_value)
    new_date = _parse_iso_date(new_value)
    field = _clean_text(event.get("field") or alert.get("changed_field"), 100)

    field_labels = {
        "primary_completion_date": "Completamento primario",
        "study_completion_date": "Completamento dello studio",
        "completion_date": "Completamento",
    }
    field_display = field_labels.get(field, field.replace("_", " ").title() if field else "Cronologia dello studio")

    details = [
        "🚨 MODIFICA DELLE DATE DELLO STUDIO",
        f"📌 Campo: {field_display}",
    ]
    if old_value:
        details.append(f"📅 Data precedente: {old_value}")
    if new_value:
        details.append(f"📅 Nuova data: {new_value}")
    if old_date and new_date:
        delta_days = (new_date - old_date).days
        if delta_days < 0:
            details.append(f"⏩ Anticipata di {abs(delta_days)} giorni")
        elif delta_days > 0:
            details.append(f"⏳ Posticipata di {delta_days} giorni")
        else:
            details.append("↔️ Nessuna variazione di giorni")
    details.append("ℹ️ È cambiata solo la tempistica: i risultati clinici non sono ancora stati comunicati.")
    return details


def _why_it_matters(alert, event, subtype):
    explainer = alert.get("catalyst_explainer") or {}
    why = _clean_text(explainer.get("why_it_matters"), 280)
    if why:
        return why

    why = _clean_text(event.get("why_it_matters") or event.get("trading_impact_reason"), 280)
    if why:
        return why

    fallback = {
        "FDA_APPROVAL": "Un’approvazione FDA confermata è una tappa regolatoria e commerciale importante.",
        "FDA_MEETING": "Incontro o confronto con la FDA: non equivale a un’approvazione.",
        "FDA_PATHWAY": "Discussione sul percorso regolatorio: l’approvazione non è confermata.",
        "FDA_REJECTION": "Un rifiuto della FDA è un ostacolo regolatorio importante e può cambiare le prospettive commerciali del programma.",
        "FDA_SAFETY_WARNING": "Un nuovo avviso di sicurezza FDA può incidere sul profilo di rischio, sull’indicazione e sulle prospettive commerciali del prodotto.",
        "CLINICAL_RESULTS": "I risultati clinici possono modificare in modo significativo la probabilità di successo e la valutazione del programma.",
        "CLINICAL_REVIEW_UPDATE": "Una revisione del comitato indipendente, in cieco o ad interim può aggiornare le aspettative di sviluppo, ma non equivale alla pubblicazione dei risultati di efficacia o dei risultati principali.",
        "LABEL_EXPANSION": "L’estensione dell’indicazione amplia la popolazione di pazienti potenzialmente trattabili e può modificare le opportunità commerciali del prodotto.",
    }
    return fallback.get(str(subtype).upper())


def format_catalyst_alert(alert):
    """Create a compact Telegram alert optimized for rapid human scanning."""
    ticker = _clean_text(alert.get("ticker", "UNKNOWN"), 20).upper()
    program = _clean_text(alert.get("program", "UNKNOWN"), 80)
    drug_name = _drug_name(alert, program)
    event = alert.get("event", {})
    if not isinstance(event, dict):
        event = {}

    event_type = event.get("type", alert.get("event_type", "UNKNOWN"))
    score = event.get("score", alert.get("score", 0))
    label = event.get("label", alert.get("label", "LOW"))
    subtype = event.get("subtype", alert.get("subtype", ""))
    trading_impact = event.get("trading_impact", alert.get("trading_impact", "LOW"))
    urgency = event.get("urgency", alert.get("urgency", "LOW"))
    alert_priority = alert.get("alert_priority", event.get("alert_priority"))
    setup_score = alert.get("trading_setup_score", event.get("trading_setup_score", 0))
    window = alert.get("trading_window", event.get("trading_window", "UNKNOWN"))
    reaction = alert.get("market_reaction") or event.get("market_reaction") or {}
    reaction_pct = alert.get("reaction_pct", reaction.get("reaction_pct"))
    reaction_direction = alert.get("reaction_direction", reaction.get("reaction_direction", "UNKNOWN"))
    title = _clean_text(alert.get("title") or event.get("title"), 260)
    why = _why_it_matters(alert, event, subtype)
    event_display = _event_display_name(subtype, event_type)
    early = alert.get("early_discovery") is True

    if alert_priority is None:
        priority_event = dict(event)
        priority_event.update({"score": score, "trading_impact": trading_impact, "urgency": urgency})
        alert_priority = enrich_alert_priority(priority_event).get("alert_priority", 0)
    alert_tier = event.get("alert_tier", alert.get("alert_tier")) or get_alert_tier(alert_priority)
    telegram_action = str(alert.get("telegram_action", "")).upper()
    display_tier = "DA VERIFICARE · NON CONFERMATO" if early else ("DA MONITORARE · NON URGENTE" if telegram_action == "WATCH" else _it_status(alert_tier))
    tier_icon = "👀" if early or telegram_action == "WATCH" else get_severity_icon(alert_tier)

    lines = [
        "🟡 PHARMA RADAR — CATALIZZATORE PRELIMINARE" if early else "🚨 PHARMA RADAR",
        "━━━━━━━━━━━━━━━━━━",
        f"{tier_icon} {display_tier}",
        *(["👀 DA MONITORARE — informativo, non urgente"] if telegram_action == "WATCH" and not early else []),
        "",
        f"🧬 {ticker}",
        f"💊 {drug_name}",
        "",
        f"📰 {event_display}",
        title or "Titolo non disponibile nella fonte.",
    ]

    timeline_details = _timeline_details(alert, event, subtype)
    if timeline_details:
        lines.extend(["", *timeline_details])

    trial = alert.get("trial") if isinstance(alert.get("trial"), dict) else {}
    if str(subtype or "").upper() == "TRIAL_COMPLETED":
        nct_id = _clean_text(alert.get("nct_id") or trial.get("nct_id"), 40)
        completion_date = _clean_text(trial.get("completion_date"), 40)
        lines.extend([
            "",
            "ℹ️ Stato su ClinicalTrials.gov: COMPLETATO — non implica risultati positivi.",
        ])
        if nct_id:
            lines.append(f"🔗 Registro: {nct_id}")
        if completion_date:
            lines.append(f"📅 Completamento studio registrato: {completion_date}")

    if alert.get("post_spike_watch") is True:
        retracement = _num(alert.get("post_spike_retracement_pct"))
        spike_pct = _num(alert.get("post_spike_pct"))
        volume_ratio = alert.get("post_spike_volume_ratio")
        spike_price = alert.get("post_spike_price")
        current_price = alert.get("post_spike_current_price")
        lines.extend([
            "",
            "🔄 MONITORAGGIO DOPO IL RIALZO",
            f"📅 Data del rialzo: {alert.get('post_spike_date', 'non disponibile')}",
            f"🚀 Rialzo: {spike_pct}% · Volume {volume_ratio:.1f}×" if isinstance(volume_ratio, (int, float)) and spike_pct is not None else "🚀 Rialzo: dato disponibile",
            f"💵 Chiusura al rialzo: {spike_price} → Prezzo attuale: {current_price}",
            f"📉 Ritracciamento: {retracement}%" if retracement is not None else "📉 Ritracciamento: non disponibile",
            "ℹ️ Il catalizzatore ha già prodotto un movimento rilevante; si monitora l’andamento successivo.",
        ])

    lines.extend([
        "",
        (f"🎯 Potenziale catalizzatore (non confermato): punteggio interno {score}/100" if early else f"🎯 Catalizzatore: {score}/100 · {_it_status(label)}"),
        *( [f"🧠 Dati clinici: {alert.get('catalyst_category', event.get('catalyst_category'))} · Novità {alert.get('novelty_score', event.get('novelty_score', 0))}/100 · Impatto sul mercato {alert.get('market_impact_score', event.get('market_impact_score', 0))}/100"] if alert.get("clinical_data_release") and not early else [] ),
        (f"📌 Punteggio interno: {alert_priority}/100 · non operativo" if early else f"🚨 Priorità: {alert_priority}/100 · {_it_status(alert_tier)}"),
        (f"📊 Configurazione: NON CONFERMATA · Finestra temporale: {_it_status(window)}" if early else f"📊 Configurazione: {setup_score}/100 · Finestra temporale: {_it_status(window)}"),
        "",
        "📈 Reazione del mercato: " + (
            f"{_num(reaction_pct)}% · {_it_status(reaction_direction)}"
            if reaction_pct is not None and _num(reaction_pct) is not None
            else " | ".join(
                f"{label_window} {_num(reaction.get(f'reaction_{label_window}_pct'))}%"
                for label_window in ("1m", "5m", "15m", "30m", "60m")
                if _num(reaction.get(f"reaction_{label_window}_pct")) is not None
            ) or "N/A"
        ),
    ])

    published_value = (
        alert.get("first_published_at") or alert.get("published_at")
        or alert.get("publication_date") or event.get("first_published_at")
        or event.get("published_at") or event.get("publication_date")
    )
    detected_value = alert.get("detected_at") or datetime.now(timezone.utc).isoformat()
    lines.extend([
        "",
        f"🗞 Pubblicata: {_format_timestamp(published_value)}",
        f"🛰 Rilevata dal Radar: {_format_timestamp(detected_value)}",
    ])
    if str(subtype or "").upper() == "TRIAL_COMPLETED" and trial.get("last_update"):
        lines.append(f"🗂 Registro aggiornato: {_format_timestamp(trial.get('last_update'))}")
    if early:
        lines.append("⚠️ Rilevazione preliminare: in attesa di conferma da una fonte primaria.")

    if why:
        lines.extend(["", "💡 PERCHÉ È IMPORTANTE", why])

    source = _clean_text(alert.get("source") or event.get("source"))
    if source:
        lines.extend(["", f"🔎 Fonte: {source}"])

    lines.extend(["", "⚠️ Solo a scopo informativo: non è un segnale automatico di acquisto o vendita.", "━━━━━━━━━━━━━━━━━━"])
    return "\n".join(str(line) for line in lines)


def format_divergence_alert(divergence):
    """Create a non-operational alert for strong catalyst/market divergence."""
    ticker = _clean_text(divergence.get("ticker", "UNKNOWN"), 20).upper()
    program = _clean_text(divergence.get("program", "UNKNOWN"), 80)
    daily_pct = _num(divergence.get("daily_pct"))
    catalyst = divergence.get("catalyst_score", "NON DISPONIBILE")
    ti = divergence.get("trading_intelligence_score", "NON DISPONIBILE")
    edge = divergence.get("historical_edge_median_1d_pct", "NON DISPONIBILE")
    win = divergence.get("historical_edge_win_rate_1d")
    win_text = f"{float(win) * 100:.1f}%" if win is not None else "NON DISPONIBILE"
    return "\n".join([
        "⚠️ PHARMA RADAR — DIVERGENZA",
        "━━━━━━━━━━━━━━━━━━",
        f"🧬 {ticker}",
        f"💊 {program}",
        "",
        "📈 Catalizzatore positivo / 📉 reazione negativa del mercato",
        f"🎯 Catalizzatore: {catalyst}/100",
        f"🧠 Punteggio di analisi: {ti}/100",
        f"📚 Vantaggio storico: {edge}% · Frequenza di esito positivo: {win_text}",
        f"📉 Variazione giornaliera: {daily_pct}% · DIVERGENTE",
        "",
        "ℹ️ Monitoraggio a scopo informativo: non è un segnale di acquisto o vendita.",
        "━━━━━━━━━━━━━━━━━━",
    ])


def send_catalyst_alert(alert):
    return send_telegram(format_catalyst_alert(alert))


def send_catalyst_alerts(alerts):
    return [send_catalyst_alert(alert) for alert in alerts]


def send_divergence_alerts(divergences):
    return [send_telegram(format_divergence_alert(item)) for item in divergences]
