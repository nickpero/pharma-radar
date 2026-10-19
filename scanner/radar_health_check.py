"""Scheduled health check for the production Pharma Radar workflow.

Alerts only on state transitions: first unhealthy observation opens a GitHub
issue and sends Telegram; recovery closes the issue and sends one recovery note.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from math import ceil
from pathlib import Path

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ISSUE_TITLE = "[Radar Health] Production workflow unhealthy"


def request(url, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("Telegram secrets are not configured for the health monitor")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": message}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.loads(response.read())
    if not result.get("ok"):
        raise RuntimeError("Telegram API did not confirm the health message")


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def inspect_latest_run():
    url = f"{API}/repos/{REPO}/actions/workflows/radar.yml/runs?branch=main&per_page=10"
    runs = request(url).get("workflow_runs", [])
    if not runs:
        return False, "Nessuna esecuzione del workflow radar.yml trovata."
    latest = max(runs, key=lambda row: row.get("created_at", ""))
    now = datetime.now(timezone.utc)
    created = utc(latest["created_at"])
    age = now - created
    status = latest.get("status")
    conclusion = latest.get("conclusion")
    run_url = latest.get("html_url", "")
    if status in {"queued", "in_progress"}:
        if age <= timedelta(minutes=25):
            return True, f"Ultima esecuzione in coda/in corso ({int(age.total_seconds() // 60)} min): {run_url}"
        return False, f"Workflow bloccato in coda/in corso da oltre 25 minuti: {run_url}"
    updated = utc(latest.get("updated_at") or latest["created_at"])
    if conclusion != "success":
        return False, f"Ultimo run concluso con esito '{conclusion or status}': {run_url}"
    if now - updated > timedelta(minutes=45):
        return False, f"Nessun run completato con successo negli ultimi 45 minuti. Ultimo: {run_url}"
    return True, f"Ultimo run completato correttamente: {run_url}"


def inspect_source_coverage(state_path=None, sources_path=None, now=None):
    """Detect degraded or stale official-source collection, not just failed workflows."""
    root = Path(__file__).resolve().parents[1]
    state_path = Path(state_path) if state_path else root / "data" / "primary_source_discovery_state.json"
    sources_path = Path(sources_path) if sources_path else root / "data" / "primary_source_pages.json"
    now = now or datetime.now(timezone.utc)

    # On first deployment, no collector state exists until the first production scan.
    if not state_path.exists():
        return True, "Copertura delle fonti ufficiali non ancora inizializzata."

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        sources = json.loads(sources_path.read_text(encoding="utf-8"))
        checked_at = utc(state["last_checked_at"])
        successful = int(state["successful_sources"])
        total = len(sources)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return False, f"Stato della raccolta fonti illeggibile o incompleto: {type(exc).__name__}."

    if total < 1:
        return False, "Configurazione delle fonti ufficiali vuota."
    age = now - checked_at
    if age > timedelta(minutes=35):
        return False, (
            f"Raccolta fonti ufficiali non aggiornata da {int(age.total_seconds() // 60)} minuti."
        )
    minimum = max(1, ceil(total * 0.75))
    if successful < minimum:
        errors = state.get("source_errors") or []
        sample = "; ".join(str(item) for item in errors[:3])
        suffix = f" Dettagli: {sample}" if sample else ""
        return False, (
            f"Copertura fonti ufficiali degradata: {successful}/{total} riuscite; "
            f"soglia minima {minimum}/{total}.{suffix}"
        )
    return True, f"Fonti ufficiali aggiornate: {successful}/{total} riuscite."

def open_health_issue():
    issues = request(f"{API}/repos/{REPO}/issues?state=open&per_page=100")
    return next((item for item in issues
                 if item.get("title") == ISSUE_TITLE and "pull_request" not in item), None)


def main():
    healthy, detail = inspect_latest_run()
    sources_healthy, sources_detail = inspect_source_coverage()
    if healthy and not sources_healthy:
        healthy, detail = False, f"{sources_detail} Ultimo workflow: {detail}"
    elif healthy:
        detail = f"{detail}\n{sources_detail}"
    issue = open_health_issue()
    if not healthy and issue is None:
        body = (
            "Il monitor indipendente ha rilevato un problema nel workflow di produzione.\n\n"
            f"- Rilevato (UTC): {datetime.now(timezone.utc).isoformat()}\n"
            f"- Dettaglio: {detail}\n\n"
            "Verificare GitHub Actions e la consegna Telegram prima di considerare il Radar operativo."
        )
        # Notify first so a Telegram failure does not leave an open issue that
        # suppresses all retries on later scheduled checks.
        telegram(f"🚨 PHARMA RADAR — CONTROLLO OPERATIVO\n{detail}")
        created = request(f"{API}/repos/{REPO}/issues", method="POST", payload={
            "title": ISSUE_TITLE, "body": body,
        })
        print(f"UNHEALTHY: issue aperta e alert Telegram inviato ({created.get('html_url', '')}).")
    elif not healthy:
        print(f"UNHEALTHY: issue già aperta; nessun alert duplicato. {detail}")
    elif issue is not None:
        # Notify recovery before closing the issue, so a transient Telegram
        # failure can be retried by the next scheduled check.
        telegram(f"✅ PHARMA RADAR — SERVIZIO RIPRISTINATO\n{detail}")
        request(f"{API}/repos/{REPO}/issues/{issue['number']}", method="PATCH",
                payload={"state": "closed", "state_reason": "completed"})
        print("RECOVERED: issue chiusa e ripristino notificato.")
    else:
        print(f"HEALTHY: {detail}")


if __name__ == "__main__":
    main()
