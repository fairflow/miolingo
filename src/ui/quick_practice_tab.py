"""
Quick Practice tab UI: material loading, guided/free-text practice.

Extracted from app.py (Phase 5 of refactor).

Exports
-------
    render_quick_practice_tab()  — top-level Quick Practice tab entry point
"""

import os
import tempfile
import time
from pathlib import Path

import streamlit as st

from audio.tts import speak_text
from scoring.phonemes import format_ipa, get_ipa_from_espeak
from translation import get_translation_from_llm
from translation import enrich_material_file
from config import get_language_code
from ui.practice_tab import render_practice_interface, render_practice_results

# True if local eSpeak build exists (development feature flag)
IS_LOCAL_DEV = os.path.exists('./local/bin/run-espeak-ng')


# ---------------------------------------------------------------------------
# Materials loader
# ---------------------------------------------------------------------------

def _render_materials_loader():
    """Render the 📚 Load Practice Materials expander (built-in + upload)."""
    from app_language_materials import (
        get_available_languages,
        get_language_structure,
        get_file_metadata,
        load_phrase_file,
        format_category_name,
        format_language_name,
    )

    if 'qp_materials_expanded' not in st.session_state:
        st.session_state.qp_materials_expanded = False

    with st.expander("📚 Load Practice Materials", expanded=st.session_state.qp_materials_expanded):
        st.session_state.qp_materials_expanded = True

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

        if material_source_index == 0:
            _render_builtin_materials(get_available_languages, get_language_structure,
                                      get_file_metadata, load_phrase_file,
                                      format_category_name, format_language_name)
        else:
            _render_upload_materials(format_language_name)


def _render_builtin_materials(get_available_languages, get_language_structure,
                               get_file_metadata, load_phrase_file,
                               format_category_name, format_language_name):
    """Render the Built-in Library sub-panel."""
    st.write("Browse curated phrase and word lists by language and level.")

    languages = get_available_languages()

    if not languages:
        st.warning("No built-in materials found in `language_materials/` directory.")
        return

    material_lang = st.session_state.get('material_language', 'fr')
    st.info(f"📚 Loading materials for: **{format_language_name(material_lang)}** (change in sidebar)")

    structure = get_language_structure(material_lang)

    if not structure:
        st.info(f"No materials found for {format_language_name(material_lang)}")
        return

    # Category and file selectors
    categories = list(structure.keys())
    category = st.selectbox(
        "Category",
        categories,
        format_func=format_category_name,
        help="Select difficulty level: Beginner (A) → Expert (D)"
    )

    files = structure[category]
    selected_file = st.selectbox(
        "File",
        files,
        help="Select a specific file from this category"
    )

    metadata = get_file_metadata(material_lang, category, selected_file)

    if not metadata:
        st.error("Could not read file metadata")
        return

    if 'line_count' not in metadata:
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Items", metadata.get('line_count', 0))
    with col2:
        st.metric("Translations", "✓" if metadata.get('has_translations') else "✗")
    with col3:
        st.metric("IPA", "✓" if metadata.get('has_ipa') else "✗")

    if metadata.get('preview'):
        with st.expander("Preview first 3 items"):
            for line in metadata['preview']:
                st.text(line)

    # Enrichment UI
    missing_translations = not metadata.get('has_translations')
    missing_ipa = not metadata.get('has_ipa')

    if missing_translations or missing_ipa:
        st.markdown("---")
        st.markdown("**✨ Enrich This Material**")

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
                progress_bar = st.progress(0)
                status_text = st.empty()

                def progress_callback(current, total, message):
                    progress = current / total if total > 0 else 0
                    progress_bar.progress(min(progress, 1.0))
                    status_text.text(message)

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
                    st.success("✅ Material enriched successfully!")

                    stat_col1, stat_col2, stat_col3 = st.columns(3)
                    with stat_col1:
                        st.metric("Lines processed", stats.get('total_lines', 0))
                    with stat_col2:
                        st.metric("Translations added", stats.get('translations_added', 0))
                    with stat_col3:
                        st.metric("IPA added", stats.get('ipa_added', 0))

                    if stats.get('errors'):
                        with st.expander(f"⚠️ {len(stats['errors'])} error(s) occurred"):
                            for error in stats['errors'][:10]:
                                st.text(error)

                    st.info("📝 Original file backed up to .bak. Click reload to see updated checkmarks.")

                    if st.button("🔄 Reload Metadata", key=f"reload_meta_{selected_file}"):
                        st.cache_data.clear()
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
            st.session_state.phrase_selector_widget = 0
            st.session_state.state_change_log.append("Load builtin: Reset position to 0")
            st.session_state.quick_last_result = None
            st.session_state.material_source = f"{format_language_name(material_lang)} - {format_category_name(category)} - {selected_file}"
            st.session_state.qp_materials_expanded = False
            st.success(f"✓ Loaded {len(phrases)} items - scroll down to practice section")
        except Exception as e:
            st.error(f"Error loading file: {e}")


def _render_upload_materials(format_language_name):
    """Render the Upload File sub-panel."""
    st.write("Upload your own phrase or word list.")
    st.caption("**Format:** One phrase per line, or `phrase | translation | [ipa]`")
    st.caption("**Limits:** Max 200 lines, 200 chars per line")

    MAX_UPLOAD_LINES = 200
    MAX_LINE_LENGTH = 200

    uploaded_file = st.file_uploader(
        "Choose a text file",
        type=['txt'],
        help="Upload a .txt file with one phrase per line. Empty lines and comments (#) are ignored."
    )

    if uploaded_file is None:
        return

    try:
        content = uploaded_file.read().decode('utf-8')

        upload_key = f"upload_{uploaded_file.name}_{uploaded_file.size}"
        if upload_key not in st.session_state:
            st.session_state[upload_key] = content
        else:
            content = st.session_state[upload_key]

        raw_lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]

        if len(raw_lines) > MAX_UPLOAD_LINES:
            st.error(f"❌ File too large: {len(raw_lines)} lines (max {MAX_UPLOAD_LINES})")
            st.stop()

        for i, line in enumerate(raw_lines, 1):
            phrase_part = line.split('|')[0].strip()
            if len(phrase_part) > MAX_LINE_LENGTH:
                st.error(f"❌ Line {i} too long: {len(phrase_part)} chars (max {MAX_LINE_LENGTH})")
                st.stop()

        # Parse phrases — support both simple and enhanced format
        phrases = []
        has_translations = False
        has_ipa = False

        for line in raw_lines:
            if line.startswith('#'):
                continue
            if '|' in line:
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
                phrases.append({'text': line, 'translation': None, 'ipa': None})

        st.success(f"✓ Loaded {len(phrases)} items from upload")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Phrases", len(phrases))
        with col2:
            st.metric("Translations", "✓" if has_translations else "✗")
        with col3:
            st.metric("IPA", "✓" if has_ipa else "✗")

        if st.session_state.get(f"{upload_key}_saved"):
            st.success("💾 Saved to server - showing saved version")

        with st.expander("📋 Preview", expanded=True):
            preview_count = min(5, len(phrases))
            for i, p in enumerate(phrases[:preview_count]):
                if p.get('translation') or p.get('ipa'):
                    translation = p.get('translation') or ''
                    ipa = p.get('ipa') or ''
                    st.text(f"{p['text']} | {translation} | {ipa}")
                else:
                    st.text(p['text'])
            if len(phrases) > preview_count:
                st.caption(f"...and {len(phrases) - preview_count} more")

        with st.expander("🔍 Raw File Content (first 5 lines)", expanded=False):
            st.caption("This shows the actual file content in session state:")
            raw_preview = [line for line in content.split('\n')[:5] if line.strip() and not line.strip().startswith('#')]
            for line in raw_preview:
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
                                with open(temp_path, 'r', encoding='utf-8') as f:
                                    enriched_content = f.read()

                                st.session_state[upload_key] = enriched_content

                                stats = result.get('stats', {})
                                st.success(f"✅ Enriched: {stats.get('translations_added', 0)} translations, {stats.get('ipa_added', 0)} IPA")

                                errors = stats.get('errors', [])
                                if errors:
                                    with st.expander(f"⚠️ {len(errors)} errors occurred", expanded=True):
                                        for err in errors[:20]:
                                            st.caption(err)
                                        if len(errors) > 20:
                                            st.caption(f"...and {len(errors) - 20} more")

                                first_lines = [line for line in enriched_content.split('\n')[:5]
                                               if line.strip() and not line.startswith('#')]
                                with st.expander("🔍 First enriched lines (actual file content)", expanded=True):
                                    st.caption("This shows what was actually written to the file:")
                                    for line in first_lines:
                                        st.code(line, language=None)

                                time.sleep(2)
                                st.info("🔄 Reloading with enriched content...")
                                st.rerun()
                            else:
                                st.error(f"❌ Enrichment failed: {result.get('error', 'Unknown error')}")
                                st.warning("💡 You can still save the original file")
                        finally:
                            try:
                                os.unlink(temp_path)
                            except Exception:
                                pass

        # Action buttons
        col1, col2 = st.columns(2)

        with col1:
            if st.button("✅ Use This File", type="primary", key="use_upload"):
                st.session_state.phrase_list = phrases
                st.session_state.qp_phrase_position = 0
                st.session_state.phrase_selector_widget = 0
                st.session_state.state_change_log.append("Upload file: Reset position to 0")
                st.session_state.quick_last_result = None
                st.session_state.material_source = f"Uploaded: {uploaded_file.name}"
                st.session_state.qp_materials_expanded = False
                st.success("✅ File loaded! Scroll down to practice section.")

        with col2:
            if st.session_state.get('authenticated'):
                if st.button("💾 Save to Server", key="save_upload"):
                    import remote_storage

                    user = st.session_state.get('user', {})
                    username = user.get('username', 'unknown')
                    current_lang = st.session_state.get('material_language', 'fr')
                    content_to_save = st.session_state.get(upload_key, content)

                    with st.spinner("Uploading to server..."):
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

                        try:
                            quota = remote_storage.get_user_quota(username)
                            st.info(f"📦 Your storage: {quota['used_mb']}/{quota['quota_mb']} MB used")
                        except Exception as e:
                            st.caption(f"⚠️ Could not check quota: {str(e)}")

                        st.session_state[f"{upload_key}_saved"] = True
                        st.success("🔄 File saved! Preview now shows server version.")
                        st.rerun()
                    else:
                        st.error(f"❌ Upload failed: {result.get('error', 'Unknown error')}")
                        if result.get('error'):
                            with st.expander("🔍 Error Details"):
                                st.code(result['error'])
            else:
                st.caption("💡 Login to save files to server")

    except Exception as e:
        st.error(f"Error reading file: {e}")


# ---------------------------------------------------------------------------
# Guided practice (list mode + free text mode)
# ---------------------------------------------------------------------------

def _render_practice_area():
    """Render the practice area: guided list mode or free text mode."""
    # Show current material source and clear button
    if 'phrase_list' in st.session_state and st.session_state.phrase_list:
        material_source = st.session_state.get('material_source', 'Unknown source')
        st.info(f"📚 **Current material:** {material_source}")

        if st.button("🗑️ Clear Material"):
            st.session_state.phrase_list = []
            st.session_state.qp_phrase_position = 0
            st.session_state.phrase_selector_widget = 0
            st.session_state.state_change_log.append("Clear material: Reset position to 0")
            st.session_state.quick_last_result = None
            st.session_state.material_source = None
            st.rerun()

    guided_mode = 'phrase_list' in st.session_state and st.session_state.phrase_list

    if guided_mode:
        text = _render_guided_mode()
    else:
        text = _render_free_text_mode()

    return text


def _render_guided_mode():
    """Render guided list practice UI; returns the current practice text."""
    st.markdown("---")
    st.subheader("📚 Guided Practice Mode")

    total_phrases = len(st.session_state.phrase_list)
    current_idx = st.session_state.qp_phrase_position

    # Keep index in bounds
    if current_idx < 0:
        current_idx = 0
        st.session_state.qp_phrase_position = 0
        st.session_state.state_change_log.append("Tab load: Bounded qp_phrase_position to 0 (was negative)")
    elif current_idx >= total_phrases:
        current_idx = total_phrases - 1 if total_phrases > 0 else 0
        st.session_state.qp_phrase_position = current_idx
        st.session_state.state_change_log.append(f"Tab load: Bounded qp_phrase_position to {current_idx} (was >= {total_phrases})")

    current_phrase_obj = st.session_state.phrase_list[current_idx]
    if isinstance(current_phrase_obj, dict):
        current_phrase = current_phrase_obj['text']
        phrase_translation = current_phrase_obj.get('translation')
        phrase_ipa = current_phrase_obj.get('ipa')
    else:
        current_phrase = current_phrase_obj
        phrase_translation = None
        phrase_ipa = None

    # Phrase-change feedback
    if 'last_phrase_index' not in st.session_state:
        st.session_state.last_phrase_index = current_idx
    if st.session_state.last_phrase_index != current_idx:
        st.success(f"✓ Moved to phrase #{current_idx + 1}")
        st.session_state.last_phrase_index = current_idx

    # Progress bar
    st.progress((current_idx + 1) / total_phrases, text=f"Phrase {current_idx + 1} of {total_phrases}")

    # Navigation
    in_edit_mode = st.session_state.get('edit_mode', False)
    col1, col2, col3, col4 = st.columns([1, 1, 2, 1])

    with col1:
        if st.button("⬅️ Previous", disabled=(current_idx == 0) or in_edit_mode,
                     key="nav_prev",
                     help="Navigation disabled in edit mode" if in_edit_mode else None):
            st.session_state.qp_phrase_position -= 1
            st.session_state.phrase_selector_widget = st.session_state.qp_phrase_position
            st.session_state.state_change_log.append(f"Prev button: qp_phrase_position → {st.session_state.qp_phrase_position}")
            st.rerun()

    with col2:
        if st.button("Next ➡️", disabled=(current_idx >= total_phrases - 1) or in_edit_mode,
                     key="nav_next",
                     help="Navigation disabled in edit mode" if in_edit_mode else None):
            st.session_state.qp_phrase_position += 1
            st.session_state.phrase_selector_widget = st.session_state.qp_phrase_position
            st.session_state.state_change_log.append(f"Next button: qp_phrase_position → {st.session_state.qp_phrase_position}")
            st.rerun()

    with col3:
        def format_phrase(i):
            phrase_obj = st.session_state.phrase_list[i]
            phrase_text = phrase_obj['text'] if isinstance(phrase_obj, dict) else phrase_obj
            preview = f"{i+1}. {phrase_text[:40]}{'...' if len(phrase_text) > 40 else ''}"
            return preview

        def on_phrase_select():
            new_pos = st.session_state.phrase_selector_widget
            st.session_state.qp_phrase_position = new_pos
            st.session_state.state_change_log.append(f"Dropdown: qp_phrase_position → {new_pos} (user selected)")

        st.selectbox(
            "Jump to phrase:",
            options=range(total_phrases),
            index=st.session_state.qp_phrase_position,
            format_func=format_phrase,
            key="phrase_selector_widget",
            on_change=on_phrase_select,
            disabled=in_edit_mode,
            help="Phrase navigation disabled in edit mode" if in_edit_mode else "Jump directly to any phrase"
        )

    with col4:
        if 'edit_mode' not in st.session_state:
            st.session_state.edit_mode = False
        if st.button("✏️ Edit", key="toggle_edit",
                     help="Edit current phrase or type your own",
                     disabled=st.session_state.edit_mode):
            st.session_state.edit_mode = True
            st.rerun()

    # State diagnostics expander
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

    # Phrase display — editable or fixed
    if st.session_state.edit_mode:
        st.markdown("### ✏️ Edit Mode:")
        st.caption("Edit the phrase below or type something completely different")
        text = st.text_input("Phrase to practice:", value=current_phrase, key="edit_phrase_input")
        if st.button("📚 Return to Guided Mode", key="back_to_guided"):
            st.session_state.edit_mode = False
            st.rerun()
    else:
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

        st.markdown(f"#### 🎯 **{current_phrase}**")
        text = current_phrase

    return text


def _render_free_text_mode():
    """Render free-text practice UI; returns the entered text."""
    source = st.session_state.get("source_language", "English")
    target_code = st.session_state.get("material_language", "fr")
    from config import MATERIAL_TO_TRAINING
    target = MATERIAL_TO_TRAINING.get(target_code, target_code)

    st.write(f"Enter a word or phrase in **{source}** to practise in **{target}**")

    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        st.button("⬅️ Previous", disabled=True, key="nav_prev_disabled",
                  help="Navigation only available in guided mode")
    with col2:
        st.button("Next ➡️", disabled=True, key="nav_next_disabled",
                  help="Navigation only available in guided mode")
    with col3:
        st.write("")

    st.markdown("---")
    return st.text_input(
        f"Enter word or phrase ({source} → {target}):",
        key="practice_text_free",
    )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def render_quick_practice_tab():
    """Render the Quick Practice tab."""
    st.header("Quick Practice")

    # Help info for new users
    current_session = st.session_state.current_sessions[st.session_state.language]
    if len(current_session["practices"]) == 0:
        st.info("👋 **New here?** Check the [User Guide](https://github.com/fairflow/miolingo/blob/feature/admin-fusion/docs/app-docs/USER_GUIDE.md) for step-by-step instructions!")

    _render_materials_loader()

    text = _render_practice_area()

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

    # Show translation + IPA reference for free text mode
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

    # Reusable practice interface
    render_practice_interface(practice_text, key_prefix="quick")

    # Show last result
    if st.session_state.get('quick_last_result'):
        render_practice_results(st.session_state.quick_last_result, key_prefix="quick")

        # Local dev: hear eSpeak phoneme pronunciation
        if IS_LOCAL_DEV and not st.session_state.quick_last_result["exact_match"]:
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
