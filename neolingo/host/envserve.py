"""THE SPEECH SERVICE: the real host's environment over HTTP, for a page whose engine runs in the browser (locus
`web/neolingo`, stage 2 of `docs/neolingo-compilation-route.md`: the engine as WebAssembly in a Web Worker).

    NEOLINGO_VAR=<a scratch folder> <miolingo venv python> -m host.envserve --port 8831 \\
        --origin https://macbook.tailcac48d.ts.net:8826 [--origin http://127.0.0.1:8826] [--preload]

The page's engine asks its questions (protocol section 3) and the page's Worker sends them here; this process answers
them with the real host's own code: `host.engine.Environment.answer` (env.target_ipa, env.audible, env.hear,
env.sounds with flags_out, the equivalence drop and the German ü/ö rule, env.gloss), under the real host's
configuration (`host.engine_config.build_config`, `NEOLINGO_COSTS`).  The ü/ö rule aligns with an engine's `align`
(protocol section 2): this process starts its own engine (`neolingo-serve`, `NEOLINGO_ENGINE`) with that configuration,
for `align` only; it holds no session.  The store, the sessions and the page are the browser's: nothing of a learner is
kept here but the takes uploaded, under `$NEOLINGO_VAR/takes` (and the log, `$NEOLINGO_VAR/host.log`).

  GET  /config          the configuration the real host sends its engine (protocol section 5), for the page's engine
  GET  /version         {service, host (this repository's commit at start), costs, started, preloaded, engine}
  POST /take            a WAV body, as the real host's POST /take (RIFF/WAVE, at most 8 MB): {"take": token}
  POST /answer          {"questions": [Q, ...]} -> {"answers": [A, ...]}: each Q answered as the real host answers it
                        (a question that fails is answered empty and logged, as host/engine.py does)
  GET  /take/<token>.wav  a take uploaded here (the page's Play it and its waveform)
  GET  /speak?text=&variant=&slow=   the host's voices (host/speech.py, NEOLINGO_TTS), cached under $NEOLINGO_VAR/speech
  GET  /lists, /wordlists   the phrase and word lists, as the real host serves them

CORS: a request whose Origin is one of the --origin values gets Access-Control-Allow-Origin for it; a request from any
other origin is refused (403), so a page elsewhere cannot use the service; a request with no Origin (curl, a test) is
served.  Bound to 127.0.0.1: share it on the tailnet with `tailscale serve --bg --https=<port>`.
It refuses to run with NEOLINGO_VAR unset or pointing at this folder's var/ (the real host's store and archive)."""
import argparse
import http.server
import json
import os
import re
import secrets
import signal
import sys
import threading
import time
import urllib.parse
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

_ROOT = Path(__file__).resolve().parent.parent
if not os.environ.get("NEOLINGO_VAR") or Path(os.environ["NEOLINGO_VAR"]).resolve() == (_ROOT / "var").resolve():
    sys.exit("host.envserve: set NEOLINGO_VAR to a scratch folder (never this folder's var/: the real host's store)")

import env                                                  # noqa: E402
from . import paths                                         # noqa: E402
from . import speech                                        # noqa: E402
from .engine import Engine                                  # noqa: E402
from .engine_config import build_config, cost_option        # noqa: E402
from .log import log                                        # noqa: E402
from .serve import read_lists, read_wordlists, git_hash, MAX_TAKE   # noqa: E402

STARTED = time.strftime("%Y-%m-%d %H:%M:%S %z")
TOKEN = re.compile(r"t[0-9a-f]{16}")
ORIGINS = set()
PRELOADED = []
LOCK = threading.Lock()          # ONE environment call at a time (the models), engine traffic included
CONFIG = None
ENGINE = None


def empty(q):
    """The answer the real host gives a question whose computation failed (host/engine.py, Engine.ask)."""
    k = q.get("q")
    return {"audible": False} if k == "audible" else {"flags": []} if k == "sounds" else \
        {"text": "", "ipa": []} if k == "hear" else {"ipa": []} if k == "targetIpa" else {"translation": "", "notes": ""}


def answer_all(questions):
    out = []
    with LOCK:
        envr = ENGINE.env
        envr.aligner = ENGINE.align              # the German ü/ö rule aligns with this process's engine, as the host's does
        for q in questions:
            t0 = time.perf_counter()
            try:
                a = envr.answer(q)
            except Exception as e:
                log(f"question {json.dumps(q, ensure_ascii=False)[:200]} FAILED: {type(e).__name__}: {e}")
                a = empty(q)
            log(f"question {q.get('q')} {json.dumps({k: v for k, v in q.items() if k != 'q'}, ensure_ascii=False)[:120]} "
                f"-> {(time.perf_counter() - t0) * 1000:.0f} ms")
            out.append(a)
    return out


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def origin_ok(self):
        o = self.headers.get("Origin")
        return o is None or o in ORIGINS

    def cors(self):
        o = self.headers.get("Origin")
        if o and o in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")

    def send(self, body, kind, status=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, d, status=200):
        self.send(json.dumps(d, ensure_ascii=False), "application/json; charset=utf-8", status)

    def refuse(self):
        self.json({"err": "this origin may not use the speech service"}, 403)

    def do_OPTIONS(self):
        if not self.origin_ok() or self.headers.get("Origin") is None:
            return self.refuse()
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if not self.origin_ok():
            return self.refuse()
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/config":
                return self.json(CONFIG)
            if u.path == "/version":
                return self.json({"service": "neolingo speech service (host.envserve)", "host": git_hash(paths.ROOT),
                                  "costs": cost_option()[0], "started": STARTED, "preloaded": PRELOADED,
                                  "engine": paths.ENGINE, "tts": speech.IN_USE})
            m = re.fullmatch(r"/take/(t[0-9a-f]{16})\.wav", u.path)
            if m:
                f = paths.TAKES / f"{m.group(1)}.wav"
                return self.send(f.read_bytes(), "audio/wav") if f.is_file() else self.json({"err": "no such take"}, 404)
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
                p, ctype, engine = speech.speak(text, variant, slow)
                log(f"speak {variant} slow={slow} {text[:60]!r}: {engine}")
                return self.send(p.read_bytes(), ctype)
        except speech.SpeechUnavailable as e:
            return self.json({"err": str(e)}, 503)
        except (ValueError, KeyError) as e:
            return self.json({"err": f"bad request: {e}"}, 400)
        except Exception as e:
            log(f"GET {u.path} failed: {type(e).__name__}: {e}")
            return self.json({"err": str(e)}, 500)
        return self.json({"err": "not found"}, 404)

    def body(self, limit):
        n = int(self.headers.get("Content-Length", "0"))
        if n > limit:
            raise ValueError("too long")
        return self.rfile.read(n)

    def do_POST(self):
        if not self.origin_ok():
            return self.refuse()
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/take":
                data = self.body(MAX_TAKE)
                if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
                    return self.json({"err": "not a WAV file"}, 400)
                token = "t" + secrets.token_hex(8)
                (paths.TAKES / f"{token}.wav").write_bytes(data)
                log(f"take {token}: {len(data)} bytes")
                return self.json({"take": token})
            if path == "/answer":
                msg = json.loads(self.body(2_000_000).decode("utf-8"))
                qs = msg.get("questions") if isinstance(msg, dict) else None
                if not isinstance(qs, list) or not all(isinstance(x, dict) and "q" in x for x in qs):
                    return self.json({"err": "questions: a list of questions is expected"}, 400)
                return self.json({"answers": answer_all(qs)})
        except (ValueError, UnicodeDecodeError) as e:
            return self.json({"err": f"bad request: {e}"}, 400)
        except Exception as e:
            log(f"POST {path} failed: {type(e).__name__}: {e}")
            return self.json({"err": str(e)}, 500)
        return self.json({"err": "not found"}, 404)


def start(port, origins, preload=False):
    """Start the service in this process (the tests call it too); returns the server, serving in a thread."""
    global CONFIG, ENGINE
    paths.make_dirs()
    ORIGINS.clear()
    ORIGINS.update(origins)
    CONFIG = build_config()
    ENGINE = Engine(CONFIG)
    log(f"speech service starting; var = {paths.VAR}; origins = {sorted(ORIGINS)}; costs = {cost_option()[0]}")
    if preload:
        def pre():
            for v in env.variants():
                t0 = time.perf_counter()
                try:
                    env.preload(v["code"])
                except Exception as e:                  # a model missing from the cache: say so, go on with the others
                    log(f"preload {v['code']} FAILED: {type(e).__name__}: {str(e)[:200]}")
                    continue
                PRELOADED.append(v["code"])
                log(f"preloaded {v['code']} in {time.perf_counter() - t0:.1f} s")
        threading.Thread(target=pre, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"speech service on 127.0.0.1:{srv.server_address[1]}")
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8831)
    ap.add_argument("--origin", action="append", default=[], help="a page origin allowed to call (repeatable)")
    ap.add_argument("--preload", action="store_true", help="load the speech models for every variant now, in the background")
    a = ap.parse_args()
    if not a.origin:
        sys.exit("host.envserve: give at least one --origin (the page's)")
    srv = start(a.port, a.origin, a.preload)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    print(f"Neolingo speech service: http://127.0.0.1:{a.port}/  (var: {paths.VAR}; origins: {', '.join(a.origin)})", flush=True)
    stop.wait()
    srv.shutdown()
    try:
        ENGINE.proc.kill()
    except Exception:
        pass
    log("speech service stopped")


if __name__ == "__main__":
    main()
