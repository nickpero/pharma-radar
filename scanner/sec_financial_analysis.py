"""Deterministic risk-signal extraction from primary SEC periodic filings.

This is a screening layer, not an accounting opinion or a trading recommendation.
It only emits signals when explicit language appears in the filing text.
"""
from __future__ import annotations

import re


_RULES = (
    ("GOING_CONCERN", "CRITICAL", (
        r"substantial doubt about (?:the )?(?:company|issuer|registrant|our)\s*'?s?\s+ability to continue as a going concern",
        r"ability to continue as a going concern.{0,100}substantial doubt",
        r"going concern.{0,100}substantial doubt",
    )),
    ("DEFAULT_OR_COVENANT", "CRITICAL", (
        r"(?:event of default|default under).{0,100}(?:credit agreement|loan agreement|indenture|debt)",
        r"(?:accelerated|acceleration of) (?:the )?(?:repayment|maturity) of.{0,80}(?:debt|loan|borrowings)",
        r"failed to (?:comply with|meet).{0,80}(?:financial )?covenant",
    )),
    ("LIQUIDITY_STRESS", "HIGH", (
        r"(?:insufficient|inadequate) liquidity to (?:fund|meet|support)",
        r"not sufficient to fund (?:our )?(?:operations|operating expenses).{0,80}(?:12|twelve) months",
        r"unable to meet (?:our )?(?:obligations|obligations as they become due)",
        r"substantial liquidity (?:shortfall|constraints|concerns)",
    )),
    ("RUNWAY_UNDER_12_MONTHS", "HIGH", (
        r"(?:cash|cash and cash equivalents|available funds).{0,100}(?:runway|fund operations).{0,50}(?:less than|under|approximately)\s*(?:6|9|10|11|twelve|12)\s*months",
        r"(?:fund|finance) (?:our )?operations for (?:less than|under)\s*12\s*months",
    )),
    ("GUIDANCE_WITHDRAWN", "HIGH", (
        r"(?:withdraw|withdrew|withdrawn|suspend|suspended) (?:its |our )?(?:full[- ]year )?guidance",
        r"no longer (?:provides|providing) (?:financial )?guidance",
    )),
    ("GUIDANCE_REDUCED", "MEDIUM", (
        r"(?:lowered|reduced|cut) (?:its |our )?(?:full[- ]year )?(?:revenue|sales|earnings|ebitda) guidance",
        r"(?:lower|revised downward) (?:its |our )?(?:full[- ]year )?guidance",
    )),
)

_PRIORITY = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}


def analyze_sec_financial_filing(text: str) -> dict:
    """Return explicit financial-risk flags, short evidence and severity."""
    source = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(source) < 300:
        return {"status": "INSUFFICIENT_CONTENT", "alert_level": "NONE", "signals": [], "evidence": []}

    signals = []
    evidence = []
    lowered = source.lower()
    for code, level, patterns in _RULES:
        for pattern in patterns:
            match = re.search(pattern, lowered, flags=re.I)
            if match:
                signals.append({"code": code, "level": level})
                start, end = max(0, match.start() - 90), min(len(source), match.end() + 110)
                snippet = re.sub(r"\s+", " ", source[start:end]).strip()
                evidence.append(snippet[:240])
                break

    level = max((item["level"] for item in signals), key=lambda x: _PRIORITY[x], default="NONE")
    return {
        "status": "ANALYZED",
        "alert_level": level,
        "signals": signals,
        "evidence": evidence[:3],
        "signal_count": len(signals),
    }
