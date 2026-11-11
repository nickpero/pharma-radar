"""Safely reconcile concurrent Pharma Radar JSON state commits.

Catalyst history is an append/upsert store keyed by deterministic memory keys.
The opportunity board is a derived snapshot and is rebuilt from the merged
history so a concurrent scan cannot erase catalysts recorded by another run.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scanner.opportunity_board import build_opportunity_board

MEMORY_PATH = "data/catalyst_history.json"
BOARD_PATH = "data/opportunity_board.json"
WATCHLIST_PATH = Path("data/watchlist.json")
MAX_RECORDS = 5000


def _git_json(ref: str, path: str) -> dict:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        # A file absent from the older side of a merge is an empty baseline.
        if "does not exist" in result.stderr or "Path '" in result.stderr:
            return {}
        raise RuntimeError(f"Unable to read {ref}:{path}: {result.stderr.strip()}")
    raw = result.stdout.strip()
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{ref}:{path} must contain a JSON object")
    return value


def _timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def merge_memory(local: dict, remote: dict) -> dict:
    """Union keyed catalyst records, preferring newer non-empty observations."""
    merged = {}
    for key in set(local) | set(remote):
        left = local.get(key) if isinstance(local.get(key), dict) else {}
        right = remote.get(key) if isinstance(remote.get(key), dict) else {}
        left_time = _timestamp(left.get("recorded_at"))
        right_time = _timestamp(right.get("recorded_at"))
        newer, older = (right, left) if (right_time or datetime.min.replace(tzinfo=timezone.utc)) >= (left_time or datetime.min.replace(tzinfo=timezone.utc)) else (left, right)
        row = dict(older)
        row.update(newer)
        # A newer scan may have incomplete fields; never discard known values.
        for field, value in older.items():
            if row.get(field) is None or row.get(field) == "":
                row[field] = value
        seen = [value for value in (left.get("first_seen_at"), right.get("first_seen_at")) if value]
        if seen:
            parsed_seen = [(value, _timestamp(value)) for value in seen]
            valid_seen = [(value, stamp) for value, stamp in parsed_seen if stamp]
            row["first_seen_at"] = min(valid_seen, key=lambda item: item[1])[0] if valid_seen else seen[0]
        row["memory_key"] = row.get("memory_key") or key
        merged[key] = row

    if len(merged) > MAX_RECORDS:
        ordered = sorted(
            merged.items(),
            key=lambda item: _timestamp(item[1].get("recorded_at")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        merged = dict(ordered[:MAX_RECORDS])
    return merged


def _newer_board(local: dict, remote: dict) -> dict:
    local_time = _timestamp(local.get("generated_at"))
    remote_time = _timestamp(remote.get("generated_at"))
    return remote if (remote_time or datetime.min.replace(tzinfo=timezone.utc)) >= (local_time or datetime.min.replace(tzinfo=timezone.utc)) else local


def reconcile(local_ref: str, remote_ref: str) -> dict:
    local_memory = _git_json(local_ref, MEMORY_PATH)
    remote_memory = _git_json(remote_ref, MEMORY_PATH)
    merged_memory = merge_memory(local_memory, remote_memory)

    local_board = _git_json(local_ref, BOARD_PATH)
    remote_board = _git_json(remote_ref, BOARD_PATH)
    latest_board = _newer_board(local_board, remote_board)

    if not WATCHLIST_PATH.exists():
        raise FileNotFoundError(f"Required watchlist not found: {WATCHLIST_PATH}")
    watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    if not isinstance(watchlist, dict):
        raise ValueError("data/watchlist.json must contain a JSON object")

    board = build_opportunity_board(
        events=list(merged_memory.values()),
        watchlist=watchlist,
        upcoming=latest_board.get("upcoming", []),
    )

    Path(MEMORY_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(MEMORY_PATH).write_text(
        json.dumps(merged_memory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(BOARD_PATH).write_text(
        json.dumps(board, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"memory_records": len(merged_memory), "board_counts": board["counts"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-ref", required=True)
    parser.add_argument("--remote-ref", required=True)
    args = parser.parse_args()
    summary = reconcile(args.local_ref, args.remote_ref)
    print(
        "Merged concurrent Pharma Radar state: "
        f"memory_records={summary['memory_records']} "
        f"board_counts={summary['board_counts']}"
    )


if __name__ == "__main__":
    main()
