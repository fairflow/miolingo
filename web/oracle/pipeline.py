"""The attempt-scoring pipeline — src/scoring/practice.py, minus streamlit.

One request = one round trip: audio in → ffmpeg-normalize → trim silence →
espeak G2P target → Whisper ASR → BOTH channels (comprehensibility = espeak
G2P of the ASR text; accuracy = phones read directly from the waveform) →
score each with the configured algorithm → per-phone ops out. Everything a
client displays about an attempt comes from this response (single source of
truth); curve params live HERE (practice.py:193-199), never client-side.
"""
from __future__ import annotations

import io
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

import schemas
from scoring.comparison import compare_phonemes, get_edit_operations
from scoring.phonemes import get_ipa, normalize_for_phoneme_scoring

import engines


def normalize_to_wav16k(audio_bytes: bytes) -> bytes:
    """Any browser container (webm/opus, mp4/aac, wav) → 16 kHz mono WAV.

    ffmpeg reads the container from stdin and writes wav to stdout. If ffmpeg
    is unavailable, WAV input passes through (soundfile handles it) and other
    containers fail loudly — the health endpoint reports ffmpeg presence.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
             "-acodec", "pcm_s16le", "-f", "wav", "pipe:1"],
            input=audio_bytes,
            capture_output=True,
            check=True,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        if audio_bytes[:4] == b"RIFF":
            return audio_bytes  # already WAV; best effort without ffmpeg
        raise


def trim_silence(audio_bytes: bytes, silence_threshold: float = 0.01) -> bytes:
    """Energy-based start/end silence trim — practice.py:32-81, verbatim
    behaviour (20 ms frames, threshold vs max energy, 200 ms padding;
    any failure returns the input unchanged)."""
    try:
        audio_data, sample_rate = sf.read(io.BytesIO(audio_bytes))
        frame_length = int(0.02 * sample_rate)
        energy = np.array([
            np.sum(audio_data[i : i + frame_length] ** 2)
            for i in range(0, len(audio_data) - frame_length, frame_length)
        ])
        threshold = silence_threshold * np.max(energy)
        speech_frames = np.where(energy > threshold)[0]
        if len(speech_frames) == 0:
            return audio_bytes
        padding = int(0.2 * sample_rate)
        start = max(0, speech_frames[0] * frame_length - padding)
        end = min(len(audio_data), (speech_frames[-1] + 1) * frame_length + padding)
        out = io.BytesIO()
        sf.write(out, audio_data[start:end], sample_rate, format="WAV")
        return out.getvalue()
    except Exception:  # noqa: BLE001 - trimming is best-effort (as in the app)
        return audio_bytes


def _weighted_ops(ops) -> list[schemas.AttemptOp]:
    """phone_distance.Op list → API ops (same orientation: target-side)."""
    return [
        schemas.AttemptOp(kind=o.kind, target=o.target, user=o.user, significant=o.significant)
        for o in ops
    ]


def _edit_ops(correct_norm: str, user_norm: str) -> list[schemas.AttemptOp]:
    """comparison.get_edit_operations(target, user) → API ops. '-' placeholders
    become ''; every non-match is significant at the character level."""
    kinds = {"match": "match", "substitute": "substitute", "insert": "insert", "delete": "delete"}
    out: list[schemas.AttemptOp] = []
    for op, _pos, c1, c2 in get_edit_operations(correct_norm, user_norm):
        target = "" if (op == "insert") else c1
        user = "" if (op == "delete") else c2
        out.append(
            schemas.AttemptOp(kind=kinds[op], target=target, user=user, significant=op != "match")
        )
    return out


def _score_channel(
    user_ipa: str, correct_ipa: str, voice: str, algorithm: str, accuracy_curve: bool
) -> schemas.AttemptChannel:
    """One channel's scores + ops — practice.py:187-203, ops from the SAME
    scorer that produced the numbers."""
    if not user_ipa:
        return schemas.AttemptChannel(
            ipa="", similarity=None, exact=False, distance=None, ops=[]
        )
    if algorithm == "weighted_phone":
        from scoring.phone_distance import score as phone_score

        if accuracy_curve:
            # stretched curve: real errors register, a single error in a long
            # phrase stays visible (practice.py:193-197). Server-side only.
            r = phone_score(user_ipa, correct_ipa, voice, gain=4.0, exp=0.6, sqrt_norm=True)
        else:
            r = phone_score(user_ipa, correct_ipa, voice)
        return schemas.AttemptChannel(
            ipa=user_ipa,
            similarity=r.similarity,
            exact=r.exact_match,
            distance=round(r.distance, 3),
            ops=_weighted_ops(r.ops),
        )
    user_norm = normalize_for_phoneme_scoring(user_ipa)
    correct_norm = normalize_for_phoneme_scoring(correct_ipa)
    exact, similarity, distance = compare_phonemes(user_norm, correct_norm, algorithm=algorithm)
    return schemas.AttemptChannel(
        ipa=user_ipa,
        similarity=similarity,
        exact=exact,
        distance=float(distance) if distance is not None else None,
        ops=_edit_ops(correct_norm, user_norm),
    )


def score_attempt(
    audio_bytes: bytes,
    target: str,
    voice: str,
    algorithm: str = "weighted_phone",
    whisper_model: str = "base",
    silence_threshold: float = 0.01,
) -> schemas.AttemptResponse:
    """The dual-channel pipeline (practice.py:84-240, streamlit-free)."""
    t_total = time.time()
    wav = trim_silence(normalize_to_wav16k(audio_bytes), silence_threshold)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.write(wav)
    tmp.close()
    try:
        target_ipa = get_ipa(target, voice)

        lang_code = voice.split("-")[0]  # whisper wants the bare language
        t_asr = time.time()
        recognized = engines.transcribe_whisper(tmp.name, whisper_model, lang_code)
        asr_ms = round((time.time() - t_asr) * 1000)

        # comprehensibility = what a listener UNDERSTOOD (G2P of the ASR text)
        comp_ipa = get_ipa(recognized, voice) if recognized else ""

        # accuracy = what the learner PRODUCED (phones from the waveform)
        from audio.phone_recognizer import phones_from_audio

        t_a2p = time.time()
        acc_ipa = phones_from_audio(tmp.name, voice)
        a2p_ms = round((time.time() - t_a2p) * 1000)

        return schemas.AttemptResponse(
            target=target,
            recognized_text=recognized,
            target_ipa=target_ipa,
            algorithm=algorithm,
            comprehensibility=_score_channel(comp_ipa, target_ipa, voice, algorithm, False),
            accuracy=_score_channel(acc_ipa, target_ipa, voice, algorithm, True),
            timings_ms=schemas.AttemptTimings(
                asr=asr_ms, a2p=a2p_ms, total=round((time.time() - t_total) * 1000)
            ),
        )
    finally:
        Path(tmp.name).unlink(missing_ok=True)
