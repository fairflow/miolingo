#!/usr/bin/env python3
"""
Common Phone bake-off: score phone recognizers on REAL audio with the app's
own weighted_phone metric (miolingo-2yv, feeds decision gate miolingo-0x9).

Unlike the older bench.py (synthetic espeak audio, plain Levenshtein), this runs
on the Common Phone corpus (real Mozilla Common Voice speech) and scores each
recognizer's audio-derived IPA against an espeak-G2P reference using
src/scoring/phone_distance.score (panphon feature distance + fold-map), i.e. the
SAME metric the shipped app uses. Weighted error = 1 - similarity.

Reference choice: espeak-G2P of the transcript text (same IPA convention as the
recognizers; matches the prior 0x9 re-scoring so numbers stay comparable). The
Common Phone TextGrid gold (MAU tier) is a truer phonetic reference but lives in
a different symbol set and is left as a future refinement.

Models (all emit espeak-convention IPA from the waveform via wav2vec2 CTC):
  fb      facebook/wav2vec2-lv-60-espeak-cv-ft   (current multilingual fallback)
  cnam    Cnam-LMSSC/wav2vec2-french-phonemizer  (French specialist, shipped)
  pklumpp pklumpp/Wav2Vec2_CommonPhone           (XLSR-53, CP-trained, 9.2% avg PER)
ZIPA is deliberately NOT here: it is Zipformer/k2 (not AutoModelForCTC) and its
shipped-weight licence is undeclared -- a separate spike + licence clearance.

Usage:
  venv/bin/python research/phonetics/phone_poc/cp_eval.py --n 150 [--lang fr] \
      [--models fb,cnam,pklumpp] [--cp-root ~/datasets/common_phone/CP]
Writes results/cp_eval_<lang>.json and prints a table.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]                       # research/phonetics/phone_poc -> repo
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "src"))        # import the app's own modules

# App modules (reused so the bake-off measures exactly what the app measures).
from audio import phone_recognizer as pr     # noqa: E402  (_load, _load_audio_16k)
from scoring.phonemes import get_ipa         # noqa: E402  espeak G2P reference
from scoring.phone_distance import score     # noqa: E402  weighted_phone metric

# Recognizer registry: label -> HuggingFace CTC model id.
MODELS = {
    "fb": "facebook/wav2vec2-lv-60-espeak-cv-ft",
    "cnam": "Cnam-LMSSC/wav2vec2-french-phonemizer",
    # pklumpp ships WEIGHTS ONLY (no processor/tokenizer/vocab in the HF repo), so
    # AutoProcessor.from_pretrained fails. Decoding its CTC output needs the
    # author's exact 101-IPA-symbol vocab + a hand-built Wav2Vec2Processor -- see
    # follow-up bead. Left registered so the harness records the blocker.
    "pklumpp": "pklumpp/Wav2Vec2_CommonPhone",
}


def recognize(model_id: str, wav_path: str) -> str:
    """Audio -> space-separated IPA via the app's loader + CTC argmax decode."""
    import torch

    processor, model = pr._load(model_id)
    audio = pr._load_audio_16k(wav_path)
    inputs = processor(audio, sampling_rate=16000, return_tensors="pt").input_values
    with torch.no_grad():
        logits = model(inputs).logits
    ids = torch.argmax(logits, dim=-1)
    text = processor.batch_decode(ids)[0]
    return " ".join(text.split())


def load_items(cp_lang_dir: Path, split: str, n: int) -> list[dict]:
    """First n rows of <split>.csv paired with their wav/<stem>.wav path."""
    items, csv_path = [], cp_lang_dir / f"{split}.csv"
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stem = Path(row["audio file"]).stem
            wav = cp_lang_dir / "wav" / f"{stem}.wav"
            if wav.exists():
                items.append({"wav": str(wav), "text": row["text"]})
            if len(items) >= n:
                break
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--lang", default="fr")
    ap.add_argument("--split", default="test")
    ap.add_argument("--models", default="fb,cnam,pklumpp")
    ap.add_argument("--cp-root", default=str(Path.home() / "datasets/common_phone/CP"))
    args = ap.parse_args()

    cp_lang_dir = Path(os.path.expanduser(args.cp_root)) / args.lang
    if not cp_lang_dir.exists():
        sys.exit(f"Common Phone lang dir not found: {cp_lang_dir}")
    wanted = [m.strip() for m in args.models.split(",") if m.strip()]
    for m in wanted:
        if m not in MODELS:
            sys.exit(f"unknown model {m!r}; known: {sorted(MODELS)}")

    items = load_items(cp_lang_dir, args.split, args.n)
    print(f"Loaded {len(items)} {args.lang}/{args.split} utterances from {cp_lang_dir}")

    # espeak-G2P reference IPA per item (voice = lang; fr for French).
    for it in items:
        it["ref_ipa"] = get_ipa(it["text"], args.lang)

    summary = {}
    for label in wanted:
        model_id = MODELS[label]
        print(f"\n=== {label} ({model_id}) ===")
        t0, werr, fails, last_err = time.time(), [], 0, None
        for i, it in enumerate(items, 1):
            try:
                hyp = recognize(model_id, it["wav"])
            except Exception as e:  # noqa: BLE001 - record and continue
                fails += 1
                last_err = str(e)
                if fails <= 3:
                    print(f"  ! {Path(it['wav']).name}: {e}")
                continue
            r = score(hyp, it["ref_ipa"], args.lang)
            werr.append(1.0 - r.similarity)
            if i % 25 == 0:
                print(f"  {i}/{len(items)} mean_werr={sum(werr)/len(werr):.4f}")
        n_ok = len(werr)
        mean_werr = round(sum(werr) / n_ok, 4) if n_ok else None
        rec = {
            "model_id": model_id,
            "n_scored": n_ok,
            "n_failed": fails,
            "mean_weighted_error": mean_werr,
            "load_and_run_s": round(time.time() - t0, 1),
        }
        if mean_werr is None:
            rec["error"] = last_err
        summary[label] = rec
        print(f"  -> mean_weighted_error={mean_werr}  ({n_ok} ok, {fails} failed)")

    out = {
        "corpus": "common_phone",
        "lang": args.lang,
        "split": args.split,
        "n_requested": args.n,
        "n_items": len(items),
        "reference": "espeak-G2P of transcript (weighted_phone metric)",
        "metric": "mean 1 - phone_distance.similarity",
        "results": summary,
    }
    out_path = RESULTS / f"cp_eval_{args.lang}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"\nwrote {out_path}")
    print("\nRANKING (lower = better):")
    ranked = sorted(summary.items(),
                    key=lambda kv: (kv[1]["mean_weighted_error"] is None,
                                    kv[1]["mean_weighted_error"] or 0.0))
    for label, r in ranked:
        val = r["mean_weighted_error"]
        cell = f"{val:.4f}" if val is not None else f"FAILED ({r.get('error','')[:40]})"
        print(f"  {label:8} {cell}  ({r['model_id']})")


if __name__ == "__main__":
    main()
