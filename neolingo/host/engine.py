"""The engine process (`explore neohost`), JSON lines, and the environment that answers its questions."""
import json
import subprocess
import threading
import time

import env
from . import paths
from .engine_config import equiv_enabled, equivalents, free_pairs
from .log import log


def distribute(targets, like):
    """A finding on a recogniser token that covers several target sounds `targets` (["t", "ʃ"] for the token "tʃ"),
    which the checker says sounded like the string `like`.  Cut `like` into sounds and align it with `targets`
    in order, keeping as many equal sounds as possible (an equal sound is no complaint).  Returns, for each target
    sound, what it sounded like: the sound itself (no complaint), another sound, or None (left out); or None
    when the finding cannot be distributed truthfully (no sound in common and a different number of sounds, so
    any split would be a guess)."""
    heard = env.phones_of(like) if like else []
    n, m = len(targets), len(heard)
    if not m or not (set(targets) & set(heard)) and n != m:
        return None
    # least edit distance (a pairing of two different sounds, a target sound left out, an extra heard sound: 1 each)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (targets[i - 1] != heard[j - 1]))
    out, i, j = [None] * n, n, m
    while i > 0 and j > 0:
        if d[i][j] == d[i - 1][j - 1] + (targets[i - 1] != heard[j - 1]):
            out[i - 1] = heard[j - 1]
            i, j = i - 1, j - 1
        elif d[i][j] == d[i - 1][j] + 1:
            i -= 1                                      # left out
        else:
            j -= 1                                      # an extra heard sound
    return out


def flags_out(libflags, target):
    """The library's findings -> the protocol's flags F = {at, sound, heardAs, off} (section 3.1 item 3).

    A flag for each target sound, each with its own `at`, `sound` exactly the string the engine holds at that
    place (taken from `target`, the sounds the engine sent in the question).  A finding of the library covers
    `span` sounds from `at` when a recogniser token such as "tʃ" or "ju" covers several.  Such a finding is
    reported sound by sound, TRUTHFULLY: what the checker says the token sounded like is cut into sounds and
    aligned in order with the target sounds it covers (`distribute`): [tʃ] heard as [tʃ] gives no flag at all,
    [tʃ] heard as [ʃ] gives "[t] left out" and nothing on [ʃ].  If it cannot be distributed (nothing in common
    and a different number of sounds) the finding is attached to the FIRST sound of the span only, with `heardAs`
    the whole token as returned; no "left out" is ever invented.  A token the checker says was left out
    leaves out every sound it covers.
    Where a target sound is cut by the recogniser into several tokens (the French model writes the nasal vowel
    "ɛ̃" as "ɛ" and U+0303) the findings land on one `at`: they are merged into one flag, `off` if any is off, and
    `heardAs` the target sound with each flagged token replaced by what it sounded like (nothing, if left out)."""
    flat = [env.norm_word(s) or s for word in target for s in word]
    by_at, order, resolved = {}, [], {}
    for f in libflags:
        left = bool(f.get("left_out"))
        like = "" if left else (f.get("like") or "")
        span = max(1, int(f.get("span") or 1))
        first = f["at"]
        covered = [a for a in range(first, first + span) if 0 <= a < len(flat)]
        if span > 1 and covered and len(covered) == span:
            if left:
                parts = [None] * span
            else:
                parts = distribute([flat[a] for a in covered], like)
            if parts is not None:
                for a, p in zip(covered, parts):
                    if p == flat[a]:
                        continue                        # heard as it should be: no complaint
                    old = resolved.get(a)
                    resolved[a] = (p, bool(f["off"]) or bool(old and old[1]))
                    if a not in order:
                        order.append(a)
                continue
            covered = covered[:1]                       # cannot be distributed: the first sound only
        for at in covered:
            if at not in by_at:
                by_at[at] = []
                if at not in order:
                    order.append(at)
            by_at[at].append((f.get("sound") or "", like, span, bool(f["off"])))
    out = []
    for at in sorted(order):
        t = flat[at]
        if at in resolved and at not in by_at:
            p, off = resolved[at]
            out.append({"at": at, "sound": t, "heardAs": p if p and p != t else None, "off": off})
            continue
        items = by_at[at]
        heard, off = t, any(o for (_s, _l, _n, o) in items)
        whole = [(l, n) for (_s, l, n, _o) in items if n > 1 or _s == t]
        if whole:                                     # the token IS the sound (or covers several sounds)
            heard = whole[0][0]
        else:                                         # tokens that are parts of the sound
            for (s, l, _n, _o) in items:
                if s and s in heard:
                    heard = heard.replace(s, l, 1)
                else:
                    heard = l
        out.append({"at": at, "sound": t, "heardAs": heard if heard and heard != t else None, "off": off})
    return out


class Environment:
    """Answers the five questions from env.  Counts the flags the engine will probably drop."""

    def __init__(self):
        self.flags_given = 0
        self.flags_mismatch = 0
        self.flags_equiv_dropped = 0        # warnings dropped because (sound, sounded like) is an equivalent pair

    def wav(self, take):
        p = paths.TAKES / f"{take}.wav"
        return str(p) if take.isalnum() and p.exists() else None

    def drop_equivalent(self, fl, variant_code):
        """With NEOLINGO_EQUIV=1: drop a warning whose (target sound, sounded like) is a pair of
        data/symbol_equivalents.json for the language (a false alarm by the same evidence as the cost); count them.
        With a cost candidate (NEOLINGO_COSTS) the same for the pairs it makes free (engine_config.free_pairs)."""
        if not fl:
            return fl
        lang = next((v["lang"] for v in env.variants() if v["code"] == variant_code), None)
        pairs = (set(equivalents(lang)) if equiv_enabled() else set()) | free_pairs(lang)
        if not pairs:
            return fl
        keep = [f for f in fl if (f["sound"], f["heardAs"]) not in pairs]
        self.flags_equiv_dropped += len(fl) - len(keep)
        return keep

    def answer(self, q):
        k = q["q"]
        if k == "targetIpa":
            return {"ipa": env.target_ipa(q["text"], q["variant"])}
        if k == "fill":
            t = env.gloss(q["word"], q["own"], q["variant"])
            return {"translation": t, "notes": ""}
        w = self.wav(q["take"]) if "take" in q else None
        if k == "audible":
            return {"audible": bool(w and env.audible(w))}
        if k == "hear":
            if not w:
                return {"text": "", "ipa": []}
            h = env.hear(w, q["variant"])
            return {"text": h["text"], "ipa": h["ipa"]}
        if k == "sounds":
            if not w:
                return {"flags": []}
            # the German ü/ö rule aligns with THIS engine's own `align` (protocol section 2), on this connection
            lib = env.sounds(w, q["target"], q["variant"], aligner=getattr(self, "aligner", None))
            fl = flags_out(lib, q["target"])
            fl = self.drop_equivalent(fl, q["variant"])
            flat = [env.norm_word(s) or s for word in q["target"] for s in word]
            bad = sum(not (0 <= f["at"] < len(flat) and flat[f["at"]] == f["sound"]) for f in fl)
            self.flags_given += len(fl)
            self.flags_mismatch += bad
            ver = [f"[{f['sound']}] as [{f['like']}] ratio {f['verified']}" for f in lib if "verified" in f]
            log(f"flags: {len(lib)} findings -> {len(fl)} sent, sound not the target's at 'at' (the engine drops these) {bad}"
                + (f"; German ü/ö rule: {', '.join(ver)}" if ver else ""))
            return {"flags": fl}
        raise ValueError(f"unknown question {q!r}")


class Engine:
    def __init__(self, config):
        self.config = config
        self.env = Environment()
        self.last_answers = []
        self.dropped_last = None            # "droppedFlags" of the latest Check press (the tests read it)
        self.lock = threading.Lock()      # ONE request at a time, engine traffic and environment calls included
        self.proc = None
        self.start_seconds = None
        self.launch()

    def launch(self):
        t0 = time.perf_counter()
        self.proc = subprocess.Popen([paths.ENGINE, "neohost"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     text=True, encoding="utf-8", bufsize=1)
        first = json.loads(self.proc.stdout.readline() or "{}")
        if first.get("ready") != 1:
            raise RuntimeError(f"the engine did not start: {first!r}")
        t1 = time.perf_counter()
        d = self.line(self.config)
        if not d.get("ok"):
            raise RuntimeError(f"the engine refused the configuration: {d!r}")
        self.start_seconds = (t1 - t0, time.perf_counter() - t1)
        log(f"engine started in {t1 - t0:.2f} s; config ({len(self.config['costs'])} cost entries, "
            f"{len(json.dumps(self.config)) // 1024} KiB) in {time.perf_counter() - t1:.2f} s")

    def line(self, msg):
        try:
            self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
            out = self.proc.stdout.readline()
        except (BrokenPipeError, OSError):
            out = ""
        if not out:
            raise RuntimeError("the engine stopped")
        return json.loads(out)

    def align(self, variant, target, heard, flags=None):
        """`{"cmd":"align"}` (protocol section 2, locus 0041de3): the alignment the judgement makes (`Neo.alignFor`)
        under the configuration in force.  It needs no session and changes nothing, so it may be sent while the engine
        waits for the answers to its questions (the German ü/ö rule asks it while answering `sounds`)."""
        h = heard if (heard and isinstance(heard[0], list)) else ([list(heard)] if heard else [])
        d = self.line({"cmd": "align", "variant": variant, "target": target, "heard": h, "flags": flags or []})
        if "columns" not in d:
            raise RuntimeError(f"the engine refused align: {d!r}")
        return d

    def ask(self, msg, store):
        """One request: answer the engine's questions until it gives its result; apply its write (BEFORE returning)."""
        self.last_answers = []              # every (question, answer) of this request, for the archive
        self.env.aligner = self.align       # the environment's German ü/ö rule aligns on this connection
        d = self.line(msg)
        while "ask" in d:
            answers = []
            for q in d["ask"]:
                t0 = time.perf_counter()
                try:
                    a = self.env.answer(q)
                except Exception as e:      # the question is answered empty, the failure is logged
                    log(f"question {json.dumps(q, ensure_ascii=False)[:200]} FAILED: {type(e).__name__}: {e}")
                    a = {"audible": False} if q["q"] == "audible" else {"flags": []} if q["q"] == "sounds" else \
                        {"text": "", "ipa": []} if q["q"] == "hear" else {"ipa": []} if q["q"] == "targetIpa" else \
                        {"translation": "", "notes": ""}
                log(f"question {q['q']} {json.dumps({k: v for k, v in q.items() if k != 'q'}, ensure_ascii=False)[:120]} "
                    f"-> {(time.perf_counter() - t0) * 1000:.0f} ms")
                answers.append({"q": q, "a": a})
                self.last_answers.append({"q": q, "a": a})
            d = self.line({"answers": answers})
        if "droppedFlags" in d:
            n = d["droppedFlags"]
            log(f"droppedFlags {n}" if n == 0 else f"WARNING droppedFlags {n}: the engine dropped flags; "
                f"the checker and targetIpa disagree")
            self.dropped_last = n
        if d.get("write"):
            done = store.apply(d["write"])
            log("write " + done)
            if done.startswith("UNKNOWN WRITE"):
                d["hostWarning"] = done
        return d

    def restart(self):
        try:
            self.proc.kill()
        except Exception:
            pass
        self.launch()
