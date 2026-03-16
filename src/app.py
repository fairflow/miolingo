#!/usr/bin/env python3
"""
Portuguese Pronunciation Trainer - Web Application

Streamlit-based app for practicing Brazilian Portuguese pronunciation
with real-time feedback using speech recognition and phonetic analysis.

Run with: streamlit run app.py
"""

# VERSION MARKER - Update this when releasing new version
__version__ = "7.1.3"
__app_name__ = "Pronunciation Trainer"
__author__ = "Matthew Fairtlough & Contributors"
__license__ = "GPL-3.0"

# Language configuration
LANGUAGE_CONFIG = {
    "Portuguese": {
        "code": "pt",
        "display_name": "Portuguese Pronunciation Trainer",
        "voices": {
            "google_cloud": ["pt-br", "pt"],
            "gtts": ["pt-br", "pt"],
            "espeak": ["pt-br", "pt"]
        }
    },
    "Dutch": {
        "code": "nl",
        "display_name": "Dutch/Flemish Pronunciation Trainer",
        "voices": {
            "google_cloud": ["nl", "nl-be"],
            "gtts": ["nl"],
            "espeak": ["nl"]
        }
    },
    "French": {
        "code": "fr",
        "display_name": "French Pronunciation Trainer",
        "voices": {
            "google_cloud": ["fr", "fr-fr"],
            "gtts": ["fr"],
            "espeak": ["fr-fr"]
        }
    },
    "German": {
        "code": "de",
        "display_name": "German Pronunciation Trainer",
        "voices": {
            "google_cloud": ["de", "de-de"],
            "gtts": ["de"],
            "espeak": ["de"]
        }
    },
    "Italian": {
        "code": "it",
        "display_name": "Italian Pronunciation Trainer",
        "voices": {
            "google_cloud": ["it", "it-it"],
            "gtts": ["it"],
            "espeak": ["it"]
        }
    },
    "Spanish": {
        "code": "es",
        "display_name": "Spanish Pronunciation Trainer",
        "voices": {
            "google_cloud": ["es", "es-es"],
            "gtts": ["es"],
            "espeak": ["es"]
        }
    }
}

# Voice locale normalization: lowercase codes → BCP 47 format
VOICE_LOCALE_NORMALIZATION = {
    'pt-br': 'pt-BR',
    'pt': 'pt-PT',
    'fr': 'fr-FR',
    'fr-fr': 'fr-FR',
    'nl': 'nl-NL',
    'nl-be': 'nl-BE',
    'de': 'de-DE',
    'de-de': 'de-DE',
    'it': 'it-IT',
    'it-it': 'it-IT',
    'es': 'es-ES',
    'es-es': 'es-ES'
}

# Google Cloud TTS voice names per locale
GOOGLE_CLOUD_VOICES = {
    "pt-BR": "pt-BR-Standard-A",  # Female Brazilian Portuguese
    "pt-PT": "pt-PT-Standard-A",  # Female European Portuguese
    "fr-FR": "fr-FR-Standard-A",  # Female French
    "nl-NL": "nl-NL-Standard-A",  # Female Dutch
    "nl-BE": "nl-BE-Standard-A",  # Female Flemish
    "de-DE": "de-DE-Standard-A",  # Female German
    "it-IT": "it-IT-Standard-A",  # Female Italian
    "es-ES": "es-ES-Standard-A",  # Female Spanish
}

# Version History:
# 1.2.1 (2025-11-13):
#   - Documentation: Update all docs to be language-agnostic (Miolingo branding)
#   - Update primary URL to miolingo.io with backup streamlit.app URL
#   - Emphasize multi-language support throughout documentation
# 1.2.0 (2025-11-13):
#   - Add built-in language materials library browser (French: 200 phrases + 428 words, Portuguese: 83 phrases + 172 words)
#   - New tabbed interface: "Built-in Library" + "Upload File" for better UX
#   - File metadata preview (item count, translations, IPA) before loading
#   - Track material source in session state
#   - Add app_language_materials.py module for materials management
# 1.1.3 (2025-11-13):
#   - Remove separator line between audio and recording for better mobile spacing
#   - Dynamic language name in recording instructions (Portuguese/French/Dutch)
# 1.1.2 (2025-11-13):
#   - Further mobile UX improvements: smaller phrase heading (h4), info box moved below recording widget
# 1.1.1 (2025-11-13):
#   - Fix eSpeak TTS auto-play bug (use --stdout to capture audio bytes)
#   - Fix mobile UX: smaller heading (h3), emoji inline, translation above phrase
#   - Add French language materials infrastructure (phrases A-D levels)
# 1.0.0 (2025-11-11):
#   - Add multi-language support (Portuguese, French, Dutch, Flemish)
#   - Language-specific session tracking
#   - Dynamic app title based on selected language
#   - Language selector in sidebar
# 0.9.3 (2025-11-11):
#   - Improve audio trimming with 200ms padding (prevents speech artifacts)
#   - Show trimmed audio in results (what was actually recognized)
#   - Use IPA instead of eIPA for normalized phonemes display (user-friendly)
#   - Fix Edit button UX: grayed out in edit mode, clear "Return to Guided Mode" button
#   - British spelling: "Normalised" in UI
# 0.9.2 (2025-11-10):
#   - Add TTS engine selection (Google TTS vs eSpeak)
#   - Fix speed/pitch settings now work (with eSpeak)
#   - Add slow mode for Google TTS (simple on/off)
#   - Add documentation links in sidebar
#   - Reorganize documentation (USER_GUIDE, TESTING_GUIDE, DEVELOPER_GUIDE)
# 0.9.1 (2025-11-10):
#   - Fix WAV audio setting not persisting when saved
# 0.9.0 (2025-11-10):
#   - Add iOS Safari audio compatibility (WAV conversion)
#   - Fix audio generation deadlock with subprocess.DEVNULL
#   - Add user-adjustable silence trimming threshold
#   - Improve CCS testing framework integration
#   - Implement edit distance scoring algorithm
#   - Add version management system

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

# SessionManager (feature-flagged; no behavior change until enabled)
from session_manager import SessionManager

ENABLE_SESSION_MANAGER = True
_session_manager = SessionManager() if ENABLE_SESSION_MANAGER else None
if ENABLE_SESSION_MANAGER and _session_manager:
    _session_manager.ensure_cookie_manager_ready()

# Import API usage logger for cost tracking
try:
    from api_usage_logger import log_api_call
except ImportError:
    # Fallback if logger not available (no-op function)
    def log_api_call(*args, **kwargs):
        pass

# Environment configuration
IS_LOCAL_DEV = os.path.exists('./local/bin/run-espeak-ng')  # True if local eSpeak build exists

# Suppress warnings
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")  # Whisper on CPU
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")  # LibreSSL compatibility

try:
    with st.spinner("Loading speech + audio libraries (first load may take a minute)…"):
        import whisper
        import soundfile as sf
        import numpy as np
        from gtts import gTTS
except ImportError as e:
    st.error(f"Error: {e}")
    st.error("Please activate the virtual environment and install dependencies")
    st.stop()
finally:
    _startup_notice.empty()

# CCS Testing Framework (optional)
try:
    from ccs_test_integration import CCSTestSession
    CCS_AVAILABLE = True
except ImportError:
    CCS_AVAILABLE = False


# ============================================================================
# SETTINGS FUNCTIONS (must be defined before authentication)
# ============================================================================

def load_settings():
    """Load user settings from database (if authenticated) or local config file"""
    default_settings = {
        "speed": 140,
        "pitch": 35,
        "voice": "pt-br",
        "model": "base",
        "duration": 3,
        "comparison_algorithm": "edit_distance",  # or "positional"
        "asr_engine": "whisper",  # "whisper" or "wav2vec2"
        "whisper_model_size": "base",  # tiny, base, small, medium, large
        "silence_threshold": 0.01,  # Energy threshold for silence detection (0.001-0.1)
        "use_wav_audio": False,  # Convert TTS audio to WAV for iOS Safari compatibility
        "tts_engine": "google_cloud",  # "google_cloud" (official API, best), "gtts" (unofficial, rate limited), or "espeak"
        "gtts_slow": False,  # Enable slow speech for Google TTS (when tts_engine='gtts')
    }

    # If authenticated, load from database
    if st.session_state.get('authenticated', False) and 'user' in st.session_state:
        try:
            user_id = st.session_state['user']['user_id']
            db_settings = app_mysql.get_user_settings(user_id)
            if db_settings:
                default_settings.update(db_settings)
                return default_settings
        except Exception as e:
            st.warning(f"Could not load settings from database: {e}")

    # Fall back to local config file for non-authenticated users
    config_file = Path("practice_config.json")
    if config_file.exists():
        try:
            with open(config_file) as f:
                saved = json.load(f)
                default_settings.update(saved)
        except Exception:
            pass

    return default_settings


def save_settings(settings: Dict):
    """Save settings to database (if authenticated) or local config file"""
    # If authenticated, save to database
    if st.session_state.get('authenticated', False) and 'user' in st.session_state:
        try:
            user_id = st.session_state['user']['user_id']
            # Save each setting individually to database
            for key, value in settings.items():
                app_mysql.save_user_setting(user_id, key, value)
            return
        except Exception as e:
            st.error(f"Could not save settings to database: {e}")
            return

    # Fall back to local config file for non-authenticated users
    try:
        with open("practice_config.json", 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        st.error(f"Could not save settings: {e}")


# ============================================================================
# MATERIAL ENRICHMENT (LLM Translations + IPA Generation)
# ============================================================================

def validate_translation_api_key() -> tuple[bool, str]:
    """
    Validate Google Translate API key from Streamlit secrets or env.

    Returns:
        Tuple of (is_valid, api_key_or_error_message)
        - If valid: (True, actual_api_key)
        - If invalid: (False, error_message)
    """
    api_key = st.secrets.get("google_cloud_translate_api_key") or os.environ.get("GOOGLE_TRANSLATE_API_KEY")
    if not api_key or api_key == "your-google-translate-api-key-here":
        return False, "Valid Google Translate API key required for translations. Please configure google_cloud_translate_api_key in secrets.toml or set GOOGLE_TRANSLATE_API_KEY."
    return True, api_key


def get_ipa_from_espeak(text: str, lang_code: str) -> str:
    """
    Generate IPA transcription using espeak-ng.

    Args:
        text: Text to transcribe
        lang_code: Language code (pt, fr, nl, de, it, es)

    Returns:
        IPA transcription or '[error]' on failure
    """
    # Map language codes to espeak voices
    ESPEAK_LANG_MAP = {
        'pt': 'pt-br',
        'fr': 'fr-fr',
        'nl': 'nl',
        'de': 'de',
        'it': 'it',
        'es': 'es'
    }

    espeak_lang = ESPEAK_LANG_MAP.get(lang_code, lang_code)
    espeak_cmd = get_espeak_path()

    try:
        result = subprocess.run(
            [espeak_cmd, '-v', espeak_lang, '-q', '--ipa', text],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            ipa = result.stdout.strip()
            # Clean up spacing
            ipa = ' '.join(ipa.split())
            return ipa
        return '[error]'
    except subprocess.TimeoutExpired:
        return '[timeout]'
    except Exception as e:
        return f'[error: {str(e)}]'


def get_translation_from_llm(text: str, source_lang: str, target_lang: str = "English") -> str:
    """
    Get translation using a pluggable provider (default: Google Translate).
    """
    try:
        # Validate API key
        is_valid, api_key_or_error = validate_translation_api_key()
        if not is_valid:
            return f"[error: {api_key_or_error}]"

        from translation_providers import get_translator

        provider = "google"

        # Cache lookup
        cached = app_mysql.get_translation_cache(
            source_lang=source_lang,
            target_lang=target_lang,
            source_text=text,
            provider=provider,
        )
        if cached and cached.get("translated_text"):
            return cached["translated_text"]

        translator = get_translator(provider, api_key=api_key_or_error)
        result = translator.translate(text, source_lang, target_lang)

        # Cache store
        app_mysql.set_translation_cache(
            source_lang=source_lang,
            target_lang=target_lang,
            source_text=text,
            translated_text=result.translated_text,
            provider=provider,
            detected_source=result.detected_source,
            confidence=result.confidence,
        )

        # Log API usage for cost tracking
        try:
            log_api_call(
                api_name=provider,
                model='google-translate',
                operation='translation',
                input_tokens=0,
                output_tokens=0,
                metadata={'source_lang': source_lang, 'target_lang': target_lang}
            )
        except Exception:
            pass

        return result.translated_text

    except Exception as e:
        return f"[error: {str(e)}]"


def enrich_material_file(
    file_path: Path,
    lang_code: str,
    add_translations: bool = True,
    add_ipa: bool = True,
    progress_callback=None
) -> Dict:
    """
    Enrich a material file by adding missing translations and/or IPA.

    Args:
        file_path: Path to the material file
        lang_code: Language code (pt, fr, nl, etc.)
        add_translations: Whether to add missing translations
        add_ipa: Whether to add missing IPA
        progress_callback: Optional callback function(current, total, message)

    Returns:
        Dict with keys: success (bool), message (str), stats (dict)
    """
    if add_translations:
        # Validate API key before proceeding
        is_valid, error_message = validate_translation_api_key()
        if not is_valid:
            return {
                'success': False,
                'message': error_message,
                'stats': {}
            }

    # Map language codes to full names for LLM
    LANG_NAMES = {
        'pt': 'Portuguese',
        'fr': 'French',
        'nl': 'Dutch',
        'de': 'German',
        'it': 'Italian',
        'es': 'Spanish'
    }
    source_lang_name = LANG_NAMES.get(lang_code, lang_code.upper())

    # Read file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return {
            'success': False,
            'message': f'Could not read file: {e}',
            'stats': {}
        }

    # Create backup
    backup_path = file_path.with_suffix('.bak')
    try:
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        return {
            'success': False,
            'message': f'Could not create backup: {e}',
            'stats': {}
        }

    # Process lines
    enriched_lines = []
    stats = {
        'total_lines': 0,
        'translations_added': 0,
        'ipa_added': 0,
        'errors': []
    }

    for i, line in enumerate(lines):
        # Skip comments and empty lines
        if line.strip().startswith('#') or not line.strip():
            enriched_lines.append(line)
            continue

        # Normalize: strip trailing pipes and whitespace
        normalized_line = line.strip()
        while normalized_line.endswith('|'):
            normalized_line = normalized_line[:-1].strip()

        # Parse the line by splitting on pipes
        if '|' in normalized_line:
            parts = [p.strip() for p in normalized_line.split('|')]
            phrase = parts[0] if len(parts) > 0 else ''
            translation = parts[1] if len(parts) > 1 else ''
            ipa = parts[2] if len(parts) > 2 else ''
        else:
            # Plain text format (no pipes) - treat entire line as phrase
            phrase = normalized_line
            translation = ''
            ipa = ''

        # Skip if no phrase
        if not phrase:
            enriched_lines.append(line)
            continue

        stats['total_lines'] += 1

        # Update progress
        if progress_callback:
            progress_callback(i + 1, len(lines), f"Processing: {phrase[:30]}...")

        # Add translation if missing
        if add_translations and not translation:
            # Debug: log what we're sending to LLM
            if progress_callback:
                progress_callback(i + 1, len(lines), f"Translating: {phrase[:30]}...")

            new_translation = get_translation_from_llm(phrase, source_lang_name)

            # Debug: check if LLM returned IPA instead of translation
            if new_translation.startswith('[') and not new_translation.startswith('[error'):
                stats['errors'].append(f"LLM returned IPA instead of translation for '{phrase}': {new_translation}")
            elif not new_translation.startswith('[error'):
                translation = new_translation
                stats['translations_added'] += 1
            else:
                stats['errors'].append(f"Translation error for '{phrase}': {new_translation}")

        # Add IPA if missing
        # Consider IPA missing if empty or just placeholder markers
        ipa_empty = not ipa or ipa in ['[ipa]', '[]']
        if add_ipa and ipa_empty:
            new_ipa = get_ipa_from_espeak(phrase, lang_code)
            if not new_ipa.startswith('[error') and not new_ipa.startswith('[timeout') and new_ipa.strip():
                ipa = f"[{new_ipa}]"  # Wrap in brackets
                stats['ipa_added'] += 1
            else:
                if new_ipa.strip():
                    stats['errors'].append(f"IPA error for '{phrase}': {new_ipa}")
                else:
                    stats['errors'].append(f"IPA empty for '{phrase}'")

        # Reconstruct line with consistent format: always 3 fields
        enriched_line = f"{phrase} | {translation} | {ipa}\n"
        enriched_lines.append(enriched_line)

    # Write enriched content
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(enriched_lines)
    except Exception as e:
        # Restore from backup
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_content = f.read()
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
        except Exception:
            pass

        return {
            'success': False,
            'message': f'Could not write enriched file: {e}',
            'stats': stats
        }

    return {
        'success': True,
        'message': 'File enriched successfully',
        'stats': stats
    }


# ============================================================================
# ANNOUNCEMENTS
# ============================================================================

@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_announcements(location: str) -> Dict[str, Optional[str]]:
    """Get active announcements for display. Cached for 60 seconds."""
    return app_mysql.get_active_announcements(location)


def show_announcements(location: str):
    """Display active announcements for the specified location."""
    loading = st.empty()
    loading.info("Loading updates…")
    try:
        announcements = get_announcements(location)
    except Exception:
        loading.warning("⚠️ Unable to load updates right now.")
        return
    loading.empty()

    # System announcement (orange, priority)
    if announcements.get('system'):
        st.warning(f"⚠️ {announcements['system']}")

    # Feature announcement (green, secondary)
    if announcements.get('feature'):
        st.success(f"✨ {announcements['feature']}")


# ============================================================================
# AUTHENTICATION (Test Implementation for v1.3.0)
# ============================================================================
#
# LOGOUT LOCATIONS IN CODE:
#
# 1. VOLUNTARY LOGOUT (line ~480): User clicks "🚪 Logout" button
#    - No forced_logout_reason set
#    - Clean logout, deletes session from DB
#
# 2. FORCED LOGOUT - Session Expired (line ~442): Session validation fails
#    - Sets forced_logout_reason = "session_expired"
#    - Shows red error banner on login page with reason code
#    - User can report if unexpected
#
# To add new forced logout scenarios, always:
#   1. Set st.session_state['forced_logout_reason'] = "code_name"
#   2. Set st.session_state['forced_logout_message'] = "User-friendly message"
#   3. Then set authenticated = False and st.rerun()
#
# ============================================================================

def show_login_page():
    """Display login/registration page."""
    st.markdown(f"# 🔐 Miolingo <small>{__version__}</small>", unsafe_allow_html=True)

    # Get language list from config
    languages = ", ".join(LANGUAGE_CONFIG.keys())
    st.markdown(f"Pronunciation trainer - practice {languages}")

    # Choose the initial practice language before login/guest
    # (keeps the main app language selection aligned on first load)
    language_names = list(LANGUAGE_CONFIG.keys())
    default_language_name = st.session_state.get('login_practice_language', 'Portuguese')
    if default_language_name not in language_names:
        default_language_name = language_names[0] if language_names else 'Portuguese'

    selected_language_name = st.selectbox(
        "Practice language",
        language_names,
        index=language_names.index(default_language_name) if default_language_name in language_names else 0,
        key='login_practice_language',
        help="Select the language you want to practice first. You can change this later in Settings."
    )

    # Persist as the canonical material language code (used by the main app selector)
    try:
        selected_code = LANGUAGE_CONFIG[selected_language_name]['code']
        if st.session_state.get('material_language') != selected_code:
            st.session_state.material_language = selected_code
    except Exception:
        pass

    # CRITICAL: Show forced logout reason if present (prominent display)
    # BUT: Don't show if this was a voluntary logout (user clicked logout button)
    if 'voluntary_logout' in st.session_state:
        # User clicked logout button - this is expected, don't show warning
        del st.session_state['voluntary_logout']
    elif 'forced_logout_reason' in st.session_state:
        # This was an unexpected/forced logout - show warning
        reason = st.session_state['forced_logout_reason']
        message = st.session_state.get('forced_logout_message', 'You have been logged out.')

        # Show as error (red banner) so it's highly visible
        st.error(f"🚨 **FORCED LOGOUT**\n\n{message}\n\n📋 *Reason code: `{reason}` - Please report if unexpected*")

        # Clear the forced logout markers after showing (so refresh doesn't show again)
        del st.session_state['forced_logout_reason']
        if 'forced_logout_message' in st.session_state:
            del st.session_state['forced_logout_message']

    # Show announcements for login page
    show_announcements('login')

    # About section with links
    st.markdown("📖 [About & Features](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/README.md) • 📚 [Development Story](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/articles/development_detailed.md)")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Guest Mode"])

    with tab1:
        st.subheader("Login to Your Account")

        with st.form("login_form"):
            username = st.text_input("Username", key="login_username", autocomplete="username")
            password = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
            submit = st.form_submit_button("Login")

            if submit:
                if not username or not password:
                    st.error("❌ Please enter both username and password")
                else:
                    # Authenticate user
                    user = app_mysql.authenticate_user(username, password)

                    if user:
                        # Get user agent for session metadata
                        try:
                            headers = st.context.headers
                            user_agent = headers.get('User-Agent', 'unknown') if headers else 'unknown'
                        except Exception:
                            user_agent = 'unknown'

                        # Create session (stores metadata directly in `sessions`)
                        session_id = app_mysql.create_session(
                            user['user_id'],
                            "127.0.0.1",
                            username=username,
                            user_agent=user_agent,
                            app_name='miolingo',
                        )

                        if session_id:
                            # HANDOVER: Close any bootstrap connection, get tracked connection
                            old_bootstrap = st.session_state.get('db_connection')
                            if old_bootstrap:
                                try:
                                    old_bootstrap.close()
                                    print("✓ Closed bootstrap connection before login")
                                except:
                                    pass
                                del st.session_state.db_connection

                            # Store in session state
                            st.session_state['authenticated'] = True
                            st.session_state['user'] = user
                            st.session_state['session_id'] = session_id

                            # Persist cookie for re-attach (feature-flagged)
                            if ENABLE_SESSION_MANAGER and _session_manager:
                                _session_manager.clear_logged_out_flag()
                                _session_manager.write_cookie_session_id(session_id)

                            # Get tracked connection from pool (replaces bootstrap)
                            tracked_conn = app_mysql.get_connection()
                            print(f"✓ Established tracked connection for {username}")

                            # Session metadata was stored at create_session()

                            # Reload settings from database (using new tracked connection)
                            st.session_state.settings = load_settings()
                            st.success(f"✅ Welcome back, {user['username']}!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to create session. Please try again.")
                    else:
                        st.error("❌ Invalid username or password")

    with tab2:
        st.subheader("Create New Account")

        with st.form("register_form"):
            new_username = st.text_input("Choose Username", key="register_username", autocomplete="username", help="3-20 characters, letters/numbers only")
            new_email = st.text_input("Email Address", key="register_email", autocomplete="email")
            new_password = st.text_input("Choose Password", type="password", key="register_password", autocomplete="new-password", help="Min 8 characters")
            new_password_confirm = st.text_input("Confirm Password", type="password", key="register_password_confirm", autocomplete="new-password")
            submit_register = st.form_submit_button("Create Account")

            if submit_register:
                # Validation
                if not all([new_username, new_email, new_password, new_password_confirm]):
                    st.error("❌ Please fill in all fields")
                elif new_password != new_password_confirm:
                    st.error("❌ Passwords do not match")
                elif len(new_password) < 8:
                    st.error("❌ Password must be at least 8 characters")
                elif len(new_username) < 3 or len(new_username) > 20:
                    st.error("❌ Username must be 3-20 characters")
                else:
                    # Create user
                    user_id = app_mysql.create_user(new_username, new_email, new_password)

                    if user_id:
                        # Note: Registration doesn't auto-login, so no handover needed here
                        # User will do handover when they click Login tab
                        st.success(f"✅ Account created! Welcome, {new_username}!")
                        st.info("👆 Please login with your new account in the Login tab")
                    # Errors are handled in app_mysql.create_user()

    with tab3:
        st.subheader("Try Without Registration")

        st.info("🎭 **Guest Mode** - Try the app instantly without creating an account!")
        st.warning("⚠️ **Note:** Guest sessions are temporary. Your progress won't be saved.")

        st.markdown("""
        **What you get as a guest:**
        - ✅ Full access to all practice features
        - ✅ All supported languages
        - ✅ AI pronunciation feedback
        - ❌ Progress not saved after session ends
        """)

        if st.button("🚀 Start as Guest", type="primary", use_container_width=True):
            # Create guest user
            # Get user agent for session metadata
            try:
                headers = st.context.headers
                user_agent = headers.get('User-Agent', 'unknown') if headers else 'unknown'
            except Exception:
                user_agent = 'unknown'

            result = app_mysql.create_guest_user(
                ip_address="127.0.0.1",
                user_agent=user_agent,
                app_name='miolingo',
            )

            if result:
                user_id, username, session_id = result

                # HANDOVER: Close any bootstrap connection, get tracked connection
                old_bootstrap = st.session_state.get('db_connection')
                if old_bootstrap:
                    try:
                        old_bootstrap.close()
                        print("✓ Closed bootstrap connection before guest login")
                    except:
                        pass
                    del st.session_state.db_connection

                # Create user dict (matching regular auth format)
                guest_user = {
                    'user_id': user_id,
                    'username': username,
                    'email': f'{username}@temp.miolingo.io',
                    'is_guest': True  # Flag for UI indication
                }

                # Store in session state
                st.session_state['authenticated'] = True
                st.session_state['user'] = guest_user
                st.session_state['session_id'] = session_id

                # Persist cookie for re-attach (feature-flagged)
                if ENABLE_SESSION_MANAGER and _session_manager:
                    _session_manager.clear_logged_out_flag()
                    _session_manager.write_cookie_session_id(session_id)

                # Get tracked connection from pool (replaces bootstrap)
                tracked_conn = app_mysql.get_connection()
                print(f"✓ Established tracked connection for guest {username}")

                # Session metadata was stored at create_guest_user()/create_session()

                # Reload settings from database (will have defaults for new guest)
                st.session_state.settings = load_settings()
                st.success(f"✅ Welcome, Guest! Enjoy exploring Miolingo!")
                st.rerun()
            else:
                st.error("❌ Failed to create guest session. Please try again.")


def check_authentication():
    """
    Check if user is authenticated. If not, show login page and stop.
    This runs at the start of every app load.

    Session validation is done periodically (every 60 minutes) rather than on every
    rerun to prevent logout due to temporary database connection issues.
    """
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False

    # Attempt cookie-based reattach (feature-flagged)
    if ENABLE_SESSION_MANAGER and not st.session_state.get('authenticated', False):
        if _session_manager:
            context = _session_manager.resolve_session()
            if context.authenticated and context.user:
                st.session_state['authenticated'] = True
                st.session_state['user'] = context.user
                st.session_state['session_id'] = context.session_id
                st.session_state.settings = load_settings()

    # Check if authenticated
    if not st.session_state['authenticated']:
        show_login_page()
        st.stop()

    # Validate session periodically (not on every rerun)
    if 'session_id' in st.session_state:
        import time

        # Only validate every 60 minutes to reduce DB load and avoid logout on connection issues
        last_check = st.session_state.get('last_session_check', 0)
        now = time.time()

        if now - last_check > 3600:  # 60 minutes = 3600 seconds
            try:
                # Get user agent for logging
                try:
                    headers = st.context.headers
                    user_agent = headers.get('User-Agent', 'unknown') if headers else 'unknown'
                except:
                    user_agent = 'unknown'

                user = app_mysql.validate_session(st.session_state['session_id'], "127.0.0.1")

                # validate_session returns None if session not valid
                # It raises exceptions for database errors (which we catch below)
                if not user:
                    # Session validation failed - could be expired or invalid
                    # Log the forced logout
                    app_mysql.write_debug_log(
                        event_type='forced_logout',
                        message='Session validation failed - forcing logout',
                        username=st.session_state.get('user', {}).get('username'),
                        user_id=st.session_state.get('user', {}).get('user_id'),
                        user_agent=user_agent,
                        session_id=st.session_state['session_id']
                    )
                    # FORCED LOGOUT: Set generic message (don't assume 7-day expiry)
                    st.session_state['forced_logout_reason'] = "session_invalid"
                    st.session_state['forced_logout_message'] = "⚠️ **Session Ended**: Your session is no longer valid. Please login again."
                    st.session_state['authenticated'] = False

                    # Clear cookie on invalid session (feature-flagged)
                    if ENABLE_SESSION_MANAGER and _session_manager:
                        _session_manager.clear_cookie_session_id()

                    st.rerun()
                else:
                    # Session valid - update check timestamp
                    st.session_state['last_session_check'] = now

            except Exception as e:
                # Database connection error or other exception - DON'T logout user
                # This is the key fix: exceptions mean errors, not expiry
                # Just show warning and keep user logged in
                st.warning(f"⚠️ Temporary connection issue during session validation. You remain logged in.")
                # Don't update last_session_check so we retry sooner (next rerun)


# ========================================
# MAINTENANCE BANNER
# When activating: Set BANNER_START_TIME to current time, banner shows time+5 minutes
# Remember to deactivate after maintenance by commenting out the st.warning line!
# ========================================
# st.success("🎉 **Now supporting 6 languages!** Practice pronunciation in Portuguese, French, Dutch, German, Italian, and Spanish.")

# Check authentication BEFORE loading the app
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

        # Clear cookie + set logged-out flag (feature-flagged)
        if ENABLE_SESSION_MANAGER and _session_manager:
            _session_manager.set_logged_out_flag()
            _session_manager.clear_cookie_session_id()

        # Cleanup session resources (connections, etc)
        app_mysql.cleanup_session_resources()

        # Clear session state, but preserve voluntary logout marker
        st.session_state.clear()
        st.session_state['voluntary_logout'] = True  # Set AFTER clear
        st.rerun()

# ============================================================================
# END AUTHENTICATION - Main app starts below
# ============================================================================


def load_history():
    """Load practice history from database (if authenticated) or return empty list"""
    if st.session_state.get('authenticated', False) and 'user' in st.session_state:
        try:
            user_id = st.session_state['user']['user_id']
            language_code = st.session_state.get('language', 'Portuguese')
            # Get recent progress from database
            progress = app_mysql.get_user_progress(user_id, language_code, limit=100)

            # Group practices by date into sessions for compatibility with old history format
            from collections import defaultdict
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


def save_history(history: List[Dict]):
    """Legacy function - history now saved immediately to database in check_pronunciation"""
    # No-op: All practice results are saved to database immediately in check_pronunciation()
    # This function kept for backward compatibility but does nothing
    pass


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


def get_whisper_model(model_name: str):
    """Load or get cached Whisper model"""
    if st.session_state.whisper_model_name != model_name:
        with st.spinner(f"Loading Whisper model '{model_name}'..."):
            st.session_state.whisper_model = whisper.load_model(model_name)
            st.session_state.whisper_model_name = model_name
    return st.session_state.whisper_model


def get_wav2vec2_model():
    """Load or get cached wav2vec2 Portuguese model"""
    if 'wav2vec2_processor' not in st.session_state or st.session_state.wav2vec2_processor is None:
        try:
            with st.spinner("Loading wav2vec2 Portuguese model (first time may take a few minutes)..."):
                from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
                model_name = "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese"
                st.session_state.wav2vec2_processor = Wav2Vec2Processor.from_pretrained(model_name)
                st.session_state.wav2vec2_model = Wav2Vec2ForCTC.from_pretrained(model_name)
        except ImportError:
            st.error("wav2vec2 requires 'transformers' and 'torch'. Install with: pip install transformers torch")
            return None, None
        except Exception as e:
            st.error(f"Failed to load wav2vec2 model: {e}")
            return None, None
    return st.session_state.wav2vec2_processor, st.session_state.wav2vec2_model


def get_espeak_path():
    """
    Get espeak path (local build or system-wide)

    Platform differences:
    - macOS (MacPorts): Binary is "espeak" at /opt/local/bin/espeak
    - Debian/Ubuntu (Streamlit Cloud): Binary is "espeak-ng" from espeak-ng package
    """
    # Try macOS MacPorts path first
    local_path = "/opt/local/bin/espeak"
    if Path(local_path).exists():
        return local_path

    # Try espeak-ng (Streamlit Cloud / Ubuntu)
    try:
        subprocess.run(["espeak-ng", "--version"], capture_output=True, check=True)
        return "espeak-ng"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback to espeak (if available)
    return "espeak"


def get_phonemes(text: str, voice: str = "pt-br") -> str:
    """Get eSpeak phoneme codes (eIPA) for text"""
    try:
        espeak_cmd = get_espeak_path()
        result = subprocess.run(
            [espeak_cmd, "-v", voice, "-x", "-q", text],
            capture_output=True,
            text=True,
            check=True
        )
        # eSpeak may insert newlines around punctuation; normalize to single spaces
        phonemes = result.stdout.strip()
        phonemes = ' '.join(phonemes.split())
        return phonemes
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        st.warning(f"eSpeak phoneme error: {e} (cmd: {get_espeak_path()})")
        return "[phonemes unavailable]"


def normalize_for_phoneme_scoring(s: str) -> str:
    """
    Normalize eSpeak phoneme strings for pronunciation scoring.

    Removes:
    - All whitespace (word boundaries, spaces)
    - Pause phonemes (_: _! _| _:: etc.) - inserted by eSpeak for punctuation

    This ensures scoring is based purely on pronunciation phonemes,
    not on text formatting artifacts like quotes, commas, periods.
    """
    import re
    if not s:
        return ""
    # Remove all whitespace
    s = re.sub(r"\s+", "", s.strip())
    # Remove eSpeak pause phonemes: _: _! _| _:: and combinations like _:_:
    # These are inserted for punctuation and should not affect pronunciation scoring
    s = re.sub(r'_[:!|]+', '', s)
    return s


def get_ipa(text: str, voice: str = "pt-br") -> str:
    """
    Get IPA transcription for text

    Note: eSpeak converts punctuation (commas, periods, etc.) into newlines
    in the IPA output. We normalize these to spaces for consistent comparison.
    """
    try:
        espeak_cmd = get_espeak_path()
        result = subprocess.run(
            [espeak_cmd, "-v", voice, "--ipa", "-q", text],
            capture_output=True,
            text=True,
            check=True
        )
        # Strip leading/trailing whitespace and normalize internal newlines to spaces
        # eSpeak inserts newlines at punctuation (commas, periods, etc.)
        ipa = result.stdout.strip()
        ipa = ' '.join(ipa.split())  # Replace all whitespace (including \n) with single space
        return ipa
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        st.warning(f"eSpeak IPA error: {e} (cmd: {get_espeak_path()})")
        return "[IPA unavailable]"


def format_ipa(ipa_text: str, size: str = "1.0em", weight: int = 400, brackets: bool = True) -> str:
    """
    Format IPA text with consistent delimiters and styling.

    Args:
        ipa_text: The IPA transcription text
        size: Font size (default "1.0em" for standard, "0.9em" for smaller)
        weight: Font weight (default 400 for normal, 300 for light)
        brackets: Whether to include square brackets (default True)

    Returns HTML-formatted IPA with consistent styling.
    Example: <span style="font-size: 1.0em; font-weight: 400;">[ipˈa]</span>
    """
    if not ipa_text:
        return ""

    # Remove any existing delimiters
    ipa_clean = ipa_text.strip().strip('[]/()')

    # Add brackets if requested
    display_text = f"[{ipa_clean}]" if brackets else ipa_clean

    # Return formatted HTML
    return f'<span style="font-size: {size}; font-weight: {weight}; font-family: \'Doulos SIL\', \'Charis SIL\', \'Gentium Plus\', \'DejaVu Sans\', sans-serif;">{display_text}</span>'


def speak_text(text: str, voice: str = "pt-br", speed: int = 160, pitch: int = 40) -> tuple[bytes, str]:
    """
    Generate speech using eSpeak NG (returns audio bytes, does not auto-play)

    Args:
        text: Text to speak
        voice: Voice/language code (e.g., 'pt-br', 'fr-fr', 'nl')
        speed: Speech speed in words per minute (80-450)
        pitch: Voice pitch (0-99)

    Returns:
        (audio_bytes, format) where format is 'audio/wav'
    """
    try:
        # Use --stdout to capture audio bytes instead of playing directly
        result = subprocess.run([
            get_espeak_path(),
            "-v", voice,
            "-s", str(speed),
            "-p", str(pitch),
            "--stdout",  # Output WAV to stdout instead of playing
            text
        ], capture_output=True, check=True)

        # Log API call (eSpeak is free/local but good to track usage)
        log_api_call(
            api_type="espeak",
            text=text,
            language=voice,
            char_count=len(text),
            audio_bytes=len(result.stdout),
            success=True,
            cached=False
        )

        return result.stdout, 'audio/wav'
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Return empty audio if espeak not available
        return b'', 'audio/wav'


@st.cache_data(ttl=86400)  # Cache for 24 hours (shared across all users!)
def speak_text_google_cloud(text: str, lang: str = "pt-BR", use_wav: bool = False, speaking_rate: float = 1.0) -> tuple[bytes, str]:
    """
    Generate speech using Google Cloud Text-to-Speech REST API with API key auth
    Returns tuple of (audio_bytes, format) for playback in Streamlit

    Cached for 24 hours and shared across all users to minimize API calls.
    Requires GOOGLE_CLOUD_TTS_API_KEY in Streamlit secrets.

    Uses REST API instead of client library because API key auth is simpler
    and doesn't require service account JSON credentials.

    Args:
        text: Text to speak
        lang: Language code (pt-BR, fr-FR, nl-NL, etc.)
        use_wav: If True, return as WAV format (LINEAR16)
        speaking_rate: Speech speed (0.25 to 4.0, default 1.0)

    Returns:
        (audio_bytes, format) where format is 'audio/mp3' or 'audio/wav'
    """
    import requests
    import json
    import base64

    # Get API key from secrets
    try:
        api_key = st.secrets["google_cloud_tts_api_key"]
    except KeyError:
        raise ValueError("google_cloud_tts_api_key not found in secrets")

    voice_name = GOOGLE_CLOUD_VOICES.get(lang, "pt-BR-Standard-A")
    audio_encoding = "LINEAR16" if use_wav else "MP3"

    # Build the REST API request
    url = "https://texttospeech.googleapis.com/v1/text:synthesize"
    headers = {
        "X-goog-api-key": api_key,
        "Content-Type": "application/json; charset=utf-8"
    }

    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": lang[:5],  # pt-BR, fr-FR, etc.
            "name": voice_name
        },
        "audioConfig": {
            "audioEncoding": audio_encoding,
            "speakingRate": speaking_rate
        }
    }

    # Make the API request
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        error_msg = f"Google Cloud TTS API error {response.status_code}: {response.text[:200]}"
        st.warning(f"⚠️ {error_msg}")
        raise Exception(error_msg)

    # Extract audio content from response (it's base64 encoded)
    response_data = response.json()
    audio_content_base64 = response_data.get("audioContent", "")
    audio_bytes = base64.b64decode(audio_content_base64)

    # Log API call for cost tracking
    log_api_call(
        api_type="google_cloud_tts",
        text=text,
        language=lang,
        char_count=len(text),
        audio_bytes=len(audio_bytes),
        success=True,
        cached=False  # This runs before cache check
    )

    # Return audio bytes and format
    format_str = 'audio/wav' if use_wav else 'audio/mp3'
    return audio_bytes, format_str


@st.cache_data(ttl=86400)  # Cache for 24 hours (shared across all users!)
def speak_text_gtts(text: str, lang: str = "pt-br", use_wav: bool = False, slow: bool = False) -> tuple[bytes, str]:
    """
    Generate speech using Google TTS (higher quality than eSpeak)
    Returns tuple of (audio_bytes, format) for playback in Streamlit

    Cached for 24 hours and shared across all users to minimize API calls.
    Once a phrase is generated, it's reused for everyone.

    Args:
        text: Text to speak
        lang: Language code (default pt-br)
        use_wav: If True, convert MP3 to WAV for iOS Safari compatibility
        slow: If True, speak at ~50% speed (Google TTS slow mode)

    Returns:
        (audio_bytes, format) where format is 'audio/mp3' or 'audio/wav'
    """
    # Use 'pt' for Portuguese (gTTS auto-detects Brazilian vs European)
    # or 'pt-br' specifically for Brazilian Portuguese
    tts = gTTS(text=text, lang=lang.replace('-br', ''), slow=slow)

    # Save to temporary file and read back
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
        mp3_path = fp.name
        tts.save(mp3_path)

        if use_wav:
            # Convert MP3 to WAV for iOS Safari compatibility
            wav_path = mp3_path.replace('.mp3', '.wav')

            # Run ffmpeg without capturing output to avoid pipe buffer deadlock
            result = subprocess.run(
                ['ffmpeg', '-i', mp3_path, '-acodec', 'pcm_s16le',
                 '-ar', '22050', '-y', wav_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            if result.returncode == 0:
                with open(wav_path, 'rb') as audio_file:
                    audio_bytes = audio_file.read()
                Path(wav_path).unlink()  # Clean up WAV
                Path(mp3_path).unlink()  # Clean up MP3
                return audio_bytes, 'audio/wav'
            else:
                # Conversion failed, fall back to MP3
                with open(mp3_path, 'rb') as audio_file:
                    audio_bytes = audio_file.read()
                Path(mp3_path).unlink()
                return audio_bytes, 'audio/mp3'
        else:
            # Return MP3
            with open(mp3_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
            Path(mp3_path).unlink()  # Clean up temp file

            # Log API call for cost tracking
            log_api_call(
                api_type="gtts",
                text=text,
                language=lang,
                char_count=len(text),
                audio_bytes=len(audio_bytes),
                success=True,
                cached=False
            )

            return audio_bytes, 'audio/mp3'


def generate_target_audio(text: str, settings: Dict) -> tuple[bytes, str]:
    """
    Generate target pronunciation audio using the configured TTS engine

    Args:
        text: Text to speak
        settings: User settings dict containing tts_engine, voice, speed, pitch, use_wav_audio

    Returns:
        (audio_bytes, format) where format is 'audio/mp3', 'audio/wav', or 'audio/x-wav'
    """
    # Remove punctuation to avoid comma/pause detection affecting scores
    import string
    text_no_punct = text.translate(str.maketrans('', '', string.punctuation))

    tts_engine = settings.get('tts_engine', 'google_cloud')  # Default to Google Cloud TTS

    # Smart fallback priority: Google Cloud TTS → gTTS → eSpeak
    # This ensures best quality audio with graceful degradation

    if tts_engine == 'espeak':
        # User explicitly chose eSpeak - use it directly
        return speak_text(
            text_no_punct,
            voice=settings.get('voice', 'pt-br'),
            speed=settings.get('speed', 140),
            pitch=settings.get('pitch', 35)
        )
    elif tts_engine == 'google_cloud':
        # Try Google Cloud TTS first (best quality)
        try:
            cloud_lang = VOICE_LOCALE_NORMALIZATION.get(settings.get('voice', 'pt-br'), 'pt-BR')

            return speak_text_google_cloud(
                text_no_punct,
                lang=cloud_lang,
                use_wav=settings.get('use_wav_audio', False),
                speaking_rate=1.0 if not settings.get('gtts_slow', False) else 0.75
            )
        except Exception as e:
            # Google Cloud TTS failed - try gTTS as fallback
            st.warning(f"⚠️ Google Cloud TTS unavailable, trying gTTS... ({str(e)[:80]})")
            try:
                return speak_text_gtts(
                    text_no_punct,
                    lang=settings.get('voice', 'pt-br'),
                    use_wav=settings.get('use_wav_audio', False),
                    slow=settings.get('gtts_slow', False)
                )
            except Exception as e2:
                # Both Google options failed - fall back to eSpeak
                st.warning("⚠️ All Google TTS options failed, using eSpeak NG")
                return speak_text(
                    text_no_punct,
                    voice=settings.get('voice', 'pt-br'),
                    speed=settings.get('speed', 140),
                    pitch=settings.get('pitch', 35)
                )
    else:
        # tts_engine is 'gtts' - but use smart fallback
        # Priority: Google Cloud → gTTS → eSpeak
        try:
            # Try Google Cloud first even if user selected gTTS (best quality)
            cloud_lang = VOICE_LOCALE_NORMALIZATION.get(settings.get('voice', 'pt-br'), 'pt-BR')

            return speak_text_google_cloud(
                text_no_punct,
                lang=cloud_lang,
                use_wav=settings.get('use_wav_audio', False),
                speaking_rate=1.0 if not settings.get('gtts_slow', False) else 0.75
            )
        except Exception:
            # Google Cloud not available - try gTTS as requested
            try:
                return speak_text_gtts(
                    text_no_punct,
                    lang=settings.get('voice', 'pt-br'),
                    use_wav=settings.get('use_wav_audio', False),
                    slow=settings.get('gtts_slow', False)
                )
            except Exception as e:
                # gTTS failed - fall back to eSpeak to preserve basic functionality
                st.warning(f"⚠️ Google TTS unavailable, using eSpeak NG instead. ({str(e)[:100]})")
                return speak_text(
                    text_no_punct,
                    voice=settings.get('voice', 'pt-br'),
                    speed=settings.get('speed', 140),
                    pitch=settings.get('pitch', 35)
                )


def transcribe_audio_whisper(audio_file: str, model, language_code: str = "pt"):
    """
    Transcribe audio to text using Whisper

    Args:
        audio_file: Path to audio file
        model: Whisper model instance
        language_code: Whisper language code (e.g., 'pt', 'fr', 'nl')

    Note: No initial_prompt is used to avoid biasing the transcription.
    We force language detection and use low temperature for consistency.
    """
    result = model.transcribe(
        audio=audio_file,
        language=language_code,  # Force language (ISO 639-1 code)
        task="transcribe",
        temperature=0.0,  # Deterministic output
        no_speech_threshold=0.6,  # Higher threshold to reject non-speech (like beeps)
        logprob_threshold=-1.0,   # Stricter on low-confidence segments
        condition_on_previous_text=False,  # Don't use context from previous segments
        word_timestamps=False,  # Disable word-level timestamps to reduce space insertion
        compression_ratio_threshold=2.4  # Default is 2.4, keep it strict
    )

    # Double-check detected language (Whisper should respect language parameter but doesn't always)
    detected_lang = result.get("language", "unknown")
    if detected_lang != language_code:
        # Log warning but continue (the transcription might still be correct)
        import warnings
        warnings.warn(f"Whisper detected language '{detected_lang}' instead of '{language_code}'")

    transcribed_text = result["text"].strip().lower()

    # CRITICAL: Detect hallucination - Whisper sometimes loops when audio is poor
    # Check for repetitive patterns like "é o que é o que é o que..."
    words = transcribed_text.split()
    if len(words) > 20:  # Only check longer transcriptions
        # Check if same 2-3 word pattern repeats many times
        # Look for patterns like "word1 word2" repeated 10+ times
        pattern_found = False
        for pattern_len in [2, 3, 4]:
            if len(words) >= pattern_len * 10:
                # Check if first pattern repeats throughout
                pattern = ' '.join(words[:pattern_len])
                repetitions = transcribed_text.count(pattern)
                if repetitions >= 10:  # Pattern repeats 10+ times
                    pattern_found = True
                    import warnings
                    warnings.warn(f"Whisper hallucination detected: '{pattern}' repeated {repetitions} times")
                    # Return truncated version to show the issue
                    return f"[hallucination detected: '{pattern}' x{repetitions}]"

        # Also check total word count - if way too long, it's probably hallucinating
        if len(words) > 100:
            import warnings
            warnings.warn(f"Suspiciously long transcription: {len(words)} words")
            return f"[error: transcription too long - {len(words)} words, possible hallucination]"

    return transcribed_text


def transcribe_audio_wav2vec2(audio_file: str, processor, model):
    """
    Transcribe audio to text using wav2vec2 Portuguese model
    """
    try:
        import torch
        import soundfile as sf

        # Load audio
        speech, sample_rate = sf.read(audio_file)

        # Resample if needed (wav2vec2 expects 16kHz)
        if sample_rate != 16000:
            import librosa
            speech = librosa.resample(speech, orig_sr=sample_rate, target_sr=16000)

        # Process
        inputs = processor(speech, sampling_rate=16000, return_tensors="pt", padding=True)

        with torch.no_grad():
            logits = model(inputs.input_values).logits

        predicted_ids = torch.argmax(logits, dim=-1)
        transcription = processor.batch_decode(predicted_ids)[0]

        return transcription.strip().lower()

    except Exception as e:
        st.error(f"wav2vec2 transcription failed: {e}")
        return ""


def transcribe_audio(audio_file: str, settings: Dict, language: str = "Portuguese"):
    """
    Transcribe audio using the selected ASR engine

    Args:
        audio_file: Path to audio file
        settings: App settings dict
        language: Selected language name (e.g., "Portuguese", "French")
    """
    asr_engine = settings.get('asr_engine', 'whisper')

    # Get language configuration
    lang_config = LANGUAGE_CONFIG[language]
    lang_code = lang_config['code']

    if asr_engine == 'wav2vec2':
        # wav2vec2 is Portuguese-only
        if lang_code != 'pt':
            st.warning("wav2vec2 only supports Portuguese, falling back to Whisper")
            asr_engine = 'whisper'
        else:
            processor, model = get_wav2vec2_model()
            if processor is None or model is None:
                st.warning("wav2vec2 unavailable, falling back to Whisper")
                asr_engine = 'whisper'
            else:
                return transcribe_audio_wav2vec2(audio_file, processor, model)

    # Default to Whisper
    model_size = settings.get('whisper_model_size', 'base')
    model = get_whisper_model(model_size)
    return transcribe_audio_whisper(audio_file, model, lang_code)


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein (edit) distance between two strings.
    Returns the minimum number of single-character edits (insertions, deletions, substitutions).
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def get_edit_operations(s1: str, s2: str):
    """
    Get the actual edit operations needed to transform s1 into s2.
    Returns a list of tuples: (operation, position, char1, char2)
    where operation is 'match', 'substitute', 'insert', or 'delete'
    """
    # Build the DP table
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(
                    dp[i-1][j],    # delete
                    dp[i][j-1],    # insert
                    dp[i-1][j-1]   # substitute
                )

    # Backtrack to find operations
    operations = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and s1[i-1] == s2[j-1]:
            operations.append(('match', i-1, s1[i-1], s2[j-1]))
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
            operations.append(('substitute', i-1, s1[i-1], s2[j-1]))
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j-1] + 1:
            operations.append(('insert', i, '-', s2[j-1]))
            j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + 1:
            operations.append(('delete', i-1, s1[i-1], '-'))
            i -= 1

    operations.reverse()
    return operations


def compare_phonemes_positional(user_phonemes: str, correct_phonemes: str):
    """
    DEPRECATED: Simple positional matching (fails with insertions/deletions).
    Kept for reference but not recommended for use.
    """
    exact_match = user_phonemes == correct_phonemes

    if len(correct_phonemes) == 0:
        similarity = 0.0
    else:
        matches = sum(
            1 for a, b in zip(user_phonemes, correct_phonemes)
            if a == b
        )
        similarity = matches / max(len(user_phonemes), len(correct_phonemes))

    return exact_match, similarity


def compare_phonemes_edit_distance(user_phonemes: str, correct_phonemes: str):
    """
    Compare phonemes using edit distance (Levenshtein).
    Handles insertions, deletions, and substitutions gracefully.

    Returns:
        exact_match: bool - True if strings are identical
        similarity: float - 0.0 to 1.0, where 1.0 is perfect match
        distance: int - Number of edits needed
    """
    exact_match = user_phonemes == correct_phonemes

    if len(correct_phonemes) == 0:
        return exact_match, 0.0, len(user_phonemes)

    distance = levenshtein_distance(user_phonemes, correct_phonemes)
    max_length = max(len(user_phonemes), len(correct_phonemes))

    # Similarity: 1.0 means perfect match, 0.0 means completely different
    similarity = 1.0 - (distance / max_length)

    return exact_match, similarity, distance


def compare_phonemes(user_phonemes: str, correct_phonemes: str, algorithm: str = "edit_distance"):
    """
    Modular phoneme comparison with selectable algorithms.

    Args:
        user_phonemes: Phonemes from user's speech
        correct_phonemes: Target phonemes
        algorithm: "edit_distance" (default) or "positional"

    Returns:
        exact_match: bool
        similarity: float (0.0 to 1.0)
        distance: int (only for edit_distance, None otherwise)
    """
    if algorithm == "edit_distance":
        return compare_phonemes_edit_distance(user_phonemes, correct_phonemes)
    elif algorithm == "positional":
        exact_match, similarity = compare_phonemes_positional(user_phonemes, correct_phonemes)
        return exact_match, similarity, None
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")


def practice_word_from_audio(text: str, audio_bytes: bytes, settings: Dict):
    """
    Practice a word/phrase using pre-recorded audio

    Logic:
    1. Transcribe audio to text (with proper spacing)
    2. Generate phonemes for both target and recognized text (preserving word boundaries)
    3. For comparison: strip spaces from phonemes only (not from text)
    4. This allows flexible matching while maintaining proper IPA display
    """
    try:
        # Save audio bytes to temporary file
        temp_audio = "temp_streamlit_recording.wav"
        with open(temp_audio, 'wb') as f:
            f.write(audio_bytes)

        # Preprocess audio: trim silence/noise from start and end
        # This helps remove system noise and other artifacts
        try:
            audio_data, sample_rate = sf.read(temp_audio)

            # Simple energy-based trimming
            # Calculate short-term energy
            frame_length = int(0.02 * sample_rate)  # 20ms frames
            energy = np.array([
                np.sum(audio_data[i:i+frame_length]**2)
                for i in range(0, len(audio_data) - frame_length, frame_length)
            ])

            # Find speech boundaries using user-configurable threshold
            # threshold is a percentage of max energy (default 0.01 = 1%)
            silence_threshold = settings.get('silence_threshold', 0.01)
            threshold = silence_threshold * np.max(energy)
            speech_frames = np.where(energy > threshold)[0]

            if len(speech_frames) > 0:
                # Add 200ms padding before and after to avoid speech artifacts
                padding_ms = 0.2  # 200ms as requested
                padding_samples = int(padding_ms * sample_rate)

                start_sample = max(0, speech_frames[0] * frame_length - padding_samples)
                end_sample = min(len(audio_data), (speech_frames[-1] + 1) * frame_length + padding_samples)

                trimmed_audio = audio_data[start_sample:end_sample]

                # Save trimmed audio
                sf.write(temp_audio, trimmed_audio, sample_rate)

                # Also save trimmed audio bytes for playback
                import io
                trimmed_buffer = io.BytesIO()
                sf.write(trimmed_buffer, trimmed_audio, sample_rate, format='WAV')
                trimmed_audio_bytes = trimmed_buffer.getvalue()
            else:
                trimmed_audio_bytes = audio_bytes
        except Exception as e:
            # If trimming fails, continue with original audio
            pass

        # Get correct pronunciation
        correct_phonemes = get_phonemes(text, settings['voice'])
        correct_ipa = get_ipa(text, settings['voice'])

        # Transcribe user's audio using selected ASR engine
        recognized_text = transcribe_audio(temp_audio, settings, st.session_state.language)

        # Get phonemes with proper spacing (for display)
        user_phonemes = get_phonemes(recognized_text, settings['voice'])
        user_ipa = get_ipa(recognized_text, settings['voice'])

        # For comparison: normalize by removing ALL whitespace from phoneme codes.
        # (eSpeak can emit newlines; remove them too to avoid phantom edit-distance penalties.)
        correct_phonemes_normalized = normalize_for_phoneme_scoring(correct_phonemes)
        user_phonemes_normalized = normalize_for_phoneme_scoring(user_phonemes)

        # Compare normalized phonemes (without spaces) using edit distance
        # Get algorithm from settings (default: edit_distance)
        algorithm = settings.get('comparison_algorithm', 'edit_distance')
        exact_match, similarity, edit_distance = compare_phonemes(
            user_phonemes_normalized,
            correct_phonemes_normalized,
            algorithm=algorithm
        )

        # Keep the original recording for playback
        # (Don't delete temp_audio - we'll save it in the result)

        result = {
            "target": text,
            "recognized": recognized_text,
            "correct_phonemes": correct_phonemes,
            "user_phonemes": user_phonemes,
            "correct_ipa": correct_ipa,
            "user_ipa": user_ipa,
            "exact_match": exact_match,
            "similarity": similarity,
            "edit_distance": edit_distance,
            "correct_phonemes_normalized": correct_phonemes_normalized,
            "user_phonemes_normalized": user_phonemes_normalized,
            "user_audio_bytes": audio_bytes,  # Original recording
            "user_audio_trimmed_bytes": trimmed_audio_bytes  # Trimmed version (what was actually recognized)
        }

        # Save to current session (exclude bytes for JSON serialization)
        session_data = {k: v for k, v in result.items() if k not in ["user_audio_bytes", "user_audio_trimmed_bytes"]}
        st.session_state.current_sessions[st.session_state.language]["practices"].append({
            "time": datetime.now().isoformat(),
            **session_data
        })
        st.session_state.session_saved = False
        # Note: last_result is now stored per-mode (quick_last_result, story_last_result) by the caller

        # Save to database immediately
        if st.session_state.get('authenticated', False):
            try:
                user_id = st.session_state['user']['user_id']
                app_mysql.save_practice(
                    user_id=user_id,
                    language_code=st.session_state.language,
                    target_phrase=result['target'],
                    recognized_phrase=result['recognized'],
                    similarity_score=result['similarity'],
                    perfect_match=result['exact_match'],
                    target_phonemes=result['correct_ipa'],
                    user_phonemes=result['user_ipa']
                )
            except Exception as e:
                st.warning(f"⚠️ Could not save to database: {e}")

        return result

    except Exception as e:
        st.error(f"Error during practice: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None


def save_current_session():
    """Save current session (for authenticated users, already saved to database)"""
    current_session = st.session_state.current_sessions[st.session_state.language]
    if current_session["practices"]:
        if st.session_state.get('authenticated', False):
            # For authenticated users, practices are already in database
            st.success("✓ All practices saved to your account!")
        else:
            # For non-authenticated users (shouldn't happen now), append to local history
            st.session_state.history.append(current_session)

        # Reset current session for this language
        st.session_state.current_sessions[st.session_state.language] = {
            "date": datetime.now().isoformat(),
            "practices": []
        }
        st.session_state.session_saved = True
        st.rerun()
    else:
        st.warning("No practices in current session to save")


def render_practice_interface(text, key_prefix="practice"):
    """
    Reusable practice interface component for audio playback, recording, and checking.

    Args:
        text: The phrase to practice
        key_prefix: Unique prefix for widget keys to avoid collisions (default: "practice")

    Returns:
        None (handles UI rendering and result storage in session state)
    """
    if not text:
        st.info("👆 Enter a word or phrase above to begin")
        return

    # Initialize mode-specific state variables
    audio_key_name = f"{key_prefix}_audio_input_key"
    if audio_key_name not in st.session_state:
        st.session_state[audio_key_name] = 0

    # Show target audio directly - one click to play
    st.write("🎯 **Target pronunciation:**")
    with st.spinner("Generating audio..."):
        audio_bytes, audio_format = generate_target_audio(
            text,
            st.session_state.settings
        )
        st.audio(audio_bytes, format=audio_format, autoplay=False)

    st.write("🎙️ **Now record your pronunciation:**")

    # Streamlit's built-in audio input with dynamic key (unique per mode)
    audio_data = st.audio_input("Click to record", key=f"{key_prefix}_audio_input_{st.session_state[audio_key_name]}")

    # Show recording tip after the recording widget (mobile-friendly)
    language_name = st.session_state.language
    st.info(f"💡 Wait for the recording icon to turn red before speaking. The app will automatically trim silence and enforce {language_name} language detection.")

    if audio_data:
        st.write("▶️ **Your recording:**")
        st.audio(audio_data, format='audio/wav')

        # Always show both buttons when recording exists - critical for UX
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✅ Check Pronunciation", key=f"{key_prefix}_submit_btn", type="primary"):
                with st.spinner("Processing..."):
                    result = practice_word_from_audio(
                        text,
                        audio_data.getvalue(),
                        st.session_state.settings
                    )
                    if result:
                        # Store result with mode-specific key
                        st.session_state[f"{key_prefix}_last_result"] = result
                        st.success("✓ Result processed successfully")
                    else:
                        st.error("❌ Processing failed - check terminal for errors")

        with col2:
            # CRITICAL: Always show Remove Recording button when audio exists
            if st.button("🗑️ Remove Recording", key=f"{key_prefix}_clear_btn"):
                # Clear the recording, results, and force widget reset
                st.session_state[f"{key_prefix}_last_result"] = None
                st.session_state[audio_key_name] += 1  # Change key to reset widget
                st.rerun()


def render_practice_results(result, key_prefix="practice"):
    """
    Reusable practice results display component.

    Args:
        result: Dictionary with practice results from practice_word_from_audio()
        key_prefix: Unique prefix for widget keys to avoid collisions (default: "practice")
    """
    if not result:
        return

    st.markdown("---")
    st.header("Results")

    # Play celebration sounds based on score (only once per result)
    import streamlit.components.v1 as components

    # Track if sound has been played for this result
    result_id = f"{result.get('target', '')}_{result.get('recognized', '')}_{result.get('similarity', 0)}"
    if 'last_sound_played' not in st.session_state:
        st.session_state.last_sound_played = None

    should_play_sound = st.session_state.last_sound_played != result_id

    if result["exact_match"]:
        st.success("🎉 PERFECT MATCH! Well done!")
        # Play perfect match bell sound (C major triad)
        if should_play_sound:
            st.session_state.last_sound_played = result_id
            components.html(
                """
                <script>
                (function () {
                    try {
                        const AudioContext = window.AudioContext || window.webkitAudioContext;
                        if (!AudioContext) return;
                        const ctx = new AudioContext();
                        const now = ctx.currentTime;
                        const freqs = [523.25, 659.25, 783.99]; // C5-E5-G5
                        const baseGain = 0.3;
                        const step = 0.15;
                        const dur = 0.6;

                        const play = () => {
                            freqs.forEach((freq, i) => {
                                const oscillator = ctx.createOscillator();
                                const gainNode = ctx.createGain();
                                oscillator.connect(gainNode);
                                gainNode.connect(ctx.destination);
                                oscillator.frequency.value = freq;
                                oscillator.type = 'sine';
                                gainNode.gain.setValueAtTime(baseGain, now + i * step);
                                gainNode.gain.exponentialRampToValueAtTime(0.01, now + i * step + dur);
                                oscillator.start(now + i * step);
                                oscillator.stop(now + i * step + dur);
                            });
                        };

                        if (ctx.resume) {
                            Promise.resolve(ctx.resume()).then(play).catch(() => {});
                        } else {
                            play();
                        }
                    } catch (e) {
                        // ignore
                    }
                })();
                </script>
                """,
                height=0,
            )
    elif result['similarity'] >= 0.90:
        # High score but not perfect: gentle encouraging sound
        st.success(f"✨ Excellent! {result['similarity']:.1%} - Almost perfect!")
        if should_play_sound:
            st.session_state.last_sound_played = result_id
            components.html(
                """
                <script>
                (function () {
                    try {
                        const AudioContext = window.AudioContext || window.webkitAudioContext;
                        if (!AudioContext) return;
                        const ctx = new AudioContext();
                        const now = ctx.currentTime;
                        const freqs = [440, 493.88, 523.25]; // A4-B4-C5
                        const baseGain = 0.15;
                        const step = 0.12;
                        const dur = 0.4;

                        const play = () => {
                            freqs.forEach((freq, i) => {
                                const oscillator = ctx.createOscillator();
                                const gainNode = ctx.createGain();
                                oscillator.connect(gainNode);
                                gainNode.connect(ctx.destination);
                                oscillator.frequency.value = freq;
                                oscillator.type = 'sine';
                                gainNode.gain.setValueAtTime(baseGain, now + i * step);
                                gainNode.gain.exponentialRampToValueAtTime(0.01, now + i * step + dur);
                                oscillator.start(now + i * step);
                                oscillator.stop(now + i * step + dur);
                            });
                        };

                        if (ctx.resume) {
                            Promise.resolve(ctx.resume()).then(play).catch(() => {});
                        } else {
                            play();
                        }
                    } catch (e) {
                        // ignore
                    }
                })();
                </script>
                """,
                height=0,
            )
    else:
        score_col1, score_col2 = st.columns([2, 1])
        with score_col1:
            st.info(f"📊 Score: {result['similarity']:.1%}")
        with score_col2:
            if result.get('edit_distance') is not None:
                st.metric("Edit Distance", result['edit_distance'],
                        help="Number of edits needed to match target")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Target")
        st.write(f"**Text:** {result['target']}")
        if result.get('correct_ipa'):
            st.markdown(f"**IPA:** {format_ipa(result['correct_ipa'])}", unsafe_allow_html=True)

        # Show target audio directly
        tts_label = "Google TTS" if st.session_state.settings.get('tts_engine', 'gtts') == 'gtts' else "eSpeak"
        st.write(f"🔊 **{tts_label}:**")
        audio_bytes, audio_format = generate_target_audio(result['target'], st.session_state.settings)
        st.audio(audio_bytes, format=audio_format)

    with col2:
        st.subheader("Your Pronunciation")
        st.write(f"**Recognized:** {result['recognized']}")
        if result.get('user_ipa'):
            st.markdown(f"**IPA:** {format_ipa(result['user_ipa'])}", unsafe_allow_html=True)

        # Show comparison note
        # Normalize text by removing punctuation for comparison
        import string
        target_clean = result['target'].lower().translate(str.maketrans('', '', string.punctuation))
        recognized_clean = result['recognized'].translate(str.maketrans('', '', string.punctuation))

        # Get normalized phonemes for comparison (the source of truth for pronunciation)
        correct_phonemes_no_space = result.get('correct_phonemes_normalized') or normalize_for_phoneme_scoring(result.get('correct_phonemes', ''))
        user_phonemes_no_space = result.get('user_phonemes_normalized') or normalize_for_phoneme_scoring(result.get('user_phonemes', ''))

        # Check if phonemes match (pronunciation is correct)
        phonemes_match = correct_phonemes_no_space == user_phonemes_no_space
        text_matches = target_clean == recognized_clean
        score_is_high = result['similarity'] >= 0.95

        # Display appropriate message based on phoneme match (source of truth)
        if phonemes_match:
            # Phonemes match perfectly - pronunciation is correct
            if not text_matches:
                st.success("✅ Perfect pronunciation! (Text punctuation/formatting differs)")
            else:
                st.success("✅ Phonemes match perfectly")
        elif score_is_high and not text_matches:
            # High score but text differs slightly
            st.info("ℹ️ Excellent pronunciation! (Minor text differences)")
        elif not text_matches and not score_is_high:
            # Both text and pronunciation differ - likely wrong word or unclear speech
            st.warning("⚠️ Different words recognized - try speaking more clearly")

    # Close the two-column layout before the detailed analysis
    # Show detailed phoneme analysis (works with edit distance!) - full width
    if st.checkbox("🔍 Show detailed phoneme analysis", key=f"{key_prefix}_show_detail"):
        st.markdown("---")

        st.markdown("#### Phoneme Analysis")
        st.write(f"**Algorithm:** {st.session_state.settings.get('comparison_algorithm', 'edit_distance')}")

        if result.get('edit_distance') is not None:
            st.write(f"**Edit Distance:** {result['edit_distance']} edit(s) needed")

        # Primary display: IPA (user-friendly)
        correct_ipa = result.get('correct_ipa', '') or ''
        user_ipa = result.get('user_ipa', '') or ''

        st.write("**IPA (from eSpeak, for readability):**")
        col_a, col_b = st.columns(2)
        with col_a:
            if correct_ipa:
                st.markdown(format_ipa(correct_ipa), unsafe_allow_html=True)
            else:
                st.write("(no IPA available)")
            st.caption("Target")
        with col_b:
            if user_ipa:
                st.markdown(format_ipa(user_ipa), unsafe_allow_html=True)
            else:
                st.write("(no IPA available)")
            st.caption("Your Pronunciation")

        # Comparison for display (whitespace ignored)
        target_ipa_no_space = "".join(correct_ipa.split())
        user_ipa_no_space = "".join(user_ipa.split())

        st.write("**Detailed IPA comparison (whitespace ignored):**")
        if target_ipa_no_space and target_ipa_no_space == user_ipa_no_space:
            st.success("🎯 IPA is identical!")
        elif target_ipa_no_space or user_ipa_no_space:
            from difflib import SequenceMatcher
            import html as _html

            def _colorize_diff(target: str, user: str) -> tuple[str, str]:
                # replace: light blue, insert: light green, delete: light pink.
                matcher_local = SequenceMatcher(None, target, user)
                target_chunks: list[str] = []
                user_chunks: list[str] = []

                for tag, i1, i2, j1, j2 in matcher_local.get_opcodes():
                    t_seg = target[i1:i2]
                    u_seg = user[j1:j2]

                    if tag == 'equal':
                        target_chunks.append(_html.escape(t_seg))
                        user_chunks.append(_html.escape(u_seg))
                    elif tag == 'replace':
                        target_chunks.append(f'<span style="background-color: #ADD8E6; padding: 0 2px;">{_html.escape(t_seg)}</span>')
                        user_chunks.append(f'<span style="background-color: #ADD8E6; padding: 0 2px;">{_html.escape(u_seg)}</span>')
                    elif tag == 'insert':
                        target_chunks.append(f'<span style="background-color: #90EE90; padding: 0 2px;">{_html.escape("·" * len(u_seg))}</span>')
                        user_chunks.append(f'<span style="background-color: #90EE90; padding: 0 2px;">{_html.escape(u_seg)}</span>')
                    elif tag == 'delete':
                        target_chunks.append(f'<span style="background-color: #FFB6C6; padding: 0 2px;">{_html.escape(t_seg)}</span>')
                        user_chunks.append(f'<span style="background-color: #FFB6C6; padding: 0 2px;">{_html.escape("·" * len(t_seg))}</span>')

                return ''.join(target_chunks), ''.join(user_chunks)

            matcher = SequenceMatcher(None, target_ipa_no_space, user_ipa_no_space)
            operations = matcher.get_opcodes()
            substitutions = [op for op in operations if op[0] == 'replace']
            insertions = [op for op in operations if op[0] == 'insert']
            deletions = [op for op in operations if op[0] == 'delete']
            matches = sum(i2 - i1 for tag, i1, i2, j1, j2 in operations if tag == 'equal')
            st.write(f"**Operations:** {matches} matches, {len(substitutions)} substitutions, {len(insertions)} insertions, {len(deletions)} deletions")

            target_html, user_html = _colorize_diff(target_ipa_no_space, user_ipa_no_space)
            mono_wrap_start = '<div style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \'Liberation Mono\', \'Courier New\', monospace; white-space: pre-wrap;">'
            mono_wrap_end = '</div>'

            col_t, col_u = st.columns(2)
            with col_t:
                st.markdown(mono_wrap_start + target_html + mono_wrap_end, unsafe_allow_html=True)
                st.caption("Target (normalized) - substitutions/insertions/deletions highlighted")
            with col_u:
                st.markdown(mono_wrap_start + user_html + mono_wrap_end, unsafe_allow_html=True)
                st.caption("Your Pronunciation (normalized) - substitutions/insertions/deletions highlighted")
        else:
            st.info("No IPA available for detailed comparison.")

        # Technical: show the eSpeak phoneme codes used for scoring
        with st.expander("Technical: eSpeak phoneme codes used for scoring", expanded=False):
            st.write("**eIPA (eSpeak -x) with word spacing:**")
            col_xa, col_xb = st.columns(2)
            with col_xa:
                st.code(result.get('correct_phonemes', ''), language=None)
                st.caption("Target")
            with col_xb:
                st.code(result.get('user_phonemes', ''), language=None)
                st.caption("Your Pronunciation")

            target_phonemes_no_space = result.get('correct_phonemes_normalized', '')
            user_phonemes_no_space = result.get('user_phonemes_normalized', '')
            st.write("**eIPA used for scoring (whitespace removed):**")
            col_n1, col_n2 = st.columns(2)
            with col_n1:
                st.code(target_phonemes_no_space, language=None)
                st.caption("Target (normalized)")
            with col_n2:
                st.code(user_phonemes_no_space, language=None)
                st.caption("Your Pronunciation (normalized)")


def render_scene_practice_mode(scenes_dir):
    """
    Story practice mode - practice pronunciation of story phrases scene by scene.

    Args:
        scenes_dir: Path to the directory containing scene JSON files
    """
    if not scenes_dir.exists():
        st.warning("Story scenes not found. Please ensure story-scenes-json/ exists.")
        return

    # Get all scene files
    scene_files = sorted(scenes_dir.glob("scene-*.json"))

    if not scene_files:
        st.warning("No scene files found in the story-scenes-json directory.")
        return

    # Initialize session state for story practice
    if 'story_practice_scene_file' not in st.session_state:
        st.session_state.story_practice_scene_file = str(scene_files[0])
    if 'story_practice_index' not in st.session_state:
        st.session_state.story_practice_index = 0

    # Create scene selector with friendly names
    scene_options = {}
    for scene_file in scene_files:
        # Extract scene number and title from filename
        parts = scene_file.stem.split('-', 2)
        if len(parts) >= 3:
            scene_num = parts[1]
            scene_title = parts[2].replace('-', ' ').title()
            display_name = f"Scene {scene_num}: {scene_title}"
        else:
            display_name = scene_file.stem

        scene_options[display_name] = str(scene_file)

    # Scene selector
    selected_scene_display = st.selectbox(
        "Select a scene to practice:",
        list(scene_options.keys()),
        index=list(scene_options.values()).index(st.session_state.story_practice_scene_file)
            if st.session_state.story_practice_scene_file in scene_options.values() else 0,
        help="Choose a scene from Sophie & Lucas's adventure",
        key="story_practice_scene_select"
    )

    selected_scene_path = scene_options[selected_scene_display]

    # If scene changed, reset index
    if selected_scene_path != st.session_state.story_practice_scene_file:
        st.session_state.story_practice_scene_file = selected_scene_path
        st.session_state.story_practice_index = 0
        st.session_state.story_last_result = None
        st.rerun()

    # Load the scene
    try:
        with open(selected_scene_path, 'r', encoding='utf-8') as f:
            scene_data = json.load(f)

        # All story scenes now use Format 2: {"lang": [...], "scene_number": 1, "scene_title": "..."}
        if not isinstance(scene_data, dict):
            st.error(f"Invalid scene format - expected dict, got {type(scene_data).__name__}")
            return

        # Get language key (pt, fr, de, nl, it, es)
        lang_keys = [k for k in scene_data.keys() if k not in ['scene_number', 'scene_title']]
        if not lang_keys:
            st.error("Invalid scene data - no language key found")
            return

        lang_key = lang_keys[0]
        phrases = scene_data[lang_key]

        if not phrases:
            st.warning("No phrases found in this scene.")
            return

        # Navigation and progress
        total_phrases = len(phrases)
        current_idx = st.session_state.story_practice_index

        # Keep index in bounds
        if current_idx >= total_phrases:
            st.session_state.story_practice_index = 0
            current_idx = 0

        current_phrase_obj = phrases[current_idx]
        current_phrase = current_phrase_obj.get(lang_key, '')
        phrase_translation = current_phrase_obj.get('english')
        phrase_ipa = current_phrase_obj.get('ipa')

        st.subheader(selected_scene_display)

        # Progress bar
        progress = (current_idx + 1) / total_phrases
        st.progress(progress, text=f"Phrase {current_idx + 1} of {total_phrases}")

        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("⬅️ Previous", disabled=(current_idx == 0), key="story_prev"):
                st.session_state.story_practice_index -= 1
                st.session_state.story_last_result = None
                st.rerun()
        with col2:
            if st.button("Next ➡️", disabled=(current_idx >= total_phrases - 1), key="story_next"):
                st.session_state.story_practice_index += 1
                st.session_state.story_last_result = None
                st.rerun()
        with col3:
            st.caption(f"💡 Navigate through {total_phrases} phrases in this scene")

        st.markdown("---")

        # Display current phrase
        if phrase_translation or phrase_ipa:
            with st.expander("📖 Translation & Reference", expanded=False):
                if phrase_translation:
                    st.markdown(f"**🇬🇧 English:** {phrase_translation}")
                if phrase_ipa:
                    st.markdown(f"**📚 Reference IPA:** {format_ipa(phrase_ipa)}", unsafe_allow_html=True)
                    st.caption("Compare with eSpeak IPA generated below")

        st.markdown(f"#### 🎯 **{current_phrase}**")

        # Practice interface with unique key prefix for story mode
        render_practice_interface(current_phrase, key_prefix="story")

        # Show results
        if st.session_state.get('story_last_result'):
            render_practice_results(st.session_state.story_last_result, key_prefix="story")

    except json.JSONDecodeError as e:
        st.error(f"Error parsing scene file: {e}")
    except Exception as e:
        st.error(f"Error loading scene: {e}")


def render_story_reader():
    """
    Story Reader tab - Read stories in various formats
    Modular design allows easy UX refactoring
    Language-aware: displays story for current target language
    """
    try:
        # Get material language from session state (affects story display)
        lang_code = st.session_state.get('material_language', 'fr')

        # Story titles and paths per language
        story_config = {
            'pt': {'title': 'Sophie & Lucas: Uma Jornada aos Alpes', 'setting': 'Brazil'},
            'fr': {'title': 'Sophie & Lucas: A Journey to the Alps', 'setting': 'French Alps'},
            'nl': {'title': 'Sophie & Lucas: Een Reis naar de Alpen', 'setting': 'Netherlands'},
            'de': {'title': 'Sophie & Lucas: Eine Reise in die Alpen', 'setting': 'Black Forest/Alps'},
            'it': {'title': 'Sophie & Lucas: Un Viaggio sulle Alpi', 'setting': 'Italian Dolomites'},
            'es': {'title': 'Sophie & Lucas: Un Viaje a Sierra Nevada', 'setting': 'Sierra Nevada, Spain'}
        }

        # Check if story materials exist for this language
        story_md_path = Path(f"language_materials/{lang_code}/story.md")
        story_scenes_dir = Path(f"language_materials/{lang_code}/story-scenes-json")

        config = story_config.get(lang_code, {'title': 'Story', 'setting': 'Unknown'})
        st.header(f"📖 {config['title']}")

        # Check what story materials are available
        has_full_story = story_md_path.exists()
        has_scenes = story_scenes_dir.exists() and list(story_scenes_dir.glob("scene-*.json"))

        if not has_full_story and not has_scenes:
            st.warning("Story materials not found. Please ensure story files exist for this language.")
            return

        # Story mode selector - show only available modes
        available_modes = []
        if has_full_story:
            available_modes.append("📄 Full Story")
        if has_scenes:
            available_modes.extend(["🎬 Scene by Scene", "🎙️ Practice Mode"])

        # Preserve story_mode across tab switches
        # Check if we have a saved preference
        saved_mode = st.session_state.get('_story_mode_preference')

        # Calculate index: use saved mode if it's still available, otherwise default to Scene by Scene
        default_idx = 0
        if saved_mode and saved_mode in available_modes:
            default_idx = available_modes.index(saved_mode)
        elif "🎬 Scene by Scene" in available_modes:
            default_idx = available_modes.index("🎬 Scene by Scene")

        story_mode = st.radio(
            "Choose reading mode:",
            available_modes,
            index=default_idx,
            horizontal=True,
            key='story_mode',
            help="Read the complete story, explore individual scenes, or practice pronunciation"
        )

        # Save preference for next time
        st.session_state._story_mode_preference = story_mode

        if story_mode == "📄 Full Story":
            render_full_story(story_md_path)
        elif story_mode == "🎬 Scene by Scene":
            render_scene_by_scene(story_scenes_dir, lang_code)
        elif story_mode == "🎙️ Practice Mode":
            render_scene_practice_mode(story_scenes_dir)

    except Exception as e:
        st.error(f"❌ Story Reader Error: {e}")
        import traceback
        st.error(f"```\n{traceback.format_exc()}\n```")


def render_full_story(story_path):
    """Render the complete story from markdown file"""
    try:
        with open(story_path, 'r', encoding='utf-8') as f:
            story_content = f.read()

        # Display the story
        st.markdown(story_content, unsafe_allow_html=False)

    except Exception as e:
        st.error(f"Error loading story: {e}")


def render_scene_by_scene(scenes_dir, lang_code):
    """Render individual scenes with target language text and English translations"""
    if not scenes_dir.exists():
        st.warning(f"Story scenes not found. Please ensure `language_materials/{lang_code}/story-scenes-json/` exists.")
        return

    # Get all scene files
    scene_files = sorted(scenes_dir.glob("scene-*.json"))

    if not scene_files:
        st.warning("No scene files found in the story-scenes-json directory.")
        return

    # Create scene selector with friendly names
    scene_options = {}
    for scene_file in scene_files:
        # Extract scene number and title from filename
        # e.g., "scene-01-le-café-du-matin.json" -> "Scene 1: Le Café du Matin"
        parts = scene_file.stem.split('-', 2)
        if len(parts) >= 3:
            scene_num = parts[1]
            scene_title = parts[2].replace('-', ' ').title()
            display_name = f"Scene {scene_num}: {scene_title}"
        else:
            display_name = scene_file.stem

        scene_options[display_name] = scene_file

    # Scene selector
    selected_scene = st.selectbox(
        "Select a scene to read:",
        list(scene_options.keys()),
        help="Choose a scene from Sophie & Lucas's adventure"
    )

    scene_file = scene_options[selected_scene]

    # Load and display the scene
    try:
        with open(scene_file, 'r', encoding='utf-8') as f:
            scene_data = json.load(f)

        # All story scenes now use Format 2: {"lang": [...], "scene_number": 1, "scene_title": "..."}
        if not isinstance(scene_data, dict):
            st.error(f"Invalid scene format - expected dict, got {type(scene_data).__name__}")
            return

        # Get language key (pt, fr, de, nl, it, es)
        lang_keys = [k for k in scene_data.keys() if k not in ['scene_number', 'scene_title']]
        if not lang_keys:
            st.error("Invalid scene data - no language key found")
            return

        lang_key = lang_keys[0]
        phrases = scene_data[lang_key]

        st.subheader(selected_scene)
        st.caption(f"📊 {len(phrases)} phrases in this scene")

        # Display options
        col1, col2 = st.columns([3, 1])
        with col1:
            show_translations = st.checkbox("Show English translations", value=False)
        with col2:
            show_ipa = st.checkbox("Show IPA", value=False)

        st.divider()

        # Display each phrase
        for i, phrase in enumerate(phrases, 1):
            # Get text in the target language (french, pt, etc.)
            target_text = phrase.get(lang_key, '')
            english_text = phrase.get('english', '[Translation missing]')
            ipa_text = phrase.get('ipa', '')

            # Target language text (always shown)
            st.markdown(f"**{i}.** {target_text}")

            # Optional: English translation
            if show_translations:
                st.markdown(f"   *{english_text}*")

            # Optional: IPA
            if show_ipa and ipa_text:
                st.markdown(f"   🔊 {format_ipa(ipa_text)}", unsafe_allow_html=True)

            # Add spacing between phrases
            if i < len(scene_data):
                st.markdown("")  # Small gap

        # Practice transition
        st.divider()
        st.info("✏️ **Ready to practice?** Go to the **🎯 Quick Practice** tab and load this scene from the Built-in Library → French → Story Scenes.")

    except json.JSONDecodeError as e:
        st.error(f"Error parsing scene file: {e}")
    except Exception as e:
        st.error(f"Error loading scene: {e}")


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

        # Material Language selection (already initialized above)
        st.markdown("**🌍 Language**")

        available_materials = get_available_languages()
        if available_materials:
            # Find current index from saved settings or existing session state
            current_idx = 0
            if 'material_language' in st.session_state:
                try:
                    current_idx = available_materials.index(st.session_state.material_language)
                except ValueError:
                    pass  # Invalid value, use default
            elif 'material_language' in st.session_state.settings:
                # First time - use saved language as default
                try:
                    current_idx = available_materials.index(st.session_state.settings['material_language'])
                except ValueError:
                    pass  # Invalid value, use default

            # Save previous value (use .get() to avoid AttributeError on first run)
            previous_material_language = st.session_state.get('material_language', None)
            st.selectbox(
                "Language",
                available_materials,
                index=current_idx,
                format_func=format_language_name,
                help="Language of practice materials and stories to display",
                key="material_language"  # Widget automatically updates st.session_state.material_language
            )

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
                if phrase_translation or phrase_ipa:
                    with st.expander("📖 Translation & Reference", expanded=False):
                        if phrase_translation:
                            st.markdown(f"**🇬🇧 English:** {phrase_translation}")
                        if phrase_ipa:
                            st.markdown(f"**📚 Reference IPA:** {format_ipa(phrase_ipa)}", unsafe_allow_html=True)
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

        # Use reusable practice interface with quick practice key prefix
        render_practice_interface(text, key_prefix="quick")

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

    # Tab 4: History
    elif selected_tab_index == 3:
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

    # CCS Testing: Extract app state after UI renders (if testing enabled)
    if CCS_AVAILABLE and st.session_state.ccs_test.enabled:
        st.session_state.ccs_test.extract_app_state_from_streamlit()


if __name__ == "__main__":
    main()
