"""The Neolingo host.   <miolingo venv python> -m host.serve --port 8810     (from neolingo/)

Drives the engine (`explore neohost`, docs/neolingo-host-protocol.md in the locus repository), keeps the store
in SQLite, answers the engine's questions from env, serves the page and the endpoints:
  GET  /  /index.html   the page, with <script src="host.js"> placed before its own script
  GET  /host.js         the recorder and the player
  GET  /version         JSON: page, changed, engine, built, instance, host, tts, started
  POST /press           the page's messages, forwarded to the engine.  `start` is answered with the engine's present
                        state when it already holds the session (a reload loses nothing); {"cmd":"start","fresh":true}
                        starts afresh
  GET  /take/<token>.wav   the stored WAV of that take, from var/takes or else the archive (404 if unknown)
  POST /take            a 16 kHz mono 16-bit WAV body; answers {"take": token}
  GET  /speak?text=&variant=&slow=   speech: MP3 (gTTS) or WAV (say); NEOLINGO_TTS; 503 {"err"} if no voice (never espeak)
  GET  /lists           the phrase lists of data/{en,fr,de}.json
  GET  /wordlists       the word lists of data/words_{en,fr,de}.json: [{name, lang, words:[...]}]
  POST /judge           {"take", "verdict": fair|harsh|generous, "note"}: appended to var/archive/judgements.jsonl
  GET  /judgement?take=  the latest judgement of that take, or {}
  GET  /archive?limit=&before=&variant=&unjudged=&hidetest=&uid=   archived checks, newest first, joined with their
                        judgements; "source":"test-voice" on the takes of var/archive/overseer_takes.txt
  GET  /review          the review page (page/review.html): a test tool for judging takes afterwards
  NEOLINGO_SLOTS=N       the number of session slots on the page (default 1; 2 shows two side by side)
  NEOLINGO_AUTOSIGNIN=U  after a real start the host signs U in at slot 1 if U is registered (default "me"; empty: start signed out)
  A clean stop (SIGTERM, SIGINT) signs every signed-in slot out first, so the settings changed since sign-in are saved
  (a vocabulary form left open, which refuses Sign out since 14 October, is cancelled first: the page that held its
  typed text is gone with the stop; the log names it).
  ONE SESSION PER LEARNER (engine of 14 October): Sign in as a learner signed in in another slot is refused (the engine's
  "“u” is already signed in."; a signed-out slot's screen lists such names in body.elsewhere); the host never starts the
  engine with a learner named twice.
  A GUEST's session (the Screen's "guest":true) is kept nowhere: no archive line, no archived take, the take files deleted at
  sign-out (and at a start or stop); GET /judgement?take= answers {"guest":true} for a guest's take and host.js draws nothing.
  NEOLINGO_JUDGING=0 turns off the judging buttons in the app page (the endpoints and /review stay)
Bound to 127.0.0.1 only."""
import argparse
import http.server
import json
import os
import re
import secrets
import signal
import subprocess
import threading
import time
import urllib.parse

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import env                                    # noqa: E402
from . import paths                           # noqa: E402
from .engine_config import build_config              # noqa: E402
from .engine import Engine                    # noqa: E402
from .log import log                          # noqa: E402
from .store import Store, DEFAULT_SETTINGS    # noqa: E402
from . import speech                          # noqa: E402
from . import archive                         # noqa: E402

STARTED = time.strftime("%Y-%m-%d %H:%M:%S %z")
UID = paths.UID
MAX_TAKE = 8_000_000                          # bytes: 30 s of 16 kHz 16-bit is under 1 MB


def slots():
    """NEOLINGO_SLOTS: how many session slots the engine is started with (default 1)."""
    try:
        return max(1, min(8, int(os.environ.get("NEOLINGO_SLOTS", "1").strip() or "1")))
    except ValueError:
        return 1


def autosignin():
    """NEOLINGO_AUTOSIGNIN: the learner the host signs in at slot 1 after a real start (default "me"; empty: none)."""
    return os.environ.get("NEOLINGO_AUTOSIGNIN", "me").strip().lower()


def judging_on():
    return os.environ.get("NEOLINGO_JUDGING", "1").strip() != "0"


def git_hash(path):
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def read_version():
    """What /version says (the fields the page reads, as the reference host gives them): `page` and `changed` from
    the first line of page/CHANGES ("version<TAB>text", newest first); `engine` the locus hash in page/SOURCE;
    `built` the engine binary's modification time; `instance` "real"; also `host` (this repository's short git
    hash), `tts` (the speech engine in use) and `started`."""
    v = {"page": "unknown", "changed": "", "engine": "", "built": "", "instance": "real",
         "host": git_hash(paths.ROOT), "tts": speech.IN_USE, "started": STARTED,
         "judging": judging_on(), "slots": slots(), "autosignin": autosignin()}
    try:
        first = (paths.PAGE / "CHANGES").read_text("utf-8").splitlines()[0].split("\t", 1)
        v["page"], v["changed"] = first[0], (first[1] if len(first) > 1 else "")
    except (OSError, IndexError):
        pass
    try:
        v["engine"] = (paths.PAGE / "SOURCE").read_text().strip()
    except OSError:
        pass
    try:
        v["built"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.stat(paths.ENGINE).st_mtime))
    except OSError:
        pass
    return v


def read_wordlists():
    out = []
    for lang in ("en", "fr", "de"):
        for l in json.loads((paths.DATA / f"words_{lang}.json").read_text("utf-8")):
            out.append({"name": l["name"], "lang": l["lang"], "words": l["words"]})
    return out


def read_lists():
    out = []
    for lang in ("en", "fr", "de"):
        d = json.loads((paths.DATA / f"{lang}.json").read_text("utf-8"))
        names = {"en": "English", "fr": "French", "de": "German"}
        out.append({"name": f"{names[lang]} phrases", "variant": d["variant"],
                    "items": [{"text": p["text"], "gloss": p.get("gloss", "")} for p in d["phrases"]]})
    return out


class Host:
    def __init__(self):
        paths.make_dirs()
        log(f"host starting; var = {paths.VAR}; engine = {paths.ENGINE}; takes are kept for good (archive: {paths.ARCHIVE})")
        self.started = False                      # the engine holds the session(s): a page's `start` is then a `state`
        self.held = {}                            # session -> the token of the latest recording held (a Check may ask nothing)
        self.uids = []                            # slot -> the learner signed in there ("" signed out), from the latest screens
        self.guests = []                          # slot -> True while a GUEST is in the slot (the Screen's "guest")
        self.guest_takes = {}                     # token -> slot of the guest who made it, or None: uploaded while a guest was in, owner unknown
        self.discard_listed()                     # takes of a guest left over from a run that did not end cleanly
        self.store = Store(paths.DB)
        self.engine = Engine(build_config())
        with self.engine.lock:
            self.start_engine()

    def note_screens(self, d):
        if isinstance(d, dict) and d.get("screens"):
            self.uids = [(s.get("uid") or "") for s in d["screens"]]
            self.guests = [bool(s.get("guest")) for s in d["screens"]]

    def is_guest(self, r):
        return isinstance(r, int) and 1 <= r <= len(self.guests) and self.guests[r - 1]

    def list_guest_takes(self):
        """var/guest_takes.txt names (not holds) the takes a guest may have made, so that a crash cannot leave them."""
        try:
            paths.GUEST_LIST.write_text("".join(t + "\n" for t in sorted(self.guest_takes)), "utf-8")
        except OSError as e:
            log(f"guest: cannot write {paths.GUEST_LIST}: {e}")

    def discard_listed(self):
        """At a start: delete the files of any guest take left over (listed in var/guest_takes.txt)."""
        try:
            toks = [t for t in paths.GUEST_LIST.read_text("utf-8").split() if archive.TOKEN.fullmatch(t)]
        except OSError:
            return
        for t in toks:
            self.remove_take_files(t, "left over from an earlier run")
        paths.GUEST_LIST.unlink(missing_ok=True)

    def remove_take_files(self, token, why):
        gone = False
        for d in (paths.TAKES, paths.ARCHIVE_TAKES):
            f = d / f"{token}.wav"
            if f.is_file():
                try:
                    f.unlink()
                    gone = True
                except OSError as e:
                    log(f"guest: take {token} NOT deleted: {e}")
        if gone:
            log(f"guest: take {token} discarded ({why})")

    def discard_guest_takes(self, slot=None, why="the guest signed out"):
        """Delete the takes of the guest in `slot` (all guests if None).  Takes uploaded while a guest was in and not yet
        recorded by anyone (owner unknown) go too unless a named learner is signed in in another slot."""
        named_elsewhere = any(u for i, u in enumerate(self.uids, 1) if i != slot)
        for t, r in list(self.guest_takes.items()):
            if slot is None or r == slot or (r is None and not named_elsewhere):
                self.remove_take_files(t, why)
                del self.guest_takes[t]
        self.list_guest_takes()

    def note_upload(self, token, data):
        """Keep an uploaded take in the archive unless a guest may have made it (then it is held back, and archived only
        if a named learner's Record turns out to own it)."""
        if any(self.guests):
            self.guest_takes[token] = None
            self.list_guest_takes()
            log(f"take {token}: not archived, a guest is in a slot")
            return
        archive.save_take(token, data)

    def start_engine(self, model=False):
        """THE START OF A REAL HOST (protocol 2): N slots, all signed out, the whole store registered; then, if
        NEOLINGO_AUTOSIGNIN names a registered learner, the host signs that learner in at slot 1."""
        self.started = False
        self.held = {}
        self.discard_guest_takes(why="the engine session ended")
        store = self.store.all_data()
        if not store:
            # The engine's register is no step while NOBODY is registered (checked 13 October 2026, against protocol 6.2,
            # which lets the first learner register), so the host registers the first learner itself.
            first = autosignin() or UID
            log("start: the store has no learner; the engine cannot register the first one, so the host does: " +
                self.store.apply({"kind": "putLearner", "uid": first, "settings": dict(DEFAULT_SETTINGS)}))
            store = self.store.all_data()
        names = [x["uid"] for x in store]
        twice = sorted({u for u in names if names.count(u) > 1})
        if twice:                                 # one session per learner: the engine refuses it too (protocol 2)
            raise RuntimeError(f"the store names a learner twice ({', '.join(twice)}): not started")
        n = slots()
        d = self.engine.ask({"cmd": "start", "slots": n, "store": store, "model": model}, self.store)
        self.started = True
        self.note_screens(d)
        log(f"start: {n} slot(s), signed out; {len(names)} learner(s) registered: {', '.join(names) or 'none'}")
        who = autosignin()
        if who and who in names:
            d = self.engine.ask({"press": "signIn", "session": 1, "input": who, "model": model}, self.store)
            self.note_screens(d)
            log(f"auto sign-in: {who} at slot 1 ({'done' if d.get('step') else 'REFUSED: ' + str(d.get('message'))})")
        elif who:
            log(f"auto sign-in: {who!r} is not registered; starting signed out")
        else:
            log("auto sign-in: off; starting signed out")
        return d

    def sign_out_all(self):
        """Send `signOut` for every signed-in slot and apply the writes (putSettings), so that the settings changed since
        sign-in are kept.  Needs the engine alive and holding the session.  Returns the learners signed out."""
        done = []
        if not self.holds_session():
            if any(self.uids):
                log("sign-out: the engine is gone; settings changed since sign-in are lost for " + ", ".join(u for u in self.uids if u))
            return done
        for r, u in enumerate(self.uids, 1):
            if not u:
                continue
            try:
                d = self.engine.ask({"press": "signOut", "session": r, "input": None}, self.store)
                self.note_screens(d)
                if not d.get("step"):
                    d = self.close_forms_and_sign_out(r, u, d)
                log(f"sign-out: slot {r} ({u}) {'settings saved' if d.get('step') else 'NOT a step: ' + str(d.get('message'))}")
                if d.get("step"):
                    done.append(u)
            except Exception as e:
                log(f"sign-out: slot {r} ({u}) FAILED: {type(e).__name__}: {e}")
        return done

    def ask_slot(self, r, press, value=None):
        d = self.engine.ask({"press": press, "session": r, "input": value}, self.store)
        self.note_screens(d)
        return d

    def close_forms_and_sign_out(self, r, u, refused):
        """Sign out refused (since 14 October Sign out is no step while a vocabulary form is open, so that no typed
        change is dropped by the PAGE).  At a stop or a fresh start the page's typed text is lost anyway, and the
        settings are worth keeping: close the settings view if open, show Vocabulary, Cancel every open form (the
        rows with "editing", and "unlisted", the forms the search hides), then Sign out again.  Returns the last reply."""
        if not any(str(refused.get("message") or "").startswith(p) for p in ("Save or cancel", "Close the settings")):
            return refused
        scr = (refused.get("screens") or [{}] * r)[r - 1]
        if scr.get("closeSettings"):
            self.ask_slot(r, "closeSettings")
        d = self.ask_slot(r, "show", "Vocabulary")
        body = d["screens"][r - 1].get("body") or {}
        open_ = [w["word"] for w in body.get("rows") or [] if w.get("editing")] + [w["word"] for w in body.get("unlisted") or []]
        for w in open_:
            self.ask_slot(r, "cancel", w)
        log(f"sign-out: slot {r} ({u}) had open form(s) {', '.join(open_) or 'none found'}: cancelled so that the settings are saved")
        return self.ask_slot(r, "signOut")

    def close(self):
        """A clean stop: sign everybody out (settings saved), then stop the engine."""
        with self.engine.lock:
            try:
                done = self.sign_out_all()
                log(f"clean stop: signed out {', '.join(done) or 'nobody'}")
                self.discard_guest_takes(why="the host stopped")
            finally:
                try:
                    self.engine.proc.terminate()
                except Exception:
                    pass

    def holds_session(self):
        return self.started and self.engine.proc is not None and self.engine.proc.poll() is None

    def page(self):
        h = (paths.PAGE / "index.html").read_text("utf-8")      # read each time: update_page.sh needs no restart
        i = h.index("<script>")
        return (h[:i] + '<script src="host.js"></script>\n' + h[i:]).encode("utf-8")

    def press(self, msg):
        t0 = time.perf_counter()
        with self.engine.lock:
            try:
                d = self.once(msg)
            except RuntimeError as e:
                log(f"engine failure: {e}; restarting it")
                try:
                    self.engine.restart()
                    self.start_engine()
                    d = {"err": f"{e}; the engine was restarted: reload the page"}
                except Exception as e2:
                    d = {"err": f"{e}; restart failed: {e2}"}
            was_guest = self.is_guest(msg.get("session"))
            self.note_screens(d)
            if "press" in msg and d.get("screens"):
                r = msg.get("session")
                tok = msg.get("input")
                if msg["press"] == "record" and self.is_guest(r):
                    # NOTHING IS KEPT FOR A GUEST: no archive line, no archived take; the take is deleted at sign-out
                    if isinstance(tok, str) and archive.TOKEN.fullmatch(tok):
                        self.guest_takes[tok] = r
                        self.list_guest_takes()
                        if d.get("step"):
                            self.held[r] = tok
                    log(f"guest: record at slot {r}: nothing archived")
                elif msg["press"] == "check" and self.is_guest(r):
                    log(f"guest: check at slot {r}: nothing archived")
                elif msg["press"] == "record":
                    if isinstance(tok, str) and tok in self.guest_takes:        # held back at upload, a named learner's after all
                        self.guest_takes.pop(tok)
                        self.list_guest_takes()
                        try:
                            archive.save_take(tok, (paths.TAKES / f"{tok}.wav").read_bytes())
                        except OSError as e:
                            log(f"archive: take {tok} NOT kept: {e}")
                    archive.log_record(msg, d, self.engine.last_answers)
                    if d.get("step") and isinstance(tok, str):
                        self.held[r] = tok
                elif msg["press"] == "check" and d.get("step"):
                    archive.log_check(msg, d, self.engine.last_answers, self.held.get(r), read_version())
                elif msg["press"] == "signOut" and was_guest and not self.is_guest(r):
                    self.discard_guest_takes(r)
                elif msg["press"] in ("signIn", "register", "signOut"):
                    log(f"press {msg['press']} slot {r}: {'step' if d.get('step') else 'no step: ' + str(d.get('message'))}; "
                        f"slots now {self.uids}")
            d.pop("test", None)
            d.pop("takes", None)
            if "screens" in d:
                d["engineMicros"] = int((time.perf_counter() - t0) * 1e6)
        what = msg.get("cmd") or msg.get("press")
        if what in ("check", "start", "load"):
            log(f"press {what}: {(time.perf_counter() - t0):.2f} s")
        return d

    def once(self, msg):
        if msg.get("cmd") == "start":
            model = bool(msg.get("model"))
            if msg.get("fresh") is True or not self.holds_session():
                log("start: " + ("fresh, as asked" if msg.get("fresh") is True else "the engine holds no session; new start"))
                if msg.get("fresh") is True:
                    self.sign_out_all()                  # the settings changed since sign-in are saved first
                return self.start_engine(model)
            return self.engine.ask({"cmd": "state", "model": model}, self.store)    # a reload: nothing is lost
        if "press" in msg and not isinstance(msg.get("session"), int):
            raise ValueError("bad press")
        return self.engine.ask(msg, self.store)


HOST = None


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send(self, body, kind, status=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, d, status=200):
        self.send(json.dumps(d, ensure_ascii=False), "application/json; charset=utf-8", status)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                return self.send(HOST.page(), "text/html; charset=utf-8")
            if u.path == "/host.js":
                return self.send((paths.PAGE / "host.js").read_bytes(), "text/javascript; charset=utf-8")
            if u.path in ("/review", "/review.html"):
                return self.send((paths.PAGE / "review.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/judgement":
                take = (q.get("take") or [""])[0]
                if not archive.TOKEN.fullmatch(take):
                    return self.json({"err": "bad take token"}, 400)
                if take in HOST.guest_takes:                        # a guest's take is not judged: the page draws nothing
                    return self.json({"guest": True})
                return self.json(archive.latest_judgement(take))
            if u.path == "/archive":
                def num(name, default):
                    try:
                        return max(1, min(500, int((q.get(name) or [default])[0])))
                    except ValueError:
                        raise ValueError(f"bad {name}")
                return self.json(archive.listing(num("limit", 50), (q.get("before") or [None])[0],
                                                 (q.get("variant") or [None])[0] or None,
                                                 (q.get("unjudged") or ["0"])[0].lower() in ("1", "true", "yes"),
                                                 (q.get("hidetest") or ["0"])[0].lower() in ("1", "true", "yes"),
                                                 (q.get("uid") or [None])[0] or None))
            if u.path == "/version":
                return self.json(read_version())
            m = re.fullmatch(r"/take/(t[0-9a-f]{16})\.wav", u.path)       # the host's own tokens only: no slash, no dot
            if m:
                for d in (paths.TAKES, paths.ARCHIVE_TAKES):                  # the archive keeps what var/takes may not
                    f = d / f"{m.group(1)}.wav"
                    if f.is_file():
                        return self.send(f.read_bytes(), "audio/wav")
                return self.send_error(404)
            if u.path == "/lists":
                return self.json(read_lists())
            if u.path == "/wordlists":
                return self.json(read_wordlists())
            if u.path == "/speak":
                text = (q.get("text") or [""])[0].strip()
                variant = (q.get("variant") or ["fr-fr"])[0]
                slow = (q.get("slow") or ["false"])[0].lower() in ("1", "true", "yes")
                if not text or len(text) > 500:
                    return self.json({"err": "bad text"}, 400)
                env.variant(variant)
                t0 = time.perf_counter()
                only = (q.get("engine") or [None])[0]       # for the tests: one engine, no fallback
                p, ctype, engine = speech.speak(text, variant, slow, only=only if only in speech.CHAINS else None)
                log(f"speak {variant} slow={slow} {text[:60]!r}: {engine}, {(time.perf_counter() - t0) * 1000:.0f} ms")
                return self.send(p.read_bytes(), ctype)
        except speech.SpeechUnavailable as e:
            log(f"speak: no voice available: {e}")
            return self.json({"err": str(e)}, 503)
        except ValueError as e:
            return self.json({"err": f"bad request: {e}"}, 400)
        except KeyError as e:
            return self.json({"err": f"unknown variant {e}"}, 400)
        except Exception as e:
            log(f"GET {u.path} failed: {type(e).__name__}: {e}")
            return self.json({"err": str(e)}, 500)
        self.send_error(404)

    def body(self, limit):
        n = int(self.headers.get("Content-Length", "0"))
        if n > limit:
            raise ValueError("too long")
        return self.rfile.read(n)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/press":
                msg = json.loads(self.body(1_000_000).decode("utf-8"))
                return self.json(HOST.press(msg))
            if path == "/judge":
                msg = json.loads(self.body(20_000).decode("utf-8"))
                if not isinstance(msg, dict):
                    raise ValueError("a JSON object is expected")
                if msg.get("take") in HOST.guest_takes:
                    raise ValueError("nothing is kept for a guest")
                return self.json(archive.judge(msg.get("take"), msg.get("verdict"), msg.get("note")))
            if path == "/take":
                data = self.body(MAX_TAKE)
                if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
                    return self.json({"err": "not a WAV file"}, 400)
                token = "t" + secrets.token_hex(8)
                (paths.TAKES / f"{token}.wav").write_bytes(data)
                try:
                    HOST.note_upload(token, data)
                except OSError as e:
                    log(f"archive: take {token} NOT kept: {e}")
                log(f"take {token}: {len(data)} bytes")
                return self.json({"take": token})
        except (ValueError, UnicodeDecodeError) as e:
            return self.json({"err": f"bad request: {e}"}, 400)
        except Exception as e:
            log(f"POST {path} failed: {type(e).__name__}: {e}")
            return self.json({"err": str(e)}, 500)
        self.send_error(404)


def main():
    global HOST
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8810)
    ap.add_argument("--preload", action="store_true", help="load the speech models for every variant now, in the background")
    a = ap.parse_args()
    HOST = Host()
    if a.preload:
        def pre():
            for v in env.variants():
                t0 = time.perf_counter()
                env.preload(v["code"])
                log(f"preloaded {v['code']} in {time.perf_counter() - t0:.1f} s")
        threading.Thread(target=pre, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), H)
    srv.daemon_threads = True

    def stop(signum, _frame):                  # shutdown() must not run in the thread that is in serve_forever()
        log(f"signal {signal.Signals(signum).name}: stopping cleanly")
        threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"Neolingo host: http://127.0.0.1:{a.port}/  (var: {paths.VAR})", flush=True)
    log(f"serving on 127.0.0.1:{a.port}")
    try:
        srv.serve_forever()
    finally:
        HOST.close()                           # sign out every slot (settings saved), then stop the engine
        log("host stopped")


if __name__ == "__main__":
    main()
