"""
Acoustic phone recognition: derive IPA phones DIRECTLY from the audio waveform.

This is the ACCURACY channel of the two-channel design (see
docs/research/phonetics/FINDING_audio_to_ipa_gap.md, miolingo-7w3): it reports
what the learner actually PRODUCED, as opposed to the comprehensibility channel
(Whisper -> espeak) which reports what a listener would have UNDERSTOOD.

Recognizer choice is per-language and EMPIRICAL (Common Phone weighted_phone
bake-off, cp_eval.py, miolingo-0x9):
  - French  -> Cnam-LMSSC/wav2vec2-french-phonemizer    (specialist, ~0.013 err)
  - Italian -> Cnam-LMSSC/wav2vec2-italian-phonemizer   (specialist, 0.046 err)
  - Dutch   -> Clementapa/wav2vec2-base-960h-phoneme-reco-dutch (specialist, 0.086)
  - Russian -> pklumpp/Wav2Vec2_CommonPhone          (specialist, 0.073; custom
               weights-only class loaded via audio/pklumpp_ctc.py, not AutoModelForCTC)
  - other   -> facebook/wav2vec2-xlsr-53-espeak-cv-ft   (multilingual fallback)
No specialist wired for Spanish/German/pt-BR: each benched WORSE than or equal to
the xlsr-53 fallback (es cnam-es 0.071>0.036 truncates; de hk-de emits empty; pt-BR
caiocrocha 0.116~0.114 tie). The fallback itself beat the old lv-60 on all 5 benched
langs. Paper PERs mispredicted Spanish -- always bench on real audio (cp_eval.py).
Both are wav2vec2 phoneme-CTC models that emit espeak-ng-convention IPA (same
convention as our espeak targets), output phones directly from audio, and load
via transformers AutoModelForCTC. Allosaurus was evaluated and dropped: weaker
(~0.14 weighted on French) and its lang_id is only a phone-inventory mask over a
single universal model.

Import-light: transformers/torch and the model load lazily on first use, so the
comprehensibility-only path never pays for them.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Callable, Optional

# espeak voice code (or its language prefix) -> HuggingFace phoneme-CTC model id.
# Per-language choice is EMPIRICAL, from the Common Phone weighted_phone bake-off
# (cp_eval.py, 2026-07-07), NOT from paper PERs -- which mispredicted Spanish:
#   fr: cnam 0.013 << fb           -> specialist
#   it: cnam-it 0.046 < fb 0.085   -> specialist
#   es: cnam-es 0.071 > fb-xlsr 0.036 -> specialist LOSES (truncates full sentences)
#       so Spanish rides the fallback, no specialist wired.
# The Cnam-LMSSC family (wav2vec2-base + linear-CTC, espeak-convention IPA) is a
# true drop-in but is NOT uniformly good -- bench before trusting each one.
_FRENCH_MODEL = "Cnam-LMSSC/wav2vec2-french-phonemizer"
_ITALIAN_MODEL = "Cnam-LMSSC/wav2vec2-italian-phonemizer"
# Dutch specialist: clementapa beat both fallbacks on FLEURS-nl (0.086 vs xlsr
# 0.112 vs lv-60 0.145). Licence undeclared -> clear before ship (miolingo-0x9
# reframe: test-only for now). nl-be/Flemish rides this via the prefix fallback.
_DUTCH_MODEL = "Clementapa/wav2vec2-base-960h-phoneme-reco-dutch"
# Russian specialist: pklumpp CommonPhone beat both fallbacks on Common Phone ru
# (0.073 vs 0.133) -- ~1.9x. Weights-only repo + custom class, so it loads via
# audio/pklumpp_ctc.py (not AutoModelForCTC). CC0 licence. (miolingo-dky)
_RUSSIAN_MODEL = "pklumpp/Wav2Vec2_CommonPhone"

# Multilingual fallback. xlsr-53 beat the old lv-60 on BOTH benched langs
# (es 0.036<0.060, it 0.065<0.085), same espeak-IPA output + loader -> new default.
# lv-60 kept as a selectable backstop (see miolingo-3ym flyout selector).
_MULTILINGUAL_MODEL = "facebook/wav2vec2-xlsr-53-espeak-cv-ft"
_MULTILINGUAL_MODEL_LV60 = "facebook/wav2vec2-lv-60-espeak-cv-ft"

_VOICE_TO_MODEL = {
    "fr": _FRENCH_MODEL,
    "fr-fr": _FRENCH_MODEL,
    "fr-be": _FRENCH_MODEL,
    "fr-ch": _FRENCH_MODEL,
    "it": _ITALIAN_MODEL,
    "nl": _DUTCH_MODEL,
    "ru": _RUSSIAN_MODEL,
}


# --- Model lifecycle & selection (miolingo-s06 load-on-demand/unload; miolingo-3ym
# --- flyout selector) -----------------------------------------------------------
#
# Models are 0.3-1.2 GB each, so we (a) load lazily on first use, (b) keep at most
# _MAX_LOADED resident and LRU-evict beyond that, and (c) expose explicit unload +
# an evict-on-language-switch hook so the app can bound memory when the learner
# changes target language. A manual OrderedDict cache (not lru_cache) is used so we
# can introspect what's loaded, evict a single model, and free torch memory.

_MODEL_CACHE: "OrderedDict[str, tuple]" = OrderedDict()  # model_id -> (proc, model)
_MAX_LOADED = 2                    # soft cap; evict LRU beyond this
_MODEL_OVERRIDE: dict[str, str] = {}  # espeak voice (lc) -> forced model id (UI)

# Candidate recognizers for the flyout selector (miolingo-3ym): the wired defaults,
# both multilingual options, and benched-but-not-default specialists a tester may
# want to A/B. label -> HuggingFace model id.
KNOWN_MODELS: "OrderedDict[str, str]" = OrderedDict([
    ("Auto (per-language default)", ""),  # "" => resolve via _VOICE_TO_MODEL
    ("fr · Cnam french (default)", _FRENCH_MODEL),
    ("it · Cnam italian (default)", _ITALIAN_MODEL),
    ("nl · Clementapa dutch (default)", _DUTCH_MODEL),
    ("ru · pklumpp CommonPhone (default)", _RUSSIAN_MODEL),
    ("es · Cnam spanish (benched: loses)", "Cnam-LMSSC/wav2vec2-spanish-phonemizer"),
    ("pt-br · caiocrocha (benched: ties)",
     "caiocrocha/wav2vec2-large-xlsr-53-phoneme-portuguese"),
    ("fallback · xlsr-53-espeak (default)", _MULTILINGUAL_MODEL),
    ("backstop · lv-60-espeak (legacy)", _MULTILINGUAL_MODEL_LV60),
])


def default_model_for_voice(voice: str) -> str:
    """The wired per-language default, ignoring any UI override."""
    if not voice:
        return _MULTILINGUAL_MODEL
    v = voice.lower()
    if v in _VOICE_TO_MODEL:
        return _VOICE_TO_MODEL[v]
    return _VOICE_TO_MODEL.get(v.split("-")[0], _MULTILINGUAL_MODEL)


def model_for_voice(voice: str) -> str:
    """Pick the model id for a voice, honoring a UI override if one is set."""
    v = (voice or "").lower()
    if v in _MODEL_OVERRIDE:
        return _MODEL_OVERRIDE[v]
    if v and v.split("-")[0] in _MODEL_OVERRIDE:
        return _MODEL_OVERRIDE[v.split("-")[0]]
    return default_model_for_voice(voice)


def set_model_override(voice: str, model_id: str) -> None:
    """Force a specific recognizer for a voice (flyout selector). Empty model_id or
    None clears the override (revert to the per-language default)."""
    v = (voice or "").lower()
    if not v:
        return
    if model_id:
        _MODEL_OVERRIDE[v] = model_id
    else:
        _MODEL_OVERRIDE.pop(v, None)


def loaded_model_ids() -> list[str]:
    """Model ids currently resident in memory (for the flyout status display)."""
    return list(_MODEL_CACHE.keys())


def unload(model_id: Optional[str] = None) -> None:
    """Free one model (by id) or all models, releasing torch memory."""
    ids = [model_id] if model_id else list(_MODEL_CACHE.keys())
    for mid in ids:
        _MODEL_CACHE.pop(mid, None)
    _free_torch_memory()


def unload_all_except_voice(voice: str) -> None:
    """Evict every resident model except the one the given voice resolves to.

    The app calls this when the learner switches target language, so we don't pin
    the previous language's large model alongside the new one."""
    keep = model_for_voice(voice)
    for mid in list(_MODEL_CACHE.keys()):
        if mid != keep:
            _MODEL_CACHE.pop(mid, None)
    _free_torch_memory()


def _free_torch_memory() -> None:
    """Best-effort release of freed model memory back to the allocator. Never
    IMPORTS torch -- only touches it if a model already pulled it in, so an
    unload call on the comprehensibility-only path stays cheap."""
    import gc
    import sys

    gc.collect()
    torch = sys.modules.get("torch")
    if torch is None:
        return
    try:
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001 - memory reclaim is advisory
        pass


def _load(model_id: str):
    """Lazily load (processor, model), cached per id with an LRU soft cap."""
    cached = _MODEL_CACHE.get(model_id)
    if cached is not None:
        _MODEL_CACHE.move_to_end(model_id)  # mark most-recently-used
        return cached

    if model_id == _RUSSIAN_MODEL:
        # Weights-only custom-class model: no processor, decoded specially below.
        from audio import pklumpp_ctc
        processor, model = None, pklumpp_ctc.load_model()
    else:
        from transformers import AutoProcessor, AutoModelForCTC

        processor = AutoProcessor.from_pretrained(model_id)
        model = AutoModelForCTC.from_pretrained(model_id)
        model.eval()
    _MODEL_CACHE[model_id] = (processor, model)
    _MODEL_CACHE.move_to_end(model_id)
    while len(_MODEL_CACHE) > _MAX_LOADED:      # evict least-recently-used
        _MODEL_CACHE.popitem(last=False)
        _free_torch_memory()
    return processor, model


def _load_audio_16k(audio_file: str):
    """Read a WAV to mono float32 at 16 kHz (what wav2vec2 expects)."""
    import soundfile as sf

    data, sr = sf.read(audio_file)
    if getattr(data, "ndim", 1) > 1:
        data = data.mean(axis=1)
    data = data.astype("float32")
    if sr != 16000:
        import resampy

        data = resampy.resample(data, sr, 16000)
    return data


def phones_from_audio(
    audio_file: str,
    voice: str = "fr",
    warn_fn: Optional[Callable] = None,
) -> str:
    """
    Recognize IPA phones directly from an audio file (the waveform).

    Args:
        audio_file: Path to a WAV file (the trimmed user recording).
        voice: espeak voice code; selects the per-language recognizer.
        warn_fn: Optional warning callback for graceful degradation.

    Returns:
        Space-separated IPA phones (espeak-ng convention), or "" if recognition
        is unavailable / fails, letting the caller fall back gracefully.
    """
    model_id = model_for_voice(voice)
    try:
        processor, model = _load(model_id)
    except ImportError:
        if warn_fn is not None:
            warn_fn(
                "Acoustic phone recognizer needs `transformers`/`torch`; "
                "falling back to the comprehensibility (ASR-text) channel."
            )
        return ""
    except Exception as e:  # download / load failure
        if warn_fn is not None:
            warn_fn(f"Phone recognizer unavailable: {e}")
        return ""

    try:
        audio = _load_audio_16k(audio_file)
        if processor is None:                       # pklumpp custom class (ru)
            from audio import pklumpp_ctc
            text = pklumpp_ctc.decode(model, audio)
        else:
            import torch

            inputs = processor(
                audio, sampling_rate=16000, return_tensors="pt"
            ).input_values
            with torch.no_grad():
                logits = model(inputs).logits
            ids = torch.argmax(logits, dim=-1)
            text = processor.batch_decode(ids)[0]
    except Exception as e:
        if warn_fn is not None:
            warn_fn(f"Phone recognition failed: {e}")
        return ""

    # Models emit space-separated (fb) or word-grouped (Cnam) IPA; collapse to a
    # single normalized whitespace run. Phone-level segmentation/normalization
    # for scoring is handled downstream by the scorer (panphon) and ipa_norm.
    return " ".join(text.split())
