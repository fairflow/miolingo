"""The engine process (`explore neohost`), JSON lines, and the environment that answers its questions."""
import json
import subprocess
import threading
import time

import env
from . import paths
from .log import log


def flag_out(f):
    """The library's flag -> the protocol's F = {at, sound, heardAs, off}."""
    like = f.get("like") or ""
    return {"at": f["at"], "sound": f["sound"], "heardAs": None if (f.get("left_out") or not like) else like,
            "off": bool(f["off"])}


class Environment:
    """Answers the five questions from env.  Counts the flags the engine will probably drop."""

    def __init__(self):
        self.flags_given = 0
        self.flags_mismatch = 0

    def wav(self, take):
        p = paths.TAKES / f"{take}.wav"
        return str(p) if take.isalnum() and p.exists() else None

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
            fl = [flag_out(f) for f in env.sounds(w, q["target"], q["variant"])]
            flat = [env.norm_word(s) or s for word in q["target"] for s in word]
            bad = 0
            for f in fl:
                if not (0 <= f["at"] < len(flat) and flat[f["at"]] == f["sound"]):
                    bad += 1
            self.flags_given += len(fl)
            self.flags_mismatch += bad
            log(f"flags given {len(fl)}, sound not the target's at 'at' (the engine drops these) {bad}")
            return {"flags": fl}
        raise ValueError(f"unknown question {q!r}")


class Engine:
    def __init__(self, config):
        self.config = config
        self.env = Environment()
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

    def ask(self, msg, store):
        """One request: answer the engine's questions until it gives its result; apply its write (BEFORE returning)."""
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
            d = self.line({"answers": answers})
        if d.get("write"):
            log("write " + store.apply(d["write"]))
        return d

    def restart(self):
        try:
            self.proc.kill()
        except Exception:
            pass
        self.launch()
