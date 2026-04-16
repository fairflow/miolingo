"""
Automatic Speech Recognition: Whisper and Wav2Vec2.

Model loading is session-cached (via Streamlit session_state).
Transcription functions are pure: they take a model and return text.
"""

import warnings
from typing import Optional, Tuple, Callable

import streamlit as st

from config import LANGUAGE_CONFIG


# ---------------------------------------------------------------------------
# Model loaders (session-cached via st.session_state)
# ---------------------------------------------------------------------------

def get_whisper_model(model_name: str):
    """Load or return cached Whisper model."""
    import whisper

    if st.session_state.get('whisper_model_name') != model_name:
        with st.spinner(f"Loading Whisper model '{model_name}'..."):
            st.session_state.whisper_model = whisper.load_model(model_name)
            st.session_state.whisper_model_name = model_name
    return st.session_state.whisper_model


def get_wav2vec2_model():
    """Load or return cached wav2vec2 Portuguese model."""
    if (
        "wav2vec2_processor" not in st.session_state
        or st.session_state.wav2vec2_processor is None
    ):
        try:
            with st.spinner(
                "Loading wav2vec2 Portuguese model "
                "(first time may take a few minutes)..."
            ):
                from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

                model_name = (
                    "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese"
                )
                st.session_state.wav2vec2_processor = (
                    Wav2Vec2Processor.from_pretrained(model_name)
                )
                st.session_state.wav2vec2_model = (
                    Wav2Vec2ForCTC.from_pretrained(model_name)
                )
        except ImportError:
            st.error(
                "wav2vec2 requires 'transformers' and 'torch'. "
                "Install with: pip install transformers torch"
            )
            return None, None
        except Exception as e:
            st.error(f"Failed to load wav2vec2 model: {e}")
            return None, None
    return st.session_state.wav2vec2_processor, st.session_state.wav2vec2_model


# ---------------------------------------------------------------------------
# Transcription engines
# ---------------------------------------------------------------------------

def transcribe_audio_whisper(
    audio_file: str,
    model,
    language_code: str = "pt",
) -> str:
    """
    Transcribe audio to text using Whisper.

    Includes hallucination detection: returns a bracketed error string if
    a 2-4 word pattern repeats 10+ times or if the transcript exceeds
    100 words.

    Args:
        audio_file: Path to audio file
        model: Whisper model instance
        language_code: Whisper language code (e.g., 'pt', 'fr', 'nl')
    """
    result = model.transcribe(
        audio=audio_file,
        language=language_code,
        task="transcribe",
        temperature=0.0,
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
        condition_on_previous_text=False,
        word_timestamps=False,
        compression_ratio_threshold=2.4,
    )

    detected_lang = result.get("language", "unknown")
    if detected_lang != language_code:
        warnings.warn(
            f"Whisper detected language '{detected_lang}' "
            f"instead of '{language_code}'"
        )

    transcribed_text = result["text"].strip().lower()

    # Hallucination detection — Whisper sometimes loops on poor audio
    words = transcribed_text.split()
    if len(words) > 20:
        for pattern_len in [2, 3, 4]:
            if len(words) >= pattern_len * 10:
                pattern = " ".join(words[:pattern_len])
                repetitions = transcribed_text.count(pattern)
                if repetitions >= 10:
                    warnings.warn(
                        f"Whisper hallucination detected: "
                        f"'{pattern}' repeated {repetitions} times"
                    )
                    return (
                        f"[hallucination detected: "
                        f"'{pattern}' x{repetitions}]"
                    )

        if len(words) > 100:
            warnings.warn(
                f"Suspiciously long transcription: {len(words)} words"
            )
            return (
                f"[error: transcription too long - "
                f"{len(words)} words, possible hallucination]"
            )

    return transcribed_text


def transcribe_audio_wav2vec2(
    audio_file: str,
    processor,
    model,
) -> str:
    """Transcribe audio to text using wav2vec2 Portuguese model."""
    try:
        import torch
        import soundfile as sf

        speech, sample_rate = sf.read(audio_file)

        if sample_rate != 16000:
            import librosa
            speech = librosa.resample(
                speech, orig_sr=sample_rate, target_sr=16000
            )

        inputs = processor(
            speech, sampling_rate=16000, return_tensors="pt", padding=True
        )

        with torch.no_grad():
            logits = model(inputs.input_values).logits

        predicted_ids = torch.argmax(logits, dim=-1)
        transcription = processor.batch_decode(predicted_ids)[0]

        return transcription.strip().lower()

    except Exception as e:
        st.error(f"wav2vec2 transcription failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Dispatcher: choose ASR engine with fallback
# ---------------------------------------------------------------------------

def transcribe_audio(
    audio_file: str,
    settings: dict,
    language: str = "Portuguese",
    *,
    warn_fn: Optional[Callable] = None,
) -> str:
    """
    Transcribe audio using the selected ASR engine.

    Args:
        audio_file: Path to audio file
        settings: App settings dict (asr_engine, whisper_model_size)
        language: Selected language name (e.g., "Portuguese", "French")
        warn_fn: Optional warning callback (defaults to st.warning)
    """
    if warn_fn is None:
        warn_fn = st.warning

    asr_engine = settings.get("asr_engine", "whisper")

    lang_config = LANGUAGE_CONFIG[language]
    lang_code = lang_config["code"]

    if asr_engine == "wav2vec2":
        if lang_code != "pt":
            warn_fn("wav2vec2 only supports Portuguese, falling back to Whisper")
            asr_engine = "whisper"
        else:
            processor, model = get_wav2vec2_model()
            if processor is None or model is None:
                warn_fn("wav2vec2 unavailable, falling back to Whisper")
                asr_engine = "whisper"
            else:
                return transcribe_audio_wav2vec2(audio_file, processor, model)

    # Default to Whisper
    model_size = settings.get("whisper_model_size", "base")
    model = get_whisper_model(model_size)
    return transcribe_audio_whisper(audio_file, model, lang_code)
