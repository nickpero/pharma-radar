"""Append-only audit trail for Telegram catalyst delivery attempts and confirmations."""

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_FILE = ROOT / "data" / "telegram_delivery_audit.json"


def append_delivery_audit(
    alerts,
    key_fn,
    delivery_status,
    attempted_at,
    confirmed_at=None,
    message_id=None,
    error=None,
    path=AUDIT_FILE,
):
    """Append one delivery lifecycle record per alert, preserving earlier attempts."""
    if path.exists():
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Telegram delivery audit is unreadable: {path}") from exc
        if not isinstance(records, list):
            raise RuntimeError(f"Telegram delivery audit has invalid structure: {path}")
    else:
        records = []

    for alert in alerts or []:
        event = alert.get("event") if isinstance(alert.get("event"), dict) else {}
        records.append({
            "dedup_key": str(key_fn(alert)),
            "ticker": str(alert.get("ticker") or "UNKNOWN").upper(),
            "program": alert.get("program"),
            "event_type": event.get("subtype") or alert.get("subtype") or alert.get("type"),
            "first_published_at": alert.get("published_at") or event.get("published_at"),
            "first_seen_at": alert.get("first_seen_at"),
            "qualified_at": alert.get("qualified_at"),
            "telegram_attempted_at": attempted_at,
            "telegram_confirmed_at": confirmed_at,
            "telegram_message_id": message_id,
            "delivery_status": str(delivery_status).upper(),
            **({"error": str(error)[:500]} if error else {}),
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise
    return records[-len(alerts or []):] if alerts else []
