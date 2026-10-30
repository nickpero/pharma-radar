"""Discover newly listed clinical press releases on official company pages.

This module deliberately creates review candidates, not live clinical alerts.
A listing page does not establish that a future event date is confirmed.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "data" / "primary_source_pages.json"
STATE_PATH = ROOT / "data" / "primary_source_discovery_state.json"
CANDIDATES_PATH = ROOT / "data" / "primary_source_candidates.json"
KEYWORDS = re.compile(
    r"clinical|phase\s*[123iv]|trial|study|studies|top.?line|readout|"
    r"interim|efficacy|safety|patient|oncology|esmo|asco|ash|aacr|"
    r"present(?:s|ed|ing|ation)?|data|results|endpoint|randomized|"
    r"randomised|primary endpoint|disease|therapeutic",
    re.IGNORECASE,
)
GENERIC = re.compile(
    r"privacy|cookie|contact|careers|investor relations|subscribe|"
    r"webcast|quarterly results|financial results|earnings call",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2}(?:,?\s+20\d{2})?\b|\b20\d{2}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)


def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def _link_text(anchor):
    return " ".join(anchor.get_text(" ", strip=True).split())


def parse_listing_page(html, source, discovered_at=None):
    """Return source-host-validated, keyword-filtered candidate links."""
    discovered_at = discovered_at or datetime.now(timezone.utc).isoformat()
    base = source["listing_url"]
    host = source["allowed_host"].lower()
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        title = _link_text(anchor)
        if len(title) < 18 or len(title) > 500:
            continue
        if not KEYWORDS.search(title) or GENERIC.search(title):
            continue
        url = urljoin(base, anchor["href"])
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != host:
            continue
        if url.rstrip("/") == base.rstrip("/"):
            continue
        if url in seen:
            continue
        seen.add(url)
        context = " ".join(anchor.parent.get_text(" ", strip=True).split())[:1200]
        date_match = DATE_PATTERN.search(context)
        candidates.append({
            "ticker": str(source["ticker"]).upper(),
            "company": source["company"],
            "title": title,
            "source_url": url,
            "listing_url": base,
            "source_host": host,
            "discovered_at": discovered_at,
            "listing_context": context,
            "publication_date_candidate": date_match.group(0) if date_match else None,
            "review_status": "PENDING_REVIEW",
            "event_type": None,
            "event_date": None,
            "event_window": None,
            "notes": "Candidate discovered from an official company page; verify the release and any future event date before alerting.",
        })
    return candidates


def collect_candidates(sources=None, state_path=None, candidates_path=None, session=None):
    sources = sources if sources is not None else load_json(SOURCES_PATH, [])
    state_path = Path(state_path) if state_path else STATE_PATH
    candidates_path = Path(candidates_path) if candidates_path else CANDIDATES_PATH
    session = session or requests
    state = load_json(state_path, {"seen_urls": []})
    if not isinstance(state, dict):
        state = {"seen_urls": []}
    seen = set(state.get("seen_urls") or [])
    all_seen = set(seen)
    pending = load_json(candidates_path, [])
    if not isinstance(pending, list):
        pending = []
    known_candidates = {item.get("source_url") for item in pending if item.get("source_url")}
    new_candidates = []
    source_errors = []
    successful_sources = 0
    now = datetime.now(timezone.utc).isoformat()
    for source in sources:
        try:
            response = session.get(
                source["listing_url"],
                timeout=20,
                headers={"User-Agent": "PharmaRadarClinicalCatalystMonitor/1.0"},
            )
            response.raise_for_status()
            successful_sources += 1
            found = parse_listing_page(response.text, source, discovered_at=now)
            for candidate in found:
                url = candidate["source_url"]
                all_seen.add(url)
                if url in seen or url in known_candidates:
                    continue
                new_candidates.append(candidate)
                known_candidates.add(url)
        except Exception as exc:
            source_errors.append(f"{source.get('ticker', 'UNKNOWN')}: {type(exc).__name__}: {exc}")
    if sources and successful_sources == 0:
        raise RuntimeError("All official press-release pages failed: " + "; ".join(source_errors))
    pending.extend(new_candidates)
    save_json(candidates_path, pending)
    save_json(state_path, {"seen_urls": sorted(all_seen), "last_checked_at": now,
                           "successful_sources": successful_sources,
                           "source_errors": source_errors})
    print(
        f"Primary-source discovery: sources_ok={successful_sources}/{len(sources)} "
        f"new_candidates={len(new_candidates)} pending_total={len(pending)}"
    )
    for error in source_errors:
        print(f"WARNING source fetch failed: {error}")
    return {"sources_ok": successful_sources, "new_candidates": new_candidates,
            "pending_total": len(pending), "source_errors": source_errors}


if __name__ == "__main__":
    collect_candidates()
