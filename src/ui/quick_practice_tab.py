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
from ui.sidebar import is_debug

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
        material_source_names = ["📦 Built-in Library", "📁 Upload File", "📚 Vocabulary"]
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
        elif material_source_index == 1:
            _render_upload_materials(format_language_name)
        else:
            _render_vocab_materials()


def _render_vocab_materials():
    """Load the user's personal vocab list as a practice phrase queue."""
    import vocab as vocab_mod

    if not st.session_state.get('authenticated', False):
        st.info("🔒 Sign in to practise from your personal vocabulary.")
        return

    from config import get_language_code
    language = st.session_state.get('language', 'Portuguese')
    source_language = st.session_state.get('source_language', 'English')
    source_language_code = get_language_code(source_language)
    user_id = st.session_state['user']['user_id']

    sort = st.selectbox(
        "Order",
        options=["alpha", "recent", "oldest"],
        format_func=lambda s: {
            "alpha": "Alphabetical",
            "recent": "Most recently added",
            "oldest": "Oldest first",
        }[s],
        key="qp_vocab_sort",
    )

    all_phrases = vocab_mod.vocab_as_practice_phrases(
        user_id=user_id,
        language=language,
        source_language_code=source_language_code,
        sort=sort,
    )
    st.caption(f"**{len(all_phrases)}** word(s) in your {language} vocabulary.")

    if not all_phrases:
        st.info(
            "No vocabulary for this language yet. Add some from the Story Reader, "
            "paste a passage, or upload a dictionary file (see the Vocabulary tab)."
        )
        return

    # Check for an active filter from the Vocabulary tab — lets the user practise
    # a filtered subset (e.g. only "ção$" endings) without re-typing the query here.
    # We read `vocab_search_active`, a persistent shadow of the Vocabulary tab's
    # search widget. Reading `vocab_search` directly would fail: Streamlit
    # garbage-collects widget-bound session_state keys when the widget unmounts,
    # so the filter disappears the moment the user switches tabs. The shadow is
    # maintained by vocabulary_tab.py whenever that tab renders.
    # Read from the persistent shadow first, fall back to the widget-bound key.
    # Observed on Streamlit 1.x: contrary to the "widget state is cleared on
    # unmount" documentation, the widget-bound key `vocab_search` actually
    # survives tab switches, while the shadow sometimes does not. Reading
    # either one that's present makes the cross-tab hand-off resilient to
    # whichever lifecycle behaviour the current Streamlit version exhibits.
    active_search = (
        st.session_state.get("vocab_search_active")
        or st.session_state.get("vocab_search")
        or ""
    ).strip()
    filtered_phrases: list = []
    filter_error: str = ""

    if active_search:
        import vocab_search
        try:
            filtered_phrases = vocab_mod.vocab_as_practice_phrases(
                user_id=user_id,
                language=language,
                source_language_code=source_language_code,
                sort=sort,
                search=active_search,
            )
        except vocab_search.QueryError as e:
            filter_error = str(e)

    if active_search:
        if filter_error:
            st.warning(
                f"🔎 Filter from Vocabulary tab (`{active_search}`) is invalid: "
                f"{filter_error}. Fix it on the Vocabulary tab, or load the full list below."
            )
        else:
            st.caption(
                f"🔎 Filter from Vocabulary tab: `{active_search}` "
                f"→ **{len(filtered_phrases)}** match(es)."
            )

    col_a, col_b = st.columns(2)
    with col_a:
        if active_search and not filter_error:
            disabled = len(filtered_phrases) == 0
            if st.button(
                f"🎯 Load filtered ({len(filtered_phrases)})",
                type="primary",
                key="load_vocab_filtered",
                disabled=disabled,
                use_container_width=True,
            ):
                st.session_state.phrase_list = filtered_phrases
                st.session_state.qp_phrase_position = 0
                st.session_state.quick_last_result = None
                st.session_state.material_source = (
                    f"Vocabulary ({language}, filter: {active_search})"
                )
                st.session_state.qp_materials_expanded = False
                st.rerun()
    with col_b:
        label = (
            f"📂 Load all ({len(all_phrases)})"
            if active_search
            else f"📂 Load vocabulary ({len(all_phrases)})"
        )
        if st.button(
            label,
            type="secondary" if active_search and not filter_error else "primary",
            key="load_vocab",
            use_container_width=True,
        ):
            st.session_state.phrase_list = all_phrases
            st.session_state.qp_phrase_position = 0
            st.session_state.quick_last_result = None
            st.session_state.material_source = f"Vocabulary ({language})"
            st.session_state.qp_materials_expanded = False
            st.rerun()

    # Minimal pairs practice option
    st.markdown("---")
    st.markdown("**🎓 IPA Ear Training: Minimal Pairs**")
    st.caption(
        "Practice word pairs that differ by exactly one sound — the gold standard "
        "for pronunciation training. Generated automatically from your vocabulary."
    )

    # Generate minimal pairs on demand
    minimal_pairs_count = 0
    minimal_pairs_phrases = []

    if len(all_phrases) >= 2:
        from ipa.minimal_pairs import generate_minimal_pair_practice_list
        from scoring.phonemes import get_phonemes
        from config import get_language_code

        # Enrich phrases with phonemes if needed
        lang_code = get_language_code(language)
        voice_map = {
            'Portuguese': 'pt-br',
            'French': 'fr-fr',
            'Dutch': 'nl',
            'German': 'de',
            'Italian': 'it',
            'Spanish': 'es',
            'English': 'en',
        }
        voice = voice_map.get(language, 'pt-br')

        vocab_with_phonemes = []
        for phrase in all_phrases:
            phrase_copy = dict(phrase)
            if 'phonemes' not in phrase_copy or not phrase_copy['phonemes']:
                # Generate phonemes on the fly
                phrase_copy['phonemes'] = get_phonemes(phrase['text'], voice=voice)
            vocab_with_phonemes.append(phrase_copy)

        minimal_pairs_phrases = generate_minimal_pair_practice_list(
            vocab_with_phonemes,
            max_pairs=20
        )
        minimal_pairs_count = len(minimal_pairs_phrases)

    if minimal_pairs_count > 0:
        if st.button(
            f"🎯 Load minimal pairs ({minimal_pairs_count})",
            type="secondary",
            key="load_minimal_pairs",
            use_container_width=True,
            help="Practice word pairs that sound almost identical"
        ):
            st.session_state.phrase_list = minimal_pairs_phrases
            st.session_state.qp_phrase_position = 0
            st.session_state.quick_last_result = None
            st.session_state.material_source = f"Minimal Pairs ({language})"
            st.session_state.qp_materials_expanded = False
            st.rerun()
    else:
        st.info(
            "No minimal pairs found. Add more vocabulary (at least 2 words) "
            "to generate minimal pair drills."
        )


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

    # Category and file selectors.
    # Explicit widget keys stabilise identity across reruns so a shape
    # change in `structure` (e.g. a category disappearing for a new
    # language) cannot silently void selectbox state. Stale values are
    # cleared before the widget reads session_state.
    categories = list(structure.keys())
    if st.session_state.get("qp_builtin_category") not in categories:
        st.session_state.pop("qp_builtin_category", None)
    category = st.selectbox(
        "Category",
        categories,
        format_func=format_category_name,
        help="Select difficulty level: Beginner (A) → Expert (D)",
        key="qp_builtin_category",
    )

    files = structure[category]
    # Stage 2 step 5: guard the empty-structure case explicitly. A
    # category that resolves to no files would otherwise hit
    # st.selectbox("File", []) — historically a source of exceptions
    # and downstream sidebar-state churn (the rerun unmounted the
    # sidebar's language widget, which then re-seeded from default).
    if not files:
        st.info(
            f"No files available in **{format_category_name(category)}** "
            f"for **{format_language_name(material_lang)}**. "
            "Pick another category, or check `language_materials/` "
            "for that language."
        )
        return
    if st.session_state.get("qp_builtin_file") not in files:
        st.session_state.pop("qp_builtin_file", None)
    selected_file = st.selectbox(
        "File",
        files,
        help="Select a specific file from this category",
        key="qp_builtin_file",
    )

    source_code = get_language_code(st.session_state.get('source_language', 'English'))
    metadata = get_file_metadata(material_lang, category, selected_file, source_code)

    if not metadata:
        st.error("Could not read file metadata")
        return

    if 'line_count' not in metadata:
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption(f"**Items:** {metadata.get('line_count', 0)}")
    with col2:
        st.caption(f"**Translations:** {'✓' if metadata.get('has_translations') else '✗'}")
    with col3:
        st.caption(f"**IPA:** {'✓' if metadata.get('has_ipa') else '✗'}")

    if metadata.get('preview'):
        with st.expander("Preview first 3 items"):
            for line in metadata['preview']:
                st.text(line)

    # Enrichment UI (not applicable for unified multi-language files)
    missing_translations = not metadata.get('has_translations')
    missing_ipa = not metadata.get('has_ipa')

    if (missing_translations or missing_ipa) and not category.startswith('unified-'):
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
            file_path_str = str(metadata['path'])
            if category.startswith('unified-'):
                from app_language_materials import load_unified_phrase_file
                target = st.session_state.get('material_language', 'fr')
                source = get_language_code(st.session_state.get('source_language', 'English'))
                phrases = load_unified_phrase_file(file_path_str, target, source)
            else:
                phrases = load_phrase_file(file_path_str)
            st.session_state.phrase_list = phrases
            st.session_state.qp_phrase_position = 0
            if is_debug(): st.session_state.state_change_log.append("Load builtin: Reset position to 0")
            st.session_state.quick_last_result = None
            st.session_state.material_source = f"{format_language_name(material_lang)} - {format_category_name(category)} - {selected_file}"
            st.session_state.qp_materials_expanded = False
            st.rerun()
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
            st.caption(f"**Phrases:** {len(phrases)}")
        with col2:
            st.caption(f"**Translations:** {'✓' if has_translations else '✗'}")
        with col3:
            st.caption(f"**IPA:** {'✓' if has_ipa else '✗'}")

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

        if is_debug():
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
                if is_debug(): st.session_state.state_change_log.append("Upload file: Reset position to 0")
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
                        if is_debug():
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
                        if is_debug():
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
            if is_debug(): st.session_state.state_change_log.append("Clear material: Reset position to 0")
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
        if is_debug(): st.session_state.state_change_log.append("Tab load: Bounded qp_phrase_position to 0 (was negative)")
    elif current_idx >= total_phrases:
        current_idx = total_phrases - 1 if total_phrases > 0 else 0
        st.session_state.qp_phrase_position = current_idx
        if is_debug(): st.session_state.state_change_log.append(f"Tab load: Bounded qp_phrase_position to {current_idx} (was >= {total_phrases})")

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

    def _reset_recorder():
        # Remount the st.audio_input widget so a stale blob / MediaRecorder
        # handle from the previous phrase can't surface as the generic
        # "An error occurred. Please try again." in-widget message.
        st.session_state["quick_audio_input_key"] = (
            st.session_state.get("quick_audio_input_key", 0) + 1
        )
        st.session_state["quick_last_result"] = None

    def _on_prev():
        st.session_state.qp_phrase_position -= 1
        st.session_state.phrase_selector_widget = st.session_state.qp_phrase_position
        _reset_recorder()
        if is_debug(): st.session_state.state_change_log.append(f"Prev button: qp_phrase_position → {st.session_state.qp_phrase_position}")

    def _on_next():
        st.session_state.qp_phrase_position += 1
        st.session_state.phrase_selector_widget = st.session_state.qp_phrase_position
        _reset_recorder()
        if is_debug(): st.session_state.state_change_log.append(f"Next button: qp_phrase_position → {st.session_state.qp_phrase_position}")

    with col1:
        st.button("⬅️ Previous", disabled=(current_idx == 0) or in_edit_mode,
                  key="nav_prev", on_click=_on_prev,
                  help="Navigation disabled in edit mode" if in_edit_mode else None)

    with col2:
        st.button("Next ➡️", disabled=(current_idx >= total_phrases - 1) or in_edit_mode,
                  key="nav_next", on_click=_on_next,
                  help="Navigation disabled in edit mode" if in_edit_mode else None)

    with col3:
        def format_phrase(i):
            phrase_obj = st.session_state.phrase_list[i]
            phrase_text = phrase_obj['text'] if isinstance(phrase_obj, dict) else phrase_obj
            preview = f"{i+1}. {phrase_text[:40]}{'...' if len(phrase_text) > 40 else ''}"
            return preview

        # Ensure widget state exists and is in bounds before selectbox renders
        if 'phrase_selector_widget' not in st.session_state:
            st.session_state.phrase_selector_widget = st.session_state.qp_phrase_position

        selected_pos = st.selectbox(
            "Jump to phrase:",
            options=range(total_phrases),
            format_func=format_phrase,
            key="phrase_selector_widget",
            disabled=in_edit_mode,
            help="Phrase navigation disabled in edit mode" if in_edit_mode else "Jump directly to any phrase"
        )
        # Detect user interaction with selectbox (no on_change — avoids callback conflicts)
        if selected_pos != st.session_state.qp_phrase_position:
            st.session_state.qp_phrase_position = selected_pos
            _reset_recorder()
            if is_debug(): st.session_state.state_change_log.append(f"Dropdown: qp_phrase_position → {selected_pos} (user selected)")
            st.rerun()

    with col4:
        if 'edit_mode' not in st.session_state:
            st.session_state.edit_mode = False
        if st.button("✏️ Edit", key="toggle_edit",
                     help="Edit current phrase or type your own",
                     disabled=st.session_state.edit_mode):
            st.session_state.edit_mode = True
            st.rerun()

    # State diagnostics expander — debug mode only
    if is_debug():
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
        is_minimal_pair = current_phrase_obj.get('minimal_pair', False) if isinstance(current_phrase_obj, dict) else False
        
        if source_lang == "English" and phrase_translation:
            translation_text = phrase_translation
        elif source_lang != target_lang:
            translation_text = get_translation_from_llm(current_phrase, target_lang, source_lang, secrets=st.secrets)

        if translation_text or phrase_ipa:
            with st.expander("📖 Translation & Reference", expanded=False):
                if translation_text and not translation_text.startswith('[error'):
                    # For minimal pairs, don't prefix with source language
                    if is_minimal_pair:
                        st.markdown(translation_text)
                    else:
                        st.markdown(f"**{source_lang}:** {translation_text}")
                if phrase_ipa:
                    st.markdown(f"**📚 Reference IPA ({target_lang}):** {format_ipa(phrase_ipa)}", unsafe_allow_html=True)
                    st.caption("Compare with eSpeak IPA generated below")
                    
                    # IPA learning tooltip — show key symbols for this language
                    from ipa.symbols import format_ipa_tooltip
                    target_code = st.session_state.get('material_language', 'fr')
                    tooltip_text = format_ipa_tooltip(target_code, max_symbols=5)
                    if tooltip_text and not tooltip_text.startswith('No quick reference'):
                        with st.expander("ℹ️ What's this? — IPA symbols explained"):
                            st.markdown(tooltip_text)

        st.markdown(f"#### 🎯 **{current_phrase}**")
        text = current_phrase

    return text


def _render_free_text_mode():
    """Render free-text practice UI with paired source/target fields.

    Two input fields, one for source language, one for target.  Typing in
    either triggers translation into the other.  Practice is always in the
    target language.

    Returns the target-language text to practise (empty string if nothing yet).
    """
    from config import MATERIAL_TO_TRAINING

    source = st.session_state.get("source_language", "English")
    target_code = st.session_state.get("material_language", "fr")
    target = MATERIAL_TO_TRAINING.get(target_code, target_code)

    # ------------------------------------------------------------------
    # Detect which field changed and translate BEFORE widgets render,
    # because Streamlit forbids setting widget keys after instantiation.
    # ------------------------------------------------------------------
    prev_source = st.session_state.get("_prev_source_text", "")
    prev_target = st.session_state.get("_prev_target_text", "")
    cur_source = st.session_state.get("free_source_text", "")
    cur_target = st.session_state.get("free_target_text", "")

    source_changed = cur_source != prev_source
    target_changed = cur_target != prev_target
    translation_error = None

    if source_changed and cur_source:
        translated = get_translation_from_llm(
            cur_source, source, target, secrets=st.secrets,
        )
        if translated and not translated.startswith('[error'):
            st.session_state.free_target_text = translated
            st.session_state._prev_target_text = translated
        else:
            translation_error = translated
        st.session_state._prev_source_text = cur_source

    elif target_changed and cur_target:
        translated = get_translation_from_llm(
            cur_target, target, source, secrets=st.secrets,
        )
        if translated and not translated.startswith('[error'):
            st.session_state.free_source_text = translated
            st.session_state._prev_source_text = translated
        else:
            translation_error = translated
        st.session_state._prev_target_text = cur_target

    # ------------------------------------------------------------------
    # Render the two input fields (they read from session state)
    # ------------------------------------------------------------------
    st.text_input(
        source,
        placeholder=f"Enter a word or phrase in {source}",
        key="free_source_text",
        label_visibility="collapsed",
    )
    st.text_input(
        target,
        placeholder=f"Enter a word or phrase in {target}",
        key="free_target_text",
        label_visibility="collapsed",
    )

    if translation_error:
        st.warning(f"Translation unavailable: {translation_error}")
        return ""

    practice_text = st.session_state.get("free_target_text", "")
    if not practice_text:
        return ""

    # Optional IPA
    show_ipa = st.checkbox("Show IPA", value=True, key="free_show_ipa")
    if show_ipa:
        ipa = get_ipa_from_espeak(practice_text, get_language_code(target))
        if ipa and not ipa.startswith('[error'):
            st.markdown(f"**IPA:** {format_ipa(ipa)}", unsafe_allow_html=True)

    return practice_text


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

    # Practice area first — quick to use without scrolling
    practice_text = _render_practice_area()

    # Reusable practice interface
    render_practice_interface(practice_text, key_prefix="quick")

    # Materials loader below the practice section
    _render_materials_loader()

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
