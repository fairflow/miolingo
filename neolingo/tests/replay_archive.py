"""Replay the archive: the regression test with real sound.

    <miolingo venv python> tests/replay_archive.py [--variant fr-fr] [--since 2026-10-13] [--limit N] [--judged]

For every line of var/archive/checks.jsonl the take (var/archive/takes/<token>.wav) is run again through
env.audible, env.hear and env.sounds, as the host answers the engine's questions, inside a scratch engine session
(a fresh `neohost` process; one phrase loaded; the take recorded; Check pressed), and compared with what was
recorded: the text heard, the sounds heard, the flags, the score, whether it was understood; and, where the
line has them (not for "reconstructed" lines), the target sounds, the banner, the flag lines, the aligned columns and
droppedFlags.  One line a take: SAME, or CHANGED with what changed.  Exit code 1 if anything changed.

Since 14 October the engine gives a "picture" in place of "columns"; both are compared as columns (host.archive.columns_of:
target, heard and mark of each column, by word), so an old line and a new result compare alike.  The banner now
writes the heard text as the app shows it (the phrase's spelling where the phrase's words were heard): a banner that
differs only so is reported as "banner: heard text now in the phrase's spelling" and counted apart in the summary.

Each line also shows the latest human judgement of the take (var/archive/judgements.jsonl: fair, harsh, generous, or
unjudged), the summary counts them, and --judged replays only the judged takes.  So a change can be read as "of the takes
judged too harsh, how many now score higher": the score shown is "old -> new" for a CHANGED line.

The scratch session has its own in-memory store and its log goes to var/replay/; the live database and the
archive are only read.  Nothing here touches the network (Hugging Face is offline)."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from host import paths                                    # noqa: E402
from host import archive                                  # noqa: E402

(paths.VAR / "replay").mkdir(parents=True, exist_ok=True)
paths.LOG = paths.VAR / "replay" / "replay.log"
import env                                                # noqa: E402
from host.engine import Engine, Environment               # noqa: E402
from host.engine_config import build_config               # noqa: E402
from host.store import Store                              # noqa: E402


class ArchiveEnvironment(Environment):
    """The host's own answers, reading the takes from the archive (`extra`: token -> path of other recordings,
    which tests/reference_sweep.py uses)."""
    extra = {}

    def wav(self, take):
        if take in self.extra:
            return str(self.extra[take])
        p = paths.ARCHIVE_TAKES / f"{take}.wav"
        return str(p) if take.isalnum() and p.exists() else None


def flat(ipa):
    return [s for w in (ipa or []) for s in w]


def flag_key(fl):
    return [(f["at"], f["sound"], f.get("heardAs"), bool(f["off"])) for f in (fl or [])]


def replay_one(eng, store_unused, line):
    """-> (new, notes): what the scratch session gave now."""
    eng.line(eng.config)                                   # a fresh configuration: the engine forgets its answers
    store = Store(":memory:")
    v = line["variant"]
    eng.ask({"cmd": "start", "sessions": [paths.UID], "store": [
        {"uid": paths.UID, "settings": {"own": "en", "practised": v, "slow": False}, "vocab": [], "history": []}]}, store)
    eng.ask({"press": "load", "session": 1, "input": line["text"]}, store)
    rec = eng.ask({"press": "record", "session": 1, "input": line["take"]}, store)
    aud = next((x["a"]["audible"] for x in eng.last_answers if x["q"]["q"] == "audible"), None)
    if not rec.get("step"):
        return {"audible": aud, "recorded": False}
    d = eng.ask({"press": "check", "session": 1, "input": None}, store)
    if not d.get("step"):
        return {"audible": aud, "recorded": True, "checked": False}
    hear = next((x for x in eng.last_answers if x["q"]["q"] == "hear"), None)
    snd = next((x for x in eng.last_answers if x["q"]["q"] == "sounds"), None)
    res = d["screens"][0]["body"]["result"]
    row = d["write"]["row"]
    return {"audible": aud, "recorded": True, "checked": True,
            "target": snd["q"]["target"] if snd else None,
            "hear": hear["a"] if hear else None, "sounds": snd["a"]["flags"] if snd else None,
            "score": row["score"], "understood": row["understood"], "banner": res.get("banner"),
            "flagLines": res.get("flagLines"), "flags": res.get("flags"), "picture": res.get("picture"),
            "columns": archive.columns_of(res), "heardShown": (res.get("heard") or {}).get("text"),
            "droppedFlags": d.get("droppedFlags")}


def spelling_only(old_banner, new_banner, old_heard, new_shown):
    """True when two banners differ only in the heard text: the old one quoting the recogniser's writing, the new one
    the text as shown (the phrase's spelling).  Compared with the heard texts cut out."""
    if not (isinstance(old_banner, str) and isinstance(new_banner, str) and old_heard and new_shown is not None):
        return False
    return old_banner.replace(old_heard, "\0") == new_banner.replace(new_shown, "\0")


def compare(old, new):
    ch = []
    if not new.get("recorded") or not new.get("checked"):
        return [f"the take is no longer accepted (audible={new.get('audible')}, recorded={new.get('recorded')})"]
    if old.get("audible") is False or new["audible"] is not True:
        ch.append(f"audible {True} -> {new['audible']}")
    oh, nh = old.get("hear") or {}, new["hear"] or {}
    lower = (lambda t: (t or "").lower()) if old.get("reconstructed") else (lambda t: t)    # history rows are lower case
    if lower(oh.get("text")) != lower(nh.get("text")):
        ch.append(f"heard text {oh.get('text')!r} -> {nh.get('text')!r}")
    if flat(oh.get("ipa")) != flat(nh.get("ipa")):
        o, n = "".join(flat(oh.get("ipa"))), "".join(flat(nh.get("ipa")))
        ch.append(f"heard sounds {o} -> {n}" + (" (only length marks differ)" if o.replace("ː", "") == n.replace("ː", "") else ""))
    if flag_key(old.get("flags")) != flag_key(new["flags"]):
        ch.append(f"flags {flag_key(old.get('flags'))} -> {flag_key(new['flags'])}")
    if old.get("sounds") is not None and flag_key(old["sounds"]) != flag_key(new["sounds"]):
        ch.append(f"sounds check {flag_key(old['sounds'])} -> {flag_key(new['sounds'])}")
    if old.get("score") != new["score"]:
        ch.append(f"score {old.get('score')} -> {new['score']}")
    if old.get("understood") != new["understood"]:
        ch.append(f"understood {old.get('understood')} -> {new['understood']}")
    for k in ("target", "flagLines", "droppedFlags"):                          # only where the line has them
        if old.get(k) is not None and old[k] != new[k]:
            ch.append(f"{k} changed" if k == "target" else f"{k} {old[k]!r} -> {new[k]!r}")
    if old.get("banner") is not None and old["banner"] != new["banner"]:
        if spelling_only(old["banner"], new["banner"], (old.get("hear") or {}).get("text"), new.get("heardShown")):
            ch.append(SPELLING)
        else:
            ch.append(f"banner {old['banner']!r} -> {new['banner']!r}")
    oc = archive.columns_of(old)
    if oc is not None and oc != new["columns"]:
        ch.append("columns changed" + (" (only the marks)" if strip_marks(oc) == strip_marks(new["columns"]) else ""))
    return ch


SPELLING = "banner: heard text now in the phrase's spelling (expected since 14 October)"


def strip_marks(cols):
    return [[(x.get("target"), x.get("heard")) for x in w] for w in (cols or [])]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--variant")
    ap.add_argument("--since", help="a date, YYYY-MM-DD: lines of that day and later")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--judged", action="store_true", help="only the takes that have a human judgement")
    a = ap.parse_args()
    f = paths.ARCHIVE / "checks.jsonl"
    if not f.exists():
        sys.exit(f"{f} does not exist yet")
    lines = [json.loads(l) for l in f.read_text("utf-8").splitlines() if l.strip()]
    if a.variant:
        lines = [l for l in lines if l["variant"] == a.variant]
    if a.since:
        lines = [l for l in lines if l["time"][:10] >= a.since]
    js = archive.judgements()
    if a.judged:
        lines = [l for l in lines if l["take"] in js]
    if a.limit:
        lines = lines[:a.limit]
    eng = Engine(build_config())
    eng.env = ArchiveEnvironment()
    same = changed = spelling_only_n = 0
    verdicts = {"fair": 0, "harsh": 0, "generous": 0, "unjudged": 0}
    harsh_up = harsh_n = gen_down = gen_n = 0               # of "too harsh" takes how many now score higher; of "too generous" lower
    t0 = time.perf_counter()
    for l in lines:
        tag = " (reconstructed)" if l.get("reconstructed") else ""
        new = None
        try:
            new = replay_one(eng, None, l)
            ch = compare(l, new)
        except Exception as e:
            ch = [f"ERROR {type(e).__name__}: {e}"]
            try:
                eng.restart()
            except Exception:
                pass
        verdict = (js.get(l["take"]) or {}).get("verdict") or "unjudged"
        verdicts[verdict if verdict in verdicts else "unjudged"] += 1
        old_s, new_s = l.get("score"), (new or {}).get("score")
        if verdict == "harsh" and isinstance(old_s, (int, float)) and isinstance(new_s, (int, float)):
            harsh_n += 1
            harsh_up += new_s > old_s
        if verdict == "generous" and isinstance(old_s, (int, float)) and isinstance(new_s, (int, float)):
            gen_n += 1
            gen_down += new_s < old_s
        head = (f"{l['time'][5:19]} {l['variant']:5} {l['take']} {l['text']!r} score {old_s}"
                + (f" -> {new_s}" if new_s is not None and new_s != old_s else "") + f" [{verdict}]{tag}")
        if ch == [SPELLING]:
            spelling_only_n += 1
        if ch:
            changed += 1
            print(f"CHANGED {head}\n          " + "\n          ".join(ch))
        else:
            same += 1
            print(f"SAME    {head}")
    rec = sum(1 for l in lines if l.get("reconstructed"))
    print(f"\nreplayed {len(lines)} takes ({rec} reconstructed lines) in {time.perf_counter() - t0:.0f} s: "
          f"{same} SAME, {changed} CHANGED ({spelling_only_n} of them only by the banner's heard text, now in the phrase's spelling)")
    print(f"judged: {verdicts['fair']} fair, {verdicts['harsh']} harsh, {verdicts['generous']} generous, {verdicts['unjudged']} unjudged")
    if harsh_n:
        print(f"of the {harsh_n} takes judged too harsh, {harsh_up} now score higher")
    if gen_n:
        print(f"of the {gen_n} takes judged too generous, {gen_down} now score lower")
    eng.proc.terminate()
    sys.exit(1 if changed else 0)


if __name__ == "__main__":
    main()
