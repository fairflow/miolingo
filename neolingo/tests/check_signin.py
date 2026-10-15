"""Sign-in, registration, sign-out and what is saved when (protocol 6.2), over HTTP, mostly without speech models.

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/check_signin.py

Works in var/check_signin/ (git-ignored, emptied first; NEOLINGO_CHECK_VAR=<folder> moves it) on a COPY of the real
database (var/neolingo.sqlite, copied with SQLite's backup, read-only on the original), so the stored data are real.  The
hosts are started WITHOUT --preload; only the guest section records and checks (it loads the speech models).  The
running host's database is never opened for writing.

The one integration test of the host (locus docs/neolingo-test-design.md 4D).  The faults it guards:
  13 Oct (found by reading): a guest's takes were kept (archived, judged); the guest section: nothing is kept.
  14 Oct (the owner: "What if one of those forms closed was in the middle of an edit?"): a sign-out or a change of
      language dropped an open form; "a form open: ..." below: both refused, and a clean stop cancels the form and
      saves the settings.
  A fault of the test itself, 14 Oct 22:09 (b0013f8): "slow is not yet stored" assumed the real store held slow
      off; it now sets slow to the opposite of what the store holds.
"""
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAR = Path(os.environ.get("NEOLINGO_CHECK_VAR") or ROOT / "var" / "check_signin")
LANG_OF = {"fr-fr": "fr", "en-gb": "en", "en-us": "en", "de": "de"}
fails = []


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        fails.append(what)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Host:
    def __init__(self, **env):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}/"
        self.env = env
        self.proc = None

    def start(self):
        t0 = time.perf_counter()
        self.proc = subprocess.Popen([sys.executable, "-m", "host.serve", "--port", str(self.port)], cwd=ROOT,
                                     env=dict(os.environ, NEOLINGO_VAR=str(VAR), **self.env),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        while True:
            if self.proc.poll() is not None:
                sys.exit("the host exited: " + self.proc.stderr.read().decode()[-2000:])
            try:
                self.get("version")
                break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.2)
            if time.perf_counter() - t0 > 180:
                sys.exit("the host did not come up")

    def stop(self, sig=signal.SIGTERM):
        self.proc.send_signal(sig)
        return self.proc.wait(30)

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=60) as r:
            return json.loads(r.read())

    def press(self, **m):
        r = urllib.request.Request(self.base + "press", json.dumps(m).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=120) as f:
            return json.load(f)

    def press_raw(self, path, m):
        r = urllib.request.Request(self.base + path, json.dumps(m).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=60) as f:
            return json.load(f)

    def do(self, press, input=None, session=1):
        return self.press(press=press, session=session, input=input)

    def setting(self, which, value, session=1):
        self.do("openSettings", None, session)
        d = self.do(which, value, session)
        self.do("closeSettings", None, session)
        return d


def db(sql, *a):
    c = sqlite3.connect(VAR / "neolingo.sqlite")
    try:
        return c.execute(sql, a).fetchall()
    finally:
        c.close()


def S(d, r=0):
    return d["screens"][r]


def log():
    return (VAR / "host.log").read_text("utf-8")


def counts():
    c = sqlite3.connect(VAR / "neolingo.sqlite")
    try:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {t: c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in names}
    finally:
        c.close()


def archive_state():
    a = VAR / "archive"
    lines = {n: ((a / n).read_text("utf-8").count("\n") if (a / n).exists() else 0) for n in ("records.jsonl", "checks.jsonl")}
    return lines, sorted(p.name for p in (a / "takes").glob("*")) if (a / "takes").exists() else []


def take_files():
    return sorted(p.name for p in (VAR / "takes").glob("*.wav"))


def guest_section():
    """Nothing is kept for a guest: no write, no archive line, no archived take, take files deleted at sign-out.
    Needs the speech models (one real Check)."""
    print("\n=== a guest: nothing is kept (this loads the speech models) ===")
    h = Host()
    h.start()
    d = h.press(cmd="start")
    check(S(d)["uid"] == "me", "start: auto sign-in as me")
    base_counts, base_arch = counts(), archive_state()
    h.do("signOut")
    d = h.do("guest")
    s = S(d)
    check(d["step"] and d["write"] is None and s["guest"] is True and s["uid"] == "" and s["summary"].startswith("Guest (nothing is kept) · ")
          and s["body"]["kind"] == "practice", f"guest: a step, write null, uid empty, summary {s['summary']!r}")
    fr = json.loads((ROOT / "data" / "fr.json").read_text("utf-8"))["phrases"]
    chosen = [p for p in fr if len(p["text"].split()) >= 3][:2]
    d = h.do("load", "\n".join(f"{p['text']} | {p.get('gloss', '')}" for p in chosen))
    check(d["step"] and d["write"] is None and S(d)["guest"] is True, "guest: Load is a step, write null")
    d = h.do("addWord", "chat")
    check(d["step"] and d["write"] is None, "guest: adding a word, write null")
    wav = VAR / "guest.wav"
    subprocess.run([shutil.which("espeak-ng") or "espeak-ng", "-v", "fr-fr", "-w", str(wav), chosen[0]["text"]], check=True)
    r = urllib.request.Request(h.base + "take", wav.read_bytes(), {"Content-Type": "audio/wav"})
    with urllib.request.urlopen(r, timeout=60) as f:
        tk = json.load(f)["take"]
    check(f"{tk}.wav" in take_files(), "the take is under var/takes/ while the guest is in")
    d = h.do("record", tk)
    check(d["step"] and d["write"] is None, "guest: Record is a step, write null")
    d = h.do("check")
    check(d["step"] and d["write"] is None and S(d)["body"]["result"] is not None, "guest: Check gives a result, write null")
    check(h.get(f"judgement?take={tk}") == {"guest": True}, "GET judgement for a guest's take says guest (the page draws no judging)")
    try:
        h.press_raw("judge", {"take": tk, "verdict": "fair"})
        check(False, "POST judge for a guest's take is refused")
    except urllib.error.HTTPError as e:
        check(e.code == 400, f"POST judge for a guest's take is refused ({e.code})")
    check(counts() == base_counts, "the store's row counts are unchanged")
    check(archive_state() == base_arch, f"no archive line and no archived take: {archive_state()}")
    d = h.do("signOut")
    check(d["step"] and d["write"] is None and S(d)["guest"] is not True, "guest: sign-out writes nothing")
    check(take_files() == [] , f"the guest's take files are deleted at sign-out ({take_files()})")
    check("guest: take " + tk + " discarded" in log(), "the log says the take was discarded")
    d = h.do("guest")
    check(S(d)["guest"] is True and S(d)["body"]["kind"] == "practice" and S(d)["body"]["list"] == [], "guest again: an empty app")
    d = h.do("show", "Vocabulary")
    check(S(d)["body"]["rows"] == [] , "guest again: no vocabulary")
    check(counts() == base_counts and archive_state() == base_arch, "counts and archive unchanged after the second guest")
    # a take uploaded and left: deleted at the next start
    r = urllib.request.Request(h.base + "take", wav.read_bytes(), {"Content-Type": "audio/wav"})
    with urllib.request.urlopen(r, timeout=60) as f:
        tk2 = json.load(f)["take"]
    d = h.do("record", tk2)
    h.proc.kill()
    h.proc.wait(10)
    check(f"{tk2}.wav" in take_files(), "after kill -9 the guest's take is still there")
    h.start()
    check(take_files() == [], "at the next start the guest's leftover take is deleted")
    d = h.press(cmd="start")
    s = S(d)
    check(s["uid"] == "me" and s["body"]["kind"] == "practice", "then auto sign-in as me")
    check(counts() == base_counts, "me: the counts are intact")
    d = h.do("show", "Vocabulary")
    check(len(S(d)["body"]["rows"]) == db("SELECT COUNT(*) FROM vocabulary WHERE uid='me' AND lang=?", LANG_OF[S(d)["settings"]["practised"]])[0][0]
          and "chat" not in json.dumps(S(d)["body"]["rows"], ensure_ascii=False), "me: the vocabulary is intact, without the guest's word")
    h.stop()


def main():
    shutil.rmtree(VAR, ignore_errors=True)
    VAR.mkdir(parents=True)
    src = ROOT / "var" / "neolingo.sqlite"
    if not src.exists():
        sys.exit("no var/neolingo.sqlite to copy: the test wants the real stored data")
    a = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    b = sqlite3.connect(VAR / "neolingo.sqlite")
    a.backup(b)
    a.close()
    b.close()
    n_vocab = db("SELECT COUNT(*) FROM vocabulary WHERE uid='me'")[0][0]
    n_hist = db("SELECT COUNT(*) FROM history WHERE uid='me'")[0][0]
    me0 = db("SELECT own, practised, slow FROM settings WHERE uid='me'")[0]
    lists = {l: n for l, n in db("SELECT lang, COUNT(*) FROM lists WHERE uid='me' GROUP BY lang")}
    print(f"copy of the real database: me has {n_vocab} vocabulary rows, {n_hist} history rows, lists {lists}, settings {me0}")
    check(n_vocab > 0 and n_hist > 0, "the copy holds real data")
    lang = LANG_OF[me0[1]]

    h = Host()
    h.start()
    ver = h.get("version")
    check(ver["slots"] == 1 and ver["autosignin"] == "me", f"/version: slots {ver['slots']}, autosignin {ver['autosignin']!r}")

    print("\n=== start: auto sign-in as me ===")
    d = h.press(cmd="start")
    s = S(d)
    check(len(d["screens"]) == 1 and s["uid"] == "me" and s["body"]["kind"] == "practice" and s["signOut"] is True,
          "one slot, signed in as me, in the app")
    check(s["settings"] == {"own": me0[0], "practised": me0[1], "slow": bool(me0[2])}, f"me's stored settings: {s['settings']}")
    stored = db("SELECT text, gloss FROM lists WHERE uid='me' AND lang=? ORDER BY position", lang)
    check(stored and [(x["text"], x["gloss"]) for x in s["body"]["list"]] == stored, f"the stored {lang} list is in use ({len(stored)} items)")
    d = h.do("show", "Vocabulary")
    rows = S(d)["body"]["rows"]
    in_lang = db("SELECT COUNT(*) FROM vocabulary WHERE uid='me' AND lang=?", lang)[0][0]
    check(len(rows) == in_lang, f"Vocabulary: {len(rows)} rows = the stored {in_lang} for {lang} (all languages: {n_vocab})")
    d = h.do("show", "History")
    check(len(S(d)["body"]["rows"]) > 0, f"History: {len(S(d)['body']['rows'])} rows shown for {me0[1]} (stored in all variants: {n_hist})")
    d = h.do("show", "Practice")
    other = next((l for l in lists if l != lang), None)
    if other:                                          # the other stored list, shown after a change of language: no write
        variant = {"fr": "fr-fr", "de": "de", "en": "en-gb"}[other]
        d = h.setting("practised", variant)
        check(d["step"] and not d.get("write"), "a change of setting is a step and produces NO write")
        d = h.press(cmd="state")
        st = db("SELECT text, gloss FROM lists WHERE uid='me' AND lang=? ORDER BY position", other)
        check([(x["text"], x["gloss"]) for x in S(d)["body"]["list"]] == st, f"the stored {other} list ({len(st)} items) shows after the change of language")
        d = h.do("show", "Vocabulary")
        nv = db("SELECT COUNT(*) FROM vocabulary WHERE uid='me' AND lang=?", other)[0][0]
        check(len(S(d)["body"]["rows"]) == nv, f"Vocabulary for {other}: {len(S(d)['body']['rows'])} rows = stored {nv}")
        h.do("show", "Practice")
        check(db("SELECT practised FROM settings WHERE uid='me'")[0][0] == me0[1], "the database still holds the old settings (nothing written at the change)")
    else:
        print("   (only one stored list: language change not exercised)")

    print("\n=== sign out: the settings are written ===")
    d = h.do("signOut")
    s = S(d)
    check(d["step"] and d["write"]["kind"] == "putSettings" and d["write"]["uid"] == "me", f"signOut writes putSettings ({d.get('write')})")
    check(s["uid"] == "" and s["summary"] == "Signed out" and s["tabs"] == [] and s["body"]["kind"] == "signedOut"
          and "me" in s["body"]["people"] and s["signOut"] is False, f"the slot is signed out; people {s['body']['people']}")
    check(db("SELECT practised FROM settings WHERE uid='me'")[0][0] == (variant if other else me0[1]), "the settings were applied to the database")
    d = h.do("check")
    check(not d["step"], "a press while signed out is no step")
    d = h.do("signIn", "nobody")
    check(not d["step"], "an unknown name does not sign in")

    print("\n=== register anna ===")
    d = h.do("register", "anna")
    s = S(d)
    check(d["step"] and d["write"] == {"kind": "putLearner", "uid": "anna", "settings": {"own": "en", "practised": "fr-fr", "slow": False}},
          f"register writes putLearner ({d.get('write')})")
    check(s["uid"] == "anna" and s["body"]["kind"] == "practice", "the slot is anna's app")
    check(db("SELECT own, practised, slow FROM settings WHERE uid='anna'") == [("en", "fr-fr", 0)], "anna is in the database")
    check(db("SELECT COUNT(*) FROM vocabulary WHERE uid='anna'")[0][0] == 0 and db("SELECT COUNT(*) FROM history WHERE uid='anna'")[0][0] == 0,
          "anna has no vocabulary and no history")
    check(len(S(h.do("show", "Vocabulary"))["body"]["rows"]) == 0 and len(S(h.do("show", "History"))["body"]["rows"]) == 0, "anna's views are empty")
    d = h.do("addWord", "chat")
    check(d["step"], "anna adds a word")
    check(len(S(h.do("show", "Vocabulary"))["body"]["rows"]) == 1 and db("SELECT COUNT(*) FROM vocabulary WHERE uid='anna'")[0][0] == 1
          and db("SELECT COUNT(*) FROM vocabulary WHERE uid='me'")[0][0] == n_vocab, "the word is anna's, me's vocabulary is as it was")
    d = h.do("register", "anna")
    check(not d["step"], "register is no step when signed in (and a name taken is none)")
    d = h.do("signOut")
    check(d["write"]["kind"] == "putSettings" and d["write"]["uid"] == "anna", "anna signs out")
    d = h.do("register", "anna")
    check(not d["step"], "a name already registered cannot be registered")
    d = h.do("signIn", "me")
    s = S(d)
    v = S(h.do("show", "Vocabulary"))["body"]["rows"]
    nv = db("SELECT COUNT(*) FROM vocabulary WHERE uid='me' AND lang=?", LANG_OF[S(d)["settings"]["practised"]])[0][0]
    check(s["uid"] == "me" and len(v) == nv and all("chat" not in json.dumps(r, ensure_ascii=False) for r in v),
          f"me signs in: me's data ({len(v)} vocabulary rows, as stored), not anna's")
    h.do("show", "Practice")

    print("\n=== a reload returns the live state ===")
    h.do("show", "Vocabulary")
    d = h.press(cmd="start")
    check(S(d)["uid"] == "me" and S(d)["body"]["kind"] == "vocabulary", "start (a reload) is the live state: me, in the Vocabulary view")
    h.do("signOut")
    d = h.press(cmd="start")
    check(S(d)["uid"] == "" and S(d)["body"]["kind"] == "signedOut", "a reload while signed out shows the signed-out screen")
    h.do("signIn", "me")
    h.do("show", "Practice")

    print("\n=== fresh: signs out (settings saved), then starts afresh ===")
    was = db("SELECT slow FROM settings WHERE uid='me'")[0][0]
    h.setting("slow", not was)                        # a change, whatever the real store holds
    check(db("SELECT slow FROM settings WHERE uid='me'")[0][0] == was, f"slow changed to {not was} is not yet stored")
    d = h.press(cmd="start", fresh=True)
    check(db("SELECT slow FROM settings WHERE uid='me'")[0][0] == int(not was), "fresh: the setting was saved by the sign-out")
    check(S(d)["uid"] == "me" and S(d)["settings"]["slow"] is (not was) and S(d)["body"]["kind"] == "practice",
          "then a start afresh, auto sign-in as me with slow kept")
    h.setting("slow", False)
    h.do("signOut")
    h.do("signIn", "me")
    h.setting("slow", True)                            # changed since sign-in, never signed out: the clean stop must save it
    h.setting("own", "de")

    print("\n=== SIGTERM while signed in with a changed setting ===")
    code = h.stop(signal.SIGTERM)
    check(code == 0, f"the host exited by itself, code {code}")
    check("clean stop: signed out me" in log(), "the log says the clean stop signed me out")
    check(db("SELECT own, slow FROM settings WHERE uid='me'") == [("de", 1)], "the settings changed since sign-in are in the database")
    h.start()
    d = h.press(cmd="start")
    check(S(d)["uid"] == "me" and S(d)["settings"]["own"] == "de" and S(d)["settings"]["slow"] is True,
          "after the restart: auto sign-in as me, the changed settings are there")
    d = h.do("signOut")
    check("anna" in S(d)["body"]["people"] and "me" in S(d)["body"]["people"], f"anna is still registered ({S(d)['body']['people']})")
    h.do("signIn", "anna")                             # leave anna signed in; SIGINT also stops cleanly
    h.setting("slow", True)
    check(h.stop(signal.SIGINT) == 0 and db("SELECT slow FROM settings WHERE uid='anna'")[0][0] == 1, "SIGINT is a clean stop too")

    print("\n=== kill -9 loses the changes since sign-in (as documented) ===")
    h.start()
    h.press(cmd="start")                               # auto sign-in: me
    h.setting("own", "fr")
    h.proc.kill()
    h.proc.wait(10)
    check(db("SELECT own FROM settings WHERE uid='me'")[0][0] == "de", "after kill -9 the setting changed since sign-in is lost")
    h.start()
    check(S(h.press(cmd="start"))["settings"]["own"] == "de", "the restart shows the last saved one")
    h.stop()

    print("\n=== NEOLINGO_AUTOSIGNIN empty, NEOLINGO_SLOTS=2 ===")
    h2 = Host(NEOLINGO_SLOTS="2", NEOLINGO_AUTOSIGNIN="")
    h2.start()
    ver = h2.get("version")
    check(ver["slots"] == 2 and ver["autosignin"] == "", f"/version: slots {ver['slots']}, autosignin {ver['autosignin']!r}")
    d = h2.press(cmd="start")
    check(len(d["screens"]) == 2 and all(x["uid"] == "" and x["body"]["kind"] == "signedOut" for x in d["screens"]),
          "two slots, both signed out")
    everyone = {u for (u,) in db("SELECT uid FROM settings")}            # the real database's learners, and anna
    check(set(S(d)["body"]["people"]) == everyone and {"me", "anna"} <= everyone, f"the people: {S(d)['body']['people']}")
    d = h2.do("signIn", "me", 1)
    check(S(d, 1)["body"].get("elsewhere") == ["me"] and S(d, 0)["uid"] == "me",
          f"me signs in at slot 1: the signed-out slot 2 marks me as signed in on another screen ({S(d, 1)['body'].get('elsewhere')})")
    print("\n=== one session per learner (14 October) ===")
    c = h2.press(cmd="can", asks=[{"press": "signIn", "session": 2, "input": "me"}, {"press": "signIn", "session": 2, "input": "anna"}])
    check(c["can"] == [False, True] and "already signed in" in c["why"][0], f"can: me at slot 2 no ({c['why'][0]!r}), anna yes")
    d = h2.do("signIn", "me", 2)
    check(not d["step"] and d["message"] == "\u201cme\u201d is already signed in." and S(d, 1)["uid"] == "" and S(d, 0)["uid"] == "me",
          f"Sign in as me at slot 2 is refused: {d['message']!r}; slot 2 stays signed out")
    check("press signIn slot 2: no step: \u201cme\u201d is already signed in." in log(), "the log says why")
    d = h2.do("signIn", "anna", 2)
    check(S(d, 0)["uid"] == "me" and S(d, 1)["uid"] == "anna", "me in slot 1 and anna in slot 2, side by side")
    d = h2.do("show", "Vocabulary", 2)
    check(S(d, 1)["body"]["kind"] == "vocabulary" and S(d, 0)["body"]["kind"] == "practice", "the slots are independent")
    h2.setting("slow", False, 2)
    print("\n=== a form open: Sign out and a change of language wait; a clean stop cancels it and saves the settings ===")
    d = h2.do("edit", "chat", 2)
    check(d["step"] and any(r["word"] == "chat" and r.get("editing") for r in S(d, 1)["body"]["rows"]), "anna opens the form of 'chat' at slot 2")
    d = h2.do("signOut", None, 2)
    check(not d["step"] and d["message"] == "Save or cancel the open form first." and S(d, 1)["uid"] == "anna",
          f"Sign out with the form open is refused: {d['message']!r}")
    h2.do("openSettings", None, 2)
    d = h2.do("practised", "de", 2)
    check(not d["step"] and d["message"] == "Save or cancel the open form first.", f"a change of language with the form open is refused: {d['message']!r}")
    d = h2.do("closeSettings", None, 2)
    check(any(r["word"] == "chat" and r.get("editing") for r in S(h2.do("show", "Vocabulary", 2), 1)["body"]["rows"]), "the form is still open")
    h2.stop()
    check("clean stop: signed out me, anna" in log(), "the clean stop signed both slots out")
    check("sign-out: slot 2 (anna) had open form(s) chat: cancelled so that the settings are saved" in log(),
          "the clean stop cancelled anna's open form first (the log names it)")
    check(db("SELECT slow FROM settings WHERE uid='anna'")[0][0] == 0, "anna's setting from slot 2 was saved")
    check(db("SELECT COUNT(*) FROM vocabulary WHERE uid='anna' AND word='chat'")[0][0] == 1, "anna's word is kept (Cancel drops only the form)")
    h3 = Host(NEOLINGO_AUTOSIGNIN="nobody")
    h3.start()
    check(S(h3.press(cmd="start"))["uid"] == "" and "'nobody' is not registered" in log(), "an auto sign-in name that is not registered: signed out, logged")
    h3.stop()

    guest_section()

    print()
    if fails:
        sys.exit(f"{len(fails)} FAILED: " + "; ".join(fails))
    print("all passed")


if __name__ == "__main__":
    main()
