"""Fill the Whisper cache for a list of jobs.

    <miolingo venv python> -m lab.whisper_run --jobs var/lab/jobs/whisper.jsonl [--shard K/N] [--threads T]

A job line: {"wav": path, "lang": "de", "prompts": [text, ...], "tf": [text, ...]}.  For each wav:

  free      `env.hearing.transcribe(wav, lang)` itself: the text the live host gets (temperature 0, the same guards)
  prompt    the same `model.transcribe` call with `initial_prompt=<text>` (the target phrase as a hint)
  tf        teacher-forced log-probability: the decoder is fed  <|sot|><|lang|><|transcribe|><|notimestamps|> + the
            tokens of " " + text  and the log-probabilities of those tokens and of the end token are summed
            (no sampling, no logit filter).  Stored: {"lp": sum, "n": tokens counted}.  The free transcription's own
            text is always teacher-forced too (key tf of that text), so that the two are measured the same way.

The audio encoder is run ONCE per wav: `model.encoder` is wrapped with a memo keyed by the bytes of the mel segment, so
the prompted call and the teacher-forced passes reuse the encoder output of the free call (identical numbers).
Whisper `medium` on the CPU with fp16 off, as the live host."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from . import cache
from .common import ROOT, mkdirs, save_sha_index, wav_sha

SIZE = "medium"


class EncoderMemo:
    """Wraps model.encoder.forward: the last few (mel bytes -> features)."""

    def __init__(self, model, keep=2):
        self.model, self.keep, self.memo, self.calls, self.hits = model, keep, {}, 0, 0
        self.orig = model.encoder.forward
        model.encoder.forward = self.forward
        self.last = None

    def forward(self, mel):
        k = (tuple(mel.shape), hashlib.sha1(mel.detach().cpu().numpy().tobytes()).hexdigest())
        self.calls += 1
        if k in self.memo:
            self.hits += 1
            self.last = self.memo[k]
            return self.last
        out = self.orig(mel)
        self.memo[k] = out
        while len(self.memo) > self.keep:
            self.memo.pop(next(iter(self.memo)))
        self.last = out
        return out


def transcribe_prompted(model, wav: str, lang: str, prompt: str | None):
    """env.hearing.transcribe with `initial_prompt` (identical parameters and guards otherwise)."""
    from env import _miolingo as mio
    from env.hearing import _LOCK
    audio = mio.phone_recognizer._load_audio_16k(wav)
    with _LOCK:
        result = model.transcribe(
            audio=audio, language=lang, task="transcribe",
            temperature=0.0, no_speech_threshold=0.6, logprob_threshold=-1.0,
            condition_on_previous_text=False, word_timestamps=False,
            compression_ratio_threshold=2.4, fp16=False, verbose=None, initial_prompt=prompt)
    text = result["text"].strip()
    words = text.lower().split()
    if len(words) > 20:
        for k in (2, 3, 4):
            if len(words) >= k * 10:
                pat = " ".join(words[:k])
                if text.lower().count(pat) >= 10:
                    return "", f"hallucination guard: {pat!r} repeated", result
        if len(words) > 100:
            return "", f"too long: {len(words)} words", result
    return text, "", result


def teacher_force(model, features, lang: str, texts: list[str]) -> list[dict]:
    """Sum of the decoder's log-probabilities of each text's tokens (and the end token) given the audio features."""
    import torch
    import whisper
    tok = whisper.tokenizer.get_tokenizer(model.is_multilingual, language=lang, task="transcribe",
                                          num_languages=model.num_languages)
    sot = list(tok.sot_sequence_including_notimestamps)
    # disallowed_special=(): a transcription may contain the text of a special token (Whisper wrote "<|de|>" for
    # one French take); it is then encoded as plain text
    seqs = [tok.encoding.encode(" " + t.strip(), disallowed_special=()) for t in texts]
    out = []
    B = 16
    for s in range(0, len(seqs), B):
        part = seqs[s:s + B]
        L = max(len(q) for q in part)
        inp = torch.full((len(part), len(sot) + L), tok.eot, dtype=torch.long)
        for i, q in enumerate(part):
            inp[i, :len(sot)] = torch.tensor(sot)
            inp[i, len(sot):len(sot) + len(q)] = torch.tensor(q, dtype=torch.long)
        with torch.no_grad():
            logits = model.decoder(inp, features.expand(len(part), -1, -1))
        lp = torch.log_softmax(logits.float(), -1)
        for i, q in enumerate(part):
            tgt = q + [tok.eot]
            pos = range(len(sot) - 1, len(sot) - 1 + len(tgt))
            vals = [float(lp[i, p, t]) for p, t in zip(pos, tgt)]
            out.append({"lp": round(sum(vals), 4), "n": len(tgt), "lp_eot": round(vals[-1], 4)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--jobs", required=True, action="append")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--reverse", action="store_true")
    a = ap.parse_args()
    mkdirs()
    k, n = (int(x) for x in a.shard.split("/"))
    jobs: dict = {}
    for jf in a.jobs:
        for l in Path(jf).read_text("utf-8").splitlines():
            if not l.strip():
                continue
            j = json.loads(l)
            w = str(Path(j["wav"]) if Path(j["wav"]).is_absolute() else ROOT / j["wav"])
            cur = jobs.setdefault((w, j["lang"]), {"prompts": [], "tf": []})
            for key in ("prompts", "tf"):
                for t in j.get(key) or []:
                    if t not in cur[key]:
                        cur[key].append(t)
    todo = []
    for (w, lang), j in jobs.items():
        sha = wav_sha(w)
        if int(sha[:8], 16) % n != k:
            continue
        have = cache.wh_all(w)
        need_free = cache.wh_key(lang) not in have
        need_p = [p for p in j["prompts"] if cache.wh_key(lang, p) not in have]
        need_tf = [t for t in j["tf"] if cache.tf_key(lang, t) not in have]
        free_text = (have.get(cache.wh_key(lang)) or {}).get("text")
        need_tf_free = need_free or (free_text and cache.tf_key(lang, free_text) not in have)
        if need_free or need_p or need_tf or need_tf_free:
            todo.append((w, lang, need_free, need_p, need_tf))
    save_sha_index()
    if a.reverse:                  # a second process on the same shard from the other end; each wav is re-checked
        todo.reverse()             # just before it is computed, so the two meet in the middle without double work
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(jobs)} wavs in the jobs, {len(todo)} need work (shard {a.shard})", flush=True)
    if not todo:
        return
    import torch
    if a.threads:
        torch.set_num_threads(a.threads)
    import env
    from env import _miolingo as mio
    t0 = time.perf_counter()
    model = env.hearing.whisper_model(SIZE)
    memo = EncoderMemo(model)
    print(f"Whisper {SIZE} loaded in {time.perf_counter() - t0:.1f} s", flush=True)
    t0 = time.perf_counter()
    for i, (w, lang, need_free, need_p, need_tf) in enumerate(todo, 1):
        entries = {}
        try:
            have = cache.wh_all(w)
            j = jobs[(w, lang)]                     # re-checked now: another process may have done this wav meanwhile
            need_free = cache.wh_key(lang) not in have
            need_p = [p for p in j["prompts"] if cache.wh_key(lang, p) not in have]
            need_tf = [t for t in j["tf"] if cache.tf_key(lang, t) not in have]
            ft = (have.get(cache.wh_key(lang)) or {}).get("text")
            if not (need_free or need_p or need_tf or (ft and cache.tf_key(lang, ft) not in have)):
                continue
            if need_free:
                text, note = env.hearing.transcribe(w, lang, SIZE)
                entries[cache.wh_key(lang)] = {"text": text, "note": note}
            else:
                text = have[cache.wh_key(lang)]["text"]
            for p in need_p:
                pt, pn, _ = transcribe_prompted(model, w, lang, p)
                entries[cache.wh_key(lang, p)] = {"text": pt, "note": pn}
            tf_texts = list(need_tf)
            if text and cache.tf_key(lang, text) not in have and text not in tf_texts:
                tf_texts.append(text)
            if tf_texts:
                audio = mio.phone_recognizer._load_audio_16k(w)
                if len(audio) <= 30 * 16000:
                    if memo.last is None or not (need_free or need_p):
                        # nothing was transcribed in this pass: run the encoder as transcribe() does
                        import whisper
                        mel = whisper.log_mel_spectrogram(audio, model.dims.n_mels, padding=whisper.audio.N_SAMPLES)
                        seg = whisper.pad_or_trim(mel[:, :mel.shape[-1] - whisper.audio.N_FRAMES], whisper.audio.N_FRAMES)
                        with torch.no_grad():
                            model.encoder(seg[None].to(torch.float32))
                    res = teacher_force(model, memo.last, lang, tf_texts)
                    for t, r in zip(tf_texts, res):
                        entries[cache.tf_key(lang, t)] = r
                else:
                    for t in tf_texts:
                        entries[cache.tf_key(lang, t)] = {"lp": None, "n": 0, "note": "longer than 30 s"}
        except Exception as e:
            print(f"FAILED {w}: {type(e).__name__}: {e}", flush=True)
            continue
        cache.wh_put(w, entries)
        if i % 20 == 0 or i == len(todo):
            el = time.perf_counter() - t0
            print(f"  {i}/{len(todo)}  {el:.0f} s  ({el / i:.2f} s each; encoder calls {memo.calls}, memo hits {memo.hits})",
                  flush=True)


if __name__ == "__main__":
    main()
