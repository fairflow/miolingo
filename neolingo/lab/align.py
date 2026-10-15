"""The engine's own alignment for the lab: `{"cmd":"align"}` (protocol section 2; locus 0041de3), `Neo.alignFor`, the
function the judgement itself aligns with.  It replaced lab/engine_py.py's copy of `align` and `dist` (15 October).

An `Aligner` is a `neolingo neohost` process given a configuration (protocol section 5) and asked for alignments: no
session, nothing changed, one line each way.  The configuration is sent again only when it changes.

    a = aligner(name)                               one per name and process (worker processes have their own)
    a.configure(config)
    ans = a.align(variant, target, heard, flags)    {"columns": [{"at", "target", "heard": [...], "cost"}], "distance"}
    pairs(ans)                                      [(target or None, heard or None, cost)]: one heard sound as a
                                                    string, a split's two as a tuple, None when left out

The host's German ü/ö rule asks its own engine the same question through its own connection (host/engine.py)."""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import subprocess

DEFAULT_ENGINE = "/Users/matthew/Lean/locus/.lake/build/bin/neolingo"


def engine_path(engine=None):
    return engine or os.environ.get("NEOLINGO_ENGINE") or DEFAULT_ENGINE


class Aligner:
    def __init__(self, engine=None):
        self.engine = engine_path(engine)
        self.proc = subprocess.Popen([self.engine, "neohost"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     text=True, encoding="utf-8", bufsize=1)
        first = json.loads(self.proc.stdout.readline() or "{}")
        if first.get("ready") != 1:
            raise RuntimeError(f"the engine did not start: {first!r}")
        self.key = None
        self.memo: dict = {}

    def line(self, msg):
        self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        out = self.proc.stdout.readline()
        if not out:
            raise RuntimeError("the engine stopped")
        return json.loads(out)

    def configure(self, config):
        key = hashlib.sha1(json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        if key == self.key:
            return
        msg = {**config, "cmd": "config"}
        msg.setdefault("variants", [])
        msg.setdefault("languages", [])
        d = self.line(msg)
        if not d.get("ok"):
            raise RuntimeError(f"the engine refused the configuration: {d!r}")
        self.key = key
        self.memo = {}

    def align(self, variant, target, heard, flags=None):
        """target: by word; heard: a flat list (or by word); -> the engine's answer."""
        h = heard if (heard and isinstance(heard[0], list)) else [list(heard)] if heard else []
        k = json.dumps([variant, target, h, flags or []], ensure_ascii=False)
        got = self.memo.get(k)
        if got is None:
            got = self.line({"cmd": "align", "variant": variant, "target": target, "heard": h, "flags": flags or []})
            if "columns" not in got:
                raise RuntimeError(f"align refused: {got!r}")
            if len(self.memo) > 200000:
                self.memo = {}
            self.memo[k] = got
        return got

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:                       # noqa: BLE001
            self.proc.kill()


_ALIGNERS: dict = {}


def aligner(name="lab", engine=None) -> Aligner:
    """The process's aligner of that name (one engine process each: "lab" for the analysis's own configurations,
    "host" for the host's configuration, so that neither has to send its configuration again each time)."""
    a = _ALIGNERS.get(name)
    if a is None:
        a = _ALIGNERS[name] = Aligner(engine)
        atexit.register(a.close)
    return a


def pairs(ans):
    """The answer's columns as [(target or None, heard or None, cost)]: one heard sound a string, a split a tuple."""
    out = []
    for c in ans["columns"]:
        h = c["heard"]
        out.append((c["target"], None if not h else h[0] if len(h) == 1 else tuple(h), c["cost"]))
    return out
