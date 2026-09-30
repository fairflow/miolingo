"""
Source 2 (HANDOFF §1b): an approved per-language recognition model used as
CONSTRAINED recognition inside an aligned segment -- not as an open recogniser.

The CTC model runs once over the whole utterance (context helps), then for each
target segment we read the frame posteriors inside the aligned window and
compare only the candidate phones. Candidates the model's vocabulary cannot
name are reported as `unsupported` (so the combination knows this source is
blind to them), never silently scored as zero.

Reuses the app's loader (audio.phone_recognizer._load / _load_audio_16k) so the
LRU cache and model lifecycle are shared with the accuracy channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from realised_phone.inventory import norm_ipa

# wav2vec2 CTC: 20 ms per frame (320-sample stride at 16 kHz)
FRAME_S = 0.02


@dataclass
class Posteriors:
    probs: np.ndarray            # (T, V) softmax
    vocab: dict[str, int]        # IPA token -> column
    frame_s: float = FRAME_S


def ctc_posteriors(model_id: str, wav_path: str) -> Posteriors:
    """Frame posteriors from a HF phoneme-CTC model (needs transformers/torch)."""
    import torch
    from audio.phone_recognizer import _load, _load_audio_16k

    processor, model = _load(model_id)
    if processor is None:
        raise NotImplementedError(f"{model_id}: custom-class model, no processor vocab")
    audio = _load_audio_16k(wav_path)
    inputs = processor(audio, sampling_rate=16000, return_tensors="pt").input_values
    with torch.no_grad():
        logits = model(inputs).logits[0]
    probs = torch.softmax(logits, dim=-1).numpy()
    vocab = {norm_ipa(tok): i for tok, i in processor.tokenizer.get_vocab().items()}
    return Posteriors(probs=probs, vocab=vocab)


def candidate_scores(post: Posteriors, window: tuple[float, float],
                     candidates: list[str], top_k: int = 3) -> tuple[dict[str, float], list[str]]:
    """Mean of the top-k frame posteriors for each nameable candidate in the window.
    Returns (scores, unsupported)."""
    s = max(0, int(window[0] / post.frame_s))
    e = min(len(post.probs), max(s + 1, int(np.ceil(window[1] / post.frame_s))))
    seg = post.probs[s:e]
    scores, unsupported = {}, []
    for c in candidates:
        col = post.vocab.get(norm_ipa(c))
        if col is None:
            unsupported.append(c)
            continue
        col_vals = np.sort(seg[:, col])[::-1][:top_k] if len(seg) else np.zeros(1)
        scores[c] = float(col_vals.mean())
    return scores, unsupported


class RecognizerSource:
    """Caches posteriors per wav so every target segment reuses one forward pass."""

    def __init__(self, model_id: str, hf_model: str,
                 posterior_fn: Optional[Callable[[str, str], Posteriors]] = None):
        self.model_id = model_id          # registry id
        self.hf_model = hf_model          # HF model id (registry `version`)
        self._fn = posterior_fn or ctc_posteriors
        self._cache: dict[str, Posteriors] = {}

    def posteriors(self, wav_path: str) -> Posteriors:
        if wav_path not in self._cache:
            self._cache[wav_path] = self._fn(self.hf_model, wav_path)
        return self._cache[wav_path]
