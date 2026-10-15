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

API = "https://api.github.com"
REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
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
    url = f"{API}/repos/{REPO}/actions/workflows/radar.yml/runs?per_page=10"
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


def open_health_issue():
    issues = request(f"{API}/repos/{REPO}/issues?state=open&per_page=100")
    return next((item for item in issues
                 if item.get("title") == ISSUE_TITLE and "pull_request" not in item), None)


def main():
    healthy, detail = inspect_latest_run()
    issue = open_health_issue()
    if not healthy and issue is None:
        body = (
            "Il monitor indipendente ha rilevato un problema nel workflow di produzione.\\n\\n"
            f"- Rilevato (UTC): {datetime.now(timezone.utc).isoformat()}\\n"
            f"- Dettaglio: {detail}\\n\\n"
            "Verificare GitHub Actions e la consegna Telegram prima di considerare il Radar operativo."
        )
        # Notify first so a Telegram failure does not leave an open issue that
        # suppresses all retries on later scheduled checks.
        telegram(f"🚨 PHARMA RADAR — CONTROLLO OPERATIVO\\n{detail}")
        created = request(f"{API}/repos/{REPO}/issues", method="POST", payload={
            "title": ISSUE_TITLE, "body": body,
        })
        print(f"UNHEALTHY: issue aperta e alert Telegram inviato ({created.get('html_url', '')}).")
    elif not healthy:
        print(f"UNHEALTHY: issue già aperta; nessun alert duplicato. {detail}")
    elif issue is not None:
        # Notify recovery before closing the issue, so a transient Telegram
        # failure can be retried by the next scheduled check.
        telegram(f"✅ PHARMA RADAR — SERVIZIO RIPRISTINATO\\n{detail}")
        request(f"{API}/repos/{REPO}/issues/{issue['number']}", method="PATCH",
                payload={"state": "closed", "state_reason": "completed"})
        print("RECOVERED: issue chiusa e ripristino notificato.")
    else:
        print(f"HEALTHY: {detail}")


if __name__ == "__main__":
    main()
