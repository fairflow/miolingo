"""
History tab UI: load, save, and render session history.

Extracted from app.py (Phase 4.2 of refactor).

Exports
-------
    load_history()           — load practice history from DB or return []
    save_history(history)    — legacy no-op kept for backward compatibility
    render_history_tab()     — top-level History tab entry point
"""

from collections import defaultdict

import streamlit as st

import app_mysql


def load_history():
    """Load practice history from database (if authenticated) or return empty list"""
    if st.session_state.get('authenticated', False) and 'user' in st.session_state:
        try:
            user_id = st.session_state['user']['user_id']
            language_code = st.session_state.get('language', 'Portuguese')
            # Get recent progress from database
            progress = app_mysql.get_user_progress(user_id, language_code, limit=100)

            # Group practices by date into sessions for compatibility with old history format
            sessions_by_date = defaultdict(list)

            for p in progress:
                date = p['practice_date'].date() if hasattr(p['practice_date'], 'date') else str(p['practice_date'])[:10]
                sessions_by_date[date].append({
                    "target": p['target_phrase'],
                    "recognized": p['recognized_phrase'],
                    "similarity": p['similarity_score'],
                    "exact_match": p['perfect_match'],
                    "correct_phonemes": p.get('target_phonemes', ''),
                    "user_phonemes": p.get('user_phonemes', '')
                })

            # Convert to list of session objects
            return [
                {
                    "date": str(date),
                    "practices": practices
                }
                for date, practices in sorted(sessions_by_date.items(), reverse=True)
            ]
        except Exception as e:
            st.warning(f"Could not load history from database: {e}")
    return []


def save_history(history: list):
    """Legacy function - history now saved immediately to database in check_pronunciation"""
    # No-op: All practice results are saved to database immediately in check_pronunciation()
    # This function kept for backward compatibility but does nothing
    pass


def render_history_tab():
    """Render the History tab showing past practice sessions."""
    st.header("📜 Session History")

    # Reload history from database when viewing this tab
    st.session_state.history = load_history()

    if not st.session_state.history:
        st.info("No previous sessions")
    else:
        # History is already sorted newest first from load_history()
        for i, session in enumerate(st.session_state.history[-10:], 1):
            date = session["date"][:10]
            count = len(session["practices"])
            perfect = sum(1 for p in session["practices"] if p.get("exact_match", False))

            with st.expander(f"{date} - {count} practices ({perfect} perfect)"):
                for j, practice in enumerate(session["practices"], 1):
                    status = "✅" if practice.get("exact_match", False) else f"📊 {practice.get('similarity', 0):.1%}"

                    st.markdown(f"**{j}. {status}**")
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("Target:", practice.get('target', 'N/A'))

                    with col2:
                        st.write("Recognized:", practice.get('recognized', 'N/A'))

                    st.markdown("---")
