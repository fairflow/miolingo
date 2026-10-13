"""Unit cases of host.store (practice lists, unknown writes) and host.archive (test voices).  No models, no engine:
    <miolingo venv python> tests/check_store.py
Works in a scratch folder; the running host's var/ is untouched."""
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


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        bad.append(what)


paths.make_dirs()
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

if bad:
    sys.exit(f"{len(bad)} FAILED")
print("all passed")
