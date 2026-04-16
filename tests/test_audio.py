"""
Tests for audio/tts.py, audio/asr.py, and scoring/practice.py.

These are import/smoke tests and unit tests for pure functions.
Functions requiring Streamlit runtime, API keys, or hardware (microphone,
Whisper models) are tested only for importability.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Import tests — verify modules load without error
# ---------------------------------------------------------------------------

class TestTTSImports:
    """Verify audio/tts.py is importable and exports expected names."""

    def test_import_speak_text(self):
        from audio.tts import speak_text
        assert callable(speak_text)

    def test_import_speak_text_google_cloud(self):
        from audio.tts import speak_text_google_cloud
        assert callable(speak_text_google_cloud)

    def test_import_speak_text_gtts(self):
        from audio.tts import speak_text_gtts
        assert callable(speak_text_gtts)

    def test_import_generate_target_audio(self):
        from audio.tts import generate_target_audio
        assert callable(generate_target_audio)


class TestASRImports:
    """Verify audio/asr.py is importable and exports expected names."""

    def test_import_transcribe_audio_whisper(self):
        from audio.asr import transcribe_audio_whisper
        assert callable(transcribe_audio_whisper)

    def test_import_transcribe_audio_wav2vec2(self):
        from audio.asr import transcribe_audio_wav2vec2
        assert callable(transcribe_audio_wav2vec2)

    def test_import_transcribe_audio(self):
        from audio.asr import transcribe_audio
        assert callable(transcribe_audio)

    def test_import_model_loaders(self):
        from audio.asr import get_whisper_model, get_wav2vec2_model
        assert callable(get_whisper_model)
        assert callable(get_wav2vec2_model)


class TestPracticeImports:
    """Verify scoring/practice.py is importable and exports expected names."""

    def test_import_practice_word_from_audio(self):
        from scoring.practice import practice_word_from_audio
        assert callable(practice_word_from_audio)

    def test_import_trim_silence(self):
        from scoring.practice import trim_silence
        assert callable(trim_silence)


# ---------------------------------------------------------------------------
# Unit tests for pure functions
# ---------------------------------------------------------------------------

class TestTrimSilence:
    """Test the silence trimming function with synthetic audio."""

    def test_returns_tuple_of_two_bytes(self):
        from scoring.practice import trim_silence
        import numpy as np
        import soundfile as sf
        import io

        # Generate 1 second of silence + 0.5s tone + 0.5s silence
        sample_rate = 16000
        silence = np.zeros(sample_rate)
        tone = 0.5 * np.sin(2 * np.pi * 440 * np.arange(sample_rate // 2) / sample_rate)
        audio = np.concatenate([silence, tone, silence // 2])

        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format="WAV")
        wav_bytes = buf.getvalue()

        trimmed, original = trim_silence(wav_bytes, silence_threshold=0.01)

        assert isinstance(trimmed, bytes)
        assert isinstance(original, bytes)
        # Trimmed should be shorter (silence removed)
        assert len(trimmed) < len(wav_bytes)

    def test_all_silence_returns_original(self):
        from scoring.practice import trim_silence
        import numpy as np
        import soundfile as sf
        import io

        sample_rate = 16000
        silence = np.zeros(sample_rate)

        buf = io.BytesIO()
        sf.write(buf, silence, sample_rate, format="WAV")
        wav_bytes = buf.getvalue()

        trimmed, original = trim_silence(wav_bytes, silence_threshold=0.01)

        # All silence → returns original bytes unchanged
        assert trimmed == wav_bytes

    def test_invalid_bytes_returns_original(self):
        from scoring.practice import trim_silence

        bad_bytes = b"not a wav file"
        trimmed, original = trim_silence(bad_bytes)

        assert trimmed == bad_bytes
        assert original == bad_bytes


class TestSpeakTextEspeak:
    """Test eSpeak TTS (requires espeak binary on PATH)."""

    def test_speak_text_returns_bytes(self):
        from audio.tts import speak_text
        import shutil

        if shutil.which("espeak") is None and not Path("/opt/local/bin/espeak").exists():
            import pytest
            pytest.skip("espeak not available")

        audio_bytes, fmt = speak_text("hello", voice="en")
        assert isinstance(audio_bytes, bytes)
        assert len(audio_bytes) > 0
        assert fmt == "audio/wav"

    def test_speak_text_empty_on_bad_voice(self):
        """eSpeak with a completely invalid voice should not crash."""
        from audio.tts import speak_text

        audio_bytes, fmt = speak_text("test", voice="xx-nonexistent-zz")
        # May return empty or valid audio depending on espeak fallback
        assert isinstance(audio_bytes, bytes)
        assert fmt == "audio/wav"
