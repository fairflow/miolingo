"""
Practice tab UI: reusable practice interface and results rendering.

Extracted from app.py (Phase 4.2 of refactor).

Exports
-------
    practice_word_from_audio(text, audio_bytes, settings)
        Thin wrapper with session-state persistence and DB save callback.
    save_current_session()
        Confirm current session is saved, reset for next session.
    render_practice_interface(text, key_prefix)
        Audio playback + recording + submit UI component.
    render_practice_results(result, key_prefix)
        Scored results with IPA coloured-diff display.
"""

import string
import html as _html
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import app_mysql
import vocab
from audio.tts import generate_target_audio
from scoring.phonemes import format_ipa, normalize_for_phoneme_scoring
from scoring.practice import practice_word_from_audio as _practice_word_from_audio_core


# ---------------------------------------------------------------------------
# practice_word_from_audio — thin wrapper
# ---------------------------------------------------------------------------

def practice_word_from_audio(text: str, audio_bytes: bytes, settings: dict):
    """
    Thin wrapper around scoring.practice.practice_word_from_audio that
    handles session-state persistence and database saves.

    The core scoring logic lives in scoring/practice.py.
    """
    def _persist_result(result):
        """Save result to session state and database."""
        session_data = {
            k: v for k, v in result.items()
            if k not in ["user_audio_bytes", "user_audio_trimmed_bytes"]
        }
        st.session_state.current_sessions[st.session_state.language]["practices"].append({
            "time": datetime.now().isoformat(),
            **session_data
        })
        st.session_state.session_saved = False

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

            # F2: auto-capture single-word perfect matches to the vocab tracker.
            # Multi-word targets are handled by the "Add a word" input rendered
            # next to the practice interface (see render_practice_results).
            try:
                target = (result.get('target') or '').strip()
                if (result.get('exact_match')
                        and target
                        and ' ' not in target):
                    from config import get_language_code
                    _src = st.session_state.get('source_language', 'English')
                    vocab.capture_vocab_entry(
                        user_id=user_id,
                        language=st.session_state.language,
                        word=target,
                        source_name=st.session_state.get(
                            'material_source'
                        ) or 'Quick Practice',
                        context_line=target,
                        enrich=True,
                        source_language=_src,
                        source_language_code=get_language_code(_src),
                        secrets=st.secrets if hasattr(st, 'secrets') else None,
                    )
            except Exception as e:
                # Never let vocab capture break the practice flow
                import logging
                logging.warning("vocab auto-capture failed: %s", e)

    return _practice_word_from_audio_core(
        text,
        audio_bytes,
        settings,
        language=st.session_state.language,
        on_result=_persist_result,
    )


# ---------------------------------------------------------------------------
# save_current_session
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Debug audio injection — feed a saved .wav in place of the mic (miolingo-7w3)
# ---------------------------------------------------------------------------

def _maybe_inject_test_audio(key_prefix):
    """In debug mode, offer a picker of saved .wav files to stand in for a live
    recording (mic is unavailable when an agent drives the shared browser).
    Returns a BytesIO of the chosen wav (so .getvalue() works like st.audio_input),
    or None. The dir is MIO_AUDIO_DUMP_DIR if set, else scratchpad recordings."""
    import os
    import streamlit as st
    if not st.session_state.get("settings", {}).get("debug_mode", False):
        return None
    test_dir = os.environ.get("MIO_AUDIO_DUMP_DIR", "")
    if not test_dir or not os.path.isdir(test_dir):
        return None
    wavs = sorted(f for f in os.listdir(test_dir) if f.lower().endswith(".wav"))
    if not wavs:
        return None
    with st.expander("🧪 Debug: inject test audio (no mic)", expanded=False):
        choice = st.selectbox("Saved recording to use as the recording",
                              ["(none)"] + wavs, key=f"{key_prefix}_test_audio_pick")
        if choice and choice != "(none)":
            with open(os.path.join(test_dir, choice), "rb") as fh:
                import io
                buf = io.BytesIO(fh.read())
                buf.name = choice  # mimic UploadedFile
                st.caption(f"Using {choice} in place of the microphone.")
                return buf
    return None


# ---------------------------------------------------------------------------
# render_practice_interface
# ---------------------------------------------------------------------------

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

    # DEBUG audio-injection (miolingo-7w3): when the mic is unavailable (e.g. an
    # agent driving the shared browser), let a saved .wav stand in for a live
    # recording so the full Results flow can be exercised. Debug-mode only; the
    # injected audio is a REAL prior recording, replayed — not fabricated.
    _injected = _maybe_inject_test_audio(key_prefix)
    if _injected is not None:
        audio_data = _injected

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


# ---------------------------------------------------------------------------
# render_practice_results
# ---------------------------------------------------------------------------

def _render_practice_vocab_capture(result, key_prefix):
    """Capture a single word from a multi-word practice phrase into the vocab tracker.

    Single-word targets are already auto-captured on perfect match (see
    `practice_word_from_audio._persist_result`); we only show the input for
    multi-word phrases so the user can pick which word is worth keeping.
    """
    if not st.session_state.get("authenticated", False):
        return
    target = (result.get("target") or "").strip()
    if not target or " " not in target:
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        word = st.text_input(
            "📚 Add a word from this phrase to my vocabulary",
            key=f"{key_prefix}_vocab_word",
            placeholder="type a single word from the phrase…",
            label_visibility="collapsed",
        )
    with col2:
        if st.button("➕ Add", key=f"{key_prefix}_vocab_btn"):
            if not word.strip():
                st.warning("Type a word first.")
            else:
                from config import get_language_code
                _src = st.session_state.get("source_language", "English")
                r = vocab.capture_vocab_entry(
                    user_id=st.session_state["user"]["user_id"],
                    language=st.session_state.language,
                    word=word,
                    source_name=st.session_state.get(
                        "material_source"
                    ) or "Quick Practice",
                    context_line=target,
                    enrich=True,
                    source_language=_src,
                    source_language_code=get_language_code(_src),
                    secrets=st.secrets if hasattr(st, "secrets") else None,
                )
                if r["ok"]:
                    st.success(
                        f"✅ {'Added' if r['created'] else 'Already in'} vocab: "
                        f"**{word}**"
                    )
                else:
                    st.error(f"⚠️ {r['message']}")


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

    # Track if sound has been played for this result
    result_id = f"{result.get('target', '')}_{result.get('recognized', '')}_{result.get('similarity', 0)}"
    if 'last_sound_played' not in st.session_state:
        st.session_state.last_sound_played = None

    should_play_sound = st.session_state.last_sound_played != result_id

    if result["exact_match"]:
        st.success("🎉 PERFECT MATCH! Well done!")
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
        # Dual-channel summary (miolingo-7w3) — show BOTH always; the gap is the
        # diagnostic. Comprehensibility = what a listener (Whisper) understood;
        # Accuracy = how close the sounds you PRODUCED are (phones from audio).
        _understood = result['target'].lower().translate(
            str.maketrans('', '', string.punctuation)
        ) == result['recognized'].lower().translate(
            str.maketrans('', '', string.punctuation)
        )
        _acc = result.get('accuracy_similarity')
        # One compact line so it never responsively stacks: comprehensibility +
        # accuracy together. The gap between them is the diagnostic.
        _u = "✓ understood" if _understood else f"✗ heard “{result['recognized']}”"
        _p = f"🎯 **{_acc:.0%}** pronunciation" if _acc is not None else "🎯 — pronunciation"
        st.markdown(f"🗣️ {_u}  ·  {_p}")
        st.caption("Understood = did a listener (Whisper) get the word, forgiving accent · "
                   "Pronunciation = how close your actual sounds were, from the recording")

    # F2: let the user capture a single word from a multi-word practice phrase.
    _render_practice_vocab_capture(result, key_prefix)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Target")
        st.write(f"**Text:** {result['target']}")
        if result.get('correct_ipa'):
            st.markdown(f"**IPA:** {format_ipa(result['correct_ipa'])}", unsafe_allow_html=True)

        tts_label = "Google TTS" if st.session_state.settings.get('tts_engine', 'gtts') == 'gtts' else "eSpeak"
        st.write(f"🔊 **{tts_label}:**")
        audio_bytes, audio_format = generate_target_audio(result['target'], st.session_state.settings)
        st.audio(audio_bytes, format=audio_format)

    with col2:
        st.subheader("Your Pronunciation")
        st.write(f"**Recognized:** {result['recognized']}")
        if result.get('user_ipa'):
            st.markdown(f"**IPA:** {format_ipa(result['user_ipa'])}", unsafe_allow_html=True)

        target_clean = result['target'].lower().translate(str.maketrans('', '', string.punctuation))
        recognized_clean = result['recognized'].translate(str.maketrans('', '', string.punctuation))

        correct_phonemes_no_space = result.get('correct_phonemes_normalized') or normalize_for_phoneme_scoring(result.get('correct_phonemes', ''))
        user_phonemes_no_space = result.get('user_phonemes_normalized') or normalize_for_phoneme_scoring(result.get('user_phonemes', ''))

        # Trust the scorer's verdict (it reflects whichever channel produced
        # user_ipa — text or acoustic). Falling back to the string compare only
        # if exact_match is absent keeps legacy results working (miolingo-dsq).
        phonemes_match = result.get(
            'exact_match', correct_phonemes_no_space == user_phonemes_no_space
        )
        text_matches = target_clean == recognized_clean
        score_is_high = result['similarity'] >= 0.95

        if phonemes_match:
            if not text_matches:
                st.success("✅ Perfect pronunciation! (Text punctuation/formatting differs)")
            else:
                st.success("✅ Phonemes match perfectly")
        elif score_is_high and not text_matches:
            st.info("ℹ️ Excellent pronunciation! (Minor text differences)")
        elif not text_matches and not score_is_high:
            st.warning("⚠️ Different words recognized - try speaking more clearly")

    # Detailed phoneme analysis — full width below the two columns
    if st.checkbox("🔍 Show detailed phoneme analysis", key=f"{key_prefix}_show_detail"):
        st.markdown("---")
        st.markdown("#### Phoneme Analysis")
        st.write(f"**Algorithm:** {st.session_state.settings.get('comparison_algorithm', 'edit_distance')}")

        if result.get('edit_distance') is not None:
            st.write(f"**Edit Distance:** {result['edit_distance']} edit(s) needed")

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

        # Diff over PHONES using the SAME normalization the scorer uses
        # (scoring.phone_distance.segment → _clean strips stress, '-', ties,
        # spaces). This keeps the displayed comparison consistent with the score
        # and removes stray artefacts (no leftover stress marks, clitic '-', or
        # filler glyphs that look like phones). (miolingo-7w3)
        from scoring.phone_distance import segment as _segment
        target_segs = _segment(correct_ipa)
        user_segs = _segment(user_ipa)

        st.write("**Detailed phone comparison:**")
        if target_segs and target_segs == user_segs:
            st.success("🎯 Phones are identical!")
        elif target_segs or user_segs:
            # Legend — use a vertical bar separator so it can't be confused with
            # any in-diff marker; missing/added phones are shown as a gap '∅'.
            st.caption("**Legend:** 🟦 different sound │ 🟩 sound you added │ 🟥 sound missing │ ∅ = gap (nothing there)")

            GAP = "∅"

            def _colorize_diff(target: list, user: list) -> tuple[str, str]:
                # replace: light blue, insert: light green, delete: light pink.
                matcher_local = SequenceMatcher(None, target, user)
                target_chunks: list[str] = []
                user_chunks: list[str] = []

                def _join(segs):
                    return _html.escape(" ".join(segs))

                for tag, i1, i2, j1, j2 in matcher_local.get_opcodes():
                    t_seg = target[i1:i2]
                    u_seg = user[j1:j2]
                    if tag == 'equal':
                        target_chunks.append(_join(t_seg))
                        user_chunks.append(_join(u_seg))
                    elif tag == 'replace':
                        target_chunks.append(f'<span style="background-color: #ADD8E6; padding: 0 2px;">{_join(t_seg)}</span>')
                        user_chunks.append(f'<span style="background-color: #ADD8E6; padding: 0 2px;">{_join(u_seg)}</span>')
                    elif tag == 'insert':
                        target_chunks.append(f'<span style="background-color: #90EE90; padding: 0 2px;">{GAP}</span>')
                        user_chunks.append(f'<span style="background-color: #90EE90; padding: 0 2px;">{_join(u_seg)}</span>')
                    elif tag == 'delete':
                        target_chunks.append(f'<span style="background-color: #FFB6C6; padding: 0 2px;">{_join(t_seg)}</span>')
                        user_chunks.append(f'<span style="background-color: #FFB6C6; padding: 0 2px;">{GAP}</span>')

                return ' '.join(c for c in target_chunks if c), ' '.join(c for c in user_chunks if c)

            matcher = SequenceMatcher(None, target_segs, user_segs)
            operations = matcher.get_opcodes()
            substitutions = [op for op in operations if op[0] == 'replace']
            insertions = [op for op in operations if op[0] == 'insert']
            deletions = [op for op in operations if op[0] == 'delete']
            matches = sum(i2 - i1 for tag, i1, i2, j1, j2 in operations if tag == 'equal')
            st.write(f"**Operations:** {matches} matches, {len(substitutions)} substitutions, {len(insertions)} insertions, {len(deletions)} deletions")

            target_html, user_html = _colorize_diff(target_segs, user_segs)
            mono_wrap_start = '<div style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \'Liberation Mono\', \'Courier New\', monospace; white-space: pre-wrap;">'
            mono_wrap_end = '</div>'

            col_t, col_u = st.columns(2)
            with col_t:
                st.markdown(mono_wrap_start + target_html + mono_wrap_end, unsafe_allow_html=True)
                st.caption("Target phones — differences highlighted")
            with col_u:
                st.markdown(mono_wrap_start + user_html + mono_wrap_end, unsafe_allow_html=True)
                st.caption("Your phones — differences highlighted")
        else:
            st.info("No IPA available for detailed comparison.")

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
