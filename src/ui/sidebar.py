"""
Sidebar UI: user panel (auth/connection/logout) and settings panel.

Extracted from app.py (Phase 6 of refactor).

Exports
-------
    render_user_panel()      — version, connection info, user info, logout button
                               (rendered immediately after auth check, outside main())
    render_settings_panel()  — languages, TTS, ASR, audio, session, help
                               (rendered inside main())
"""

from datetime import datetime

import streamlit as st

import app_mysql
from auth import on_logout
from config import (
    __version__,
    LANGUAGE_CONFIG,
    MATERIAL_TO_TRAINING,
)
from ui.practice_tab import save_current_session


# ---------------------------------------------------------------------------
# User panel  (version · connection · user info · logout)
# ---------------------------------------------------------------------------

def render_user_panel():
    """
    Render the top sidebar block shown immediately after authentication.
    Contains: version badge, connection info expander, user info, logout button.
    """
    with st.sidebar:
        st.markdown(f"### 🎯 Miolingo v{__version__}")

        # Connection info panel
        conn_info = app_mysql.get_current_connection_info()
        with st.expander("🔌 Connection Info", expanded=False):
            if conn_info:
                st.caption(f"**Tunnel:** `{conn_info['tunnel_id']}` (PID: {conn_info['tunnel_pid']}, Port: {conn_info['tunnel_port']})")
                st.caption(f"**Created:** {conn_info['tunnel_created']}")
                st.caption(f"**Connections:** {conn_info['tunnel_conn_count']} on this tunnel")
                st.caption("---")
                st.caption(f"**SQL Conn:** `{conn_info['connection_id'][:30]}...`")
                st.caption(f"**MySQL ID:** {conn_info['mysql_conn_id']} ({conn_info['connection_status']})")
                st.caption(f"**Age:** {conn_info['connection_age']} | **TTL:** {conn_info['session_ttl']}")
                st.caption(f"**Now:** {conn_info['current_time'].strftime('%H:%M:%S')}")
            else:
                st.caption("⚠️ No connection info available")

            # Reconnect button — always visible inside expander
            if st.button("🔄 Reconnect", help="Get new connection from pool and swap it in"):
                try:
                    old_conn_id = conn_info.get('connection_id') if conn_info else None
                    old_conn = st.session_state.get('db_connection')

                    # Clear session connection so get_connection() creates a new one
                    if 'db_connection' in st.session_state:
                        del st.session_state.db_connection
                    if '_last_connection_info' in st.session_state:
                        del st.session_state['_last_connection_info']
                    if '_last_tunnel_info' in st.session_state:
                        del st.session_state['_last_tunnel_info']

                    new_conn = app_mysql.get_connection()

                    # Verify connection by running a lightweight query
                    cursor = new_conn.cursor(buffered=True)
                    cursor.execute("SELECT 1")
                    cursor.fetchall()
                    cursor.close()

                    # Close old connection after new one is verified
                    if old_conn_id and old_conn:
                        pool = app_mysql.get_connection_pool_instance()
                        pool.close_connection(old_conn_id)
                        try:
                            old_conn.close()
                        except Exception:
                            pass

                    st.success("✓ Switched to fresh connection from pool.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Reconnect failed: {e}")

        st.markdown("---")

        # User info
        if st.session_state['user'].get('is_guest', False):
            st.markdown("👤 **Guest User** 🎭")
            st.warning("⚠️ **Temporary session**: Your progress and settings will be lost when you log out. Create an account to save everything!")
        else:
            st.markdown(f"👤 **{st.session_state['user']['username']}**")
            st.markdown(f"📧 {st.session_state['user']['email']}")

        # Logout button
        if st.button("🚪 Logout"):
            try:
                app_mysql.write_debug_log(
                    event_type="logout_button_clicked",
                    message="Logout button clicked",
                    username=st.session_state.get('user', {}).get('username'),
                    user_id=st.session_state.get('user', {}).get('user_id'),
                    session_id=st.session_state.get('session_id'),
                )
            except Exception:
                pass

            if 'session_id' in st.session_state:
                app_mysql.delete_session(st.session_state['session_id'])

            on_logout()
            app_mysql.cleanup_session_resources()
            st.session_state.clear()
            st.session_state['voluntary_logout'] = True
            st.rerun()


# ---------------------------------------------------------------------------
# Settings panel  (languages · TTS · ASR · audio · session · help)
# ---------------------------------------------------------------------------

def render_settings_panel():
    """
    Render the settings sidebar block inside main().
    Contains: language selectors, TTS settings, ASR settings,
    audio processing, current session summary, help & docs links.
    """
    from app_language_materials import get_available_languages, format_language_name

    with st.sidebar:
        st.markdown("---")
        st.header("⚙️ Settings")

        # ── Languages ────────────────────────────────────────────────────────
        st.markdown("**🌍 Languages**")

        available_materials = get_available_languages()
        if available_materials:
            # ── Source language: locked for this session ─────────────────────────
            _SOURCE_FLAGS = {
                "English": "🇬🇧", "French": "🇫🇷", "German": "🇩🇪",
                "Spanish": "🇪🇸", "Italian": "🇮🇹", "Dutch": "🇳🇱", "Portuguese": "🇵🇹",
            }
            _source = st.session_state.get("source_language", "English")
            _sflag = _SOURCE_FLAGS.get(_source, "🌍")
            st.markdown(
                f"**Your language:** {_sflag}&nbsp;{_source}&emsp;"
                f"<small style='color:gray'>*(fixed until logout)*</small>",
                unsafe_allow_html=True,
            )
            # ─────────────────────────────────────────────────────────────────────

            # Target language — exclude the source language from options
            from config import get_language_code
            _source_code = get_language_code(st.session_state.get("source_language", "English"))
            _target_options = [m for m in available_materials if m != _source_code]

            current_idx = 0
            if 'material_language' in st.session_state:
                try:
                    current_idx = _target_options.index(st.session_state.material_language)
                except ValueError:
                    pass
            elif 'material_language' in st.session_state.settings:
                try:
                    current_idx = _target_options.index(st.session_state.settings['material_language'])
                except ValueError:
                    pass

            previous_material_language = st.session_state.get('material_language', None)
            st.selectbox(
                "Target Language",
                _target_options,
                index=current_idx,
                format_func=format_language_name,
                help="Language being learned (IPA + practice target)",
                key="material_language"
            )

            # Sync target language
            st.session_state.target_language = st.session_state.material_language

            # Resolve full target name for display
            _target_full = MATERIAL_TO_TRAINING.get(
                st.session_state.material_language,
                st.session_state.material_language,
            )

            st.caption(f"Direction: {st.session_state.source_language} → {_target_full}")

            # Update training language if material language changed
            training_language = MATERIAL_TO_TRAINING.get(
                st.session_state.material_language, 'French'
            )
            if previous_material_language != st.session_state.material_language:
                st.session_state.language = training_language
                if training_language not in st.session_state.current_sessions:
                    st.session_state.current_sessions[training_language] = {
                        "date": datetime.now().isoformat(),
                        "practices": []
                    }

        # Safety: ensure session exists for current language
        if st.session_state.language not in st.session_state.current_sessions:
            st.session_state.current_sessions[st.session_state.language] = {
                "date": datetime.now().isoformat(),
                "practices": []
            }

        lang_config = LANGUAGE_CONFIG[st.session_state.language]

        # ── TTS Engine ───────────────────────────────────────────────────────
        st.markdown("**🔊 Text-to-Speech Engine**")

        current_engine = st.session_state.settings.get('tts_engine', 'google_cloud')
        engine_options = ["google_cloud", "gtts", "espeak"]
        try:
            current_index = engine_options.index(current_engine)
        except ValueError:
            current_index = 0

        st.session_state.settings['tts_engine'] = st.selectbox(
            "TTS Engine",
            engine_options,
            index=current_index,
            help=(
                "google_cloud: Official Google Cloud TTS (best quality, requires API key)\n"
                "gtts: Unofficial Google TTS (rate limited)\n"
                "espeak: eSpeak (adjustable speed/pitch, robotic voice)"
            )
        )

        tts_is_espeak = st.session_state.settings.get('tts_engine') == 'espeak'

        if tts_is_espeak:
            st.session_state.settings['speed'] = st.slider(
                "Speed (wpm)", 80, 450, st.session_state.settings['speed'], 10,
                help="Lower = slower speech (eSpeak only)"
            )
            st.session_state.settings['pitch'] = st.slider(
                "Pitch", 0, 99, st.session_state.settings['pitch'], 5,
                help="Voice pitch (eSpeak only)"
            )
        else:
            st.session_state.settings['gtts_slow'] = st.checkbox(
                "Slow speech",
                value=st.session_state.settings.get('gtts_slow', False),
                help="Enable slower speech (~50% speed). Google TTS only supports normal or slow."
            )
            st.caption("💡 For more speed control, change the speed settings on the playback control (⋮)")

        # Voice selector
        tts_engine = st.session_state.settings['tts_engine']
        available_voices = lang_config['voices'][tts_engine]

        current_voice = st.session_state.settings.get('voice', available_voices[0])
        if current_voice not in available_voices:
            current_voice = available_voices[0]
            st.session_state.settings['voice'] = current_voice

        st.session_state.settings['voice'] = st.selectbox(
            "Voice",
            available_voices,
            index=available_voices.index(current_voice),
            help=f"Available voices for {st.session_state.language}"
        )

        # ── Speech Recognition ───────────────────────────────────────────────
        st.markdown("**🎙️ Speech Recognition**")

        # wav2vec2 disabled — Whisper is the primary ASR engine
        st.session_state.settings['asr_engine'] = 'whisper'

        st.session_state.settings['whisper_model_size'] = st.selectbox(
            "Whisper Model Size",
            ["tiny", "base", "small", "medium", "large"],
            index=["tiny", "base", "small", "medium", "large"].index(
                st.session_state.settings.get('whisper_model_size', 'base')
            ),
            help="Larger = more accurate but slower. tiny is fastest, large is most accurate."
        )
        # Keep 'model' in sync for backwards compatibility
        st.session_state.settings['model'] = st.session_state.settings['whisper_model_size']

        st.session_state.settings['comparison_algorithm'] = st.selectbox(
            "Scoring Algorithm",
            ["edit_distance", "positional"],
            index=0 if st.session_state.settings.get('comparison_algorithm', 'edit_distance') == 'edit_distance' else 1,
            help="edit_distance: Handles insertions/deletions (recommended)\npositional: Simple character-by-character matching"
        )

        # ── Audio Processing ─────────────────────────────────────────────────
        st.markdown("**🎚️ Audio Processing**")

        st.session_state.settings['silence_threshold'] = st.slider(
            "Silence Trim Threshold",
            min_value=0.001,
            max_value=0.1,
            value=st.session_state.settings.get('silence_threshold', 0.01),
            step=0.001,
            format="%.3f",
            help=(
                "Audio above this threshold (% of max) is kept as speech. "
                "Lower = keep more audio (may include noise). "
                "Higher = more aggressive trimming (may cut speech ends). Default: 0.01"
            )
        )

        use_wav = st.checkbox(
            "Use WAV audio format",
            value=st.session_state.settings.get('use_wav_audio', False),
            help="Enable if TTS audio doesn't play on your device (iOS Safari compatibility). Converts MP3→WAV.",
            key="use_wav_checkbox"
        )
        if use_wav != st.session_state.settings.get('use_wav_audio', False):
            st.session_state.settings['use_wav_audio'] = use_wav
            _save_settings(st.session_state.settings)
            st.info("WAV audio setting saved")

        if st.button("💾 Save Settings"):
            settings_to_save = st.session_state.settings.copy()
            settings_to_save['material_language'] = st.session_state.get('material_language', 'fr')
            _save_settings(settings_to_save)
            st.success("Settings saved!")
            st.rerun()

        # ── Current Session ──────────────────────────────────────────────────
        st.markdown("---")
        st.header("📊 Current Session")

        current_session = st.session_state.current_sessions[st.session_state.language]
        practice_count = len(current_session["practices"])
        st.metric("Practices", practice_count)

        if practice_count > 0:
            perfect = sum(1 for p in current_session["practices"] if p.get("exact_match", False))
            st.metric("Perfect", f"{perfect}/{practice_count}")

            if not st.session_state.session_saved:
                st.warning(f"⚠️ {practice_count} unsaved practice(s)")
                if st.button("💾 Save Session Now"):
                    save_current_session()

        # ── Help & Docs ──────────────────────────────────────────────────────
        st.markdown("---")
        st.header("📚 Help & Docs")
        st.markdown("""
        **📖 Guides:**
        - [User Guide](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/docs/app-docs/USER_GUIDE.md) - How to use the app
        - [Testing Guide](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/docs/app-docs/TESTING_GUIDE.md) - Report bugs & test
        - [All Documentation](https://github.com/fairflow/miolingo/tree/feature/admin-fusion/docs/app-docs)

        **📚 Stories:**
        """)

        lang_code = st.session_state.get('material_language', 'fr')
        _render_story_link(lang_code)

        st.markdown("""
        **💬 Support:**
        - Email: io@miolingo.io
        - Discord: [Coming soon]
        """)


def _render_story_link(lang_code: str):
    """Render the language-appropriate story link."""
    base = "https://github.com/fairflow/miolingo/blob/feature/admin-fusion/language_materials"
    stories = {
        'pt': (f"{base}/pt/story.md", "Sophie & Lucas: Uma Jornada aos Alpes (Portuguese)"),
        'fr': (f"{base}/fr/story.md", "Sophie & Lucas: A Journey to the Alps (French)"),
        'nl': (f"{base}/nl/story.md", "Sophie & Lucas: Een Reis naar de Alpen (Dutch)"),
        'de': (f"{base}/de/story.md", "Sophie & Lucas: Eine Reise in die Alpen (German)"),
        'it': (f"{base}/it/story.md", "Sophie & Lucas: Un Viaggio sulle Alpi (Italian)"),
        'es': (f"{base}/es/story.md", "Sophie & Lucas: Un Viaje a Sierra Nevada (Spanish)"),
    }
    if lang_code in stories:
        url, label = stories[lang_code]
        st.markdown(f"- [{label}]({url})")


def _save_settings(settings: dict):
    """Thin wrapper — delegates to config.save_settings via app.py pattern."""
    from config import save_settings as _save
    import app_mysql as _db
    _save(settings, session_state=st.session_state, db_module=_db,
          error_callback=st.error)
