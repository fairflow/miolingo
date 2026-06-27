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
    SOURCE_LANGUAGE_OPTIONS,
    get_language_code,
)
from ui.practice_tab import save_current_session
from ui.language_state import assert_sidebar_owner, drain_tripwire_messages


# ---------------------------------------------------------------------------
# User panel  (version · connection · user info · logout)
# ---------------------------------------------------------------------------

def is_debug() -> bool:
    """Return True when debug mode is enabled in settings."""
    return st.session_state.get('settings', {}).get('debug_mode', False)


def render_user_panel():
    """
    Render the top sidebar block shown immediately after authentication.
    Contains: version badge, connection info expander, user info, logout button.
    """
    with st.sidebar:
        st.markdown(f"### 🎯 Miolingo v{__version__}")

        # Connection info panel — debug mode only
        if is_debug():
            conn_info = app_mysql.get_current_connection_info()
            with st.expander("🔌 Connection Info", expanded=False):
                # DB target indicator (LOCAL vs REMOTE) — first thing shown
                # so split-brain bugs are spotted at a glance.
                db_target = (conn_info or {}).get('db_target', 'REMOTE')
                if db_target == 'LOCAL':
                    st.success(f"🏠 **DB target:** {db_target} (Unix socket, no tunnel)")
                else:
                    st.info(f"🌐 **DB target:** {db_target} (SSH tunnel)")
                st.caption("---")

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

                if st.button("🔄 Reconnect", help="Get new connection from pool and swap it in"):
                    try:
                        old_conn_id = conn_info.get('connection_id') if conn_info else None
                        old_conn = st.session_state.get('db_connection')

                        if 'db_connection' in st.session_state:
                            del st.session_state.db_connection
                        if '_last_connection_info' in st.session_state:
                            del st.session_state['_last_connection_info']
                        if '_last_tunnel_info' in st.session_state:
                            del st.session_state['_last_tunnel_info']

                        new_conn = app_mysql.get_connection()

                        cursor = new_conn.cursor(buffered=True)
                        cursor.execute("SELECT 1")
                        cursor.fetchall()
                        cursor.close()

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

            # Preserve the cookie_manager across the clear so the already-queued
            # save() in on_logout() can finish committing to the browser on
            # the next render. Re-instantiating it mid-logout races the
            # component and can leave the session cookie in place (auto
            # re-login) or block the login page from rendering (blank page).
            preserved = {}
            if 'cookie_manager' in st.session_state:
                preserved['cookie_manager'] = st.session_state['cookie_manager']
            st.session_state.clear()
            st.session_state.update(preserved)
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
    from app_language_materials import format_language_name

    with st.sidebar:
        st.markdown("---")
        st.header("⚙️ Settings")

        # ── Languages ────────────────────────────────────────────────────────
        st.markdown("**🌍 Languages**")

        # Target options: all languages in LANGUAGE_CONFIG, keyed by code.
        # Using LANGUAGE_CONFIG (not a filesystem scan) ensures every
        # configured language — including English — is always available.
        _all_target_codes = [cfg['code'] for cfg in LANGUAGE_CONFIG.values()]

        # ── Source language (free selectbox) ─────────────────────────────────
        # Determine what the current target name is so we can exclude it
        # from source options (source ≠ target).
        _cur_target_code = st.session_state.get('material_language', 'fr')
        # Guard: if the target code isn't recognised in LANGUAGE_CONFIG (a
        # transient corruption mid-rerun, or a stale value from a saved
        # setting referencing a removed language), skip the source-filter
        # exclusion entirely. Resetting source on the basis of a phantom
        # target was Stage 1 / route 1 of the "language keeps reverting"
        # regression — never reset on the basis of a stale lookup.
        _target_known = _cur_target_code in MATERIAL_TO_TRAINING
        _cur_target_name = MATERIAL_TO_TRAINING.get(_cur_target_code, 'French')
        if _target_known:
            _source_options = [l for l in SOURCE_LANGUAGE_OPTIONS if l != _cur_target_name]
        else:
            _source_options = list(SOURCE_LANGUAGE_OPTIONS)

        # Guard: current source must be a valid option AND _source_options
        # must be non-empty. A momentarily empty option list (config
        # half-loaded mid-rerun) is NOT a reason to overwrite the user's
        # saved choice — that's the bug Stage 1 was hunting. Only reset
        # when the source is unambiguously not in a non-empty list.
        _cur_source = st.session_state.get('source_language', 'English')
        if _source_options and _cur_source not in _source_options:
            import logging as _logging
            _logging.getLogger(__name__).info(
                "[sidebar] resetting source_language %r → %r "
                "(not in options=%r, target=%r)",
                _cur_source, _source_options[0], _source_options,
                _cur_target_code,
            )
            assert_sidebar_owner('source_language')
            st.session_state['source_language'] = _source_options[0]

        st.selectbox(
            "Your language (source)",
            _source_options,
            help="The language you speak — freely changeable",
            key="source_language",
        )
        # Keep settings dict in sync so Save Settings persists the choice
        st.session_state.settings['source_language'] = st.session_state.source_language

        # ── Target language ────────────────────────────────────────────────────
        # Exclude the selected source from target options (source ≠ target).
        _source_code = get_language_code(st.session_state.source_language)
        _target_options = [c for c in _all_target_codes if c != _source_code]

        # Ensure material_language is set to a valid option BEFORE the
        # widget renders.  The selectbox with key= reads its value from
        # session state — we must NOT also pass index= or Streamlit warns
        # about conflicting defaults.
        #
        # Guard discipline (Stage 2 step 3):
        #   - Compute the candidate replacement BEFORE deciding whether to
        #     overwrite, so an empty/stale `_target_options` list never
        #     silently picks 'fr' and clobbers a valid saved choice.
        #   - Skip the reset entirely when `_target_options` is empty —
        #     that means the source filter ate every option, which can
        #     happen transiently on a rerun where settings is half-loaded.
        #   - Log every reset on info so the next regression names itself.
        import logging as _logging
        _log_sb = _logging.getLogger(__name__)

        if 'material_language' not in st.session_state:
            # First render — pick from saved settings or first available
            _saved = st.session_state.settings.get('material_language')
            if _saved in _target_options:
                _candidate = _saved
            elif _target_options:
                _candidate = _target_options[0]
            else:
                _candidate = 'fr'
            _log_sb.info(
                "[sidebar] seeding material_language=%r (saved=%r, options=%r)",
                _candidate, _saved, _target_options,
            )
            assert_sidebar_owner('material_language')
            st.session_state.material_language = _candidate
        elif _target_options and st.session_state.material_language not in _target_options:
            # Current value not valid AND we have a real options list to
            # pick from. (If options list is empty, leave the value alone
            # — overwriting based on a momentarily-empty list is the
            # original "sidebar reverts to default" bug.)
            _candidate = _target_options[0]
            _log_sb.info(
                "[sidebar] resetting material_language %r → %r (options=%r)",
                st.session_state.material_language, _candidate, _target_options,
            )
            assert_sidebar_owner('material_language')
            st.session_state.material_language = _candidate

        previous_material_language = st.session_state.get('material_language', None)
        st.selectbox(
            "Target Language",
            _target_options,
            format_func=format_language_name,
            help="Language you are practising — includes all configured languages",
            key="material_language",
        )

        # Sync target language
        assert_sidebar_owner('target_language')
        st.session_state.target_language = st.session_state.material_language

        # Resolve full target name for display
        _target_full = MATERIAL_TO_TRAINING.get(
            st.session_state.material_language,
            st.session_state.material_language,
        )

        st.caption(f"Direction: {st.session_state.source_language} → {_target_full}")

        # Debug-mode diagnostic: surface any unexpected writes to the
        # sidebar-owned language keys detected during this render cycle.
        if is_debug():
            _tripwire_msgs = drain_tripwire_messages()
            if _tripwire_msgs:
                with st.expander("⚠️ Sidebar-ownership tripwire", expanded=True):
                    for _msg in _tripwire_msgs:
                        st.warning(_msg)

        # Update training language if material language changed
        training_language = MATERIAL_TO_TRAINING.get(
            st.session_state.material_language, 'French'
        )
        if previous_material_language != st.session_state.material_language:
            assert_sidebar_owner('language')
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

        # Scoring algorithm: char-level edit distance (default) or phone-level
        # weighted distance over IPA with the espeak-ng accent fold-map.
        _algos = ['edit_distance', 'weighted_phone']
        _algo_labels = {
            'edit_distance': 'edit_distance (character-level)',
            'weighted_phone': 'weighted_phone (IPA feature distance + accent fold-map)',
        }
        st.session_state.settings['comparison_algorithm'] = st.selectbox(
            "Scoring Algorithm",
            _algos,
            index=_algos.index(
                st.session_state.settings.get('comparison_algorithm', 'edit_distance')
            ),
            format_func=lambda a: _algo_labels.get(a, a),
            help="weighted_phone scores at the phone level: phonetically-near "
                 "substitutions and tolerated accent variation cost less than "
                 "genuine errors.",
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

        # ── Developer ────────────────────────────────────────────────────────
        st.markdown("---")
        debug_val = st.toggle(
            "🔧 Debug Mode",
            value=st.session_state.settings.get('debug_mode', False),
            help="Show state diagnostics, connection info, and raw file content",
            key="debug_mode_toggle",
        )
        st.session_state.settings['debug_mode'] = debug_val

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

        with st.expander("📖 About IPA — read the brackets next to every word", expanded=False):
            _render_ipa_primer()

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


def _render_ipa_primer():
    """Render the local IPA primer inside the sidebar expander.

    Reads ``docs/app-docs/IPA_PRIMER.md`` and shows it via
    ``st.markdown``. The primer is the canonical user-facing
    explanation of the bracketed transcriptions shown across the app
    (Quick Practice, Story Reader, vocabulary). Falling back to a
    short message if the file is missing keeps the expander useful
    in stripped-down deployments.
    """
    from pathlib import Path

    primer_path = Path(__file__).resolve().parent.parent.parent / "docs" / "app-docs" / "IPA_PRIMER.md"
    try:
        text = primer_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        st.info(
            "IPA primer not found in this deployment. See "
            "[`docs/app-docs/IPA_PRIMER.md`](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/docs/app-docs/IPA_PRIMER.md) "
            "in the repo."
        )
        return
    st.markdown(text)


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
