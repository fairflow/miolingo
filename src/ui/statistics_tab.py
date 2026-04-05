"""
Statistics tab UI: current session and all-time practice stats.

Extracted from app.py (Phase 4.2 of refactor).

Exports
-------
    render_statistics_tab()  — top-level Statistics tab entry point
"""

import streamlit as st

import app_mysql


def render_statistics_tab():
    """Render the Statistics tab with current session and all-time metrics."""
    st.header("📊 Practice Statistics")

    # Current session stats
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

    # Overall stats - from database for authenticated users
    if st.session_state.get('authenticated', False):
        st.subheader("📈 All Time")
        try:
            user_id = st.session_state['user']['user_id']
            stats = app_mysql.get_user_stats(user_id, st.session_state.language)

            if stats and stats['total'] > 0:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Practices", stats['total'])
                col2.metric("Total Perfect", f"{stats['perfect_count']} ({stats['perfect_count']/stats['total']:.1%})")
                col3.metric("Overall Avg", f"{stats['avg_score']:.1%}")
                col4.metric("Recent Avg (last 10)", f"{stats['recent_avg']:.1%}")
            else:
                st.info("No practice history yet. Start practicing!")
        except Exception as e:
            st.error(f"Could not load stats: {e}")
    else:
        st.info("No practice history yet. Start practicing!")
