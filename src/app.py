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
    DEFAULT_SETTINGS, MATERIAL_TO_TRAINING,
    get_language_code, get_language_for_provider,
)

# Scoring and phoneme modules
from scoring.comparison import (
    levenshtein_distance, get_edit_operations,
    compare_phonemes_edit_distance,
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
from ui.quick_practice_tab import render_quick_practice_tab
from ui.vocabulary_tab import render_vocabulary_tab
from ui.sidebar import render_user_panel, render_settings_panel, is_debug

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

# CCS Testing Framework removed — see commit history for rationale


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

# If we get here, user is authenticated! Show user panel in sidebar.
render_user_panel()

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
        # Source language is session-only (not read from DB settings)
        st.session_state.source_language = "English"
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

    # Quick Practice state (moved from render functions to avoid per-render init)
    if 'last_phrase_index' not in st.session_state:
        st.session_state.last_phrase_index = -1
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False



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

    # State-change tracker — only active in debug mode
    if is_debug():
        if 'last_state_snapshot' not in st.session_state:
            st.session_state.last_state_snapshot = {}

        current_snapshot = {
            'material_language': st.session_state.get('material_language'),
            'story_mode': st.session_state.get('story_mode'),
            'quick_last_result': st.session_state.get('quick_last_result') is not None,
            'story_last_result': st.session_state.get('story_last_result') is not None,
        }

        changes = []
        for key, val in current_snapshot.items():
            old_val = st.session_state.last_state_snapshot.get(key)
            if key in st.session_state.last_state_snapshot and old_val != val:
                changes.append(f"{key}: {old_val} → {val}")

        if changes:
            st.warning(f"🔍 State changed: {', '.join(changes)}")

        st.session_state.last_state_snapshot = current_snapshot.copy()

    # Initialize language state BEFORE rendering title
    # Material Language selection
    from app_language_materials import get_available_languages, format_language_name

    # Map material language to training language (canonical definition in config.py)
    material_to_training = MATERIAL_TO_TRAINING

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

    flag = flag_emojis.get(st.session_state.language, "🌍")
    st.title(f"Miolingo · Multi-language · Practicing: {flag} {st.session_state.language}")

    # Show announcements for main app
    show_announcements('app')

    st.markdown("---")

    render_settings_panel()

    # Main content - Tabs with state management
    tab_names = ["🎯 Quick Practice", "📖 Story Reader", "📚 Vocabulary", "📊 Statistics", "📜 History"]

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
        render_quick_practice_tab()

    # Tab 2: Story Reader
    elif selected_tab_index == 1:
        render_story_reader()

    # Tab 3: Vocabulary
    elif selected_tab_index == 2:
        render_vocabulary_tab()

    # Tab 4: Statistics
    elif selected_tab_index == 3:
        render_statistics_tab()

    # Tab 5: History
    elif selected_tab_index == 4:
        render_history_tab()

if __name__ == "__main__":
    main()
