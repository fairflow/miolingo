"""
Loader/decoder for pklumpp/Wav2Vec2_CommonPhone — the Russian A2P specialist
(miolingo-dky; benched 0.073 weighted err vs the fallback's 0.133 on Common Phone
Russian, ~1.9x better).

The HF repo ships WEIGHTS ONLY (no processor/tokenizer/vocab) and is NOT a
Wav2Vec2ForCTC, so it can't load via AutoModelForCTC like the other recognizers.
It is the author's custom class (github.com/PKlumpp/phd_model): a HF Wav2Vec2Model
(xlsr-53) + Linear(1024, 102) CTC head, blank index 0, over 101 IPA symbols. We
vendor the tiny class + the exact vocab so it runs with no extra deps.

Two requirements from the author's example.py:
  - input audio must be STANDARDIZED (zero mean, unit std), NOT run through a
    Wav2Vec2 feature extractor;
  - CTC blank is index 0; decode is greedy argmax + collapse repeats + drop blank.
The "(...)" placeholder (id 49) is dropped as a non-phone token.

Licence: model is CC0-1.0; vocab + class transcribed from the author's CC0 repo.
"""
from __future__ import annotations

HF_ID = "pklumpp/Wav2Vec2_CommonPhone"

# id -> IPA symbol (blank = 0). From phd_model/phonetics/ipa.py SYMBOLS, inverted.
_SYMBOLS = {
    "r": 1, "ʝ": 2, "ã": 3, "gː": 4, "t": 5, "n": 6, "w": 7, "u": 8, "l": 9,
    "yː": 10, "ʎ": 11, "bʲ": 12, "ə": 13, "ʃʲ": 14, "sː": 15, "zʲ": 16, "kː": 17,
    "y": 18, "ɒ": 19, "fʲ": 20, "ɑ": 21, "ʏ": 22, "ɣ": 23, "s": 24, "m": 25,
    "tː": 26, "xʲ": 27, "vː": 28, "ø": 29, "h": 30, "ɨ": 31, "dʲ": 32, "dː": 33,
    "bː": 34, "ɲː": 35, "ɑː": 36, "ɪ": 37, "ɛ": 38, "i": 39, "ʔ": 40, "g": 41,
    "ʃ": 42, "ɜː": 43, "mː": 44, "øː": 45, "fː": 46, "p": 47, "iː": 48, "(...)": 49,
    "v": 50, "ʌ": 51, "b": 52, "k": 53, "x": 54, "ɲ": 55, "ʒ": 56, "rː": 57,
    "eː": 58, "ç": 59, "ŋ": 60, "ɔː": 61, "œ": 62, "ẽ": 63, "θ": 64, "a": 65,
    "rʲ": 66, "vʲ": 67, "ʃː": 68, "æ": 69, "ɶ̃": 70, "pː": 71, "nː": 72, "lʲ": 73,
    "õ": 74, "pʲ": 75, "ɱ": 76, "ð": 77, "f": 78, "j": 79, "o": 80, "nʲ": 81,
    "sʲ": 82, "lː": 83, "e": 84, "d": 85, "ʊ": 86, "gʲ": 87, "z": 88, "ɛː": 89,
    "tʲ": 90, "β": 91, "mʲ": 92, "uː": 93, "ɥ": 94, "ʀ": 95, "aː": 96, "ɐ": 97,
    "ɔ": 98, "oː": 99, "ʎː": 100, "kʲ": 101,
}
_ID_TO_SYMBOL = {i: s for s, i in _SYMBOLS.items()}
_SKIP = {0, 49}  # blank + "(...)" placeholder


def load_model():
    """Instantiate the vendored class and load the safetensors weights directly.

    from_pretrained() breaks on newer transformers (the class predates
    `all_tied_weights_keys`), so we load the state dict by hand -- keys are
    `wav2vec.*` / `linear.*`, matching the class attributes.
    """
    import torch.nn as nn
    from transformers import (Wav2Vec2Model, Wav2Vec2Config, PreTrainedModel,
                              PretrainedConfig)
    from huggingface_hub import hf_hub_download
    from safetensors.torch import load_file

    class _Config(PretrainedConfig):
        model_type = "wav2vec2"

        def __init__(self, n_classes: int = 102, **kwargs):
            self.n_classes = n_classes
            super().__init__(**kwargs)

    class _Wav2Vec2(PreTrainedModel):
        config_class = _Config

        def __init__(self, config):
            super().__init__(config)
            self.wav2vec = Wav2Vec2Model(
                Wav2Vec2Config.from_pretrained("facebook/wav2vec2-large-xlsr-53"))
            self.linear = nn.Linear(in_features=1024, out_features=config.n_classes)

        def forward(self, x):
            x = self.wav2vec(x)
            return self.linear(x.last_hidden_state)

    model = _Wav2Vec2(_Config(n_classes=102))
    sd = load_file(hf_hub_download(HF_ID, "model.safetensors"))
    missing, _ = model.load_state_dict(sd, strict=False)
    if [k for k in missing if k.startswith("linear.")]:
        raise RuntimeError("pklumpp head weights missing")
    model.eval()
    return model


def decode(model, audio_16k) -> str:
    """Standardized-audio -> space-separated IPA via greedy CTC (blank=0)."""
    import numpy as np
    import torch

    a = np.asarray(audio_16k, dtype="float32")
    a = (a - a.mean()) / (a.std() + 1e-9)                # standardize (required)
    x = torch.tensor(a, dtype=torch.float).unsqueeze(0)  # (1, T)
    with torch.no_grad():
        logits = model(x)                                # (1, T, 102)
    ids = torch.argmax(logits[0], dim=-1).tolist()
    out, prev = [], None
    for i in ids:                                        # collapse + drop skips
        if i != prev and i not in _SKIP:
            out.append(_ID_TO_SYMBOL.get(i, ""))
        prev = i
    return " ".join(s for s in out if s)
