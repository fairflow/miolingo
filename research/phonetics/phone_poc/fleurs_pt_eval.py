#!/usr/bin/env python3
"""
pt-BR A2P bake-off on FLEURS (miolingo-0x9, sweep 2026-07-07).

Common Phone has NO Portuguese, so the CP harness (cp_eval.py) can't score pt-BR.
FLEURS (google/fleurs, config 'pt_br') is a small CC-BY Brazilian-Portuguese
read-speech test set with transcripts -> a relative fb-vs-specialist harness until
a truer BR gold (CORAA / UFPAlign) is stood up.

Same metric as cp_eval: audio-derived IPA vs espeak-G2P('pt-br') reference, scored
with src/scoring/phone_distance.score (weighted_phone). Weighted error = 1 - sim.

Models:
  fb             facebook/wav2vec2-lv-60-espeak-cv-ft   (multilingual fallback)
  fb-xlsr        facebook/wav2vec2-xlsr-53-espeak-cv-ft  (fallback A/B candidate)
  caiocrocha-pt  caiocrocha/wav2vec2-large-xlsr-53-phoneme-portuguese (BR specialist)

Note: caiocrocha emits its own 42-symbol BR IPA inventory (not espeak convention);
scoring runs on panphon feature distance, so this is a fair *relative* ranking but
a symbol map could sharpen the absolute numbers.

Usage:
  venv/bin/python research/phonetics/phone_poc/fleurs_pt_eval.py --n 150 \
      [--models fb,fb-xlsr,caiocrocha-pt]
Writes results/fleurs_pt_br.json and prints a ranking.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "src"))

from audio import phone_recognizer as pr     # noqa: E402
from scoring.phonemes import get_ipa         # noqa: E402
from scoring.phone_distance import score     # noqa: E402

MODELS = {
    "fb": "facebook/wav2vec2-lv-60-espeak-cv-ft",
    "fb-xlsr": "facebook/wav2vec2-xlsr-53-espeak-cv-ft",
    "caiocrocha-pt": "caiocrocha/wav2vec2-large-xlsr-53-phoneme-portuguese",
    "clementapa-nl": "Clementapa/wav2vec2-base-960h-phoneme-reco-dutch",
}


def recognize_array(model_id: str, audio, sr: int) -> str:
    """Audio array -> space-separated IPA via the app loader + CTC argmax decode."""
    import torch

    processor, model = pr._load(model_id)
    if sr != 16000:  # FLEURS is 16k, but stay safe
        import librosa
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    inputs = processor(audio, sampling_rate=16000, return_tensors="pt").input_values
    with torch.no_grad():
        logits = model(inputs).logits
    ids = torch.argmax(logits, dim=-1)
    text = processor.batch_decode(ids)[0]
    return " ".join(text.split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--models", default="fb,fb-xlsr,caiocrocha-pt")
    ap.add_argument("--config", default="pt_br", help="FLEURS config, e.g. pt_br, nl_nl")
    ap.add_argument("--lang", default="pt-br", help="espeak voice for ref/scoring")
    args = ap.parse_args()
    LANG = args.lang

    wanted = [m.strip() for m in args.models.split(",") if m.strip()]
    for m in wanted:
        if m not in MODELS:
            sys.exit(f"unknown model {m!r}; known: {sorted(MODELS)}")

    import io
    import soundfile as sf
    from datasets import load_dataset, Audio
    print(f"Loading FLEURS {args.config} test split ...")
    # decode=False -> avoid datasets' torchcodec dependency; decode wav bytes with
    # soundfile (already a project dep). FLEURS ships 16kHz mono wav.
    ds = load_dataset("google/fleurs", args.config, split="test").cast_column(
        "audio", Audio(decode=False))
    items = []
    for row in ds:
        a = row["audio"]
        data = a["bytes"] if a.get("bytes") else Path(a["path"]).read_bytes()
        audio, sr = sf.read(io.BytesIO(data), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        items.append({"audio": audio, "sr": sr, "text": row["transcription"]})
        if len(items) >= args.n:
            break
    print(f"Loaded {len(items)} pt_br utterances")

    for it in items:
        it["ref_ipa"] = get_ipa(it["text"], LANG)

    summary = {}
    for label in wanted:
        model_id = MODELS[label]
        print(f"\n=== {label} ({model_id}) ===")
        t0, werr, fails, last_err = time.time(), [], 0, None
        for i, it in enumerate(items, 1):
            try:
                hyp = recognize_array(model_id, it["audio"], it["sr"])
            except Exception as e:  # noqa: BLE001
                fails += 1
                last_err = str(e)
                if fails <= 3:
                    print(f"  ! item {i}: {e}")
                continue
            r = score(hyp, it["ref_ipa"], LANG)
            werr.append(1.0 - r.similarity)
            if i % 25 == 0:
                print(f"  {i}/{len(items)} mean_werr={sum(werr)/len(werr):.4f}")
        n_ok = len(werr)
        mean_werr = round(sum(werr) / n_ok, 4) if n_ok else None
        rec = {"model_id": model_id, "n_scored": n_ok, "n_failed": fails,
               "mean_weighted_error": mean_werr,
               "load_and_run_s": round(time.time() - t0, 1)}
        if mean_werr is None:
            rec["error"] = last_err
        summary[label] = rec
        print(f"  -> mean_weighted_error={mean_werr}  ({n_ok} ok, {fails} failed)")

    out = {"corpus": "fleurs", "lang": LANG, "split": "test",
           "n_requested": args.n, "n_items": len(items),
           "reference": f"espeak-G2P('{LANG}') of transcript (weighted_phone metric)",
           "metric": "mean 1 - phone_distance.similarity", "results": summary}
    out_path = RESULTS / f"fleurs_{LANG.replace('-', '_')}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"\nwrote {out_path}")
    print("\nRANKING (lower = better):")
    ranked = sorted(summary.items(),
                    key=lambda kv: (kv[1]["mean_weighted_error"] is None,
                                    kv[1]["mean_weighted_error"] or 0.0))
    for label, r in ranked:
        val = r["mean_weighted_error"]
        cell = f"{val:.4f}" if val is not None else f"FAILED ({r.get('error','')[:40]})"
        print(f"  {label:14} {cell}  ({r['model_id']})")


if __name__ == "__main__":
    main()
