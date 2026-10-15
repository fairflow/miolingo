"""The host, over HTTP only (plus a look into its SQLite file).
ARCHIVED 15 October 2026 (tests/archive/README.md): the full check_host of 14 October, before H1 (tests/check_suite.py).

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/archive/check_host_before_h1.py

Starts the host on a free port with its own var/ directory (var/check_host/, git-ignored, emptied first), so the
running host's database is untouched.  Every recording is SYNTHETIC (espeak-ng); the microphone is not exercised.
The phrase said is the first phrase of the list with at least three words: the first phrase of each list is a
single short word ("Oui"), under the quarter second of sound that env.audible requires.
"""
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VAR = ROOT / "var" / "check_host"
ESPEAK = shutil.which("espeak-ng") or "espeak-ng"
VOICE = {"fr-fr": "fr-fr", "en-gb": "en-gb", "de": "de"}
LANG_OF = {"fr-fr": "fr", "en-gb": "en", "de": "de"}
KINDS = {"ok", "accepted", "near", "off", "missing", "added", "unjudged"}       # protocol 6.0, the picture's kinds
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
    def __init__(self):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}/"
        self.proc = None

    def start(self):
        t0 = time.perf_counter()
        self.proc = subprocess.Popen([sys.executable, "-m", "host.serve", "--port", str(self.port)], cwd=ROOT,
                                     env=dict(os.environ, NEOLINGO_VAR=str(VAR), NEOLINGO_JUDGING="1"),
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
        return time.perf_counter() - t0

    def stop(self):
        self.proc.terminate()
        self.proc.wait(20)

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=300) as r:
            return r.read(), r.headers.get("Content-Type")

    def press(self, **m):
        r = urllib.request.Request(self.base + "press", json.dumps(m).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=600) as f:
            return json.load(f)

    def setting(self, which, value, session=1):
        """Change a setting.  Since 13 October the settings are a view of their own: `practised`, `own` and `slow` are
        steps only while it is open, so open it, change, close it.  Returns the reply to the change itself."""
        self.press(press="openSettings", session=session, input=None)
        d = self.press(press=which, session=session, input=value)
        self.press(press="closeSettings", session=session, input=None)
        return d

    def begin(self):
        """The page's `start`; a new database gets `me` (registered by the host) and auto sign-in."""
        d = self.press(cmd="start")
        assert d["screens"][0]["uid"] == "me", "not signed in as me"
        return d

    def take(self, wav):
        r = urllib.request.Request(self.base + "take", Path(wav).read_bytes(), {"Content-Type": "audio/wav"})
        with urllib.request.urlopen(r, timeout=60) as f:
            return json.load(f)["take"]


def db_counts():
    c = sqlite3.connect(VAR / "neolingo.sqlite")
    try:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("settings", "vocabulary", "history")}
    finally:
        c.close()


def body(d):
    return d["screens"][0]["body"]


def main():
    shutil.rmtree(VAR, ignore_errors=True)
    VAR.mkdir(parents=True)
    h = Host()
    print(f"engine and host start: {h.start():.1f} s (first start, models not yet loaded)")
    print(open(VAR / "host.log").read().strip().splitlines()[1])
    ver = json.loads(h.get("version")[0])
    print("version:", ver)
    first = (ROOT / "page" / "CHANGES").read_text("utf-8").splitlines()[0].split("\t", 1)
    check(ver["page"] == first[0] and ver["page"] != "unknown" and ver["changed"] == first[1], f"version.page/changed are the first line of CHANGES ({ver['page']})")
    check(ver["engine"] == (ROOT / "page" / "SOURCE").read_text().strip() and ver["engine"], f"version.engine is the hash in SOURCE ({ver['engine']})")
    check(len(ver["built"]) >= 16 and ver["instance"] == "real" and ver["host"] not in ("", "unknown"), f"version.built {ver['built']!r}, instance, host {ver['host']}")
    check(ver["tts"] in ("gtts", "say"), f"version.tts = {ver['tts']} (espeak is not a voice)")
    page = h.get("")[0].decode()
    check(page.index('<script src="host.js"></script>') < page.index("<script>"), "the page carries host.js before its own script")
    check(b"NeolingoHost" in h.get("host.js")[0], "host.js is served")
    lists = json.loads(h.get("lists")[0])
    check([l["variant"] for l in lists] == ["en-gb", "fr-fr", "de"] and all(len(l["items"]) > 10 for l in lists), "lists: en, fr, de")

    wl = json.loads(h.get("wordlists")[0])
    check(len(wl) >= 8 and all(set(l) == {"name", "lang", "words"} and l["words"] and all(isinstance(w, str) and w for w in l["words"]) for l in wl)
          and {l["lang"] for l in wl} == {"en", "fr", "de"}, f"wordlists: {len(wl)} lists, {sum(len(l['words']) for l in wl)} words, languages en fr de")
    d = h.press(cmd="start")
    check("test" not in d and "takes" not in d, "start: a real host (no 'test', no 'takes')")
    check(d["screens"][0]["uid"] == "me" and d["screens"][0]["body"]["kind"] == "practice",
          "a new database has no learner: the host registers me (the engine cannot register the first) and signs me in")
    check(d["screens"][0]["settings"] == {"own": "en", "practised": "fr-fr", "slow": False}, "default settings en / fr-fr / not slow")

    timings, dropped = {}, []
    for variant in ("fr-fr", "en-gb", "de"):
        print(f"\n=== {variant} ===")
        if variant != "fr-fr":
            d = h.setting("practised", variant)
            check(d["step"], f"practised {variant}")
        lst = next(l for l in lists if l["variant"] == variant)["items"]
        chosen = [p for p in lst if len(p["text"].split()) >= 3][:3]
        text = "\n".join(f"{p['text']} | {p['gloss']}" for p in chosen)
        d = h.press(press="load", session=1, input=text)
        b = body(d)
        check(b["phrase"] and b["phrase"]["text"] == chosen[0]["text"], f"load: first phrase is {chosen[0]['text']!r}, ipa {b['phrase']['ipa'] if b['phrase'] else None}")
        c = h.press(cmd="can", asks=[{"press": "record", "session": 1, "input": "x"}, {"press": "check", "session": 1, "input": None}])
        check(c["can"] == [True, False], f"can: record yes, check not yet ({c['can']})")
        wav = VAR / f"{variant}.wav"
        subprocess.run([ESPEAK, "-v", VOICE[variant], "-w", str(wav), chosen[0]["text"]], check=True)
        tk = h.take(wav)
        check(tk.isalnum(), f"take uploaded: {tk}")
        check((VAR / "takes" / f"{tk}.wav").exists(), "take file is under var/takes/")
        got, gct = h.get(f"take/{tk}.wav")
        check(got == wav.read_bytes() and gct == "audio/wav", f"GET take/{tk}.wav returns the uploaded bytes ({len(got)}, {gct})")
        d = h.press(press="record", session=1, input=tk)
        check(d["step"] and body(d)["held"], f"record: step, held ({d['message']!r})")
        before = db_counts()["history"]
        runs = []
        for run in ("cold", "warm"):
            t0 = time.perf_counter()
            d = h.press(press="check", session=1, input=None)
            runs.append(time.perf_counter() - t0)
            check(d["step"] and "write" in d and d["write"], f"check ({run}): a step with a write, {runs[-1]:.2f} s")
            check(d.get("droppedFlags") == 0, f"check ({run}): droppedFlags = {d.get('droppedFlags')!r} (0 expected)")
            dropped.append(d.get("droppedFlags"))
            if run == "cold":
                res = body(d)["result"]
                check(res is not None, "check: a result")
                print("   result:", json.dumps(res, ensure_ascii=False)[:400])
                pic = res.get("picture")
                check(isinstance(pic, list) and len(pic) == len(chosen[0]["text"].split()) and all(set(w) == {"token", "sounds"} for w in pic)
                      and all(set(x) == {"target", "heard", "kind", "mark"} and x["kind"] in KINDS and x["mark"] in (0, 1, 2)
                              for w in pic for x in w["sounds"]),
                      f"check: the result's picture, one entry a word ({len(pic or [])}), kinds "
                      f"{sorted({x['kind'] for w in pic or [] for x in w['sounds']})}")
                check("columns" not in res and "marked" not in res and isinstance(res.get("pictureLegend"), list)
                      and isinstance(res["heard"].get("text"), str), "check: no columns, no marked; pictureLegend and heard.text present")
                check(db_counts()["history"] == before + 1, "check: exactly one history row written to SQLite")
                check(isinstance(d["write"]["row"]["score"], int), f"score {d['write']['row']['score']}%")
            if run == "cold":
                shown = len(body(d)["result"]["flags"])
                flaglog = [l for l in open(VAR / "host.log").read().splitlines() if "flags:" in l][-1]
                print(f"   flags: {shown} shown on the screen; host log: {flaglog[20:]}")
                tk = h.take(wav)                         # a NEW token: the engine remembers answers per take
                d = h.press(press="record", session=1, input=tk)
                check(d["step"], "record again (new token) for the warm Check")
        timings[variant] = runs

    for bad in ("take/t0000000000000000.wav", "take/nonsense.wav", "take/..%2Fneolingo.sqlite", "take/t0123456789abcdef.wav.x",
                "take/%2e%2e/%2e%2e/etc/passwd", "take/", "take/t0000000000000000"):
        try:
            h.get(bad)
            check(False, f"GET {bad} should be 404")
        except urllib.error.HTTPError as e:
            check(e.code == 404, f"GET {bad}: {e.code} (404 expected)")

    print("\n=== German, a long vowel (length is kept: 'iː' is one sound, not 'i') ===")
    d = h.press(press="load", session=1, input="Ihnen geht es gut | You are well")
    b = body(d)
    check(b["phrase"] and "ː" in b["phrase"]["ipa"], f"load: the Target line shows a length mark: {b['phrase']['ipa'] if b['phrase'] else None}")
    wav = VAR / "de_long.wav"
    subprocess.run([ESPEAK, "-v", "de", "-w", str(wav), "Ihnen geht es gut"], check=True)
    d = h.press(press="record", session=1, input=h.take(wav))
    check(d["step"], "record: step")
    d = h.press(press="check", session=1, input=None)
    check(d["step"] and d.get("droppedFlags") == 0, f"check: droppedFlags = {d.get('droppedFlags')!r} (0 expected)")
    dropped.append(d.get("droppedFlags"))
    res = body(d)["result"]
    print("   result:", json.dumps(res, ensure_ascii=False)[:600])
    rs = json.dumps(res, ensure_ascii=False)
    check("iː" in rs and not any(c == "ː" and (k == 0 or rs[k - 1] in " [\"]") for k, c in enumerate(rs)),
          "the result shows the long sound 'iː' attached to its sound, no lone ː")

    print("\n=== a reload loses nothing: `start` is answered with the engine's present state ===")
    h.press(press="show", session=1, input="Practice")
    h.setting("practised", "fr-fr")
    three = [p for p in next(l for l in lists if l["variant"] == "fr-fr")["items"] if len(p["text"].split()) >= 3][:5]
    d = h.press(press="load", session=1, input="\n".join(f"{p['text']} | {p['gloss']}" for p in three))
    d = h.press(press="goto", session=1, input=3)
    check(body(d)["position"] == {"at": 3, "of": 5}, f"goto 3: place {body(d)['position']}")
    wav = VAR / "reload.wav"
    subprocess.run([ESPEAK, "-v", "fr-fr", "-w", str(wav), three[2]["text"]], check=True)
    tk = h.take(wav)
    d = h.press(press="record", session=1, input=tk)
    check(d["step"] and body(d)["held"], "record: held")
    d = h.press(cmd="start")                                   # the page loads again
    b = body(d)
    check(b["position"] == {"at": 3, "of": 5} and b["phrase"]["text"] == three[2]["text"] and len(b["list"]) == 5 and b["held"],
          f"reload: still phrase 3 of 5, list kept, recording held ({b['position']}, held {b['held']})")
    check("screens" in d and d["screens"][0]["settings"]["practised"] == "fr-fr", "reload: a full set of screens, settings as before")
    d = h.press(press="check", session=1, input=None)
    check(d["step"] and body(d)["result"] is not None, "check: a result")
    res1 = json.dumps(body(d)["result"], sort_keys=True)
    d = h.press(cmd="start")
    check(body(d)["result"] is not None and json.dumps(body(d)["result"], sort_keys=True) == res1 and body(d)["position"]["at"] == 3,
          "reload after Check: the result is still there, unchanged")
    d = h.press(cmd="start", model=True)
    check(d.get("model") is not None, "reload with model:true carries the model view")
    rows_before = db_counts()
    d = h.press(cmd="start", fresh=True)
    # Since the stored practice lists: a session starts on the STORED list of the language practised (Load wrote it), at
    # its first phrase; the place, the recording held and the result are per session and are gone.
    check([x["text"] for x in body(d)["list"]] == [p["text"] for p in three] and body(d)["position"]["at"] == 1
          and body(d)["phrase"]["text"] == three[0]["text"] and body(d)["result"] is None and not body(d)["held"],
          "start with fresh:true starts afresh: the stored list at its first phrase, no result, nothing held")
    check(db_counts() == rows_before, "the fresh start leaves the stored data as it was")
    check("fresh, as asked" in open(VAR / "host.log").read(), "the log says the start was fresh")
    h.setting("practised", "de")        # the later sections run in German, as before

    print("\n=== vocabulary and restart ===")
    h.press(press="show", session=1, input="Vocabulary")
    d = h.press(press="addWord", session=1, input="gare")
    check(d["step"], f"addWord: {d['message']!r}")
    counts = db_counts()
    print("   database:", counts)
    check(counts["history"] == 8 and counts["vocabulary"] >= 1, "SQLite holds the history rows and the word")
    settings_before = h.press(cmd="state")["screens"][0]["settings"]
    h.stop()
    print(f"host stopped; restart: {h.start():.1f} s")
    d = h.press(cmd="start")
    s = d["screens"][0]
    check(db_counts() == counts, "after restart the database is unchanged")
    d = h.press(press="show", session=1, input="Vocabulary")
    rows = body(d)["rows"]
    check(any("gare" in json.dumps(r, ensure_ascii=False) for r in rows), f"vocabulary after restart has 'gare' ({len(rows)} rows)")
    d = h.press(press="show", session=1, input="History")
    hist = json.dumps(body(d), ensure_ascii=False)
    check(len(body(d)["rows"]) >= 1, f"history after restart: {len(body(d)['rows'])} row(s) shown for the variant practised")
    print("   history view:", hist[:300])
    check(s["settings"] == settings_before and s["settings"]["practised"] == "de", f"settings after restart as before: {s['settings']}")

    print("\n=== judgements, the archive listing, the review page ===")
    def post_json(path, obj, raw=None):
        r = urllib.request.Request(h.base + path, raw if raw is not None else json.dumps(obj).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=30) as f:
                return f.status, json.load(f)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def get_json(path):
        try:
            return 200, json.loads(h.get(path)[0])
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    arch = json.loads(h.get("archive?limit=50")[0])
    items = arch["items"]
    check(len(items) >= 6 and arch["total"] == len(items) and arch["judged"] == 0, f"archive: {len(items)} checks, none judged ({arch['judged']} of {arch['total']})")
    check(all(a["time"] >= b["time"] for a, b in zip(items, items[1:])) and all(i["judgement"] is None for i in items), "archive: newest first, each with judgement null")
    check(all(k in items[0] for k in ("take", "variant", "text", "banner", "target", "hear", "picture")), "archive: the lines of checks.jsonl, with their fields")
    check(all(isinstance(i["picture"], list) and "columns" not in i and "missing" not in i for i in items),
          "archive: every new line carries the picture (no columns), nothing missing")
    sys.path.insert(0, str(ROOT))
    from host.archive import columns_of
    check(all([x["target"] for w in columns_of(i) for x in w if x["target"]] == [s for w in i["target"] for s in w] for i in items),
          "archive: columns_of(picture) gives the target sounds the engine asked about, in order")
    check(all(i["uid"] == "me" for i in items) and all(json.loads(l)["uid"] == "me" for l in open(VAR / "archive" / "checks.jsonl")),
          "archive: every check line and item carries the learner (me)")
    check(all(json.loads(l)["uid"] == "me" for l in open(VAR / "archive" / "records.jsonl")), "archive: every record line carries the learner")
    check(json.loads(h.get("archive?uid=me")[0])["total"] == len(items) and json.loads(h.get("archive?uid=anna")[0])["total"] == 0,
          "archive: the uid filter")
    t1, t2 = items[0]["take"], items[1]["take"]
    check(get_json(f"judgement?take={t1}") == (200, {}), "judgement of an unjudged take is {}")
    st, j = post_json("judge", {"take": t1, "verdict": "harsh", "note": "the rise was fine"})
    check(st == 200 and j["verdict"] == "harsh" and j["who"] == "me" and j["take"] == t1, f"judge: harsh stored ({st})")
    st, j = post_json("judge", {"take": t1, "verdict": "fair"})
    check(st == 200, "judge: a later line for the same take")
    got = get_json(f"judgement?take={t1}")[1]
    check(got["verdict"] == "fair" and "note" not in got, f"judgement: the later line supersedes ({got})")
    post_json("judge", {"take": t2, "verdict": "generous", "note": "  heard a vowel that was not there "})
    got = get_json(f"judgement?take={t2}")[1]
    check(got["verdict"] == "generous" and got["note"] == "heard a vowel that was not there", "judgement: a note is kept (trimmed)")
    lines = [json.loads(l) for l in open(VAR / "archive" / "judgements.jsonl")]
    check(len(lines) == 3 and all(l["time"][:4].isdigit() and l["who"] == "me" for l in lines), "judgements.jsonl: one line a judgement, appended")
    for what, bad in (("bad verdict", {"take": t1, "verdict": "great"}), ("no verdict", {"take": t1}), ("bad token", {"take": "../x", "verdict": "fair"}),
                       ("short token", {"take": "t12", "verdict": "fair"}), ("no take", {"verdict": "fair"}), ("note not text", {"take": t1, "verdict": "fair", "note": 5})):
        check(post_json("judge", bad)[0] == 400, f"judge refused: {what}")
    check(post_json("judge", None, raw=b"not json")[0] == 400 and post_json("judge", None, raw=b"[1]")[0] == 400, "judge refused: not a JSON object")
    check(len(open(VAR / "archive" / "judgements.jsonl").read().splitlines()) == 3, "the refused ones wrote nothing")
    check(all(json.loads(l)["uid"] == "me" for l in open(VAR / "archive" / "judgements.jsonl")), "every judgement carries the learner of its take")
    check(get_json("judgement?take=nonsense")[0] == 400, "judgement: bad token refused")
    arch = json.loads(h.get("archive?limit=50")[0])
    byt = {i["take"]: i for i in arch["items"]}
    check(byt[t1]["judgement"]["verdict"] == "fair" and byt[t2]["judgement"]["verdict"] == "generous" and arch["judged"] == 2,
          "archive: lines joined with the latest judgement; judged 2")
    un = json.loads(h.get("archive?unjudged=1")[0])
    check(t1 not in [i["take"] for i in un["items"]] and len(un["items"]) == len(items) - 2 and un["total"] == len(items), "archive: unjudged=1 leaves the judged out")
    one = json.loads(h.get("archive?limit=2")[0])
    rest = json.loads(h.get("archive?limit=50&before=" + urllib.request.quote(one["next"]))[0])
    check(len(one["items"]) == 2 and one["next"] and [i["take"] for i in one["items"] + rest["items"]] == [i["take"] for i in arch["items"]] and rest["next"] is None,
          "archive: paging with before= gives the same lines, no overlap")
    fr = json.loads(h.get("archive?variant=fr-fr")[0])
    check(fr["items"] and all(i["variant"] == "fr-fr" for i in fr["items"]) and fr["total"] < len(items), "archive: variant filter")
    check(get_json("archive?limit=x")[0] == 400, "archive: bad limit refused")
    data, ctype = h.get("review")
    check(b"<title>Neolingo: review of takes</title>" in data and ctype.startswith("text/html") and b"http://" not in data and b"https://" not in data,
          "review: HTML with its title, no external resource")
    check(json.loads(h.get("version")[0])["judging"] is True, "version: judging true by default")

    tv = items[2]["take"]
    (VAR / "archive" / "overseer_takes.txt").write_text(f"# test\n{tv}  2026-10-13 13:57  fr-fr  x  macOS say\n", "utf-8")
    arch2 = json.loads(h.get("archive?limit=50")[0])
    check({i["take"]: i.get("source") for i in arch2["items"]}.get(tv) == "test-voice" and sum(1 for i in arch2["items"] if i.get("source")) == 1
          and len(arch2["items"]) == len(items), "archive: source test-voice on the listed take, no take removed")
    arch3 = json.loads(h.get("archive?limit=50&hidetest=1")[0])
    check(tv not in [i["take"] for i in arch3["items"]] and len(arch3["items"]) == len(items) - 1, "archive: hidetest=1 leaves it out")
    check(b"hide test voices" in data and b"Mac voice (test)" in data, "review: has the filter and the label")
    (VAR / "archive" / "overseer_takes.txt").unlink()

    print("\n=== speak ===")
    CT = {"gtts": "audio/mpeg", "say": "audio/wav", "espeak": "audio/wav"}
    for engine in ("say", "gtts"):
        for variant, text in (("fr-fr", "Je cherche la gare"), ("en-gb", "Thank you very much"), ("en-us", "Thank you very much"), ("de", "Guten Tag")):
            t0 = time.perf_counter()
            try:
                data, ctype = h.get("speak?text=" + urllib.request.quote(text) + f"&variant={variant}&slow=false&engine={engine}")
            except urllib.error.HTTPError as e:
                if engine == "gtts":
                    print(f"   SKIPPED gtts {variant}: the network call failed (HTTP {e.code}: {e.read()[:120]!r}); no network?")
                    continue
                raise
            t1 = time.perf_counter() - t0
            ok = (data[:4] == b"RIFF" and data[8:12] == b"WAVE") if CT[engine] == "audio/wav" else (data[:3] == b"ID3" or data[:2] == b"\xff\xfb" or data[:2] == b"\xff\xf3")
            check(ok and len(data) > 3000 and ctype == CT[engine], f"speak {engine} {variant}: {ctype}, {len(data)} bytes, {t1:.2f} s")
    data, ctype = h.get("speak?text=Bonjour&variant=fr-fr&slow=true&engine=say")
    check(data[:4] == b"RIFF", "speak slow")
    import re
    chains = re.search(r"^CHAINS = (.*)$", (ROOT / "host" / "speech.py").read_text("utf-8"), re.M).group(1)
    check("espeak" not in chains, f"no speech chain contains espeak ({chains})")
    data, ctype = h.get("speak?text=Bonjour&variant=fr-fr&slow=false&engine=espeak")      # a request for espeak is not honoured
    check(not (ctype == "audio/wav" and len(data) > 3000 and json.loads(h.get("version")[0])["tts"] == "espeak"), "speak: engine=espeak is not honoured")
    data, ctype = h.get("speak?text=Bonjour%20tout%20le%20monde&variant=fr-fr&slow=false")      # the default engine, with its fallbacks
    ver = json.loads(h.get("version")[0])
    print(f"   default speak: {ctype}, {len(data)} bytes, engine in use: {ver['tts']}")
    check(ctype == CT[ver["tts"]] and len(data) > 3000, "default speak answers in the engine reported by /version")
    names = {p.suffix for p in (VAR / "speech").iterdir() if p.is_file()}
    check(bool(names & {".wav", ".mp3"}), f"speech cached under var/speech/ ({sorted(names)})")
    spoken = [l for l in open(VAR / "host.log").read().splitlines() if " speak " in l]
    print("   host log:", spoken[-1][20:])
    print(f"   droppedFlags on the Check presses: {dropped}")

    print("\n=== word lists: choose a list, upload its words, see the meanings ===")
    wl = json.loads(h.get("wordlists")[0])
    report = {}
    h.setting("own", "en")
    for lang in ("fr", "de", "en"):                      # for English the engine moves the learner's own language off English (to fr)
        variant = {"fr": "fr-fr", "de": "de", "en": "en-gb"}[lang]
        h.setting("practised", variant)
        h.press(press="show", session=1, input="Vocabulary")
        own = h.press(cmd="state")["screens"][0]["settings"]["own"]
        offered = got = 0
        for l in (x for x in wl if x["lang"] == lang):
            d = h.press(press="upload", session=1, input=l["words"])
            check(d["step"], f"upload {l['name']!r} ({len(l['words'])} words), own {own}: {d['message']!r}")
            rows = {r["word"]: r["translation"] for r in body(d)["rows"]}
            offered += len(l["words"]); got += sum(1 for w in l["words"] if rows.get(w))
        report[(lang, own)] = (offered, got)
        print(f"   words of {lang} lists with a meaning in own language {own}: {got} of {offered}")
    sys.path.insert(0, str(ROOT))
    import env                                           # the meaning tables (gloss.json, meanings.json), no model loaded
    for own in ("fr", "de"):                             # English words, by the tables themselves, for other own languages
        n = sum(1 for l in wl if l["lang"] == "en" for w in l["words"] if env.gloss(w, own, "en-gb"))
        print(f"   words of en lists with a meaning in own language {own} (table): {n}")
    check(report[("fr", "en")][1] >= 0.9 * report[("fr", "en")][0] and report[("de", "en")][1] >= 0.9 * report[("de", "en")][0],
          "at least 90% of the French and of the German words have an English meaning")
    check(db_counts()["vocabulary"] > 500, "the vocabulary rows are in SQLite")
    h.setting("own", "en")

    print("\nCheck timings (seconds), cold = first Check in that language in this host process, warm = second:")
    for v, (c, w) in timings.items():
        print(f"   {v}: cold {c:.2f}, warm {w:.2f}")
    log = open(VAR / "host.log").read()
    print("flag lines of the host log:")
    for l in log.splitlines():
        if "flags:" in l:
            print("  ", l)
    h.stop()
    node = shutil.which("node")
    if node:
        r = subprocess.run([node, str(ROOT / "tests" / "check_host_js.js")], capture_output=True, text=True)
        print(r.stdout + r.stderr)
        check(r.returncode == 0, "tests/check_host_js.js (WAV parser, peaks, showTake cache) under node")
    else:
        print("   SKIPPED tests/check_host_js.js: node is not installed")
    if fails:
        sys.exit(f"{len(fails)} FAILED: {fails}")
    print("\nall checks passed")


if __name__ == "__main__":
    main()
