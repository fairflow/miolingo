"""
Story tab UI: full story reader, scene-by-scene browser, and practice mode.

Extracted from app.py (Phase 4.2 of refactor).

Exports
-------
    render_story_reader()           — top-level Story Reader tab entry point
    render_full_story(story_path)   — render complete markdown story
    render_scene_by_scene(scenes_dir, lang_code)  — scene browser with translations
    render_scene_practice_mode(scenes_dir)         — pronunciation practice over scenes
"""

import json
import streamlit as st
from pathlib import Path

from app_language_materials import format_language_name
from scoring.phonemes import format_ipa
from translation import get_translation_from_llm
from ui.practice_tab import render_practice_interface, render_practice_results

# Unified materials directory
_UNIFIED_STORIES = Path(__file__).parent.parent.parent / "language_materials" / "unified" / "stories"


def _extract_scene_phrases(scene_data, lang_code, source_lang_code="en"):
    """Extract phrases from a scene JSON, handling both unified and legacy formats.

    Returns:
        list of {text, translation, ipa} dicts, scene_title str
    """
    # Unified format: {"meta": {...}, "phrases": [{text: {lang: ...}, ...}]}
    if 'meta' in scene_data and 'phrases' in scene_data:
        title = scene_data['meta'].get('scene_title', {}).get(lang_code, '')
        phrases = []
        for entry in scene_data['phrases']:
            target = entry.get('text', {}).get(lang_code)
            if not target:
                continue
            source = (entry.get('text', {}).get(source_lang_code)
                      or entry.get('text', {}).get('en', ''))
            ipa = entry.get('ipa', {}).get(lang_code, '')
            phrases.append({'text': target, 'translation': source, 'ipa': ipa or None})
        return phrases, title

    # Legacy format: {"lang_code": [...], "scene_number": N, "scene_title": "..."}
    lang_keys = [k for k in scene_data.keys() if k not in ('scene_number', 'scene_title')]
    if not lang_keys:
        return [], ''
    lang_key = lang_keys[0]
    raw = scene_data.get(lang_key, [])
    title = scene_data.get('scene_title', '')
    phrases = []
    for item in raw:
        phrases.append({
            'text': item.get(lang_key, ''),
            'translation': item.get('english', ''),
            'ipa': item.get('ipa'),
        })
    return phrases, title


@st.cache_data
def _scene_display_name(scene_file_str: str, lang_code: str) -> str:
    """Get a display name for a scene file, using JSON meta if available."""
    scene_file = Path(scene_file_str)
    parts = scene_file.stem.split('-', 2)
    scene_num = parts[1] if len(parts) >= 2 else '??'

    # Try reading title from JSON meta (unified files)
    try:
        with open(scene_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'meta' in data:
            titles = data['meta'].get('scene_title', {})
            title = titles.get(lang_code) or titles.get('en', '')
            if title:
                return f"Scene {scene_num}: {title}"
    except Exception:
        pass

    # Fallback: parse from filename
    if len(parts) >= 3:
        title = parts[2].replace('-', ' ').title()
        return f"Scene {scene_num}: {title}"
    return scene_file.stem


def _get_scene_files(lang_code):
    """Return sorted scene file paths, preferring unified over per-language.

    Returns:
        (scene_files list, is_unified bool)
    """
    if _UNIFIED_STORIES.is_dir():
        files = sorted(_UNIFIED_STORIES.glob("scene-*.json"))
        if files:
            return files, True
    legacy = Path(f"language_materials/{lang_code}/story-scenes-json")
    if legacy.is_dir():
        files = sorted(legacy.glob("scene-*.json"))
        if files:
            return files, False
    return [], False


# ---------------------------------------------------------------------------
# Scene practice mode
# ---------------------------------------------------------------------------

def render_scene_practice_mode(scenes_dir):
    """
    Story practice mode - practice pronunciation of story phrases scene by scene.

    Args:
        scenes_dir: Path to the directory containing scene JSON files (may be ignored
                    if unified scenes are available)
    """
    lang_code = st.session_state.get('material_language', 'fr')
    scene_files, is_unified = _get_scene_files(lang_code)

    if not scene_files:
        st.warning("No scene files found.")
        return

    # Initialize session state for story practice
    if 'story_practice_scene_file' not in st.session_state:
        st.session_state.story_practice_scene_file = str(scene_files[0])
    if 'story_practice_index' not in st.session_state:
        st.session_state.story_practice_index = 0

    # Create scene selector with friendly names
    scene_options = {}
    for scene_file in scene_files:
        display_name = _scene_display_name(str(scene_file), lang_code)
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

        from config import get_language_code
        source_lang_code = get_language_code(st.session_state.get('source_language', 'English'))
        phrases, _ = _extract_scene_phrases(scene_data, lang_code, source_lang_code)

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
        current_phrase = current_phrase_obj.get('text', '')
        phrase_translation = current_phrase_obj.get('translation')
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


# ---------------------------------------------------------------------------
# Story reader
# ---------------------------------------------------------------------------

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
        scene_files, is_unified = _get_scene_files(lang_code)
        story_scenes_dir = scene_files[0].parent if scene_files else Path(f"language_materials/{lang_code}/story-scenes-json")

        config = story_config.get(lang_code, {'title': 'Story', 'setting': 'Unknown'})
        st.header(f"📖 {config['title']}")

        # Check what story materials are available
        has_full_story = story_md_path.exists()
        has_scenes = bool(scene_files)

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
    scene_files, is_unified = _get_scene_files(lang_code)

    if not scene_files:
        st.warning("No scene files found.")
        return

    # Create scene selector with friendly names
    scene_options = {}
    for scene_file in scene_files:
        display_name = _scene_display_name(str(scene_file), lang_code)
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

        from config import get_language_code
        source_lang = st.session_state.get('source_language', 'English')
        source_lang_code = get_language_code(source_lang)
        phrases, scene_title = _extract_scene_phrases(scene_data, lang_code, source_lang_code)

        if not phrases:
            st.warning("No phrases found in this scene.")
            return

        st.subheader(selected_scene)
        st.caption(f"📊 {len(phrases)} phrases in this scene")

        # Display options
        col1, col2 = st.columns([3, 1])
        with col1:
            show_translations = st.checkbox(f"Show {source_lang} translations", value=False)
        with col2:
            show_ipa = st.checkbox("Show IPA", value=False)

        st.divider()

        # Display each phrase
        for i, phrase in enumerate(phrases, 1):
            target_text = phrase.get('text', '')
            translation_text = phrase.get('translation', '')

            # If no pre-stored translation and source isn't English, use LLM
            if not translation_text and source_lang != "English":
                target_lang = st.session_state.get('target_language', '')
                translation_text = get_translation_from_llm(target_text, target_lang, source_lang)

            ipa_text = phrase.get('ipa', '')

            # Target language text (always shown)
            st.markdown(f"**{i}.** {target_text}")

            # Optional: Source-language translation
            if show_translations and translation_text and not str(translation_text).startswith('[error'):
                st.markdown(f"   *{translation_text}*")

            # Optional: IPA
            if show_ipa and ipa_text:
                st.markdown(f"   🔊 {format_ipa(ipa_text)}", unsafe_allow_html=True)

            # Add spacing between phrases
            if i < len(phrases):
                st.markdown("")  # Small gap

        # Practice transition
        st.divider()
        lang_display = format_language_name(lang_code).split(' ', 1)[-1] if lang_code else 'French'
        st.info(f"✏️ **Ready to practice?** Go to the **🎯 Quick Practice** tab and load this scene from the Built-in Library → {lang_display} → Story Scenes.")

    except json.JSONDecodeError as e:
        st.error(f"Error parsing scene file: {e}")
    except Exception as e:
        st.error(f"Error loading scene: {e}")
