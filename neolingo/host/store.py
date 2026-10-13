"""The store: SQLite, the three tables of protocol section 4, ONE learner."""
import json
import sqlite3
import threading

DEFAULT_SETTINGS = {"own": "en", "practised": "fr-fr", "slow": False}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (uid TEXT PRIMARY KEY, own TEXT NOT NULL, practised TEXT NOT NULL, slow INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS vocabulary (uid TEXT NOT NULL, lang TEXT NOT NULL, word TEXT NOT NULL,
  translation TEXT NOT NULL, notes TEXT NOT NULL, position INTEGER NOT NULL, PRIMARY KEY (uid, lang, word));
CREATE TABLE IF NOT EXISTS history (uid TEXT NOT NULL, seq INTEGER NOT NULL, variant TEXT NOT NULL, target TEXT NOT NULL,
  recognised TEXT NOT NULL, ipa TEXT NOT NULL, score INTEGER NOT NULL, understood INTEGER NOT NULL, flags TEXT NOT NULL,
  PRIMARY KEY (uid, seq));
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.lock = threading.Lock()
        self.db.executescript(SCHEMA)

    def data(self, uid):
        """The stored data of one learner, as `start` wants it."""
        with self.lock:
            c = self.db
            row = c.execute("SELECT own, practised, slow FROM settings WHERE uid=?", (uid,)).fetchone()
            if row is None:
                c.execute("INSERT INTO settings VALUES (?,?,?,?)", (uid, DEFAULT_SETTINGS["own"],
                          DEFAULT_SETTINGS["practised"], 0))
                settings = dict(DEFAULT_SETTINGS)
            else:
                settings = {"own": row[0], "practised": row[1], "slow": bool(row[2])}
            vocab = []
            for (lang,) in c.execute("SELECT DISTINCT lang FROM vocabulary WHERE uid=? ORDER BY "
                                     "(SELECT MIN(position) FROM vocabulary v WHERE v.uid=vocabulary.uid AND v.lang=vocabulary.lang)", (uid,)).fetchall():
                es = [{"word": w, "translation": t, "notes": n} for (w, t, n) in c.execute(
                    "SELECT word, translation, notes FROM vocabulary WHERE uid=? AND lang=? ORDER BY position", (uid, lang))]
                vocab.append({"lang": lang, "entries": es})
            history = [{"uid": uid, "variant": v, "target": t, "recognised": r, "ipa": json.loads(i), "score": s,
                        "understood": bool(u), "flags": json.loads(f)}
                       for (v, t, r, i, s, u, f) in c.execute(
                "SELECT variant, target, recognised, ipa, score, understood, flags FROM history WHERE uid=? ORDER BY seq", (uid,))]
            return {"uid": uid, "settings": settings, "vocab": vocab, "history": history}

    def counts(self, uid):
        with self.lock:
            q = lambda t: self.db.execute(f"SELECT COUNT(*) FROM {t} WHERE uid=?", (uid,)).fetchone()[0]
            return {"vocabulary": q("vocabulary"), "history": q("history")}

    def _put(self, uid, lang, e):
        c = self.db
        if c.execute("SELECT 1 FROM vocabulary WHERE uid=? AND lang=? AND word=?", (uid, lang, e["word"])).fetchone():
            c.execute("UPDATE vocabulary SET translation=?, notes=? WHERE uid=? AND lang=? AND word=?",
                      (e.get("translation", ""), e.get("notes", ""), uid, lang, e["word"]))
        else:
            pos = c.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM vocabulary WHERE uid=? AND lang=?", (uid, lang)).fetchone()[0]
            c.execute("INSERT INTO vocabulary VALUES (?,?,?,?,?,?)",
                      (uid, lang, e["word"], e.get("translation", ""), e.get("notes", ""), pos))

    def apply(self, w):
        """One write of the engine, in one transaction.  Returns a line saying what was done."""
        k, uid = w["kind"], w["uid"]
        with self.lock:
            c = self.db
            c.execute("BEGIN")
            try:
                if k == "appendRow":
                    r = w["row"]
                    seq = c.execute("SELECT COALESCE(MAX(seq), -1) + 1 FROM history WHERE uid=?", (uid,)).fetchone()[0]
                    c.execute("INSERT INTO history VALUES (?,?,?,?,?,?,?,?,?)",
                              (uid, seq, r["variant"], r["target"], r["recognised"],
                               json.dumps(r["ipa"], ensure_ascii=False), r["score"], int(bool(r["understood"])),
                               json.dumps(r["flags"], ensure_ascii=False)))
                    what = f"history row: {r['target']} / {r['recognised']} / {r['score']}%"
                elif k == "putEntry":
                    self._put(uid, w["lang"], w["entry"])
                    what = f"entry {w['entry']['word']} ({w['lang']})"
                elif k == "putEntries":
                    for e in w["entries"]:
                        self._put(uid, w["lang"], e)
                    what = f"{len(w['entries'])} entries ({w['lang']})"
                elif k == "dropEntry":
                    c.execute("DELETE FROM vocabulary WHERE uid=? AND lang=? AND word=?", (uid, w["lang"], w["key"]))
                    what = f"drop {w['key']} ({w['lang']})"
                elif k == "putSettings":
                    s = w["settings"]
                    c.execute("INSERT OR REPLACE INTO settings VALUES (?,?,?,?)", (uid, s["own"], s["practised"], int(bool(s["slow"]))))
                    what = f"settings {s}"
                else:
                    raise ValueError(f"unknown write {k!r}")
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
        return f"{k}: {what}"
