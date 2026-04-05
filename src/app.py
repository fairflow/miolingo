#!/usr/bin/env python3
"""
Portuguese Pronunciation Trainer - Web Application

Streamlit-based app for practicing Brazilian Portuguese pronunciation
with real-time feedback using speech recognition and phonetic analysis.

Run with: streamlit run app.py
"""

# Configuration, constants, and language definitions — now in config.py
from config import (
    __version__, __app_name__, __author__, __license__,
    LANGUAGE_CONFIG, VOICE_LOCALE_NORMALIZATION, GOOGLE_CLOUD_VOICES,
    DEFAULT_SETTINGS, get_language_code, get_language_for_provider,
)

# Scoring and phoneme modules
from scoring.comparison import (
    levenshtein_distance, get_edit_operations,
    compare_phonemes_positional, compare_phonemes_edit_distance,
    compare_phonemes,
)
from scoring.phonemes import (
    get_espeak_path, get_phonemes, normalize_for_phoneme_scoring,
    get_ipa, get_ipa_from_espeak, format_ipa,
)

# Audio modules
from audio.tts import (
    speak_text, speak_text_google_cloud, speak_text_gtts,
    generate_target_audio,
)
from audio.asr import (
    get_whisper_model, get_wav2vec2_model,
    transcribe_audio_whisper, transcribe_audio_wav2vec2,
    transcribe_audio,
)

# Practice orchestration
from scoring.practice import (
    practice_word_from_audio as _practice_word_from_audio_core,
    trim_silence,
)

# Translation module
from translation import (
    get_translation_provider, validate_translation_api_key,
    get_translation_from_llm, enrich_material_file,
)

import streamlit as st


# Page configuration (must be the first Streamlit command)
st.set_page_config(
    page_title="Miolingo - Multi-language Pronunciation Practice",
    page_icon="🌍",
    layout="wide",
)


_startup_notice = st.empty()
_startup_notice.info(
    "Starting up… first load can take a bit while models and libraries warm up."
)


import json
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import subprocess
import tempfile
import os

# Import authentication module
import app_mysql

# Auth module: login page, session validation, announcements, session manager
from auth import (
    init_session_manager,
    check_authentication,
    show_announcements,
    on_logout,
)

# UI tab modules (Phase 4 refactor)
from ui.practice_tab import (
    practice_word_from_audio,
    save_current_session,
    render_practice_interface,
    render_practice_results,
)
from ui.story_tab import render_story_reader
from ui.statistics_tab import render_statistics_tab
from ui.history_tab import load_history, save_history, render_history_tab

# Import API usage logger for cost tracking
try:
    from api_usage_logger import log_api_call
except ImportError:
    # Fallback if logger not available (no-op function)
    def log_api_call(*args, **kwargs):
        pass

# ---------------------------------------------------------------------------
# Ensure common binary paths are available regardless of how the app is
# launched. When spawned from sandboxed environments (e.g. Claude Code,
# launchd, cron) the inherited PATH may lack dirs like /opt/local/bin
# where MacPorts installs ffmpeg, espeak, etc.
# ---------------------------------------------------------------------------
_EXTRA_BIN_DIRS = ["/opt/local/bin", "/usr/local/bin"]
_current_path = os.environ.get("PATH", "")
_missing = [d for d in _EXTRA_BIN_DIRS if d not in _current_path.split(os.pathsep)]
if _missing:
    os.environ["PATH"] = os.pathsep.join(_missing) + os.pathsep + _current_path

# Environment configuration
IS_LOCAL_DEV = os.path.exists('./local/bin/run-espeak-ng')  # True if local eSpeak build exists

# Suppress warnings
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")  # Whisper on CPU
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")  # LibreSSL compatibility

# Audio libraries (whisper, soundfile, numpy, gTTS) are now imported
# inside audio/tts.py, audio/asr.py, and scoring/practice.py.
# Verify they're loadable at startup so we fail fast with a clear message.
try:
    with st.spinner("Loading speech + audio libraries (first load may take a minute)…"):
        import whisper  # noqa: F401 — preload for ASR
        import soundfile as sf  # noqa: F401 — preload for audio I/O
        import numpy as np  # noqa: F401 — preload for silence trimming
except ImportError as e:
    st.error(f"Error: {e}")
    st.error("Please activate the virtual environment and install dependencies")
    st.stop()
finally:
    _startup_notice.empty()

# Initialise session manager (auth infrastructure — must happen after st.set_page_config)
init_session_manager()

# CCS Testing Framework (optional)
try:
    from ccs_test_integration import CCSTestSession
    CCS_AVAILABLE = True
except ImportError:
    CCS_AVAILABLE = False


# ============================================================================
# SETTINGS FUNCTIONS — thin wrappers over config.py
# ============================================================================

def load_settings():
    """Load user settings from database or local config file."""
    from config import load_settings as _load
    return _load(session_state=st.session_state, db_module=app_mysql)


def save_settings(settings: Dict):
    """Save settings to database or local config file."""
    from config import save_settings as _save
    _save(settings, session_state=st.session_state, db_module=app_mysql,
          error_callback=st.error)


# ============================================================================
# MATERIAL ENRICHMENT — now in translation.py (imported above)
# The imported functions accept secrets/db_module as parameters.
# Call sites in this file that previously used st.secrets / app_mysql directly
# now go through the imported versions. Where needed, pass st.secrets and
# app_mysql explicitly.
# ============================================================================


# ============================================================================
# ANNOUNCEMENTS + AUTHENTICATION — now in auth.py (Phase 3 of refactor).
# get_announcements, show_announcements, show_login_page, check_authentication
# are imported from auth at the top of this file.
#
# LOGOUT LOCATIONS IN CODE:
#
# 1. VOLUNTARY LOGOUT (below): User clicks "🚪 Logout" button
#    - Calls on_logout() from auth, then clears session state
#
# 2. FORCED LOGOUT — Session Expired: inside check_authentication() in auth.py
#    - Sets forced_logout_reason = "session_invalid"
#    - Shows red error banner on login page
#
# To add new forced logout scenarios:
#   1. Set st.session_state['forced_logout_reason'] = "code_name"
#   2. Set st.session_state['forced_logout_message'] = "User-friendly message"
#   3. Then set authenticated = False and st.rerun()
#
# ============================================================================

# ========================================
# MAINTENANCE BANNER
# When activating: Set BANNER_START_TIME to current time, banner shows time+5 minutes
# Remember to deactivate after maintenance by commenting out the st.warning line!
# ========================================
# st.success("🎉 **Now supporting 6 languages!** Practice pronunciation in Portuguese, French, Dutch, German, Italian, and Spanish.")

# Check authentication BEFORE loading the app (show_login_page + session validation in auth.py)
check_authentication()

# ========================================
# RECOMMENDATION 3: User-Visible Capacity Warning
# ========================================
# Show capacity warning to users if system is under high load
try:
    pool = app_mysql.get_connection_pool_instance()
    with pool.get_bootstrap_connection() as capacity_conn:
        cursor = capacity_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM connection_monitor WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        cursor.close()

        MAX_TOTAL_CONNECTIONS = 100
        capacity_pct = (active_count / MAX_TOTAL_CONNECTIONS) * 100

        if capacity_pct > 85:
            st.warning(f"⚠️ **High System Load**: Miolingo is currently at {capacity_pct:.0f}% capacity. You may experience slower response times. Please be patient!")
        elif capacity_pct > 75:
            st.info(f"ℹ️ **Busy Period**: System is at {capacity_pct:.0f}% capacity. Service is running normally but may be slower during peak usage.")
except Exception:
    # Don't break the app if capacity check fails
    pass

# If we get here, user is authenticated! Show logout button in sidebar
with st.sidebar:
    # Version at very top
    st.markdown(f"### 🎯 Miolingo v{__version__}")

    # Connection info panel (thin, below version)
    # Connection info panel - ALWAYS show (even if no connection)
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

        # Reconnect button - OUTSIDE conn_info check so always visible
        if st.button("🔄 Reconnect", help="Get new connection from pool and swap it in"):
            try:
                # Get old connection details for cleanup
                old_conn_id = conn_info.get('connection_id') if conn_info else None
                old_conn = st.session_state.get('db_connection')

                # Clear the session connection so get_connection() creates a new one
                if 'db_connection' in st.session_state:
                    del st.session_state.db_connection

                # Clear cached display info BEFORE getting new connection
                # This ensures get_connection() will update the cache with fresh data
                if '_last_connection_info' in st.session_state:
                    del st.session_state['_last_connection_info']
                if '_last_tunnel_info' in st.session_state:
                    del st.session_state['_last_tunnel_info']

                # Get new connection from pool (this creates new tracked connection AND updates cache)
                new_conn = app_mysql.get_connection()

                # Verify new connection is tracked by doing a simple query
                # This ensures the connection info is fully populated in the database
                cursor = new_conn.cursor(buffered=True)
                cursor.execute("SELECT 1")
                cursor.fetchall()  # Consume all results
                cursor.close()

                # Now close the old connection (after new one is established and verified)
                if old_conn_id and old_conn:
                    pool = app_mysql.get_connection_pool_instance()
                    pool.close_connection(old_conn_id)
                    try:
                        old_conn.close()
                    except:
                        pass

                st.success("✓ Switched to fresh connection from pool.")
                st.rerun()
            except Exception as e:
                st.error(f"Reconnect failed: {e}")

    st.markdown("---")

    # User info below divider
    if st.session_state['user'].get('is_guest', False):
        st.markdown("👤 **Guest User** 🎭")
        st.warning("⚠️ **Temporary session**: Your progress and settings will be lost when you log out. Create an account to save everything!")
    else:
        st.markdown(f"👤 **{st.session_state['user']['username']}**")
        st.markdown(f"📧 {st.session_state['user']['email']}")

    # Logout button at bottom of this section
    if st.button("🚪 Logout"):
        # VOLUNTARY LOGOUT: User clicked the button
        # Mark as voluntary BEFORE clearing, so login page doesn't show forced logout warning
        voluntary_logout = True

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

        # Delete session from database
        if 'session_id' in st.session_state:
            app_mysql.delete_session(st.session_state['session_id'])

        # Clear cookie + set logged-out flag (delegated to auth module)
        on_logout()

        # Cleanup session resources (connections, etc)
        app_mysql.cleanup_session_resources()

        # Clear session state, but preserve voluntary logout marker
        st.session_state.clear()
        st.session_state['voluntary_logout'] = True  # Set AFTER clear
        st.rerun()

# ============================================================================
# END AUTHENTICATION - Main app starts below
# ============================================================================


# load_history, save_history — now in ui/history_tab.py (imported above)


def initialize_session_state():
    """Initialize Streamlit session state"""
    # Set app name for connection tracking
    if 'app_name' not in st.session_state:
        st.session_state.app_name = 'miolingo'

    if 'settings' not in st.session_state:
        st.session_state.settings = load_settings()

    # Material language will be initialized by the selectbox widget with key="material_language"
    # Do NOT manually initialize it here - that conflicts with the widget's key

    # Initialize language - will be set correctly in main() based on material_language
    if 'language' not in st.session_state:
        st.session_state.language = 'French'  # Safe default

    # Two-way language settings
    if 'source_language' not in st.session_state:
        st.session_state.source_language = 'English'
    if 'target_language' not in st.session_state:
        st.session_state.target_language = st.session_state.language
    if 'translation_direction' not in st.session_state:
        st.session_state.translation_direction = 'source_to_target'

    # Initialize Quick Practice phrase position (app state, persists across tabs)
    # This is separate from widget state to avoid dual-management conflicts
    if 'qp_phrase_position' not in st.session_state:
        st.session_state.qp_phrase_position = 0

    # Diagnostic tracking for state management debugging
    if 'state_change_log' not in st.session_state:
        st.session_state.state_change_log = []

    if 'history' not in st.session_state:
        st.session_state.history = load_history()

    # Language-specific session tracking
    if 'current_sessions' not in st.session_state:
        st.session_state.current_sessions = {}

    # Get or create current session for selected language
    if st.session_state.language not in st.session_state.current_sessions:
        st.session_state.current_sessions[st.session_state.language] = {
            "date": datetime.now().isoformat(),
            "practices": []
        }

    if 'session_saved' not in st.session_state:
        st.session_state.session_saved = False

    # Mode-specific result storage (no shared last_result)
    if 'quick_last_result' not in st.session_state:
        st.session_state.quick_last_result = None
    if 'story_last_result' not in st.session_state:
        st.session_state.story_last_result = None

    # Legacy - keep for backward compatibility but unused
    if 'audio_input_key' not in st.session_state:
        st.session_state.audio_input_key = 0

    if 'whisper_model' not in st.session_state:
        st.session_state.whisper_model = None
        st.session_state.whisper_model_name = None

    if 'wav2vec2_processor' not in st.session_state:
        st.session_state.wav2vec2_processor = None
        st.session_state.wav2vec2_model = None

    # CCS Testing Framework initialization (disabled by default)
    if CCS_AVAILABLE and 'ccs_test' not in st.session_state:
        st.session_state.ccs_test = CCSTestSession(enabled=False)


# ASR model loaders — now in audio/asr.py (imported above)
# get_whisper_model, get_wav2vec2_model are imported at top of file.

# Phoneme/IPA functions — now in scoring/phonemes.py (imported above)
# espeak path, get_phonemes, normalize_for_phoneme_scoring, get_ipa,
# get_ipa_from_espeak, format_ipa are all imported at top of file.

# TTS functions — now in audio/tts.py (imported above)
# speak_text, speak_text_google_cloud, speak_text_gtts,
# generate_target_audio are all imported at top of file.

# ASR transcription — now in audio/asr.py (imported above)
# transcribe_audio_whisper, transcribe_audio_wav2vec2,
# transcribe_audio are all imported at top of file.

# Scoring/comparison functions — now in scoring/comparison.py (imported above)
# levenshtein_distance, get_edit_operations, compare_phonemes_positional,
# compare_phonemes_edit_distance, compare_phonemes are all imported at top.


# practice_word_from_audio — now in ui/practice_tab.py (imported above)
# save_current_session      — now in ui/practice_tab.py (imported above)


# render_practice_interface — now in ui/practice_tab.py (imported above)
# render_practice_results   — now in ui/practice_tab.py (imported above)


# render_practice_results     — now in ui/practice_tab.py (imported above)
# render_scene_practice_mode  — now in ui/story_tab.py (imported above)
# render_story_reader          — now in ui/story_tab.py (imported above)
# render_full_story            — now in ui/story_tab.py (imported above)
# render_scene_by_scene        — now in ui/story_tab.py (imported above)

def main():
    """Main Streamlit app"""
    initialize_session_state()

    # DEBUG: Track what changed to trigger this rerun
    import inspect
    caller_frame = inspect.currentframe()
    if 'last_state_snapshot' not in st.session_state:
        st.session_state.last_state_snapshot = {}

    # Compare key state variables
    current_snapshot = {
        'material_language': st.session_state.get('material_language'),
        'story_mode': st.session_state.get('story_mode'),
        'quick_last_result': st.session_state.get('quick_last_result') is not None,
        'story_last_result': st.session_state.get('story_last_result') is not None,
    }

    changes = []
    for key, val in current_snapshot.items():
        old_val = st.session_state.last_state_snapshot.get(key)
        # Only report actual changes (not None → None, not missing → False)
        if key in st.session_state.last_state_snapshot and old_val != val:
            changes.append(f"{key}: {old_val} → {val}")

    if changes:
        st.warning(f"🔍 State changed: {', '.join(changes)}")

    st.session_state.last_state_snapshot = current_snapshot.copy()

    # Initialize language state BEFORE rendering title
    # Material Language selection
    from app_language_materials import get_available_languages, format_language_name

    # Map material language to training language
    material_to_training = {
        'de': 'German',
        'es': 'Spanish',
        'fr': 'French',
        'it': 'Italian',
        'nl': 'Dutch',
        'pt': 'Portuguese'
    }

    # Initialize material_language from saved settings if not already set
    # Do this BEFORE rendering title so the correct language is displayed
    # NOTE: We use a temporary variable to avoid conflict with the selectbox widget
    if 'material_language' not in st.session_state and 'material_language' in st.session_state.settings:
        saved_lang = st.session_state.settings['material_language']
        # Don't set material_language directly - it will be set by the selectbox widget
        # Instead, just update training language to match
        if saved_lang in material_to_training:
            st.session_state.language = material_to_training[saved_lang]
            # Validate voice is appropriate for this language
            lang_cfg = LANGUAGE_CONFIG[st.session_state.language]
            tts_eng = st.session_state.settings.get('tts_engine', 'google_cloud')
            available_vcs = lang_cfg['voices'][tts_eng]
            current_vce = st.session_state.settings.get('voice')
            if current_vce not in available_vcs:
                st.session_state.settings['voice'] = available_vcs[0]

    # Ensure session_state.language is set from material_language
    # This runs after the selectbox has set material_language
    if 'material_language' in st.session_state:
        if st.session_state.material_language in material_to_training:
            st.session_state.language = material_to_training[st.session_state.material_language]
        else:
            st.session_state.language = 'French'
    elif 'language' not in st.session_state:
        st.session_state.language = 'French'

    # NOW we can safely render the title with correct language
    flag_emojis = {
        "Portuguese": "🇧🇷",
        "French": "🇫🇷",
        "Dutch": "🇳🇱",
        "Flemish": "🇧🇪",
        "German": "🇩🇪",
        "Italian": "🇮🇹",
        "Spanish": "🇪🇸"
    }

    # Get language config AFTER material_language is initialized
    lang_config = LANGUAGE_CONFIG[st.session_state.language]
    flag = flag_emojis.get(st.session_state.language, "🌍")
    st.title(f"Miolingo · Multi-language · Practicing: {flag} {st.session_state.language}")

    # Show announcements for main app
    show_announcements('app')

    st.markdown("---")

    # Sidebar - Settings and Navigation
    with st.sidebar:
        st.markdown("---")
        st.header("⚙️ Settings")

        # Source/Target Language selection
        st.markdown("**🌍 Languages**")

        available_materials = get_available_languages()
        if available_materials:
            # Source language (default English)
            source_options = ["English"] + available_materials
            if st.session_state.get('source_language') not in source_options:
                st.session_state.source_language = "English"

            st.selectbox(
                "Source Language",
                source_options,
                format_func=format_language_name,
                help="Language the learner is most comfortable with",
                key="source_language"
            )

            # Target language (drives materials + IPA)
            # Find current index from saved settings or existing session state
            current_idx = 0
            if 'material_language' in st.session_state:
                try:
                    current_idx = available_materials.index(st.session_state.material_language)
                except ValueError:
                    pass
            elif 'material_language' in st.session_state.settings:
                try:
                    current_idx = available_materials.index(st.session_state.settings['material_language'])
                except ValueError:
                    pass

            previous_material_language = st.session_state.get('material_language', None)
            st.selectbox(
                "Target Language",
                available_materials,
                index=current_idx,
                format_func=format_language_name,
                help="Language being learned (IPA + practice target)",
                key="material_language"
            )

            # Sync target language
            st.session_state.target_language = st.session_state.material_language

            # Prevent source == target
            if st.session_state.source_language == st.session_state.target_language:
                st.warning("Source and target must be different. Source reset to English.")
                st.session_state.source_language = "English"

            # Translation direction toggle
            direction = st.session_state.get('translation_direction', 'source_to_target')
            if st.button("⇄ Switch translation direction"):
                st.session_state.translation_direction = (
                    'target_to_source' if direction == 'source_to_target' else 'source_to_target'
                )
                st.rerun()

            # Direction label
            if st.session_state.translation_direction == 'source_to_target':
                st.caption(f"Direction: {st.session_state.source_language} → {st.session_state.target_language}")
            else:
                st.caption(f"Direction: {st.session_state.target_language} → {st.session_state.source_language}")

            # Derive training language from material language
            if st.session_state.material_language in material_to_training:
                training_language = material_to_training[st.session_state.material_language]
            else:
                training_language = 'French'

            # Update training language if material language changed
            if previous_material_language != st.session_state.material_language:
                st.session_state.language = training_language
                # Ensure session exists for new language
                if training_language not in st.session_state.current_sessions:
                    st.session_state.current_sessions[training_language] = {
                        "date": datetime.now().isoformat(),
                        "practices": []
                    }

        # Ensure session exists for current language (safety check)
        if st.session_state.language not in st.session_state.current_sessions:
            st.session_state.current_sessions[st.session_state.language] = {
                "date": datetime.now().isoformat(),
                "practices": []
            }

        # Get current language config from the derived training language
        lang_config = LANGUAGE_CONFIG[st.session_state.language]

        # TTS Engine selection
        st.markdown("**🔊 Text-to-Speech Engine**")

        # Map current setting to dropdown index
        current_engine = st.session_state.settings.get('tts_engine', 'google_cloud')
        engine_options = ["google_cloud", "gtts", "espeak"]
        try:
            current_index = engine_options.index(current_engine)
        except ValueError:
            current_index = 0  # Default to google_cloud if unknown

        st.session_state.settings['tts_engine'] = st.selectbox(
            "TTS Engine",
            engine_options,
            index=current_index,
            help="google_cloud: Official Google Cloud TTS (best quality, requires API key)\ngtts: Unofficial Google TTS (rate limited)\nespeak: eSpeak (adjustable speed/pitch, robotic voice)"
        )

        tts_is_espeak = st.session_state.settings.get('tts_engine', 'gtts') == 'espeak'

        # Voice settings
        if tts_is_espeak:
            # eSpeak: Full speed and pitch control
            st.session_state.settings['speed'] = st.slider(
                "Speed (wpm)", 80, 450, st.session_state.settings['speed'], 10,
                help="Lower = slower speech (eSpeak only)"
            )

            st.session_state.settings['pitch'] = st.slider(
                "Pitch", 0, 99, st.session_state.settings['pitch'], 5,
                help="Voice pitch (eSpeak only)"
            )
        else:
            # Google TTS: Limited speed control (normal/slow only)
            st.session_state.settings['gtts_slow'] = st.checkbox(
                "Slow speech",
                value=st.session_state.settings.get('gtts_slow', False),
                help="Enable slower speech (~50% speed). Google TTS only supports normal or slow."
            )
            st.caption("💡 For more speed control, change the speed settings on the playback control (⋮)")

        # Get available voices for current language and TTS engine
        tts_engine = st.session_state.settings['tts_engine']
        available_voices = lang_config['voices'][tts_engine]

        # Make sure current voice is valid for selected language, otherwise use first available
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

        st.markdown("**🎙️ Speech Recognition**")

        # wav2vec2 temporarily disabled (requires large dependencies: transformers, torch, librosa)
        # Whisper is the primary ASR engine and works across all 6 languages
        st.session_state.settings['asr_engine'] = 'whisper'  # Force whisper

        # Commented out: ASR Engine selector (can be re-enabled if wav2vec2 dependencies are added back)
        # st.session_state.settings['asr_engine'] = st.selectbox(
        #     "ASR Engine",
        #     ["whisper", "wav2vec2"],
        #     index=0 if st.session_state.settings.get('asr_engine', 'whisper') == 'whisper' else 1,
        #     help="whisper: Multilingual (99 languages)\nwav2vec2: Portuguese-specific (may be more accurate)"
        # )

        # Whisper model size selection
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

        st.markdown("**🎚️ Audio Processing**")

        st.session_state.settings['silence_threshold'] = st.slider(
            "Silence Trim Threshold",
            min_value=0.001,
            max_value=0.1,
            value=st.session_state.settings.get('silence_threshold', 0.01),
            step=0.001,
            format="%.3f",
            help="Audio above this threshold (% of max) is kept as speech. Lower = keep more audio (may include noise). Higher = more aggressive trimming (may cut speech ends). Default: 0.01"
        )

        use_wav = st.checkbox(
            "Use WAV audio format",
            value=st.session_state.settings.get('use_wav_audio', False),
            help="Enable if TTS audio doesn't play on your device (iOS Safari compatibility). Converts MP3→WAV.",
            key="use_wav_checkbox"
        )
        # Update setting immediately when checkbox changes
        if use_wav != st.session_state.settings.get('use_wav_audio', False):
            st.session_state.settings['use_wav_audio'] = use_wav
            save_settings(st.session_state.settings)
            st.info("WAV audio setting saved")

        if st.button("💾 Save Settings"):
            # Include material_language in settings to persist it
            settings_to_save = st.session_state.settings.copy()
            settings_to_save['material_language'] = st.session_state.get('material_language', 'fr')
            save_settings(settings_to_save)
            st.success("Settings saved!")
            st.rerun()

        st.markdown("---")

        # Session info
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

        # Documentation links
        st.markdown("---")
        st.header("📚 Help & Docs")
        st.markdown("""
        **📖 Guides:**
        - [User Guide](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/docs/app-docs/USER_GUIDE.md) - How to use the app
        - [Testing Guide](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/docs/app-docs/TESTING_GUIDE.md) - Report bugs & test
        - [All Documentation](https://github.com/fairflow/miolingo/tree/feature/admin-fusion/docs/app-docs)

        **📚 Stories:**
        """)

        # Language-aware story links (based on material language)
        lang_code = st.session_state.get('material_language', 'fr')

        if lang_code == 'pt':
            st.markdown("- [Sophie & Lucas: Uma Jornada aos Alpes](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/language_materials/pt/story.md) (Portuguese)")
        elif lang_code == 'fr':
            st.markdown("- [Sophie & Lucas: A Journey to the Alps](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/language_materials/fr/story.md) (French)")
        elif lang_code == 'nl':
            st.markdown("- [Sophie & Lucas: Een Reis naar de Alpen](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/language_materials/nl/story.md) (Dutch)")
        elif lang_code == 'de':
            st.markdown("- [Sophie & Lucas: Eine Reise in die Alpen](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/language_materials/de/story.md) (German)")
        elif lang_code == 'it':
            st.markdown("- [Sophie & Lucas: Un Viaggio sulle Alpi](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/language_materials/it/story.md) (Italian)")
        elif lang_code == 'es':
            st.markdown("- [Sophie & Lucas: Un Viaje a Sierra Nevada](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/language_materials/es/story.md) (Spanish)")

        st.markdown("""
        **💬 Support:**
        - Email: io@miolingo.io
        - Discord: [Coming soon]
        """)

        # Fun section - hidden advanced features (currently disabled)
        st.markdown("---")
        st.header("🎉 Fun")

        st.markdown("**Mix up the spoken language**")
        st.info("🚧 Feature temporarily disabled - Training language automatically matches material language for now.")

        # Display current training language (read-only)
        st.text(f"Current training language: {st.session_state.language}")

        # TODO: Re-enable training language override after fixing widget state synchronization issues
        # The challenge is that Streamlit widgets maintain their own state that can conflict
        # with programmatic session_state updates during auto-sync

        # CCS Testing Framework Controls
        if CCS_AVAILABLE:
            st.markdown("---")
            st.header("🧪 CCS Testing")
            st.session_state.ccs_test.render_toggle_ui()
            if st.session_state.ccs_test.enabled:
                st.session_state.ccs_test.render_validation_ui()

    # Main content - Tabs with state management
    tab_names = ["🎯 Quick Practice", "📖 Story Reader", "📊 Statistics", "📜 History"]

    # Use radio buttons to preserve tab state across reruns
    selected_tab_index = st.radio(
        "Select Tab",
        range(len(tab_names)),
        format_func=lambda i: tab_names[i],
        key='active_tab',
        horizontal=True,
        label_visibility='collapsed'
    )

    # Tab 1: Quick Practice
    if selected_tab_index == 0:
        st.header("Quick Practice")

        # Language announcement banner
        # st.info("🎉 **Now supporting 6 languages!** Practice pronunciation in Portuguese, French, Dutch, German, Italian, and Spanish.")

        # Help info for new users
        current_session = st.session_state.current_sessions[st.session_state.language]
        if len(current_session["practices"]) == 0:
            st.info("👋 **New here?** Check the [User Guide](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/docs/app-docs/USER_GUIDE.md) for step-by-step instructions!")

        # Phrase/Word list loading - Built-in Library + User Upload
        # Keep expander open during interactions
        if 'qp_materials_expanded' not in st.session_state:
            st.session_state.qp_materials_expanded = False

        with st.expander("📚 Load Practice Materials", expanded=st.session_state.qp_materials_expanded):
            # Set to expanded when user opens it
            st.session_state.qp_materials_expanded = True

            from app_language_materials import (
                get_available_languages,
                get_language_structure,
                get_file_metadata,
                load_phrase_file,
                format_category_name,
                format_language_name
            )

            # Use radio buttons for material source to preserve state across reruns
            material_source_names = ["📦 Built-in Library", "📁 Upload File"]
            material_source_index = st.radio(
                "Material Source",
                range(len(material_source_names)),
                format_func=lambda i: material_source_names[i],
                key='material_source_tab',
                horizontal=True,
                label_visibility='collapsed'
            )

            # Show content based on selection
            if material_source_index == 0:
                # Built-in materials
                st.write("Browse curated phrase and word lists by language and level.")

                languages = get_available_languages()

                if not languages:
                    st.warning("No built-in materials found in `language_materials/` directory.")
                else:
                    # Use material language from sidebar session state
                    material_lang = st.session_state.get('material_language', 'fr')

                    # Show which material language is active
                    st.info(f"📚 Loading materials for: **{format_language_name(material_lang)}** (change in sidebar)")

                    structure = get_language_structure(material_lang)

                    if structure:
                        # Category selection (phrases vs words, level A-D)
                        categories = list(structure.keys())
                        category = st.selectbox(
                            "Category",
                            categories,
                            format_func=format_category_name,
                            help="Select difficulty level: Beginner (A) → Expert (D)"
                        )

                        # File selection within category
                        files = structure[category]
                        selected_file = st.selectbox(
                            "File",
                            files,
                            help="Select a specific file from this category"
                        )

                        # Show metadata preview
                        metadata = get_file_metadata(material_lang, category, selected_file)

                        if metadata and 'line_count' in metadata:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Items", metadata.get('line_count', 0))
                            with col2:
                                st.metric("Translations", "✓" if metadata.get('has_translations') else "✗")
                            with col3:
                                st.metric("IPA", "✓" if metadata.get('has_ipa') else "✗")

                            # Preview
                            if metadata.get('preview'):
                                with st.expander("Preview first 3 items"):
                                    for line in metadata['preview']:
                                        st.text(line)

                            # Material Enrichment UI
                            missing_translations = not metadata.get('has_translations')
                            missing_ipa = not metadata.get('has_ipa')

                            if missing_translations or missing_ipa:
                                st.markdown("---")
                                st.markdown("**✨ Enrich This Material**")

                                # Enrichment options
                                enrich_col1, enrich_col2 = st.columns(2)
                                with enrich_col1:
                                    add_trans = st.checkbox(
                                        "Add translations",
                                        value=missing_translations,
                                        disabled=not missing_translations,
                                        key=f"enrich_trans_{selected_file}"
                                    )
                                with enrich_col2:
                                    add_ipa_check = st.checkbox(
                                        "Add IPA",
                                        value=missing_ipa,
                                        disabled=not missing_ipa,
                                        key=f"enrich_ipa_{selected_file}"
                                    )

                                if st.button(
                                    "✨ Enrich Material",
                                    type="secondary",
                                    disabled=not (add_trans or add_ipa_check),
                                    key=f"enrich_btn_{selected_file}"
                                ):
                                    with st.spinner("Enriching material... This may take a minute for translations."):
                                        # Progress bar
                                        progress_bar = st.progress(0)
                                        status_text = st.empty()

                                        def progress_callback(current, total, message):
                                            progress = current / total if total > 0 else 0
                                            progress_bar.progress(min(progress, 1.0))
                                            status_text.text(message)

                                        # Perform enrichment
                                        result = enrich_material_file(
                                            file_path=metadata['path'],
                                            lang_code=material_lang,
                                            add_translations=add_trans,
                                            add_ipa=add_ipa_check,
                                            progress_callback=progress_callback
                                        )

                                        progress_bar.empty()
                                        status_text.empty()

                                        if result['success']:
                                            stats = result['stats']
                                            st.success(f"✅ Material enriched successfully!")

                                            # Show stats
                                            stat_col1, stat_col2, stat_col3 = st.columns(3)
                                            with stat_col1:
                                                st.metric("Lines processed", stats.get('total_lines', 0))
                                            with stat_col2:
                                                st.metric("Translations added", stats.get('translations_added', 0))
                                            with stat_col3:
                                                st.metric("IPA added", stats.get('ipa_added', 0))

                                            # Show errors if any
                                            if stats.get('errors'):
                                                with st.expander(f"⚠️ {len(stats['errors'])} error(s) occurred"):
                                                    for error in stats['errors'][:10]:  # Show first 10
                                                        st.text(error)

                                            st.info("📝 Original file backed up to .bak. Click reload to see updated checkmarks.")

                                            # Suggest reloading
                                            if st.button("🔄 Reload Metadata", key=f"reload_meta_{selected_file}"):
                                                # Clear all cached data to force reload of file metadata
                                                st.cache_data.clear()
                                                # active_tab already preserved by radio key
                                                st.rerun()
                                        else:
                                            st.error(f"❌ Enrichment failed: {result['message']}")
                                            if result.get('stats', {}).get('errors'):
                                                with st.expander("Error details"):
                                                    for error in result['stats']['errors']:
                                                        st.text(error)

                                st.markdown("---")

                            # Load button
                            if st.button("📂 Load This File", type="primary", key="load_builtin"):
                                try:
                                    phrases = load_phrase_file(str(metadata['path']))
                                    st.session_state.phrase_list = phrases
                                    st.session_state.qp_phrase_position = 0
                                    st.session_state.phrase_selector_widget = 0  # Sync widget state
                                    st.session_state.state_change_log.append(f"Load builtin: Reset position to 0")
                                    st.session_state.quick_last_result = None
                                    st.session_state.material_source = f"{format_language_name(material_lang)} - {format_category_name(category)} - {selected_file}"
                                    st.session_state.qp_materials_expanded = False  # Close expander
                                    st.success(f"✓ Loaded {len(phrases)} items - scroll down to practice section")
                                    # NO rerun - let Streamlit update naturally to preserve tab
                                except Exception as e:
                                    st.error(f"Error loading file: {e}")
                        else:
                            st.error("Could not read file metadata")
                    else:
                        st.info(f"No materials found for {format_language_name(material_lang)}")

            elif material_source_index == 1:
                # User upload
                st.write("Upload your own phrase or word list.")
                st.caption("**Format:** One phrase per line, or `phrase | translation | [ipa]`")
                st.caption("**Limits:** Max 200 lines, 200 chars per line")

                # File upload size limits
                MAX_UPLOAD_LINES = 200
                MAX_LINE_LENGTH = 200

                uploaded_file = st.file_uploader(
                    "Choose a text file",
                    type=['txt'],
                    help="Upload a .txt file with one phrase per line. Empty lines and comments (#) are ignored."
                )

                if uploaded_file is not None:
                    try:
                        # Read content
                        content = uploaded_file.read().decode('utf-8')

                        # Store in session state (original or enriched version)
                        upload_key = f"upload_{uploaded_file.name}_{uploaded_file.size}"
                        if upload_key not in st.session_state:
                            st.session_state[upload_key] = content
                        else:
                            # Use stored version (may be enriched)
                            content = st.session_state[upload_key]

                        # Validate size limits (parse from current content, not original)
                        raw_lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]

                        if len(raw_lines) > MAX_UPLOAD_LINES:
                            st.error(f"❌ File too large: {len(raw_lines)} lines (max {MAX_UPLOAD_LINES})")
                            st.stop()

                        for i, line in enumerate(raw_lines, 1):
                            # Check the original phrase part only (before first |)
                            phrase_part = line.split('|')[0].strip()
                            if len(phrase_part) > MAX_LINE_LENGTH:
                                st.error(f"❌ Line {i} too long: {len(phrase_part)} chars (max {MAX_LINE_LENGTH})")
                                st.stop()

                        # Parse phrases - support both simple and enhanced format
                        phrases = []
                        has_translations = False
                        has_ipa = False

                        for line in raw_lines:
                            # Skip comments
                            if line.startswith('#'):
                                continue

                            if '|' in line:
                                # Enhanced format with translation
                                parts = [p.strip() for p in line.split('|')]
                                phrase_dict = {
                                    'text': parts[0],
                                    'translation': parts[1] if len(parts) > 1 and parts[1] else None,
                                    'ipa': parts[2] if len(parts) > 2 and parts[2] else None
                                }
                                if phrase_dict['translation']:
                                    has_translations = True
                                if phrase_dict['ipa']:
                                    has_ipa = True
                                phrases.append(phrase_dict)
                            else:
                                # Simple format - just the text
                                phrases.append({'text': line, 'translation': None, 'ipa': None})

                        st.success(f"✓ Loaded {len(phrases)} items from upload")

                        # Show metadata and preview
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Phrases", len(phrases))
                        with col2:
                            st.metric("Translations", "✓" if has_translations else "✗")
                        with col3:
                            st.metric("IPA", "✓" if has_ipa else "✗")

                        # Show saved status
                        if st.session_state.get(f"{upload_key}_saved"):
                            st.success("💾 Saved to server - showing saved version")

                        # Preview
                        with st.expander("📋 Preview", expanded=True):
                            preview_count = min(5, len(phrases))
                            for i, p in enumerate(phrases[:preview_count]):
                                if p.get('translation') or p.get('ipa'):
                                    # Always show all 3 fields to match file format
                                    translation = p.get('translation') or ''
                                    ipa = p.get('ipa') or ''
                                    st.text(f"{p['text']} | {translation} | {ipa}")
                                else:
                                    st.text(p['text'])
                            if len(phrases) > preview_count:
                                st.caption(f"...and {len(phrases) - preview_count} more")

                        # Raw content view for debugging
                        with st.expander("🔍 Raw File Content (first 5 lines)", expanded=False):
                            st.caption("This shows the actual file content in session state:")
                            raw_lines = [line for line in content.split('\n')[:5] if line.strip() and not line.strip().startswith('#')]
                            for line in raw_lines:
                                st.code(line, language=None)

                        # Enrichment UI for uploaded files
                        missing_translations = not has_translations
                        missing_ipa = not has_ipa

                        if missing_translations or missing_ipa:
                            st.markdown("---")
                            st.markdown("**✨ Enrich This Material**")
                            st.caption("💡 Add translations and/or IPA pronunciation to your uploaded file using AI")

                            enrich_col1, enrich_col2 = st.columns(2)
                            with enrich_col1:
                                add_trans_upload = st.checkbox(
                                    "Add translations",
                                    value=missing_translations,
                                    disabled=not missing_translations,
                                    key="enrich_trans_upload"
                                )
                            with enrich_col2:
                                add_ipa_upload = st.checkbox(
                                    "Add IPA",
                                    value=missing_ipa,
                                    disabled=not missing_ipa,
                                    key="enrich_ipa_upload"
                                )

                            if st.button("✨ Enrich Now", type="secondary", key="enrich_upload_btn"):
                                if add_trans_upload or add_ipa_upload:
                                    with st.spinner("Enriching material... This may take a minute."):
                                        # Enrich the phrases in memory
                                        import tempfile
                                        import os
                                        from pathlib import Path

                                        # Save to temp file for enrichment
                                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tf:
                                            for p in phrases:
                                                parts = [p['text']]
                                                if p.get('translation'):
                                                    parts.append(p['translation'])
                                                if p.get('ipa'):
                                                    parts.append(p['ipa'])
                                                tf.write(' | '.join(parts) + '\n')
                                            temp_path = Path(tf.name)

                                        try:
                                            progress_bar = st.progress(0)
                                            status_text = st.empty()

                                            def progress_callback(current, total, message):
                                                progress = current / total if total > 0 else 0
                                                progress_bar.progress(min(progress, 1.0))
                                                status_text.text(message)

                                            # Enrich the temp file
                                            # Use material_language (short code like 'pt', 'fr') not language (full name)
                                            current_lang = st.session_state.get('material_language', 'fr')
                                            result = enrich_material_file(
                                                file_path=temp_path,
                                                lang_code=current_lang,
                                                add_translations=add_trans_upload,
                                                add_ipa=add_ipa_upload,
                                                progress_callback=progress_callback
                                            )

                                            progress_bar.empty()
                                            status_text.empty()

                                            if result['success']:
                                                # Read enriched content and update session state
                                                with open(temp_path, 'r', encoding='utf-8') as f:
                                                    enriched_content = f.read()

                                                # Update session state with enriched version
                                                st.session_state[upload_key] = enriched_content

                                                # Show enrichment stats
                                                stats = result.get('stats', {})
                                                success_msg = st.success(f"✅ Enriched: {stats.get('translations_added', 0)} translations, {stats.get('ipa_added', 0)} IPA")

                                                # Show any errors
                                                errors = stats.get('errors', [])
                                                if errors:
                                                    with st.expander(f"⚠️ {len(errors)} errors occurred", expanded=True):
                                                        for err in errors[:20]:  # Show first 20
                                                            st.caption(err)
                                                        if len(errors) > 20:
                                                            st.caption(f"...and {len(errors) - 20} more")

                                                # Show preview of first enriched lines for debugging
                                                first_lines = [line for line in enriched_content.split('\n')[:5] if line.strip() and not line.startswith('#')]
                                                with st.expander("🔍 First enriched lines (actual file content)", expanded=True):
                                                    st.caption("This shows what was actually written to the file:")
                                                    for line in first_lines:
                                                        st.code(line, language=None)

                                                # Wait a moment so user can see the stats
                                                import time
                                                time.sleep(2)

                                                st.info("🔄 Reloading with enriched content...")
                                                st.rerun()
                                            else:
                                                st.error(f"❌ Enrichment failed: {result.get('error', 'Unknown error')}")
                                                st.warning("💡 You can still save the original file")
                                        finally:
                                            # Clean up temp file
                                            try:
                                                os.unlink(temp_path)
                                            except:
                                                pass

                        # Buttons row
                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button("✅ Use This File", type="primary", key="use_upload"):
                                st.session_state.phrase_list = phrases
                                st.session_state.qp_phrase_position = 0
                                st.session_state.phrase_selector_widget = 0  # Sync widget state
                                st.session_state.state_change_log.append(f"Upload file: Reset position to 0")
                                st.session_state.quick_last_result = None
                                st.session_state.material_source = f"Uploaded: {uploaded_file.name}"
                                st.session_state.qp_materials_expanded = False  # Close expander
                                st.success("✅ File loaded! Scroll down to practice section.")
                                # NO rerun - let Streamlit update naturally to preserve tab

                        with col2:
                            # Save to server button (only for authenticated users)
                            if st.session_state.get('authenticated'):
                                if st.button("💾 Save to Server", key="save_upload"):
                                    import remote_storage

                                    # Get username from user dict (not 'anonymous' fallback - only authenticated users see this button)
                                    user = st.session_state.get('user', {})
                                    username = user.get('username', 'unknown')
                                    # Use material_language (short code like 'pt', 'fr') not language (full name)
                                    current_lang = st.session_state.get('material_language', 'fr')

                                    # Use current content from session state (may be enriched)
                                    upload_key = f"upload_{uploaded_file.name}_{uploaded_file.size}"
                                    content_to_save = st.session_state.get(upload_key, content)

                                    with st.spinner("Uploading to server..."):
                                        # Show debug info
                                        st.caption(f"📤 Uploading as user: {username}, language: {current_lang}")
                                        st.caption(f"📁 Target: ~/miolingo.io/public_ftp/incoming/{username}/{current_lang}/")

                                        result = remote_storage.save_user_material(
                                            content=content_to_save,
                                            filename=uploaded_file.name,
                                            language=current_lang,
                                            username=username
                                        )

                                    if result['success']:
                                        st.success(f"✅ Saved to server: {result['path']}")
                                        st.caption(f"📊 {result['verification']}")

                                        # Show quota info
                                        try:
                                            quota = remote_storage.get_user_quota(username)
                                            st.info(f"📦 Your storage: {quota['used_mb']}/{quota['quota_mb']} MB used")
                                        except Exception as e:
                                            st.caption(f"⚠️ Could not check quota: {str(e)}")

                                        # Mark that this file has been saved (so preview shows saved version)
                                        st.session_state[f"{upload_key}_saved"] = True
                                        st.success("🔄 File saved! Preview now shows server version.")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Upload failed: {result.get('error', 'Unknown error')}")
                                        # Show full error details in expander for debugging
                                        if result.get('error'):
                                            with st.expander("🔍 Error Details"):
                                                st.code(result['error'])
                            else:
                                st.caption("💡 Login to save files to server")

                    except Exception as e:
                        st.error(f"Error reading file: {e}")

        # Show current material source
        if 'phrase_list' in st.session_state and st.session_state.phrase_list:
            material_source = st.session_state.get('material_source', 'Unknown source')
            st.info(f"📚 **Current material:** {material_source}")

            if st.button("🗑️ Clear Material"):
                st.session_state.phrase_list = []
                st.session_state.qp_phrase_position = 0
                st.session_state.phrase_selector_widget = 0  # Sync widget state
                st.session_state.state_change_log.append(f"Clear material: Reset position to 0")
                st.session_state.quick_last_result = None
                st.session_state.material_source = None
                st.rerun()

        # Determine practice mode
        guided_mode = 'phrase_list' in st.session_state and st.session_state.phrase_list

        # MODE 1: Guided List Practice
        if guided_mode:
            st.markdown("---")
            st.subheader("📚 Guided Practice Mode")

            # Use global app state (initialized once at startup)
            # No per-tab initialization needed - qp_phrase_position persists

            # Progress and navigation
            total_phrases = len(st.session_state.phrase_list)
            current_idx = st.session_state.qp_phrase_position

            # Keep index in bounds (e.g., if phrase list changes)
            if current_idx < 0:
                current_idx = 0
                st.session_state.qp_phrase_position = 0
                st.session_state.state_change_log.append(f"Tab load: Bounded qp_phrase_position to 0 (was negative)")
            elif current_idx >= total_phrases:
                current_idx = total_phrases - 1 if total_phrases > 0 else 0
                st.session_state.qp_phrase_position = current_idx
                st.session_state.state_change_log.append(f"Tab load: Bounded qp_phrase_position to {current_idx} (was >= {total_phrases})")
            current_phrase_obj = st.session_state.phrase_list[current_idx]
            # Handle both dict and string formats for backward compatibility
            if isinstance(current_phrase_obj, dict):
                current_phrase = current_phrase_obj['text']
                phrase_translation = current_phrase_obj.get('translation')
                phrase_ipa = current_phrase_obj.get('ipa')
            else:
                current_phrase = current_phrase_obj
                phrase_translation = None
                phrase_ipa = None

            # Track phrase changes to show feedback
            if 'last_phrase_index' not in st.session_state:
                st.session_state.last_phrase_index = current_idx

            if st.session_state.last_phrase_index != current_idx:
                st.success(f"✓ Moved to phrase #{current_idx + 1}")
                st.session_state.last_phrase_index = current_idx

            # Progress bar
            progress = (current_idx + 1) / total_phrases
            st.progress(progress, text=f"Phrase {current_idx + 1} of {total_phrases}")

            # Navigation buttons
            # Check if we're in edit mode
            in_edit_mode = st.session_state.get('edit_mode', False)

            col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
            with col1:
                # Disable navigation in edit mode to avoid confusion
                prev_disabled = (current_idx == 0) or in_edit_mode
                if st.button("⬅️ Previous", disabled=prev_disabled, key="nav_prev",
                           help="Navigation disabled in edit mode" if in_edit_mode else None):
                    # Update app state
                    st.session_state.qp_phrase_position -= 1
                    # Sync widget state so dropdown stays in sync
                    st.session_state.phrase_selector_widget = st.session_state.qp_phrase_position
                    st.session_state.state_change_log.append(f"Prev button: qp_phrase_position → {st.session_state.qp_phrase_position}")
                    # Keep result when navigating
                    st.rerun()
            with col2:
                # Disable navigation in edit mode to avoid confusion
                next_disabled = (current_idx >= total_phrases - 1) or in_edit_mode
                if st.button("Next ➡️", disabled=next_disabled, key="nav_next",
                           help="Navigation disabled in edit mode" if in_edit_mode else None):
                    # Update app state
                    st.session_state.qp_phrase_position += 1
                    # Sync widget state so dropdown stays in sync
                    st.session_state.phrase_selector_widget = st.session_state.qp_phrase_position
                    st.session_state.state_change_log.append(f"Next button: qp_phrase_position → {st.session_state.qp_phrase_position}")
                    # Keep result when navigating
                    st.rerun()
            with col3:
                def format_phrase(i):
                    phrase_obj = st.session_state.phrase_list[i]
                    phrase_text = phrase_obj['text'] if isinstance(phrase_obj, dict) else phrase_obj
                    preview = f"{i+1}. {phrase_text[:40]}{'...' if len(phrase_text) > 40 else ''}"
                    return preview

                # Callback to sync widget selection to app state
                def on_phrase_select():
                    """When user changes dropdown, update app state from widget state"""
                    new_pos = st.session_state.phrase_selector_widget
                    st.session_state.qp_phrase_position = new_pos
                    st.session_state.state_change_log.append(f"Dropdown: qp_phrase_position → {new_pos} (user selected)")

                # Two-key pattern: app state (qp_phrase_position) + widget state (phrase_selector_widget)
                # Widget reads from app state via index=, writes to widget state via key=
                # on_change callback syncs widget state back to app state
                st.selectbox(
                    "Jump to phrase:",
                    options=range(total_phrases),
                    index=st.session_state.qp_phrase_position,  # Read from app state
                    format_func=format_phrase,
                    key="phrase_selector_widget",  # Widget state (separate from app state)
                    on_change=on_phrase_select,  # Sync back to app state
                    disabled=in_edit_mode,
                    help="Phrase navigation disabled in edit mode" if in_edit_mode else "Jump directly to any phrase"
                )
            with col4:
                # Edit button - disabled when in edit mode
                if 'edit_mode' not in st.session_state:
                    st.session_state.edit_mode = False

                # Disable Edit button when already in edit mode (grayed out)
                if st.button("✏️ Edit", key="toggle_edit",
                            help="Edit current phrase or type your own",
                            disabled=st.session_state.edit_mode):
                    st.session_state.edit_mode = True
                    st.rerun()

            # Diagnostic expander (collapsible, for debugging state management)
            with st.expander("🔍 State Diagnostics (for debugging)", expanded=False):
                st.markdown("""
                **Purpose**: Verify state persistence across tab switches and widget interactions.

                This shows how `qp_phrase_position` (app state) and `phrase_selector_widget` (widget state)
                are managed separately but kept in sync via callbacks.
                """)

                col_diag1, col_diag2 = st.columns(2)
                with col_diag1:
                    st.write("**Current State:**")
                    st.json({
                        "qp_phrase_position (app)": st.session_state.qp_phrase_position,
                        "phrase_selector_widget": st.session_state.get('phrase_selector_widget', 'Not created yet'),
                        "active_tab": st.session_state.get('active_tab', 'Unknown'),
                        "edit_mode": st.session_state.get('edit_mode', False),
                        "total_phrases": len(st.session_state.phrase_list) if st.session_state.get('phrase_list') else 0
                    })

                with col_diag2:
                    st.write("**State Change Log (last 10):**")
                    recent_log = st.session_state.state_change_log[-10:] if st.session_state.state_change_log else ["(No changes yet)"]
                    for entry in reversed(recent_log):
                        st.text(entry)

                if st.button("Clear Log", key="clear_state_log"):
                    st.session_state.state_change_log = []
                    st.rerun()

            st.markdown("---")

            # Display current phrase - editable or fixed
            if st.session_state.edit_mode:
                st.markdown("### ✏️ Edit Mode:")
                st.caption("Edit the phrase below or type something completely different")
                text = st.text_input(
                    "Phrase to practice:",
                    value=current_phrase,
                    key="edit_phrase_input"
                )
                if st.button("📚 Return to Guided Mode", key="back_to_guided"):
                    st.session_state.edit_mode = False
                    st.rerun()
            else:
                # Show translation/IPA if available (above phrase for mobile visibility)
                source_lang = st.session_state.source_language
                target_lang = st.session_state.target_language

                translation_text = None
                if source_lang == "English" and phrase_translation:
                    translation_text = phrase_translation
                elif source_lang != target_lang:
                    translation_text = get_translation_from_llm(current_phrase, target_lang, source_lang)

                if translation_text or phrase_ipa:
                    with st.expander("📖 Translation & Reference", expanded=False):
                        if translation_text and not translation_text.startswith('[error'):
                            st.markdown(f"**{source_lang}:** {translation_text}")
                        if phrase_ipa:
                            st.markdown(f"**📚 Reference IPA ({target_lang}):** {format_ipa(phrase_ipa)}", unsafe_allow_html=True)
                            st.caption("Compare with eSpeak IPA generated below")

                # Display phrase - mobile-friendly with emoji inline
                st.markdown(f"#### 🎯 **{current_phrase}**")

                # Use this phrase for practice
                text = current_phrase

        # MODE 2: Free Text Practice
        else:
            st.write("Practice any word or phrase you like")

            # Show navigation buttons (disabled) for consistency
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                st.button("⬅️ Previous", disabled=True, key="nav_prev_disabled",
                         help="Navigation only available in guided mode")
            with col2:
                st.button("Next ➡️", disabled=True, key="nav_next_disabled",
                         help="Navigation only available in guided mode")
            with col3:
                st.write("")  # Spacing

            st.markdown("---")
            text = st.text_input("Enter word or phrase:", key="practice_text_free")

        # Translation-aware practice text
        source_lang = st.session_state.source_language
        target_lang = st.session_state.target_language
        direction = st.session_state.translation_direction

        translated_text = None
        practice_text = text

        if text:
            if direction == 'source_to_target':
                translated_text = get_translation_from_llm(text, source_lang, target_lang)
                if translated_text and not translated_text.startswith('[error'):
                    practice_text = translated_text
            else:
                translated_text = get_translation_from_llm(text, target_lang, source_lang)

        # Show translation + IPA reference for free text
        if text and translated_text and not translated_text.startswith('[error'):
            with st.expander("📖 Translation & Reference", expanded=False):
                if direction == 'source_to_target':
                    st.markdown(f"**{source_lang}:** {text}")
                    st.markdown(f"**{target_lang}:** {translated_text}")
                else:
                    st.markdown(f"**{target_lang}:** {text}")
                    st.markdown(f"**{source_lang}:** {translated_text}")

                ipa = get_ipa_from_espeak(practice_text, get_language_code(target_lang))
                if ipa and not ipa.startswith('[error'):
                    st.markdown(f"**📚 Reference IPA ({target_lang}):** {format_ipa(ipa)}", unsafe_allow_html=True)

        # Use reusable practice interface with quick practice key prefix
        render_practice_interface(practice_text, key_prefix="quick")

        # Show last result using reusable component
        if st.session_state.get('quick_last_result'):
            render_practice_results(st.session_state.quick_last_result, key_prefix="quick")

            # Optional: Hear eSpeak phoneme pronunciation (local development only)
            if IS_LOCAL_DEV and st.session_state.quick_last_result and not st.session_state.quick_last_result["exact_match"]:
                st.markdown("---")
                st.subheader("Compare Phoneme Sounds (eSpeak)")
                st.caption("🔧 Development feature - requires local audio device")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔊 Correct Phonemes", key="phoneme_correct"):
                        speak_text(st.session_state.quick_last_result['target'],
                                 voice=st.session_state.settings['voice'],
                                 speed=st.session_state.settings['speed'],
                                 pitch=st.session_state.settings['pitch'])
                with col2:
                    if st.button("🔊 Your Phonemes", key="phoneme_yours"):
                        speak_text(st.session_state.quick_last_result['recognized'],
                                 voice=st.session_state.settings['voice'],
                                 speed=st.session_state.settings['speed'],
                                 pitch=st.session_state.settings['pitch'])

    # Tab 2: Story Reader
    elif selected_tab_index == 1:
        render_story_reader()

    # Tab 3: Statistics
    elif selected_tab_index == 2:
        render_statistics_tab()

    # Tab 4: History
    elif selected_tab_index == 3:
        render_history_tab()

    # CCS Testing: Extract app state after UI renders (if testing enabled)
    if CCS_AVAILABLE and st.session_state.ccs_test.enabled:
        st.session_state.ccs_test.extract_app_state_from_streamlit()


if __name__ == "__main__":
    main()
