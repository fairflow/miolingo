"""
Statistics tab UI: current session and all-time practice stats, plus
compact charts for accuracy trend, practice volume, score distribution,
and weakest phrases.

Extracted from app.py (Phase 4.2 of refactor); charts added in v7.5.0.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import altair as alt

import app_mysql


CHART_HEIGHT = 220  # compact — deliberately small so the tab stays scrollable
WINDOW_DAYS = 90


def render_statistics_tab():
    """Render the Statistics tab with current session, all-time metrics, and charts."""
    st.header("📊 Practice Statistics")

    # ── Current session ────────────────────────────────────────────────
    current_session = st.session_state.current_sessions[st.session_state.language]
    if current_session["practices"]:
        st.subheader("🔵 Current Session")
        practices = current_session["practices"]
        perfect = sum(1 for p in practices if p.get("exact_match", False))
        avg_sim = sum(p["similarity"] for p in practices) / len(practices)

        col1, col2, col3 = st.columns(3)
        col1.metric("Practices", len(practices))
        col2.metric("Perfect", f"{perfect} ({perfect/len(practices):.1%})")
        col3.metric("Avg Similarity", f"{avg_sim:.1%}")

    # ── All-time (auth required) ───────────────────────────────────────
    if not st.session_state.get("authenticated", False):
        st.info("Log in to see all-time statistics and charts.")
        return

    user_id = st.session_state["user"]["user_id"]
    lang = st.session_state.language

    st.subheader("📈 All Time")
    try:
        stats = app_mysql.get_user_stats(user_id, lang)
    except Exception as e:
        st.error(f"Could not load stats: {e}")
        return

    if not stats or stats["total"] == 0:
        st.info("No practice history yet. Start practicing!")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Practices", stats["total"])
    col2.metric("Total Perfect", f"{stats['perfect_count']} ({stats['perfect_count']/stats['total']:.1%})")
    col3.metric("Overall Avg", f"{stats['avg_score']:.1%}")
    col4.metric("Recent Avg (last 10)", f"{stats['recent_avg']:.1%}")

    # ── Charts ─────────────────────────────────────────────────────────
    rows = app_mysql.get_user_progress_timeseries(user_id, lang, days=WINDOW_DAYS)
    if not rows:
        st.caption(f"No practice data in the last {WINDOW_DAYS} days.")
        return

    df = pd.DataFrame(rows)
    df["practice_date"] = pd.to_datetime(df["practice_date"])
    df["similarity_score"] = pd.to_numeric(df["similarity_score"], errors="coerce")

    st.markdown(f"_Charts below cover the last {WINDOW_DAYS} days ({len(df)} practices)._")

    _render_accuracy_trend(df)
    col_a, col_b = st.columns(2)
    with col_a:
        _render_volume_chart(df)
    with col_b:
        _render_score_distribution(df)
    _render_weakest_phrases(user_id, lang)


def _render_accuracy_trend(df: pd.DataFrame) -> None:
    """Per-practice score + rolling-10 average overlay."""
    st.markdown("**Accuracy trend**")
    plot_df = df[["practice_date", "similarity_score"]].copy()
    plot_df["rolling10"] = plot_df["similarity_score"].rolling(window=10, min_periods=1).mean()

    base = alt.Chart(plot_df).encode(x=alt.X("practice_date:T", title=None))
    points = base.mark_circle(size=20, opacity=0.4).encode(
        y=alt.Y("similarity_score:Q", title="score", scale=alt.Scale(domain=[0, 1])),
        tooltip=[
            alt.Tooltip("practice_date:T", title="when"),
            alt.Tooltip("similarity_score:Q", title="score", format=".1%"),
        ],
    )
    line = base.mark_line(color="#ff6b35", strokeWidth=2).encode(
        y=alt.Y("rolling10:Q", scale=alt.Scale(domain=[0, 1])),
    )
    chart = (points + line).properties(height=CHART_HEIGHT)
    st.altair_chart(chart, use_container_width=True)


def _render_volume_chart(df: pd.DataFrame) -> None:
    """Bar chart of practices per day."""
    st.markdown("**Practices per day**")
    by_day = (
        df.assign(day=df["practice_date"].dt.date)
        .groupby("day")
        .size()
        .reset_index(name="count")
    )
    chart = (
        alt.Chart(by_day)
        .mark_bar()
        .encode(
            x=alt.X("day:T", title=None),
            y=alt.Y("count:Q", title="practices"),
            tooltip=["day:T", "count:Q"],
        )
        .properties(height=CHART_HEIGHT)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_score_distribution(df: pd.DataFrame) -> None:
    """Histogram of similarity scores."""
    st.markdown("**Score distribution**")
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("similarity_score:Q", bin=alt.Bin(maxbins=20), title="score"),
            y=alt.Y("count():Q", title="practices"),
            tooltip=[alt.Tooltip("count():Q", title="practices")],
        )
        .properties(height=CHART_HEIGHT)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_weakest_phrases(user_id: int, lang: str) -> None:
    """Small table of the hardest phrases (min 3 attempts)."""
    rows = app_mysql.get_user_weakest_phrases(user_id, lang, min_attempts=3, limit=10)
    if not rows:
        return
    st.markdown("**Weakest phrases** (min 3 attempts)")
    tbl = pd.DataFrame(rows)
    tbl["avg_score"] = pd.to_numeric(tbl["avg_score"], errors="coerce")
    tbl["avg_score"] = tbl["avg_score"].map(lambda v: f"{v:.1%}")
    tbl = tbl.rename(columns={
        "target_phrase": "phrase",
        "attempts": "attempts",
        "avg_score": "avg score",
        "last_attempt": "last attempt",
    })
    st.dataframe(tbl, hide_index=True, use_container_width=True)
