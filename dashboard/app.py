"""Dashboard 6 panel cho Day 13. Chạy: streamlit run dashboard/app.py"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import panels as P  # noqa: E402

cfg = P.load_config()
spec = {p["id"]: p for p in cfg["panels"]}
TIME_RANGE = cfg["time_range_minutes"]
REFRESH = cfg["refresh_seconds"]

st.set_page_config(page_title=cfg["title"], layout="wide")


@st.fragment(run_every=REFRESH)
def render() -> None:
    logs = P.load_logs()
    end = datetime.now(timezone.utc)
    data = P.window(logs, TIME_RANGE, end)
    st.title(cfg["title"])
    st.caption(
        f"Time range: last {TIME_RANGE} minutes (now {end:%H:%M:%S} UTC) · auto refresh {REFRESH}s · "
        f"source: data/logs.jsonl · {len(data)} log records"
    )

    def status(ok: bool | None) -> str:
        return {True: "✅ trong ngưỡng", False: "🔴 vi phạm ngưỡng", None: "⚪ chưa có dữ liệu"}[ok]

    def th(pid: str) -> dict:
        return spec[pid]["threshold"]

    def th_text(pid: str) -> str:
        t = th(pid)
        return f"threshold: {t['aggregation']} {'≤' if t['operator'] == 'lte' else '≥'} {t['value']} {spec[pid]['unit']}"

    def line_chart(df: pd.DataFrame, unit: str, threshold: float | None = None, label: str = "threshold") -> None:
        if df.empty:
            st.info("Chưa có dữ liệu trong 60 phút gần nhất.")
            return
        long = df.reset_index().melt("ts", var_name="series", value_name="value").dropna()
        long["ts"] = long["ts"].dt.tz_convert("UTC").dt.tz_localize(None)  # hiển thị đúng giờ UTC, không đổi theo múi giờ trình duyệt
        base = alt.Chart(long).mark_line(point=True).encode(
            x=alt.X("ts:T", title="time (UTC)"),
            y=alt.Y("value:Q", title=unit),
            color=alt.Color("series:N", title=None),
            tooltip=["ts:T", "series:N", "value:Q"],
        )
        layers = [base]
        if threshold is not None:
            rule = alt.Chart(pd.DataFrame({"y": [threshold], "label": [f"{label} = {threshold}"]}))
            layers.append(rule.mark_rule(color="red", strokeDash=[6, 4]).encode(y="y:Q"))
            layers.append(rule.mark_text(color="red", align="left", dx=4, dy=-6).encode(y="y:Q", text="label:N"))
        st.altair_chart(alt.layer(*layers).properties(height=240), use_container_width=True)

    left, right = st.columns(2)

    with left.container(border=True):  # 1. latency
        m = P.latency(data)
        st.subheader(f"1. {spec['latency']['title']} (ms)")
        cols = st.columns(4)
        for col, key, label in zip(cols, ["p50", "p95", "p99", "ttft_p95"], ["P50", "P95", "P99", "TTFT P95"]):
            col.metric(label, "—" if m[key] is None else f"{m[key]:.0f} ms")
        st.write(f"{status(P.check_threshold(m['p95'], th('latency')))} · {th_text('latency')}")
        line_chart(m["series"], "ms", th("latency")["value"], "P95 threshold")

    with right.container(border=True):  # 2. traffic
        m = P.traffic(data)
        st.subheader(f"2. {spec['traffic']['title']} (requests/min)")
        cols = st.columns(2)
        cols[0].metric("Requests (60 phút)", m["count"])
        cols[1].metric("Rate", "—" if m["rate_per_minute"] is None else f"{m['rate_per_minute']:.2f} req/min")
        st.write(f"{status(P.check_threshold(m['rate_per_minute'], th('traffic')))} · {th_text('traffic')}")
        line_chart(m["series"], "requests/min", th("traffic")["value"], "min rate")

    with left.container(border=True):  # 3. errors
        m = P.errors(data)
        st.subheader(f"3. {spec['errors']['title']} (%)")
        cols = st.columns(2)
        cols[0].metric("Error rate", "—" if m["error_rate_pct"] is None else f"{m['error_rate_pct']:.2f} %")
        cols[1].metric(
            "Retrieval success",
            "—" if m["tool_success_rate_pct"] is None else f"{m['tool_success_rate_pct']:.1f} %",
        )
        st.write(f"{status(P.check_threshold(m['error_rate_pct'], th('errors')))} · {th_text('errors')}")
        line_chart(m["series"], "% error rate", th("errors")["value"], "error threshold")
        st.caption("Breakdown theo error_type")
        if m["breakdown"].empty:
            st.write("Không có lỗi trong khoảng thời gian này.")
        else:
            st.dataframe(m["breakdown"], hide_index=True)

    with right.container(border=True):  # 4. cost
        m = P.cost(data)
        st.subheader(f"4. {spec['cost']['title']} (USD)")
        st.metric("Total cost (60 phút)", "—" if m["total"] is None else f"${m['total']:.4f}")
        st.write(f"{status(P.check_threshold(m['total'], th('cost')))} · {th_text('cost')}")
        line_chart(m["series"], "USD/min")

    with left.container(border=True):  # 5. tokens
        m = P.tokens(data)
        st.subheader(f"5. {spec['tokens']['title']} (tokens)")
        cols = st.columns(2)
        cols[0].metric("Input tokens", "—" if m["tokens_in"] is None else f"{m['tokens_in']:,}")
        cols[1].metric("Output tokens", "—" if m["tokens_out"] is None else f"{m['tokens_out']:,}")
        ok = None if m["tokens_in"] is None else all(
            P.check_threshold(m[k], th("tokens")) for k in ("tokens_in", "tokens_out")
        )
        st.write(f"{status(ok)} · {th_text('tokens')} (áp dụng cho từng field)")
        line_chart(m["series"], "tokens/min")

    with right.container(border=True):  # 6. quality
        m = P.quality(data)
        st.subheader(f"6. {spec['quality']['title']} (score 0–1)")
        st.metric("Mean quality score", "—" if m["mean"] is None else f"{m['mean']:.2f}")
        st.write(f"{status(P.check_threshold(m['mean'], th('quality')))} · {th_text('quality')}")
        line_chart(m["series"], "score 0–1", th("quality")["value"], "min quality")


render()
