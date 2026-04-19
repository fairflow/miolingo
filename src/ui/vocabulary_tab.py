"""
Vocabulary tab — per-user, per-language personal dictionary (F2).

Capture routes wired in this tab:
  - Paste a passage, then type a word to capture from it (source = label)
  - Bulk upload a pipe-delimited dictionary file (word | source | context)
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


def _capture_from_passage(passage: str, word: str, source_label: str) -> dict:
    """Capture a single word from a pasted passage, pulling ±2 lines of context."""
    lines = [ln for ln in passage.splitlines() if ln.strip()]
    # Find the first line containing the word (case-insensitive).
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
        if st.button("➕ Add from passage", key="vocab_paste_btn", type="primary"):
            if not word.strip():
                st.warning("Type a word to add.")
            else:
                r = _capture_from_passage(passage, word, source_label)
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
            "Pipe-delimited `.txt`: `word | source | context` — one entry per line. "
            "Lines starting with `#` are ignored. Multi-word entries are skipped."
        )
        uploaded = st.file_uploader(
            "Upload .txt",
            type=["txt"],
            key="vocab_bulk_upload",
        )
        enrich = st.checkbox(
            "Auto-fetch translation + IPA on import",
            value=True,
            key="vocab_bulk_enrich",
            help="Slower but more useful. Uncheck for a raw import you'll enrich later.",
        )
        if uploaded is not None and st.button(
            "Import file", key="vocab_bulk_btn", type="primary"
        ):
            try:
                contents = uploaded.getvalue().decode("utf-8")
            except UnicodeDecodeError:
                st.error("File is not UTF-8 encoded.")
                return
            with st.spinner("Importing..."):
                summary = vocab.import_from_file_contents(
                    user_id=_user_id(),
                    language=_current_language(),
                    contents=contents,
                    enrich=enrich,
                    source_language=_source_language(),
                    secrets=st.secrets if hasattr(st, "secrets") else None,
                )
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
        "times_seen", "first_seen_at", "last_seen_at", "notes",
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
        ])
    st.download_button(
        "⬇️ Export CSV",
        data=buf.getvalue(),
        file_name=f"vocab_{_current_language()}.csv",
        mime="text/csv",
        key="vocab_export_csv",
    )


def _render_entry_row(row: dict):
    # Summary line: word · translation · IPA · source · date
    summary_bits = [f"**{row['display_word']}**"]
    if row.get("translation"):
        summary_bits.append(f"_{row['translation']}_")
    if row.get("ipa"):
        summary_bits.append(f"`{row['ipa']}`")
    summary_bits.append(f"· {row.get('source_name') or '—'}")
    summary_bits.append(f"· {str(row.get('last_seen_at') or '')[:16]}")
    with st.expander(" ".join(summary_bits), expanded=False):
        if row.get("context_before") or row.get("context_line") or row.get("context_after"):
            st.markdown("**Context:**")
            if row.get("context_before"):
                st.caption(row["context_before"])
            if row.get("context_line"):
                st.markdown(f"> {row['context_line']}")
            if row.get("context_after"):
                st.caption(row["context_after"])

        notes = st.text_area(
            "Notes",
            value=row.get("notes") or "",
            key=f"vocab_notes_{row['vocab_id']}",
            height=60,
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💾 Save notes", key=f"vocab_save_{row['vocab_id']}"):
                if vocab.update_vocab_notes(
                    user_id=_user_id(),
                    vocab_id=row["vocab_id"],
                    notes=notes,
                ):
                    st.success("Notes saved.")
                    st.rerun()
        with col2:
            if st.button("🔊 Play", key=f"vocab_tts_{row['vocab_id']}"):
                try:
                    audio_bytes, fmt = generate_target_audio(
                        row["display_word"], st.session_state.settings
                    )
                    st.audio(audio_bytes, format=fmt, autoplay=True)
                except Exception as e:
                    st.warning(f"TTS failed: {e}")
        with col3:
            if st.button("🗑️ Delete", key=f"vocab_del_{row['vocab_id']}"):
                vocab.delete_vocab_entry(
                    user_id=_user_id(), vocab_id=row["vocab_id"]
                )
                st.success("Deleted.")
                st.rerun()


def render_vocabulary_tab():
    """Top-level entry point for the Vocabulary tab."""
    st.header("📚 My Vocabulary")
    if not _require_auth():
        return

    language = _current_language()
    st.caption(f"Language: **{language}** — change in sidebar to view another language's vocab.")

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
            placeholder="type to filter…",
        )

    rows = vocab.list_vocab(
        user_id=_user_id(), language=language, sort=sort, search=search
    )

    st.caption(f"**{len(rows)}** entr{'y' if len(rows) == 1 else 'ies'}")

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

    st.markdown("---")
    _render_paste_capture()
    _render_bulk_upload()
