#!/usr/bin/env python3
"""
Calibrate and evaluate the sound check (src/scoring/sound_check.py) on NATIVE speech.

Per language:
  1. inventory  -- the recognizer tokens espeak produces for the language (dev texts)
  2. thresholds -- from native dev speakers: ok_threshold = the p_ok below which only
                   --check-rate of native sounds fall; off_threshold likewise --off-rate
  3. evaluation -- on native TEST speakers (different people):
       native false flags : native sounds marked "check"/"off"
       simulated errors   : the target IPA is changed to a typical English-speaker
                            substitution (english_l1_errors, e.g. German ɾ -> ɹ) while the
                            audio keeps the native sound; a good check flags the changed
                            sound. (Proxy: real learners say the English sound for the
                            German target; here the roles are swapped.)

    venv/bin/python scripts/sound_check/calibrate.py --voice de \\
        --dev cphf:/opt/cphf/dev-0.parquet:de --test cphf:/opt/cphf/test-0.parquet:de \\
        --n 400 --cache /opt/sc_cache --write --out research/phonetics/sound_check/results/de.json

Sources: cphf:<parquet>:<language> (Common Phone HF parquet) | tsv:<list.tsv>
(wav<TAB>text, wav relative to the tsv's folder).
"""

from __future__ import annotations

import argparse, io, json, os, random, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402

from scoring import sound_check as sc  # noqa: E402
from scoring.phonemes import get_ipa  # noqa: E402

OUT_YAML = ROOT / "src" / "scoring" / "data" / "sound_check_calibrated.yaml"


def items(spec: str, n: int, seed: int = 0):
    kind, rest = spec.split(":", 1)
    rows = []
    if kind == "cphf":
        import pyarrow.parquet as pq
        path, lang = rest.rsplit(":", 1)
        t = pq.read_table(path, columns=["language", "text", "audio"])
        for r in t.to_pylist():
            if r["language"] == lang:
                rows.append((r["audio"]["path"] or str(len(rows)), r["text"], r["audio"]["bytes"]))
    elif kind == "tsv":
        base = Path(rest).parent
        for line in open(rest, encoding="utf-8"):
            wav, text = line.rstrip("\n").split("\t")[:2]
            rows.append((wav, text, base / wav))
    random.Random(seed).shuffle(rows)
    return rows[:n]


def audio_of(src):
    x, sr = sf.read(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else str(src))
    if x.ndim > 1:
        x = x.mean(1)
    if sr != 16000:
        import resampy
        x = resampy.resample(x, sr, 16000)
    return x.astype(np.float32)


class Rec:
    def __init__(self, voice, cache):
        from audio import phone_recognizer as pr
        self.model_id = pr.model_for_voice(voice)
        self.proc, self.model = pr._load(self.model_id)
        tok = self.proc.tokenizer
        self.vocab, self.blank = tok.get_vocab(), tok.pad_token_id
        self.cache = Path(cache) / self.model_id.replace("/", "_") if cache else None
        if self.cache:
            self.cache.mkdir(parents=True, exist_ok=True)

    def lp(self, key, src):
        f = self.cache / (str(abs(hash(key)) if False else Path(str(key)).stem) + ".npy") if self.cache else None
        if f is not None and f.exists():
            return torch.from_numpy(np.load(f).astype(np.float32))
        x = audio_of(src)
        inp = self.proc(x, sampling_rate=16000, return_tensors="pt").input_values
        with torch.no_grad():
            lp = torch.log_softmax(self.model(inp).logits[0].float(), -1)
        if f is not None:
            np.save(f, lp.numpy().astype(np.float16))
        return lp


def collect(rec, rows, voice, ipas):
    out = []
    for (key, text, src) in rows:
        ipa = ipas.get(text) or get_ipa(text, voice)
        ipas[text] = ipa
        if not ipa.strip():
            continue
        out.append((key, text, ipa, rec.lp(key, src)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", required=True)
    ap.add_argument("--dev", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--cache")
    ap.add_argument("--check-rate", type=float, default=0.08)
    ap.add_argument("--off-rate", type=float, default=0.02)
    ap.add_argument("--min-count", type=int, default=3)
    ap.add_argument("--accept-weight", type=float, default=0.7)
    ap.add_argument("--accept-rate", type=float, default=0.10,
                    help="auto-accept a variant natives produce for >= this share of a sound")
    ap.add_argument("--min-off", type=float, default=0.02, help="floor for off_threshold")
    ap.add_argument("--write", action="store_true", help="update sound_check_calibrated.yaml")
    ap.add_argument("--out")
    a = ap.parse_args()
    v = a.voice
    rec = Rec(v, a.cache)
    ipas: dict = {}
    dev = collect(rec, items(a.dev, a.n), v, ipas)
    test = collect(rec, items(a.test, a.n, seed=1), v, ipas)

    # 1. inventory from dev texts
    cnt = Counter(t for _, _, ipa, _ in dev for t, _ in sc.tokenize(ipa, rec.vocab))
    inventory = sorted(t for t, c in cnt.items() if c >= a.min_count)

    def run(data, cfg_over, ipa_of=lambda ipa: ipa):
        base = sc.lang_config(v)
        cfg = {**base, **cfg_over}
        orig = sc.lang_config
        sc.lang_config = lambda _v: cfg
        try:
            return [sc.score(lp, rec.vocab, rec.blank, ipa_of(ipa), v, rec.model_id) for _, _, ipa, lp in data]
        finally:
            sc.lang_config = orig

    # 2a. learned acceptance: what natives regularly produce for an expected sound is
    #     accepted -- except the known English-speaker errors (never auto-accepted)
    probe = {"inventory": inventory, "ok_threshold": 0.5, "off_threshold": 0.0}
    banned = {tuple(e) for e in (sc.lang_config(v).get("english_l1_errors") or [])}
    tot, alt = Counter(), Counter()
    for r in run(dev, probe):
        for p in r.phones:
            tot[p.phone] += 1
            if p.p_ok < 0.5 and p.heard:
                alt[(p.phone, p.heard)] += 1
    learned = {}
    for (e, h), c in alt.items():
        if (c >= a.min_count and c / tot[e] >= a.accept_rate and (e, h) not in banned
                and h != sc.DEL):                 # omissions: hand-written lists only
            learned.setdefault(e, {})[h] = a.accept_weight
    hand = sc.lang_config(v).get("accept") or {}
    acc = {k: dict(d) for k, d in learned.items()}
    for k, d in hand.items():
        acc.setdefault(k, {}).update(d)

    # 2b. thresholds from native dev, with the learned acceptance applied
    probe = {**probe, "accept": acc, "ok_threshold": 0.0}
    p_dev = np.array([p.p_ok for r in run(dev, probe) for p in r.phones])
    ok_t = float(np.quantile(p_dev, a.check_rate))
    off_t = float(np.quantile(p_dev, a.off_rate))
    off_t = max(off_t, a.min_off)
    cal = {"inventory": inventory, "ok_threshold": round(ok_t, 4), "off_threshold": round(off_t, 4),
           "accept_learned": learned}
    cal_run = {**cal, "accept": acc}

    # 3. evaluation on native test
    res_test = run(test, cal_run)
    lv = Counter(p.level for r in res_test for p in r.phones)
    nph = sum(lv.values())
    per_phone = Counter(); per_phone_flag = Counter()
    for r in res_test:
        for p in r.phones:
            per_phone[p.phone] += 1; per_phone_flag[p.phone] += p.level != "ok"
    worst = sorted(((p, round(per_phone_flag[p] / per_phone[p], 3), per_phone[p])
                    for p in per_phone if per_phone[p] >= 20), key=lambda x: -x[1])[:10]

    sim = {}
    for exp, said in (sc.lang_config(v).get("english_l1_errors") or []):
        if exp not in rec.vocab or said not in rec.vocab:
            sim[f"{exp}->{said}"] = "token not in recognizer vocab"; continue
        flags, n = Counter(), 0
        heard_ok = 0
        for _, _, ipa, lp in test:
            toks = sc.tokenize(ipa, rec.vocab)
            pos = [i for i, (t, _) in enumerate(toks) if t == exp]
            if not pos:
                continue
            i = pos[0]
            # rebuild IPA with one substituted token (word structure kept)
            words = [[] for _ in ipa.split()]
            for k, (t, wi) in enumerate(toks):
                words[wi].append(said if k == i else t)
            new_ipa = " ".join("".join(w) for w in words if w)
            r = run([(None, None, new_ipa, lp)], cal_run)[0]
            ph = [p for p in r.phones if p.phone == said]
            if not ph:
                continue
            # the substituted phone is the first `said` at/after position i (approx.)
            p = min(ph, key=lambda q: abs(r.phones.index(q) - i))
            flags[p.level] += 1; n += 1
            heard_ok += p.heard == exp
            if n >= 150:
                break
        if n:
            sim[f"{exp}->{said}"] = {"n": n, "flagged": round((flags["check"] + flags["off"]) / n, 3),
                                    "off": round(flags["off"] / n, 3),
                                    "heard_the_native_sound": round(heard_ok / n, 3)}
    report = {"voice": v, "model": rec.model_id, "n_dev_utts": len(dev), "n_test_utts": len(test),
              "calibration": {k: cal[k] for k in ("ok_threshold", "off_threshold")},
              "inventory_size": len(inventory), "accept_learned": learned,
              "native_test": {"phones": nph, "check": round(lv["check"] / nph, 4), "off": round(lv["off"] / nph, 4),
                              "most_flagged_sounds": [{"sound": p, "flagged": f, "n": n} for p, f, n in worst]},
              "simulated_english_speaker_errors": sim}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.write:
        doc = yaml.safe_load(OUT_YAML.read_text(encoding="utf-8")) if OUT_YAML.exists() else {}
        doc = doc or {}
        doc.setdefault("languages", {})[v] = {**cal, "calibrated_on": f"{a.dev} (n={len(dev)})", "model": rec.model_id,
                                              "native_test_flag_rate": round((lv["check"] + lv["off"]) / nph, 4)}
        OUT_YAML.write_text("# GENERATED by scripts/sound_check/calibrate.py -- do not edit by hand.\n"
                            + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()
