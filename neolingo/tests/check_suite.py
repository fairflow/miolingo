"""H1 (locus docs/neolingo-test-design.md 4C): the generated conformance suite replayed through THE REAL HOST'S DRIVER.

    <miolingo venv python> tests/check_suite.py <locus>/var/neolingo-suite.json [--engine <neolingo binary>]

The suite is written by `.lake/build/bin/neolingo runs` in locus (format "neolingo-conformance 1", locus
docs/neolingo-conformance.md): a toy environment and eighteen runs, each a store, the sessions, the starting screens,
then each press with its step, write, message and screens, then the store at the end.  The engine must be the one
that wrote the suite: by default <locus>/.lake/build/bin/neolingo beside the suite's var/.

The path under test is the host's own, not a copy of it: Host.press and Host.once (host/serve.py), Engine.ask
(host/engine.py: the engine's questions answered, its write applied to the store before the reply returns), and
Store.apply / Store.all_data (host/store.py, SQLite).  Stood in, as the suite prescribes: the recognisers and tables
(Environment.answer gives the suite's toy answers) and the configuration (the suite's tables in place of
build_config).  For each run: the run's store is written into a fresh SQLite store with Store.apply and read back
(compared with the run's store); the engine is started with the run's sessions and Store.all_data() (the suite's
start: sessions signed in from the first moment; the host's own start with slots and the auto sign-in is
check_signin's); then each press goes through Host.press, `can` first: compared are the step (and what `can` said),
droppedFlags, the write, the message and every screen; at the end Store.all_data() against the run's endStore.
The stores are compared with the order the protocol states (section 4.1, locus 563b41f: a language's vocabulary
rows and the history ordered; a list's items in order); the learners and a learner's lists, which the protocol leaves
unordered, are compared as sets, and a difference of their order is reported, not failed: the host keeps them by
name, the model in the order they came (15 October: runs (xi) and (xiii) differ only so).

Works in a temporary folder (NEOLINGO_VAR); the running host and var/ are not touched.  No speech model is loaded.
Exits 1 on any difference."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(description="H1: the generated suite through the real host's driver")
ap.add_argument("suite", type=Path)
ap.add_argument("--engine", type=Path, help="the neolingo binary that wrote the suite "
                "(default: .lake/build/bin/neolingo of the locus folder holding the suite)")
ap.add_argument("--show", type=int, default=30, help="differences printed (default 30)")
A = ap.parse_args()
engine = A.engine or A.suite.resolve().parent.parent / ".lake" / "build" / "bin" / "neolingo"
if not engine.exists():
    sys.exit(f"no engine at {engine}: give --engine")
os.environ["NEOLINGO_VAR"] = tempfile.mkdtemp(prefix="neolingo_suite_")
os.environ["NEOLINGO_ENGINE"] = str(engine)
os.environ["NEOLINGO_AUTOSIGNIN"] = ""
os.environ["NEOLINGO_SLOTS"] = "1"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(ROOT))

from host import serve, paths                  # noqa: E402
from host.engine import Environment            # noqa: E402
from host.store import Store                   # noqa: E402

suite = json.loads(A.suite.read_text("utf-8"))
if suite.get("format") != "neolingo-conformance 1":
    sys.exit(f"not a suite of format 'neolingo-conformance 1': {suite.get('format')!r}")
E = suite["environment"]
names = E["names"]
CONFIG = {"cmd": "config",
          "variants": [n for n in names if n["code"] in E["variants"]],
          "languages": [n for n in names if "-" not in n["code"]],
          "costs": E["tables"]["sub"], "costOtherwise": E["tables"]["subOtherwise"],
          "significant": E["tables"].get("significant", 340),
          "splits": E["tables"].get("splits", []), "offFloor": E["tables"].get("offFloor", 0),
          "curve": {"kind": "sqrt", "scale": 2250000}}


class SuiteEnvironment(Environment):
    """The recognisers and tables stood in by the suite's toy environment (anything not listed gives nothing)."""
    T = {x["text"]: x["ipa"] for x in E["targetIpa"]}
    AUD = {x["take"]: x["audible"] for x in E["audible"]}
    HEAR = {x["take"]: x for x in E["hear"]}
    SND = {x["take"]: x["flags"] for x in E["sounds"]}
    FILL = {x["word"]: x for x in E["fill"]}

    def answer(self, q):
        k = q["q"]
        if k == "targetIpa":
            return {"ipa": self.T.get(q["text"], [])}
        if k == "fill":
            f = self.FILL.get(q["word"], {})
            return {"translation": f.get("translation", ""), "notes": f.get("notes", "")}
        if k == "audible":
            return {"audible": self.AUD.get(q["take"], True)}
        if k == "hear":
            h = self.HEAR.get(q["take"], {})
            return {"text": h.get("text", ""), "ipa": h.get("ipa", [])}
        if k == "sounds":
            return {"flags": self.SND.get(q["take"], [])}
        raise ValueError(f"unknown question {q!r}")


def load(store, learners):
    """The run's store, written through the host's own writes."""
    for x in learners:
        store.apply({"kind": "putLearner", "uid": x["uid"], "settings": x["settings"]})
        for v in x.get("vocab", []):
            store.apply({"kind": "putEntries", "uid": x["uid"], "lang": v["lang"], "entries": v["entries"]})
        for r in x.get("history", []):
            store.apply({"kind": "appendRow", "uid": x["uid"], "row": r})
        for l in x.get("lists", []):
            store.apply({"kind": "putList", "uid": x["uid"], "lang": l["lang"], "items": l["items"]})


serve.build_config = lambda: CONFIG             # the suite's tables
host = serve.Host()                             # the real host: its engine started with the configuration
host.engine.env = SuiteEnvironment()            # the recognisers stood in
bad, presses, order = [], 0, []


def canon(store):
    """A store with what the protocol leaves unordered (learners; a learner's languages) put by name."""
    return sorted(({**x, "vocab": sorted(x.get("vocab", []), key=lambda v: v["lang"]),
                    "lists": sorted(x.get("lists", []), key=lambda l: l["lang"])} for x in store), key=lambda x: x["uid"])


def same_store(at, what, got, want):
    if canon(got) != canon(want):
        differ(at, what, got, want)
    elif got != want:
        order.append(f"{at}: {what}, in the order of learners or languages only")


def differ(at, what, got, want):
    bad.append(f"{at}: {what}" + (f"\n      host  {json.dumps(got, ensure_ascii=False)[:300]}"
                                  f"\n      suite {json.dumps(want, ensure_ascii=False)[:300]}" if got is not None or want is not None else ""))


for k, run in enumerate(suite["runs"], 1):
    name = run["name"][:60]
    host.store = Store(paths.VAR / f"run{k}.sqlite")
    load(host.store, run["store"])
    same_store(name, "the run's store, written and read back by the host's store, differs", host.store.all_data(), run["store"])
    ok = host.engine.ask(CONFIG, host.store)    # a new configuration forgets the answers: each run asks afresh
    if not ok.get("ok"):
        differ(name, "the configuration was refused", ok, None)
        continue
    d = host.engine.ask({"cmd": "start", "sessions": run["sessions"], "store": host.store.all_data()}, host.store)
    host.started, host.held = True, {}
    host.note_screens(d)
    if d.get("screens") != run["start"]:
        differ(name, "the screens at the start differ", d.get("screens"), run["start"])
    for i, st in enumerate(run["steps"], 1):
        presses += 1
        at = f"{name}: press {i} ({st['press']} {json.dumps(st['input'], ensure_ascii=False)[:40]})"
        c = host.press({"cmd": "can", "asks": [{"press": st["press"], "session": st["session"], "input": st["input"]}]})
        if c.get("can") != [st["step"]]:
            differ(at, f"can says {c.get('can')}, the press is a step: {st['step']}", None, None)
        d = host.press({"press": st["press"], "session": st["session"], "input": st["input"]})
        if "err" in d:
            differ(at, f"the host answered an error: {d['err']}", None, None)
            continue
        if d["step"] != st["step"]:
            differ(at, f"step is {d['step']}", None, None)
        if d.get("droppedFlags") != st.get("droppedFlags"):
            differ(at, f"droppedFlags is {d.get('droppedFlags')}, the suite says {st.get('droppedFlags')}", None, None)
        if d.get("write") != st["write"]:
            differ(at, "the write differs", d.get("write"), st["write"])
        if d.get("message") != st["message"]:
            differ(at, "the message differs", d.get("message"), st["message"])
        if d.get("screens") != st["screens"]:
            differ(at, "a screen differs", d.get("screens"), st["screens"])
    same_store(name, "the host's store at the end differs", host.store.all_data(), run["endStore"])

host.engine.proc.terminate()
for o in order:
    print("  REPORTED (an order the protocol leaves free, section 4.1): " + o)
for b in bad[:A.show]:
    print("  " + b)
if len(bad) > A.show:
    print(f"  ... and {len(bad) - A.show} more")
if bad:
    sys.exit(f"H1 FAILED: {len(bad)} difference(s) from {A.suite} through the real host's driver")
print(f"H1 ok: {len(suite['runs'])} runs, {presses} presses through the real host's driver (Host.press, Engine.ask, "
      f"Store.apply): every step (and `can`), write, message, screen, droppedFlags and the store at the start and end "
      f"as in {A.suite}")
