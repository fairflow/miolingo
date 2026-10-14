"""`sounds`: Miolingo's sound check, GIVEN the target."""
from __future__ import annotations

import unicodedata

from . import _miolingo as mio
from .hearing import _LOCK
from .ipa import norm_word
from .variants import variant

STRIP = mio.sound_check.STRIP
DEL = mio.sound_check.DEL

# THE GERMAN ü/ö RULE (the lab's recommendation `rec de`, lab/RESULTS.md, rule A5 "phoneme+lr"): a target sound on the
# language's calibrated `unreliable` list (German y yː øː œ ɔø), which the check itself never flags, is flagged
# "likely off" exactly when the free reading hears a different FULL vowel of the language there and the likelihood
# ratio log P(target with that vowel | audio) - log P(target | audio) >= VERIFY_TAU.  The rule is the lab's own code
# (lab.analyse.unreliable_subs, lab.check.phones_from_tokens and lr_from_lp), called on the take in hand.
VERIFY_LANGS = {"de"}
VERIFY_TAU = 2.0


def _map_tokens_to_phones(words: list[list[str]], ref: list[tuple[str, int]],
                          hidden: set[int]) -> dict[int, tuple[int, int]]:
    """Map index in the recogniser's token list -> (flat index of the first
    target phone it covers, flat index of the last), by character offset
    within the word."""
    spans: list[tuple[int, int, int, int]] = []   # (word, start, end, flat)
    flat = 0
    for wi, ph in enumerate(words):
        pos = 0
        for p in ph:
            q = unicodedata.normalize("NFC", "".join(c for c in p if c not in STRIP))
            spans.append((wi, pos, pos + len(q), flat))
            pos += len(q)
            flat += 1
    out: dict[int, tuple[int, int]] = {}
    cur_word, off = None, 0
    for i, (tok, wi) in enumerate(ref):
        if i in hidden:
            continue
        if wi != cur_word:
            cur_word, off = wi, 0
        end = off + len(tok)
        cover = [f for (w, a, b, f) in spans if w == wi and a < end and b > off]
        if not cover:                        # beyond what is left: last phone of the word
            cover = [max((f for (w, a, b, f) in spans if w == wi), default=0)]
        out[i] = (min(cover), max(cover))
        off = end
    return out


def sounds(wav_path: str, target: list[list[str]], variant_code: str) -> list[dict]:
    """The sound check.  `target` is `target_ipa(...)`.

    Returns, for each target sound flagged:
      at    index of the sound in the flat sequence of the target's phones
            (word 0's phones, then word 1's, ...); if the recogniser's token
            covers several phones ("ju" for j + u) it is the first of them
            and `span` is how many;
      off   True = "probably off", False = "worth checking";
      like  what it sounded like ("" if left out or unknown);
      left_out  True if the sound sounded left out;
      sound the target sound as the recogniser's token (normalised);
            Miolingo's French model writes a nasal vowel as two tokens
            (vowel, then U+0303), so that gives two flags at one `at`;
      word  index of the word it is in.
    Length marks are kept (a long sound is another sound): `sound` and `like` carry them
    attached ("iː"); a flag whose `like` equals its `sound` is dropped.
    GERMAN (VERIFY_LANGS): an `unreliable` target sound (y yː øː œ ɔø), which the check leaves unflagged, gets a "likely
    off" finding when the free reading hears another full vowel there and the likelihood ratio confirms it (>= 2);
    such a finding also carries "verified" (the ratio).  See verified_unreliable.
    [] when nothing is flagged, or when the check cannot run (a model
    without a CTC vocabulary, or a take too short for the target)."""
    v = variant(variant_code)
    words = [w for w in target if w]
    ipa_str = " ".join("".join(w) for w in words)
    if not ipa_str:
        return []
    with _LOCK:
        got = mio.phone_recognizer.log_probs_from_audio(wav_path, v["espeak"])
        if got is None:
            return []
        lp, vocab, blank, model_id = got
        res = mio.sound_check.score(lp, vocab, blank, ipa_str, v["espeak"], model_id)
    if not res.phones:
        return []
    ref = mio.sound_check.tokenize(ipa_str, vocab)
    hidden: set[int] = set()
    cfg = mio.sound_check.lang_config(v["espeak"])
    if cfg.get("glottal_onsets") and "ʔ" in vocab:
        ref = mio.sound_check._with_glottal_onsets(ref)
        hidden = {i for i, (t, _) in enumerate(ref) if t == "ʔ"}
    visible = [i for i in range(len(ref)) if i not in hidden]   # res.phones skips hidden
    place = _map_tokens_to_phones(words, ref, hidden)
    out, tokens = [], []
    for pv, i in zip(res.phones, visible):
        first, last = place.get(i, (0, 0))
        tokens.append({"tok": pv.phone, "word": pv.word_index, "p_ok": pv.p_ok, "level": pv.level,
                       "heard": pv.heard, "p_heard": pv.p_heard, "first": first, "last": last})
        if pv.level not in ("check", "off"):
            continue
        like = "" if pv.heard in (None, DEL) else norm_word(pv.heard)
        sound = norm_word(pv.phone) or pv.phone
        if like and like == sound:
            continue
        out.append({"at": first, "span": last - first + 1, "off": pv.level == "off",
                    "like": like, "left_out": pv.heard == DEL,
                    "sound": sound, "word": pv.word_index})
    if v["lang"] in VERIFY_LANGS and any(t["level"] == "unchecked" for t in tokens):
        out += verified_unreliable(v["lang"], words, tokens, lp, vocab, blank, model_id)
        out.sort(key=lambda f: f["at"])
    return out


def free_reading(lp, model_id: str) -> list[str]:
    """The phone model's own greedy reading of the take, from the log-probabilities in hand, cut as env.hear and the
    lab cut it (the same decode as mio.phone_recognizer.phones_from_audio: argmax, then the processor's decode)."""
    from lab.analyse import _cut
    with _LOCK:
        processor, _model = mio.phone_recognizer._load(model_id)
        decode = processor.batch_decode(lp.argmax(-1).unsqueeze(0))[0]
    return list(_cut(" ".join(decode.split())))


def verified_unreliable(lang: str, words, tokens, lp, vocab, blank, model_id: str) -> list[dict]:
    """The findings of the German ü/ö rule (see VERIFY_LANGS): one "likely off" finding, `like` the heard vowel, at each
    unreliable target sound where lab.analyse.unreliable_subs keeps the free reading's substitution.  Each carries
    "verified": the likelihood ratio.  [] when the rule finds nothing (or cannot run)."""
    from lab.analyse import unreliable_subs
    from lab.check import phones_from_tokens, lr_from_lp
    target = [[norm_word(x) or x for x in w] for w in words]      # as the engine holds it (flags_out does the same)
    flat = [s for w in target for s in w]
    word_of = [k for k, w in enumerate(target) for _ in w]
    phones = phones_from_tokens(tokens, target)["phones"]
    kept = unreliable_subs(lang, target, free_reading(lp, model_id), phones,
                           lambda edits: lr_from_lp(lp, vocab, blank, target, edits), VERIFY_TAU)
    return [{"at": i, "span": 1, "off": True, "like": h, "left_out": False, "sound": flat[i], "word": word_of[i],
             "verified": round(r, 2)} for (i, h, r) in kept]
