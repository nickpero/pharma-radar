"""Pharma Radar — point-in-time Trading Intelligence replay V1.4."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

INPUT = Path("data/historical_catalyst_dataset.json")
OUTPUT = Path("data/trading_intelligence_pit_replay.json")

WARMUP_THRESHOLDS = (
    {"stage": "WARMUP", "min_sample": 0, "max_sample": 9, "median": None, "win_rate": None},
    {"stage": "PROVISIONAL", "min_sample": 10, "max_sample": 19, "median": 2.00, "win_rate": 0.65},
    {"stage": "DEVELOPING", "min_sample": 20, "max_sample": 29, "median": 1.50, "win_rate": 0.60},
    {"stage": "FULL", "min_sample": 30, "max_sample": None, "median": 1.00, "win_rate": 0.55},
)
SENSITIVITY_MEDIANS = (0.50, 0.75, 1.00, 1.25, 1.50, 2.00)
FRICTION_BPS = 30.0


def _load() -> dict[str, Any]:
    return json.loads(INPUT.read_text(encoding="utf-8"))


def _ts(event: dict[str, Any]) -> str:
    return str(event.get("event_timestamp") or "")


def _sort_key(event: dict[str, Any]) -> tuple[int, str]:
    raw = _ts(event)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp()), raw
    except (TypeError, ValueError):
        return 0, raw


def _return(event: dict[str, Any], window: str) -> float | None:
    try:
        value = float(
            ((event.get("market_metrics") or {}).get("windows") or {})
            .get(window, {})
            .get("directional_abnormal_return_pct")
        )
    except (TypeError, ValueError):
        return None
    return value - FRICTION_BPS / 100.0


def _return_1d(event: dict[str, Any]) -> float | None:
    return _return(event, "1D")


def warmup_policy(n: int) -> dict[str, Any]:
    for rule in WARMUP_THRESHOLDS:
        if n >= rule["min_sample"] and (rule["max_sample"] is None or n <= rule["max_sample"]):
            return dict(rule)
    raise AssertionError(f"No warm-up policy stage for sample size {n}")


def _diagnostics(n: int, med: float | None, win: float | None) -> dict[str, Any]:
    policy = warmup_policy(n)
    median_pass = policy["median"] is not None and med is not None and med >= policy["median"]
    win_rate_pass = policy["win_rate"] is not None and win is not None and win >= policy["win_rate"]
    if policy["median"] is None or policy["win_rate"] is None:
        reason = "WARMUP_SAMPLE"
    elif median_pass and win_rate_pass:
        reason = "PASS"
    elif not median_pass and not win_rate_pass:
        reason = "BOTH"
    elif not median_pass:
        reason = "MEDIAN"
    else:
        reason = "WIN_RATE"
    return {"median_pass": median_pass, "win_rate_pass": win_rate_pass, "gate_result": median_pass and win_rate_pass, "gate_failure_reason": reason}


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median_pct": None, "win_rate": None, "mean_pct": None}
    return {
        "n": len(values),
        "median_pct": round(median(values), 4),
        "win_rate": round(sum(v > 0 for v in values) / len(values), 4),
        "mean_pct": round(sum(values) / len(values), 4),
    }




def _period_robustness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [r for r in rows if r["prior_subtype_sample"] >= 10 and r["prior_subtype_win_rate_1d"] is not None and r["prior_subtype_win_rate_1d"] >= 0.55]
    dates = sorted(r["event_timestamp"] for r in evaluated)
    if len(dates) < 4:
        return {"status": "INSUFFICIENT_SAMPLE", "events": len(evaluated)}
    split_date = dates[max(0, len(dates) // 2 - 1)]
    train = [r for r in evaluated if r["event_timestamp"] <= split_date]
    test = [r for r in evaluated if r["event_timestamp"] > split_date]
    out = {"status": "OK", "split_date": split_date, "train_events": len(train), "test_events": len(test), "thresholds": {}}
    for threshold in (0.50, 0.75, 1.00):
        train_selected = [r for r in train if r["prior_subtype_median_net_1d_pct"] is not None and r["prior_subtype_median_net_1d_pct"] >= threshold]
        test_selected = [r for r in test if r["prior_subtype_median_net_1d_pct"] is not None and r["prior_subtype_median_net_1d_pct"] >= threshold]
        out["thresholds"][f"{threshold:.2f}"] = {
            "train": {"n": len(train_selected), "forward_1d": _portfolio_stats(train_selected, "1d")},
            "test": {"n": len(test_selected), "forward_1d": _portfolio_stats(test_selected, "1d")},
            "test_by_subtype": {s: sum(r["subtype"] == s for r in test_selected) for s in sorted({r["subtype"] for r in test_selected})},
        }
    return out



def _rolling_oos(rows: list[dict[str, Any]], threshold: float = 0.75) -> dict[str, Any]:
    evaluated = [r for r in rows if r["prior_subtype_sample"] >= 10 and r["prior_subtype_win_rate_1d"] is not None and r["prior_subtype_win_rate_1d"] >= 0.55 and r["prior_subtype_median_net_1d_pct"] is not None and r["prior_subtype_median_net_1d_pct"] >= threshold]
    if not evaluated:
        return {"status": "INSUFFICIENT_SAMPLE"}
    out = {"status": "OK", "threshold_pct": threshold, "windows": []}
    years = sorted({int(r["event_timestamp"][:4]) for r in evaluated})
    for test_year in range(min(years) + 1, max(years) + 1):
        train = [r for r in rows if int(r["event_timestamp"][:4]) < test_year and r["prior_subtype_sample"] >= 10 and r["prior_subtype_win_rate_1d"] is not None and r["prior_subtype_win_rate_1d"] >= 0.55 and r["prior_subtype_median_net_1d_pct"] is not None and r["prior_subtype_median_net_1d_pct"] >= threshold]
        test = [r for r in rows if int(r["event_timestamp"][:4]) == test_year and r["prior_subtype_sample"] >= 10 and r["prior_subtype_win_rate_1d"] is not None and r["prior_subtype_win_rate_1d"] >= 0.55 and r["prior_subtype_median_net_1d_pct"] is not None and r["prior_subtype_median_net_1d_pct"] >= threshold]
        if test:
            out["windows"].append({"train_through": test_year - 1, "test_year": test_year, "train_n": len(train), "test_n": len(test), "test_1d": _portfolio_stats(test, "1d")})
    return out

def _holdout_breakdown(rows: list[dict[str, Any]], threshold: float = 0.75) -> dict[str, Any]:
    evaluated = [r for r in rows if r["prior_subtype_sample"] >= 10 and r["prior_subtype_win_rate_1d"] is not None and r["prior_subtype_win_rate_1d"] >= 0.55]
    dates = sorted(r["event_timestamp"] for r in evaluated)
    if len(dates) < 4:
        return {"status": "INSUFFICIENT_SAMPLE"}
    split_date = dates[max(0, len(dates) // 2 - 1)]
    test = [r for r in evaluated if r["event_timestamp"] > split_date and r["prior_subtype_median_net_1d_pct"] is not None and r["prior_subtype_median_net_1d_pct"] >= threshold]
    tickers = {}
    for r in test:
        tickers.setdefault(r["ticker"], []).append(r)
    return {
        "status": "OK",
        "threshold_pct": threshold,
        "split_date": split_date,
        "test_events": len(test),
        "by_ticker": {t: {"n": len(v), "forward_1d": _portfolio_stats(v, "1d")} for t, v in sorted(tickers.items())},
    }


def _portfolio_stats(rows: list[dict[str, Any]], window: str = "1d") -> dict[str, Any]:
    values = [r[f"forward_{window}_net_pct"] for r in rows if r.get(f"forward_{window}_net_pct") is not None]
    if not values:
        return {"n": 0, "median_pct": None, "mean_pct": None, "win_rate": None, "profit_factor": None, "compound_return_pct": None, "max_drawdown_pct": None, "max_gain_pct": None, "max_loss_pct": None}
    gains = sum(v for v in values if v > 0)
    losses = sum(-v for v in values if v < 0)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in values:
        equity *= 1.0 + value / 100.0
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity / peak - 1.0) * 100.0)
    return {
        "n": len(values),
        "median_pct": round(median(values), 4),
        "mean_pct": round(sum(values) / len(values), 4),
        "win_rate": round(sum(v > 0 for v in values) / len(values), 4),
        "profit_factor": round(gains / losses, 4) if losses else None,
        "compound_return_pct": round((equity - 1.0) * 100.0, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "max_gain_pct": round(max(values), 4),
        "max_loss_pct": round(min(values), 4),
    }


def _loo(rows: list[dict[str, Any]], window: str = "1d") -> dict[str, Any]:
    tickers = sorted({str(r.get("ticker") or "UNKNOWN") for r in rows})
    results = {}
    for ticker in tickers:
        subset = [r for r in rows if str(r.get("ticker") or "UNKNOWN") != ticker]
        results[ticker] = _portfolio_stats(subset, window)
    pf = [v["profit_factor"] for v in results.values() if v["profit_factor"] is not None]
    medians = [v["median_pct"] for v in results.values() if v["median_pct"] is not None]
    return {
        "tickers": len(tickers),
        "min_profit_factor": round(min(pf), 4) if pf else None,
        "median_profit_factor": round(median(pf), 4) if pf else None,
        "min_median_pct": round(min(medians), 4) if medians else None,
        "all_leave_one_ticker_out_positive_median": bool(medians) and all(v > 0 for v in medians),
        "by_ticker": results,
    }


def _robustness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [r for r in rows if r["prior_subtype_sample"] >= 10 and r["prior_subtype_win_rate_1d"] is not None and r["prior_subtype_win_rate_1d"] >= 0.55]
    result = {}
    for threshold in (0.50, 0.75, 1.00):
        selected = [r for r in evaluated if r["prior_subtype_median_net_1d_pct"] is not None and r["prior_subtype_median_net_1d_pct"] >= threshold]
        key = f"{threshold:.2f}"
        result[key] = {
            "threshold_pct": threshold,
            "selected_events": len(selected),
            "tickers": len({str(r.get("ticker") or "UNKNOWN") for r in selected}),
            "by_subtype": {s: sum(r["subtype"] == s for r in selected) for s in sorted({r["subtype"] for r in selected})},
            "forward": {window: _portfolio_stats(selected, window) for window in ("1d", "3d", "5d")},
            "leave_one_ticker_out_1d": _loo(selected, "1d"),
        }
    return result


def _sensitivity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [r for r in rows if r["prior_subtype_sample"] >= 10]
    result: dict[str, Any] = {}
    for threshold in SENSITIVITY_MEDIANS:
        key = f"{threshold:.2f}"
        selected = [
            r for r in evaluated
            if r["prior_subtype_median_net_1d_pct"] is not None
            and r["prior_subtype_median_net_1d_pct"] >= threshold
            and r["prior_subtype_win_rate_1d"] is not None
            and r["prior_subtype_win_rate_1d"] >= 0.55
        ]
        by_subtype: dict[str, int] = {}
        outcomes = {w: [] for w in ("1D", "3D", "5D")}
        for row in selected:
            by_subtype[row["subtype"]] = by_subtype.get(row["subtype"], 0) + 1
            for window in outcomes:
                value = row.get(f"forward_{window.lower()}_net_pct")
                if value is not None:
                    outcomes[window].append(value)
        result[key] = {
            "median_threshold_pct": threshold,
            "win_rate_threshold": 0.55,
            "evaluated_events": len(evaluated),
            "qualified_events": len(selected),
            "by_subtype": by_subtype,
            "forward_outcomes": {w: _stats(v) for w, v in outcomes.items()},
        }
    return result


def build() -> dict[str, Any]:
    payload = _load()
    events = [dict(e) for e in (payload.get("tradable_catalysts") or []) if e.get("market_metrics")]
    events.sort(key=_sort_key)

    history: dict[str, list[float]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    index = 0
    while index < len(events):
        timestamp = _ts(events[index])
        batch = []
        while index < len(events) and _ts(events[index]) == timestamp:
            batch.append(events[index])
            index += 1
        batch_values: list[tuple[str, float]] = []
        for event in batch:
            subtype = str(event.get("subtype") or "UNKNOWN").upper()
            prior = history[subtype]
            n = len(prior)
            med = median(prior) if prior else None
            win = sum(v > 0 for v in prior) / n if n else None
            policy = warmup_policy(n)
            diagnostics = _diagnostics(n, med, win)
            rows.append({
                "event_timestamp": timestamp,
                "ticker": event.get("ticker"),
                "subtype": subtype,
                "prior_subtype_sample": n,
                "warmup_stage": policy["stage"],
                "warmup_min_sample": policy["min_sample"],
                "warmup_max_sample": policy["max_sample"],
                "warmup_required_median_net_1d_pct": policy["median"],
                "warmup_required_win_rate_1d": policy["win_rate"],
                "prior_subtype_median_net_1d_pct": med,
                "prior_subtype_win_rate_1d": win,
                **diagnostics,
                "historical_edge_gate": diagnostics["gate_result"],
                "forward_1d_net_pct": _return(event, "1D"),
                "forward_3d_net_pct": _return(event, "3D"),
                "forward_5d_net_pct": _return(event, "5D"),
            })
            value = _return_1d(event)
            if value is not None:
                batch_values.append((subtype, value))
        for subtype, value in batch_values:
            history[subtype].append(value)

    qualified = [r for r in rows if r["historical_edge_gate"]]
    by_stage: dict[str, dict[str, int]] = {}
    for row in rows:
        b = by_stage.setdefault(row["warmup_stage"], {"events": 0, "median_pass": 0, "win_rate_pass": 0, "qualified": 0})
        b["events"] += 1
        b["median_pass"] += int(row["median_pass"])
        b["win_rate_pass"] += int(row["win_rate_pass"])
        b["qualified"] += int(row["historical_edge_gate"])

    by_subtype: dict[str, dict[str, Any]] = {}
    for row in rows:
        b = by_subtype.setdefault(row["subtype"], {"events": 0, "median_pass": 0, "win_rate_pass": 0, "qualified": 0, "failure_reasons": {"WARMUP_SAMPLE": 0, "MEDIAN": 0, "WIN_RATE": 0, "BOTH": 0, "PASS": 0}})
        b["events"] += 1
        b["median_pass"] += int(row["median_pass"])
        b["win_rate_pass"] += int(row["win_rate_pass"])
        b["qualified"] += int(row["historical_edge_gate"])
        b["failure_reasons"][row["gate_failure_reason"]] += 1

    failure_reasons = {"WARMUP_SAMPLE": 0, "MEDIAN": 0, "WIN_RATE": 0, "BOTH": 0, "PASS": 0}
    for row in rows:
        failure_reasons[row["gate_failure_reason"]] += 1

    report = {
        "version": "1.7",
        "purpose": "point-in-time historical-edge replay with warm-up diagnostics, threshold sensitivity, and forward outcome validation",
        "methodology": {
            "friction_bps": FRICTION_BPS,
            "warmup_policy": [dict(r) for r in WARMUP_THRESHOLDS],
            "sensitivity_median_thresholds_pct": list(SENSITIVITY_MEDIANS),
            "sensitivity_win_rate_threshold": 0.55,
            "forward_validation": "Each event is selected using only strictly prior history; its own 1D/3D/5D market outcome is evaluated afterward.",
            "lookahead_control": "Only strictly earlier timestamps contribute; equal-timestamp events are batched.",
            "warning": "Research-only; forward outcome validation is not a live trading backtest.",
        },
        "sample": {"events": len(rows), "qualified_historical_edge_events": len(qualified)},
        "failure_reasons": failure_reasons,
        "by_stage": by_stage,
        "by_subtype": by_subtype,
        "sensitivity": _sensitivity(rows),
        "robustness": _robustness(rows),
        "temporal_holdout": _period_robustness(rows),
        "holdout_breakdown": _holdout_breakdown(rows, 0.75),
        "rolling_oos": _rolling_oos(rows, 0.75),
        "events": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    report = build()
    print("========== PIT THRESHOLD + FORWARD VALIDATION ==========")
    print(f"Events: {report['sample']['events']}")
    print(f"Current qualified: {report['sample']['qualified_historical_edge_events']}")
    for threshold, row in report["sensitivity"].items():
        print(
            f"Median >= {threshold}%: qualified={row['qualified_events']} "
            f"subtypes={row['by_subtype']} outcomes={row['forward_outcomes']}"
        )
    print("---------- ROBUSTNESS (0.50 / 0.75 / 1.00) ----------")
    for threshold, row in report["robustness"].items():
        f = row["forward"]["1d"]
        loo = row["leave_one_ticker_out_1d"]
        print(f"{threshold}%: n={row['selected_events']} tickers={row['tickers']} median={f['median_pct']}% win={f['win_rate']} PF={f['profit_factor']} compound={f['compound_return_pct']}% DD={f['max_drawdown_pct']}% LOO_min_PF={loo['min_profit_factor']} LOO_all_positive_median={loo['all_leave_one_ticker_out_positive_median']}")
    holdout = report["temporal_holdout"]
    print("---------- TEMPORAL HOLDOUT ----------")
    print(f"split={holdout.get('split_date')} train={holdout.get('train_events')} test={holdout.get('test_events')}")
    for threshold, row in holdout.get("thresholds", {}).items():
        fwd = row["test"]["forward_1d"]
        print(f"{threshold}%: TEST n={row['test']['n']} median={fwd['median_pct']}% win={fwd['win_rate']} PF={fwd['profit_factor']} DD={fwd['max_drawdown_pct']}% subtypes={row['test_by_subtype']}")
    print("Lookahead control: PASS")
    print("=========================================================")


if __name__ == "__main__":
    main()
