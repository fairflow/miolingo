#!/usr/bin/env python3
"""
Benchmark two phone-level recognizers against the synthesized ground-truth corpus.

Models:
  1. facebook/wav2vec2-lv-60-espeak-cv-ft  (transformers) -> eSpeak-style phones,
     with CTC posteriors for a confidence/abstention signal.
  2. allosaurus                            -> universal IPA phones.

Metrics:
  - PER (phone-level Levenshtein) vs espeak reference IPA, for CORRECT items.
  - Error detection: for "error" items, does recognizer output match the SPOKEN
    (mispronounced) phones rather than the INTENDED ones? i.e. PER(rec, intended)
    should be HIGH and the per-item diff should localize the injected error.
  - False alarm: for "correct" items, PER should be LOW.
  - Confidence: wav2vec2 mean/min CTC posterior; allosaurus emit -> per-phone notes.

Run: python bench.py   (loads corpus.json, writes results/results.json + prints table)
"""
import json
import os
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
os.makedirs(RESULTS, exist_ok=True)


# --------------------------------------------------------------------------
# Phone normalization + edit distance
# --------------------------------------------------------------------------
def strip_diacritics(s):
    """Drop combining marks (stress, length, nasal tie) for a lenient compare,
    but KEEP nasalization-relevant base chars. We keep base letters only."""
    # Decompose; drop combining marks.
    out = []
    for ch in unicodedata.normalize("NFD", s):
        if unicodedata.combining(ch):
            continue
        out.append(ch)
    return "".join(out)


def norm_phone(p, strip=True):
    p = p.replace("ˈ", "").replace("ˌ", "").replace("ː", "").replace("ˑ", "")
    p = p.replace("ʰ", "")  # aspiration
    if strip:
        p = strip_diacritics(p)
    return p


def levenshtein(a, b):
    """Token-level Levenshtein with backtrace; returns (dist, ops) where ops is
    list of ('=',x)/('sub',x,y)/('del',x)/('ins',y)."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1,
                           dp[i - 1][j - 1] + cost)
    # backtrace
    i, j, ops = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + (0 if a[i - 1] == b[j - 1] else 1):
            if a[i - 1] == b[j - 1]:
                ops.append(("=", a[i - 1]))
            else:
                ops.append(("sub", a[i - 1], b[j - 1]))
            i -= 1; j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(("del", a[i - 1])); i -= 1
        else:
            ops.append(("ins", b[j - 1])); j -= 1
    ops.reverse()
    return dp[n][m], ops


def per(ref, hyp, strip=True):
    r = [norm_phone(p, strip) for p in ref if norm_phone(p, strip)]
    h = [norm_phone(p, strip) for p in hyp if norm_phone(p, strip)]
    if not r:
        return (0.0 if not h else 1.0), []
    d, ops = levenshtein(r, h)
    return d / len(r), ops


# --------------------------------------------------------------------------
# Model wrappers
# --------------------------------------------------------------------------
def run_wav2vec2(corpus):
    import torch
    import soundfile as sf
    from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC

    name = "facebook/wav2vec2-lv-60-espeak-cv-ft"
    t0 = time.time()
    processor = Wav2Vec2Processor.from_pretrained(name)
    model = Wav2Vec2ForCTC.from_pretrained(name)
    model.eval()
    load_t = time.time() - t0

    out = {}
    for it in corpus:
        speech, sr = sf.read(it["wav16"])
        assert sr == 16000
        inputs = processor(speech, sampling_rate=16000, return_tensors="pt", padding=True)
        t = time.time()
        with torch.no_grad():
            logits = model(inputs.input_values).logits  # [1, T, V]
        infer_t = time.time() - t
        probs = torch.softmax(logits, dim=-1)
        ids = torch.argmax(logits, dim=-1)[0]            # [T]
        conf_frames = probs.max(dim=-1).values[0]        # [T] top posterior/frame

        # Decode to phone string (CTC collapse done by tokenizer)
        phone_str = processor.batch_decode(ids.unsqueeze(0))[0]
        phones = phone_str.split()

        # Confidence on NON-blank emitting frames (frames whose argmax != pad/blank)
        blank_id = model.config.pad_token_id
        emit_mask = ids != blank_id
        if emit_mask.any():
            emit_conf = conf_frames[emit_mask]
            mean_conf = float(emit_conf.mean())
            min_conf = float(emit_conf.min())
        else:
            mean_conf = min_conf = 0.0

        out[it["id"]] = dict(phones=phones, phone_str=phone_str,
                             mean_conf=mean_conf, min_conf=min_conf,
                             n_frames=int(logits.shape[1]),
                             infer_t=infer_t)
    return out, load_t, name


def run_allosaurus(corpus):
    from allosaurus.app import read_recognizer
    t0 = time.time()
    model = read_recognizer()  # default 'latest' universal model
    load_t = time.time() - t0
    out = {}
    for it in corpus:
        # allosaurus accepts a language id; use 'ipa' (universal) for fairness,
        # but also try language-specific inventory.
        lang = {"pt-pt": "por", "pt-br": "por", "fr-fr": "fra"}.get(it["voice"], "ipa")
        t = time.time()
        try:
            res = model.recognize(it["wav16"], lang)
        except Exception as e:
            res = ""
        infer_t = time.time() - t
        phones = res.split()
        out[it["id"]] = dict(phones=phones, phone_str=res, infer_t=infer_t, lang=lang)
    return out, load_t, "allosaurus(latest)"


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------
def evaluate(corpus, model_out, model_name):
    rows = []
    correct_pers = []
    for it in corpus:
        mo = model_out[it["id"]]
        # PER vs INTENDED reference (what the learner aimed for)
        p_intended, ops_int = per(it["ref_phones"], mo["phones"])
        # PER vs SPOKEN ipa (what was actually synthesized)
        p_spoken, _ = per(it["spoken_phones"], mo["phones"])
        row = dict(
            id=it["id"], kind=it["kind"], voice=it["voice"],
            ref="/" + " ".join(it["ref_phones"]) + "/",
            spoken_ipa="/" + " ".join(it["spoken_phones"]) + "/",
            hyp="/" + " ".join(mo["phones"]) + "/",
            per_vs_intended=round(p_intended, 3),
            per_vs_spoken=round(p_spoken, 3),
        )
        if "mean_conf" in mo:
            row["mean_conf"] = round(mo["mean_conf"], 3)
            row["min_conf"] = round(mo["min_conf"], 3)
        if it["kind"] == "correct":
            correct_pers.append(p_intended)
        rows.append(row)
    avg_correct_per = sum(correct_pers) / len(correct_pers) if correct_pers else None
    return rows, avg_correct_per


def main():
    corpus = json.load(open(os.path.join(HERE, "corpus.json")))
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    all_results = {}

    if which in ("both", "w2v"):
        try:
            mo, load_t, name = run_wav2vec2(corpus)
            rows, avg = evaluate(corpus, mo, name)
            all_results["wav2vec2"] = dict(name=name, load_t=load_t,
                                           avg_correct_per=avg, rows=rows)
            print(f"\n### {name}  (load {load_t:.1f}s, avg correct PER={avg:.3f})")
        except Exception as e:
            import traceback; traceback.print_exc()
            all_results["wav2vec2"] = dict(error=str(e))

    if which in ("both", "allo"):
        try:
            mo, load_t, name = run_allosaurus(corpus)
            rows, avg = evaluate(corpus, mo, name)
            all_results["allosaurus"] = dict(name=name, load_t=load_t,
                                             avg_correct_per=avg, rows=rows)
            print(f"\n### {name}  (load {load_t:.1f}s, avg correct PER={avg:.3f})")
        except Exception as e:
            import traceback; traceback.print_exc()
            all_results["allosaurus"] = dict(error=str(e))

    with open(os.path.join(RESULTS, "results.json"), "w") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # Pretty print tables
    for mk, mv in all_results.items():
        if "rows" not in mv:
            print(f"\n[{mk}] FAILED: {mv.get('error')}")
            continue
        print(f"\n===== {mk}: {mv['name']} =====")
        for r in mv["rows"]:
            cf = ""
            if "mean_conf" in r:
                cf = f" conf(mean/min)={r['mean_conf']}/{r['min_conf']}"
            print(f"{r['id']:22s}[{r['kind']:7s}] PERvsIntended={r['per_vs_intended']:.2f} "
                  f"PERvsSpoken={r['per_vs_spoken']:.2f}{cf}")
            print(f"    ref     {r['ref']}")
            print(f"    spokenIP{r['spoken_ipa']}")
            print(f"    hyp     {r['hyp']}")
    print("\nWrote results/results.json")


if __name__ == "__main__":
    main()
