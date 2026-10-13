"""The Neolingo host.   <miolingo venv python> -m host.serve --port 8810     (from neolingo/)

Drives the engine (`explore neohost`, docs/neolingo-host-protocol.md in the locus repository), keeps the store
in SQLite, answers the engine's questions from env, serves the page and the endpoints:
  GET  /  /index.html   the page, with <script src="host.js"> placed before its own script
  GET  /host.js         the recorder and the player
  GET  /version         JSON: page version, SOURCE hash, host git hash, start time
  POST /press           the page's messages, forwarded to the engine
  POST /take            a 16 kHz mono 16-bit WAV body; answers {"take": token}
  GET  /speak?text=&variant=&slow=   a WAV, made locally
  GET  /lists           the phrase lists of data/{en,fr,de}.json
Bound to 127.0.0.1 only."""
import argparse
import http.server
import json
import os
import re
import secrets
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
from .store import Store                      # noqa: E402
from . import speech                          # noqa: E402

STARTED = time.strftime("%Y-%m-%d %H:%M:%S %z")
UID = paths.UID
MAX_TAKE = 8_000_000                          # bytes: 30 s of 16 kHz 16-bit is under 1 MB


def git_hash(path):
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def page_version(html):
    m = re.search(r"·\s*(v\d+\.\d+)\s*·", html)
    return m.group(1) if m else "unknown"


def read_lists():
    out = []
    for lang in ("en", "fr", "de"):
        d = json.loads((paths.DATA / f"{lang}.json").read_text("utf-8"))
        names = {"en": "English", "fr": "French", "de": "German"}
        out.append({"name": f"{names[lang]} phrases", "variant": d["variant"],
                    "items": [{"text": p["text"], "gloss": p.get("gloss", "")} for p in d["phrases"]]})
    return out


def clean_takes(max_age=86400):
    n = 0
    for p in paths.TAKES.glob("*.wav"):
        if time.time() - p.stat().st_mtime > max_age:
            p.unlink(missing_ok=True)
            n += 1
    return n


class Host:
    def __init__(self):
        paths.make_dirs()
        log(f"host starting; var = {paths.VAR}; engine = {paths.ENGINE}; {clean_takes()} old takes deleted")
        self.store = Store(paths.DB)
        self.engine = Engine(build_config())
        self.page_html = (paths.PAGE / "index.html").read_text("utf-8")
        self.version = {"page": page_version(self.page_html),
                        "source": (paths.PAGE / "SOURCE").read_text().strip() if (paths.PAGE / "SOURCE").exists() else "unknown",
                        "host": git_hash(paths.ROOT), "started": STARTED}
        with self.engine.lock:
            self.start_engine()

    def start_engine(self, model=False):
        return self.engine.ask({"cmd": "start", "sessions": [UID], "store": [self.store.data(UID)], "model": model}, self.store)

    def page(self):
        h = self.page_html
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
            return self.start_engine(bool(msg.get("model")))
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
            if u.path == "/version":
                return self.json(HOST.version)
            if u.path == "/lists":
                return self.json(read_lists())
            if u.path == "/speak":
                text = (q.get("text") or [""])[0].strip()
                variant = (q.get("variant") or ["fr-fr"])[0]
                slow = (q.get("slow") or ["false"])[0].lower() in ("1", "true", "yes")
                if not text or len(text) > 500:
                    return self.json({"err": "bad text"}, 400)
                env.variant(variant)
                t0 = time.perf_counter()
                p = speech.speak_wav(text, variant, slow)
                log(f"speak {variant} slow={slow} {text[:60]!r}: {(time.perf_counter() - t0) * 1000:.0f} ms")
                return self.send(p.read_bytes(), "audio/wav")
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
            if path == "/take":
                data = self.body(MAX_TAKE)
                if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
                    return self.json({"err": "not a WAV file"}, 400)
                token = "t" + secrets.token_hex(8)
                (paths.TAKES / f"{token}.wav").write_bytes(data)
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
    print(f"Neolingo host: http://127.0.0.1:{a.port}/  (var: {paths.VAR})", flush=True)
    log(f"serving on 127.0.0.1:{a.port}")
    try:
        srv.serve_forever()
    finally:
        HOST.engine.proc.terminate()


if __name__ == "__main__":
    main()
