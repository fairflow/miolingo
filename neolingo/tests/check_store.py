"""Unit cases of host.store (practice lists, unknown writes) and host.archive (test voices).  No models, no engine:
    <miolingo venv python> tests/check_store.py
Works in a scratch folder; the running host's var/ is untouched.

Each case is named by the fault it guards (locus docs/neolingo-test-design.md 4D).  No case here guards a fault that
occurred: each is "designed <date> (<commit>)", written with the feature it states.
The faults of the store that did occur are guarded elsewhere: a guest's takes kept (13 Oct) in check_signin's guest
section; the first learner of an empty store (13 Oct, the protocol's fault) in check_host."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

tmp = tempfile.mkdtemp(prefix="neolingo_store_")
os.environ["NEOLINGO_VAR"] = tmp
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from host import paths, archive      # noqa: E402
from host.store import Store         # noqa: E402

bad = []
TAG = ""                                     # the case's name prefix: the feature's date and commit


def check(cond, what):
    what = TAG + what
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        bad.append(what)


paths.make_dirs()
TAG = "designed 13 Oct (e1352e0, stored lists): "
# a database made BEFORE the lists table existed: the three old tables, with data
old = Path(tmp) / "old.sqlite"
c = sqlite3.connect(old)
c.executescript("""
CREATE TABLE settings (uid TEXT PRIMARY KEY, own TEXT NOT NULL, practised TEXT NOT NULL, slow INTEGER NOT NULL);
CREATE TABLE vocabulary (uid TEXT NOT NULL, lang TEXT NOT NULL, word TEXT NOT NULL, translation TEXT NOT NULL, notes TEXT NOT NULL,
  position INTEGER NOT NULL, PRIMARY KEY (uid, lang, word));
CREATE TABLE history (uid TEXT NOT NULL, seq INTEGER NOT NULL, variant TEXT NOT NULL, target TEXT NOT NULL, recognised TEXT NOT NULL,
  ipa TEXT NOT NULL, score INTEGER NOT NULL, understood INTEGER NOT NULL, flags TEXT NOT NULL, PRIMARY KEY (uid, seq));
INSERT INTO settings VALUES ('me','en','de',0);
INSERT INTO vocabulary VALUES ('me','fr','gare','station','',0);
INSERT INTO history VALUES ('me',0,'fr-fr','a','a','[["a"]]',90,1,'[]');
""")
c.commit()
c.close()
s = Store(old)
d = s.data("me")
check(d["settings"] == {"own": "en", "practised": "de", "slow": False} and d["vocab"][0]["entries"][0]["word"] == "gare"
      and len(d["history"]) == 1, "an old database keeps working (settings, vocabulary, history as before)")
check(d["lists"] == [], "no stored lists: \"lists\": []")
tables = {r[0] for r in sqlite3.connect(old).execute("select name from sqlite_master where type='table'")}
check("lists" in tables, "the lists table was created beside the old ones")

w = {"kind": "putList", "uid": "me", "lang": "fr", "items": [{"text": "Bonjour", "gloss": "Hello"}, {"text": "Merci", "gloss": ""}, {"text": "Au revoir", "gloss": "Goodbye"}]}
r = s.apply(w)
check(s.data("me")["lists"] == [{"lang": "fr", "items": w["items"]}], f"putList stores the list in order ({r})")
w2 = dict(w, items=[{"text": "Salut", "gloss": "Hi"}])
s.apply(w2)
check(s.data("me")["lists"] == [{"lang": "fr", "items": w2["items"]}], "putList again REPLACES the list of that language")
s.apply({"kind": "putList", "uid": "me", "lang": "de", "items": [{"text": "Hallo", "gloss": "Hello"}]})
check([x["lang"] for x in s.data("me")["lists"]] == ["de", "fr"], "a list for each language")
s.apply({"kind": "putList", "uid": "me", "lang": "fr", "items": []})
check([x["lang"] for x in s.data("me")["lists"]] == ["de"], "putList with no items empties that language")
before = s.data("me")
try:                                        # a bad item must roll the whole transaction back
    s.apply({"kind": "putList", "uid": "me", "lang": "de", "items": [{"text": "Eins"}, {"nogloss": 1}]})
    check(False, "a bad item should raise")
except KeyError:
    check(s.data("me") == before, "a bad item rolls the transaction back: the old list is intact")
other = s.data("you")
check(other["lists"] == [], "another learner has no lists")
n = len(open(paths.LOG).read()) if paths.LOG.exists() else 0
r = s.apply({"kind": "putNonsense", "uid": "me"})
log = open(paths.LOG).read()[n:]
check("UNKNOWN WRITE KIND" in r and "ERROR" in log and "putNonsense" in log, "an unknown write kind is logged loudly and reported, not applied")
check(s.data("me")["history"] == before["history"] and s.counts("me")["lists"] == 1, "the unknown write changed nothing")
s2 = Store(old)
check(s2.data("me")["lists"] == before["lists"], "the lists survive a reopen")

# test voices
TAG = "designed 13 Oct (66ff9a5, test voices): "
(paths.ARCHIVE / "overseer_takes.txt").write_text("# comment\nt7719675e889caccd  2026-10-13 13:57  fr-fr  D'accord  macOS say\n\nnonsense line\n", "utf-8")
check(archive.test_voice_tokens() == {"t7719675e889caccd"}, "overseer_takes.txt: first field of each non-comment line that is a take token")
import json
lines = [{"time": "2026-10-13T10:00:00", "take": "t7719675e889caccd", "variant": "fr-fr", "text": "D'accord"},
         {"time": "2026-10-13T11:00:00", "take": "t0123456789abcdef", "variant": "fr-fr", "text": "Bonjour"}]
(paths.ARCHIVE / "checks.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n", "utf-8")
L = archive.listing()
src = {i["take"]: i.get("source") for i in L["items"]}
check(src == {"t7719675e889caccd": "test-voice", "t0123456789abcdef": None} and L["total"] == 2, f"archive items: test voice labelled, none removed ({src})")
H = archive.listing(hide_test=True)
check([i["take"] for i in H["items"]] == ["t0123456789abcdef"] and H["total"] == 1, "hide_test leaves the test voice out (and out of the count)")
(paths.ARCHIVE / "overseer_takes.txt").unlink()
check(archive.test_voice_tokens() == set() and all("source" not in i for i in archive.listing()["items"]), "no overseer_takes.txt: nothing labelled")

# sign-in: putLearner, the whole store, the learner in the archive
TAG = "designed 13 Oct (85d5f9b, sign-in): "
t = Store(Path(tmp) / "new.sqlite")
check(t.uids() == [] and t.all_data() == [], "a new store has no learner")
P = {"own": "en", "practised": "fr-fr", "slow": False}
r = t.apply({"kind": "putLearner", "uid": "anna", "settings": P})
check(t.uids() == ["anna"] and t.data("anna") == {"uid": "anna", "settings": P, "vocab": [], "history": [], "lists": []}, f"putLearner adds a learner with nothing kept ({r})")
t.apply({"kind": "putEntry", "uid": "anna", "lang": "fr", "entry": {"word": "chat", "translation": "cat", "notes": ""}})
r = t.apply({"kind": "putLearner", "uid": "anna", "settings": dict(P, slow=True)})
check(t.data("anna")["settings"] == P and len(t.data("anna")["vocab"]) == 1, f"putLearner on a name that exists does nothing ({r})")
t.apply({"kind": "putLearner", "uid": "bo", "settings": P})
check(t.uids() == ["anna", "bo"] and [x["uid"] for x in t.all_data()] == ["anna", "bo"], "all_data: every learner")
check(s.uids()[0] == "me" and s.all_data()[0]["uid"] == "me", "an old database: its one learner is found")

paths.make_dirs()
reply = {"screens": [{"uid": "anna", "body": {}}, {"uid": "", "body": {}}]}
check(archive.learner_of({"session": 1}, reply) == "anna" and archive.learner_of({"session": 2}, reply) == ""
      and archive.learner_of({"session": 3}, reply) == "", "learner_of: the session's learner, empty when signed out or unknown")
n = len(archive.read_lines("records.jsonl"))
archive.log_record({"press": "record", "session": 2, "input": "t0123456789abcdef"}, dict(reply, step=True), [])
check(len(archive.read_lines("records.jsonl")) == n, "a Record line is not written for a signed-out session")
archive.log_record({"press": "record", "session": 1, "input": "t0123456789abcdef"}, dict(reply, step=True), [])
check(archive.read_lines("records.jsonl")[-1]["uid"] == "anna", "a Record line carries the learner")
rows = [{"time": "2026-10-13T12:00:00", "uid": "anna", "take": "t1111111111111111", "variant": "fr-fr"},
        {"time": "2026-10-13T12:01:00", "uid": "me", "take": "t2222222222222222", "variant": "fr-fr"}]
with open(paths.ARCHIVE / "checks.jsonl", "a", encoding="utf-8") as f:
    f.write("\n".join(json.dumps(x) for x in rows) + "\n")
L = archive.listing()
check({i["take"]: i["uid"] for i in L["items"]} == {"t7719675e889caccd": "me", "t0123456789abcdef": "me", "t1111111111111111": "anna", "t2222222222222222": "me"},
      "listing: every item has a uid; lines without one count as me")
A = archive.listing(uid="anna")
check([i["take"] for i in A["items"]] == ["t1111111111111111"] and A["total"] == 1, "listing: the uid filter (and the count)")
check(archive.listing(uid="me")["total"] == 3, "listing: me includes the older lines")
j = archive.judge("t1111111111111111", "fair")
check(j["uid"] == "anna" and archive.judge("t7719675e889caccd", "harsh")["uid"] == "me" and archive.judge("t3333333333333333", "fair")["uid"] == "me",
      "judge: the uid of the take's learner (older or unknown takes: me)")

# columns_of: an old line's columns, a new line's picture, alike
TAG = "designed 14 Oct (f13808e, the picture): "
old_line = {"columns": [[{"target": "ɡ", "heard": "d", "mark": 2}]]}
new_line = {"picture": [{"token": "gare", "sounds": [{"target": "ɡ", "heard": "d", "kind": "off", "mark": 2}]}]}
check(archive.columns_of(old_line) == archive.columns_of(new_line) == old_line["columns"]
      and archive.columns_of({"result": {"picture": new_line["picture"]}}) == old_line["columns"]
      and archive.columns_of({"columns": None, "result": None}) is None, "columns_of: columns (before 14 October) and picture (since) alike")

# the configuration's optional numbers (protocol 5): significant, and unjudged from the calibrated unreliable lists
TAG = "designed 14 Oct (f13808e, the configuration): "
import json                          # noqa: E402
from host.engine_config import build_config   # noqa: E402
cfg = build_config()
table = json.loads((paths.DATA / "cost_table.json").read_text("utf-8"))
check(cfg["significant"] == 42, "config: significant 42 (raw panphon costs)")
check(cfg["unjudged"] == [{"lang": "en", "sounds": table["langs"]["en"]["unreliable"]}, {"lang": "de", "sounds": ["y", "yː", "øː", "œ", "ɔø"]}]
      and table["langs"]["en"]["unreliable"] and not table["langs"]["fr"]["unreliable"],
      f"config: unjudged for en {cfg['unjudged'][0]['sounds']} and de, none for fr")

if bad:
    sys.exit(f"{len(bad)} FAILED")
print("all passed")
