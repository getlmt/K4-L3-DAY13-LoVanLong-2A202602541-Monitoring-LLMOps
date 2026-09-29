from __future__ import annotations

import pandas as pd

from dashboard import panels as P


def _logs() -> pd.DataFrame:
    rows = [
        {"ts": "2026-01-01T00:00:01Z", "event": "request_received"},
        {"ts": "2026-01-01T00:00:02Z", "event": "response_sent", "latency_ms": 100, "ttft_ms": 50,
         "cost_usd": 0.001, "tokens_in": 10, "tokens_out": 20, "quality_score": 0.8, "tool_success": True},
        {"ts": "2026-01-01T00:00:03Z", "event": "request_received"},
        {"ts": "2026-01-01T00:00:04Z", "event": "request_failed", "error_type": "RuntimeError", "tool_success": False},
    ]
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def test_panel_values() -> None:
    df = _logs()
    assert P.latency(df)["p95"] == 100
    assert P.traffic(df)["count"] == 2
    err = P.errors(df)
    assert err["error_rate_pct"] == 50
    assert err["tool_success_rate_pct"] == 50
    assert err["breakdown"].iloc[0]["error_type"] == "RuntimeError"
    assert P.cost(df)["total"] == 0.001
    assert (P.tokens(df)["tokens_in"], P.tokens(df)["tokens_out"]) == (10, 20)
    assert P.quality(df)["mean"] == 0.8


def test_empty_logs_do_not_crash() -> None:
    empty = pd.DataFrame()
    assert P.latency(empty)["p95"] is None
    assert P.errors(empty)["error_rate_pct"] is None
    assert P.check_threshold(None, {"operator": "lte", "value": 1}) is None


def test_thresholds_follow_contract() -> None:
    cfg = P.load_config()
    thresholds = {p["id"]: p["threshold"] for p in cfg["panels"]}
    assert P.check_threshold(2900, thresholds["latency"]) is True
    assert P.check_threshold(3100, thresholds["latency"]) is False
    assert P.check_threshold(0.5, thresholds["quality"]) is False
