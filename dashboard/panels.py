"""Tính giá trị 6 panel từ data/logs.jsonl theo config/dashboard.yaml."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path = REPO_ROOT / "config" / "dashboard.yaml") -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["dashboard"]


def load_logs(path: Path = REPO_ROOT / "data" / "logs.jsonl") -> pd.DataFrame:
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    return df


def window(df: pd.DataFrame, minutes: int, end: datetime | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    end = end or datetime.now(timezone.utc)
    return df[(df["ts"] >= end - timedelta(minutes=minutes)) & (df["ts"] <= end)]


def _events(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if df.empty or "event" not in df:
        return pd.DataFrame()
    return df[df["event"] == name]


def _per_minute(df: pd.DataFrame, column: str | None = None, how: str = "sum") -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    resampled = df.set_index("ts").resample("1min")
    return resampled.size() if column is None else getattr(resampled[column], how)()


def latency(df: pd.DataFrame) -> dict[str, Any]:
    sent = _events(df, "response_sent")
    if sent.empty:
        return {"p50": None, "p95": None, "p99": None, "ttft_p95": None, "series": pd.DataFrame()}
    ts = sent.set_index("ts")
    lat = ts["latency_ms"].resample("1min")
    return {
        "p50": float(sent["latency_ms"].quantile(0.50)),
        "p95": float(sent["latency_ms"].quantile(0.95)),
        "p99": float(sent["latency_ms"].quantile(0.99)),
        "ttft_p95": float(sent["ttft_ms"].quantile(0.95)),
        "series": pd.DataFrame(
            {
                "P50": lat.quantile(0.50),
                "P95": lat.quantile(0.95),
                "P99": lat.quantile(0.99),
                "TTFT P95": ts["ttft_ms"].resample("1min").quantile(0.95),
            }
        ).dropna(how="all"),
    }


def traffic(df: pd.DataFrame) -> dict[str, Any]:
    req = _events(df, "request_received")
    per_min = _per_minute(req)
    # rate_per_minute: trung bình theo mọi phút nằm giữa request đầu và cuối (phút trống tính 0).
    return {
        "count": int(len(req)),
        "rate_per_minute": float(per_min.mean()) if len(per_min) else None,
        "series": per_min.rename("requests/min").to_frame(),
    }


def errors(df: pd.DataFrame) -> dict[str, Any]:
    received, failed, sent = (_events(df, n) for n in ("request_received", "request_failed", "response_sent"))
    error_rate = len(failed) / len(received) * 100 if len(received) else None
    if not failed.empty and "error_type" in failed:
        breakdown = failed["error_type"].value_counts().rename_axis("error_type").reset_index(name="count")
    else:
        breakdown = pd.DataFrame(columns=["error_type", "count"])
    tool_rows = pd.concat([sent, failed]) if not (sent.empty and failed.empty) else pd.DataFrame()
    success = None
    if not tool_rows.empty and "tool_success" in tool_rows:
        known = tool_rows["tool_success"].dropna()
        if len(known):
            success = float((known == True).sum() / len(known) * 100)  # noqa: E712
    series = pd.DataFrame({"error_rate_pct": _per_minute(failed) / _per_minute(received) * 100}).fillna(0)
    return {"error_rate_pct": error_rate, "breakdown": breakdown, "tool_success_rate_pct": success, "series": series}


def cost(df: pd.DataFrame) -> dict[str, Any]:
    sent = _events(df, "response_sent")
    return {
        "total": float(sent["cost_usd"].sum()) if not sent.empty else None,
        "series": _per_minute(sent, "cost_usd", "sum").rename("cost_usd/min").to_frame(),
    }


def tokens(df: pd.DataFrame) -> dict[str, Any]:
    sent = _events(df, "response_sent")
    if sent.empty:
        return {"tokens_in": None, "tokens_out": None, "series": pd.DataFrame()}
    ts = sent.set_index("ts")
    return {
        "tokens_in": int(sent["tokens_in"].sum()),
        "tokens_out": int(sent["tokens_out"].sum()),
        "series": pd.DataFrame(
            {
                "tokens_in": ts["tokens_in"].resample("1min").sum(),
                "tokens_out": ts["tokens_out"].resample("1min").sum(),
            }
        ),
    }


def quality(df: pd.DataFrame) -> dict[str, Any]:
    sent = _events(df, "response_sent")
    if sent.empty:
        return {"mean": None, "series": pd.DataFrame()}
    series = sent.set_index("ts")["quality_score"].resample("1min").mean().rename("quality_score").to_frame()
    return {"mean": float(sent["quality_score"].mean()), "series": series}


def check_threshold(value: float | None, threshold: dict[str, Any]) -> bool | None:
    """True nếu đạt threshold, False nếu vi phạm, None nếu chưa có dữ liệu."""
    if value is None:
        return None
    return value <= threshold["value"] if threshold["operator"] == "lte" else value >= threshold["value"]
