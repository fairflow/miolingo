"""
Vocabulary tab — per-user, per-language personal dictionary (F2).

Capture routes wired in this tab:
  - Paste a passage, then type a word to capture from it (source = label)
  - Bulk upload a pipe-delimited dictionary file (word | source | context | url)
Capture from Story Reader and Quick Practice hooks into `vocab.capture_vocab_entry`
directly; this tab is the view layer + paste/upload routes + export.
"""

from __future__ import annotations

import csv
import io
from typing import List

import streamlit as st

import vocab
from audio.tts import generate_target_audio


def _current_language() -> str:
    return st.session_state.get("language", "Portuguese")


def _source_language() -> str:
    return st.session_state.get("source_language", "English")


def _require_auth() -> bool:
    if not st.session_state.get("authenticated", False):
        st.info("🔒 Sign in to use the personal vocabulary tracker.")
        return False
    if "user" not in st.session_state or "user_id" not in st.session_state["user"]:
        st.warning("Could not resolve your user id — try signing in again.")
        return False
    return True


def _user_id() -> int:
    return st.session_state["user"]["user_id"]


def _capture_from_passage(passage: str, word: str, source_label: str, url: str = "") -> dict:
    """Capture a single word from a pasted passage, pulling ±2 lines of context."""
    lines = [ln for ln in passage.splitlines() if ln.strip()]
    lower_word = word.strip().lower()
    idx = next(
        (i for i, ln in enumerate(lines) if lower_word in ln.lower()),
        None,
    )
    context_before = context_line = context_after = ""
    if idx is not None:
        context_line = lines[idx]
        context_before = "\n".join(lines[max(0, idx - 2):idx])
        context_after = "\n".join(lines[idx + 1:idx + 3])

    return vocab.capture_vocab_entry(
        user_id=_user_id(),
        language=_current_language(),
        word=word,
        source_name=source_label or "(pasted)",
        context_before=context_before,
        context_line=context_line,
        context_after=context_after,
        url=url or None,
        enrich=True,
        source_language=_source_language(),
        secrets=st.secrets if hasattr(st, "secrets") else None,
    )


def _render_paste_capture():
    with st.expander("✍️ Paste a passage and add a word", expanded=False):
        passage = st.text_area(
            "Paste source text (poem, passage, paragraph)",
            key="vocab_paste_passage",
            height=140,
        )
        col1, col2 = st.columns([2, 3])
        with col1:
            word = st.text_input("Word to add", key="vocab_paste_word")
        with col2:
            source_label = st.text_input(
                "Source label (e.g. poem title)",
                key="vocab_paste_source",
                placeholder="(pasted)",
            )
        url = st.text_input(
            "Source URL (optional)",
            key="vocab_paste_url",
            placeholder="https://…",
        )
        if st.button("➕ Add from passage", key="vocab_paste_btn", type="primary"):
            if not word.strip():
                st.warning("Type a word to add.")
            else:
                r = _capture_from_passage(passage, word, source_label, url)
                if r["ok"]:
                    st.success(
                        f"✅ {r['message'].capitalize()}: **{word}** "
                        f"({'new entry' if r['created'] else 'already in your vocab'})"
                    )
                else:
                    st.error(f"⚠️ {r['message']}")


def _render_bulk_upload():
    with st.expander("📥 Upload a dictionary file", expanded=False):
        st.caption(
            "Pipe-delimited `.txt`: `word | translation | ipa | source | url` — one entry per line. "
            "Only word is required. Use `||` to skip a field while keeping later ones in position "
            "(e.g. `word || [atˈɛ] | src`). IPA brackets `[]` are stripped automatically. "
            "Lines starting with `#` are ignored; multi-word entries are skipped."
        )
        uploaded = st.file_uploader(
            "Upload .txt",
            type=["txt"],
            key="vocab_bulk_upload",
        )
        enrich = st.checkbox(
            "Auto-fetch missing translation + IPA on import",
            value=True,
            key="vocab_bulk_enrich",
            help="Fills any blank translation/IPA via LLM + eSpeak. Skipped if the file already has those fields.",
        )
        _over_limit = False
        if uploaded is not None:
            try:
                contents = uploaded.getvalue().decode("utf-8")
            except UnicodeDecodeError:
                st.error("File is not UTF-8 encoded.")
                return
            n_lines = vocab.count_import_lines(contents)
            if n_lines > vocab.IMPORT_LINE_LIMIT:
                st.error(
                    f"⚠️ File has **{n_lines}** words — maximum is "
                    f"**{vocab.IMPORT_LINE_LIMIT}**. Split into smaller files and import separately."
                )
                _over_limit = True
            else:
                est = f" (~{n_lines * 2}–{n_lines * 4}s if enrichment needed)" if enrich and n_lines > 10 else ""
                st.caption(f"{n_lines} words to import{est}.")

        if uploaded is not None and not _over_limit and st.button(
            "Import file", key="vocab_bulk_btn", type="primary"
        ):
            progress_bar = st.progress(0, text="Importing…")

            def _progress(done, total):
                pct = done / total if total else 1
                progress_bar.progress(pct, text=f"Importing… {done}/{total}")

            summary = vocab.import_from_file_contents(
                user_id=_user_id(),
                language=_current_language(),
                contents=contents,
                enrich=enrich,
                source_language=_source_language(),
                secrets=st.secrets if hasattr(st, "secrets") else None,
                progress_fn=_progress,
            )
            progress_bar.empty()
            st.success(
                f"✅ Imported — {summary['added']} new, "
                f"{summary['updated']} updated."
            )
            if summary["skipped_not_single"]:
                st.warning(
                    f"⚠️ {len(summary['skipped_not_single'])} multi-word rows skipped: "
                    + ", ".join(f"`{w}`" for w in summary["skipped_not_single"][:10])
                )
            if summary["skipped_other"]:
                st.warning(
                    f"⚠️ {len(summary['skipped_other'])} other rows skipped."
                )


def _render_export_csv(rows: List[dict]):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "word", "translation", "ipa", "source",
        "context_before", "context_line", "context_after",
        "times_seen", "first_seen_at", "last_seen_at", "notes", "url",
    ])
    for r in rows:
        writer.writerow([
            r.get("display_word", r.get("word", "")),
            r.get("translation") or "",
            r.get("ipa") or "",
            r.get("source_name") or "",
            r.get("context_before") or "",
            r.get("context_line") or "",
            r.get("context_after") or "",
            r.get("times_seen", 1),
            r.get("first_seen_at") or "",
            r.get("last_seen_at") or "",
            r.get("notes") or "",
            r.get("url") or "",
        ])
    st.download_button(
        "⬇️ Export CSV",
        data=buf.getvalue(),
        file_name=f"vocab_{_current_language()}.csv",
        mime="text/csv",
        key="vocab_export_csv",
    )


_EDIT_FIELDS = (
    "display_word", "translation", "ipa", "source_name", "url",
    "context_before", "context_line", "context_after",
)


def _clear_edit_state(vocab_id: int) -> None:
    """Drop the editing flag + all per-field widget keys for one entry."""
    st.session_state.pop(f"vocab_editing_{vocab_id}", None)
    for field in _EDIT_FIELDS:
        st.session_state.pop(f"vocab_edit_{field}_{vocab_id}", None)


def _prune_stale_session_keys(rows: list) -> None:
    """Drop vocab_editing_* / vocab_notes_* / vocab_edit_*_<id> keys whose
    vocab_id is no longer in the current result set. Prevents a slow leak
    of orphan widget state after deletes, and cross-user leaks after logout.
    """
    live_ids = {str(r["vocab_id"]) for r in rows}
    stale: list = []
    for key in st.session_state.keys():
        for prefix in ("vocab_editing_", "vocab_notes_", "vocab_save_"):
            if key.startswith(prefix):
                if key[len(prefix):] not in live_ids:
                    stale.append(key)
                break
        else:
            if key.startswith("vocab_edit_"):
                # key form: vocab_edit_<field>_<vocab_id>
                vid = key.rsplit("_", 1)[-1]
                if vid.isdigit() and vid not in live_ids:
                    stale.append(key)
    for key in stale:
        st.session_state.pop(key, None)


def _render_entry_edit_form(row: dict) -> None:
    """Inline edit form — seven editable text fields + Save / Cancel."""
    vocab_id = row["vocab_id"]

    st.markdown("**Edit entry**")
    c1, c2 = st.columns(2)
    with c1:
        display_word = st.text_input(
            "Word (casing only — lookup key is immutable)",
            value=row.get("display_word") or "",
            key=f"vocab_edit_display_word_{vocab_id}",
        )
        translation = st.text_input(
            "Translation",
            value=row.get("translation") or "",
            key=f"vocab_edit_translation_{vocab_id}",
        )
    with c2:
        ipa = st.text_input(
            "IPA",
            value=row.get("ipa") or "",
            key=f"vocab_edit_ipa_{vocab_id}",
        )
        source_name = st.text_input(
            "Source",
            value=row.get("source_name") or "",
            key=f"vocab_edit_source_name_{vocab_id}",
        )

    url = st.text_input(
        "URL",
        value=row.get("url") or "",
        key=f"vocab_edit_url_{vocab_id}",
        placeholder="https://…",
    )
    context_before = st.text_area(
        "Context before",
        value=row.get("context_before") or "",
        key=f"vocab_edit_context_before_{vocab_id}",
        height=60,
    )
    context_line = st.text_area(
        "Context line",
        value=row.get("context_line") or "",
        key=f"vocab_edit_context_line_{vocab_id}",
        height=60,
    )
    context_after = st.text_area(
        "Context after",
        value=row.get("context_after") or "",
        key=f"vocab_edit_context_after_{vocab_id}",
        height=60,
    )

    bcol1, bcol2, _ = st.columns([1, 1, 4])
    with bcol1:
        save_clicked = st.button(
            "💾 Save", key=f"vocab_edit_save_{vocab_id}", type="primary"
        )
    with bcol2:
        cancel_clicked = st.button(
            "✖ Cancel", key=f"vocab_edit_cancel_{vocab_id}"
        )

    if cancel_clicked:
        _clear_edit_state(vocab_id)
        st.rerun()

    if save_clicked:
        fields = {
            "display_word":   display_word,
            "translation":    translation,
            "ipa":            ipa,
            "source_name":    source_name,
            "url":            url,
            "context_before": context_before,
            "context_line":   context_line,
            "context_after":  context_after,
        }
        try:
            ok = vocab.update_vocab_entry(
                user_id=_user_id(), vocab_id=vocab_id, **fields
            )
        except ValueError as e:
            st.error(f"⚠️ {e}")
            return
        if ok:
            _clear_edit_state(vocab_id)
            st.success("Saved.")
            st.rerun()
        else:
            st.error("Could not save — entry no longer exists.")


def _render_entry_row(row: dict):
    # Summary line: word · translation · IPA · source · date
    summary_bits = [f"**{row['display_word']}**"]
    if row.get("translation"):
        summary_bits.append(f"_{row['translation']}_")
    if row.get("ipa"):
        summary_bits.append(f"`{row['ipa']}`")
    summary_bits.append(f"· {row.get('source_name') or '—'}")
    summary_bits.append(f"· {str(row.get('last_seen_at') or '')[:16]}")

    vocab_id = row["vocab_id"]
    editing = st.session_state.get(f"vocab_editing_{vocab_id}", False)

    with st.expander(" ".join(summary_bits), expanded=editing):
        if editing:
            _render_entry_edit_form(row)
            return

        if row.get("context_before") or row.get("context_line") or row.get("context_after"):
            st.markdown("**Context:**")
            if row.get("context_before"):
                st.caption(row["context_before"])
            if row.get("context_line"):
                st.markdown(f"> {row['context_line']}")
            if row.get("context_after"):
                st.caption(row["context_after"])

        if row.get("url"):
            st.markdown(f"[🔗 Source]({row['url']})")

        notes = st.text_area(
            "Notes",
            value=row.get("notes") or "",
            key=f"vocab_notes_{vocab_id}",
            height=60,
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💾 Save notes", key=f"vocab_save_{vocab_id}"):
                if vocab.update_vocab_notes(
                    user_id=_user_id(),
                    vocab_id=vocab_id,
                    notes=notes,
                ):
                    st.success("Notes saved.")
                    st.rerun()
        with col2:
            if st.button("🔊 Play", key=f"vocab_tts_{vocab_id}"):
                try:
                    audio_bytes, fmt = generate_target_audio(
                        row["display_word"], st.session_state.settings
                    )
                    st.audio(audio_bytes, format=fmt, autoplay=True)
                except Exception as e:
                    st.warning(f"TTS failed: {e}")
        with col3:
            if st.button("🗑️ Delete", key=f"vocab_del_{vocab_id}"):
                vocab.delete_vocab_entry(
                    user_id=_user_id(), vocab_id=vocab_id
                )
                st.success("Deleted.")
                st.rerun()

        # Secondary action row: Edit + Auto-fill (auto-fill only when needed).
        need_autofill = not (row.get("translation") or "").strip() \
                        or not (row.get("ipa") or "").strip()
        acol1, acol2, _ = st.columns([1, 1, 4])
        with acol1:
            if st.button("✏️ Edit", key=f"vocab_edit_btn_{vocab_id}"):
                st.session_state[f"vocab_editing_{vocab_id}"] = True
                st.rerun()
        with acol2:
            if need_autofill and st.button(
                "✨ Auto-fill", key=f"vocab_autofill_{vocab_id}",
                help="Fill missing translation / IPA via LLM + eSpeak.",
            ):
                with st.spinner("Auto-filling…"):
                    result = vocab.autofill_vocab_entry(
                        user_id=_user_id(),
                        vocab_id=vocab_id,
                        language=_current_language(),
                        source_language=_source_language(),
                        secrets=st.secrets if hasattr(st, "secrets") else None,
                    )
                filled = result.get("filled", {})
                if filled:
                    st.toast(f"Filled: {', '.join(filled.keys())}")
                    st.rerun()
                else:
                    st.info("Nothing to fill — enrichment didn't return a value.")


def render_vocabulary_tab():
    """Top-level entry point for the Vocabulary tab."""
    st.header("📚 Vocabulary")
    if not _require_auth():
        return

    language = _current_language()
    st.caption(f"Language: **{language}** — change in sidebar to view another language's vocabulary.")

    col1, col2 = st.columns([2, 3])
    with col1:
        sort = st.selectbox(
            "Sort by",
            options=["alpha", "recent", "oldest"],
            format_func=lambda s: {
                "alpha": "Alphabetical",
                "recent": "Most recent",
                "oldest": "Oldest first",
            }[s],
            key="vocab_sort",
        )
    with col2:
        search = st.text_input(
            "Search (word or translation)",
            key="vocab_search",
            placeholder="type to filter…   try: ^a    ção$    source:Pessoa    none:ipa",
            help=(
                "Plain text searches word + translation.\n\n"
                "Operators (all AND, any order):\n"
                "- `^a` → word starts with \"a\" or \"A\"\n"
                "- `ção$` → word ends with \"ção\"\n"
                "- `[a-c]+ão.*` → regex on word (advanced)\n"
                "- `source:foo` → only in that field\n"
                "- `source:\"Foo Bar\"` → quote values with spaces\n"
                "- `has:url` / `none:ipa` → presence tests\n\n"
                "Fields: word, translation, ipa, source, url, note, context.\n"
                "Whitespace around `:` is fine (`has : url` works).\n"
                "Only the first colon splits field from value, so URLs are safe."
            ),
        )

    st.markdown("---")
    _render_paste_capture()
    _render_bulk_upload()
    st.markdown("---")

    import vocab_search
    try:
        rows = vocab.list_vocab(
            user_id=_user_id(), language=language, sort=sort, search=search
        )
    except vocab_search.QueryError as e:
        st.warning(f"🔎 {e}")
        rows = []
    _prune_stale_session_keys(rows)

    st.caption(f"**{len(rows)}** entr{'y' if len(rows) == 1 else 'ies'}")

    if rows and search.strip():
        # Let the user jump straight to Quick Practice with just these entries
        # as the phrase list — handy for drilling e.g. "ção$" endings.
        if st.button(
            f"🎯 Practise these ({len(rows)})",
            key="vocab_practise_filtered",
            help="Load these filtered entries into Quick Practice",
        ):
            st.session_state.phrase_list = [
                {
                    "text": r["display_word"],
                    "translation": r.get("translation") or "",
                    "ipa": r.get("ipa") or "",
                }
                for r in rows
            ]
            st.session_state.qp_phrase_position = 0
            st.session_state.quick_last_result = None
            st.session_state.material_source = (
                f"Vocabulary ({language}, filter: {search.strip()})"
            )
            st.session_state.qp_materials_expanded = False
            # Switch tabs: active_tab=0 → Quick Practice; material_source_tab=2 → Vocabulary panel
            st.session_state.active_tab = 0
            st.session_state.material_source_tab = 2
            st.rerun()

    if rows:
        _render_export_csv(rows)

    if not rows:
        if search.strip():
            st.info(f'**\"{search.strip()}\"** not in your vocabulary — add it below.')
        else:
            st.info(
                "No vocabulary yet for this language. Add words from the Story Reader, "
                "Quick Practice, or paste a passage below."
            )
    else:
        for row in rows:
            _render_entry_row(row)
