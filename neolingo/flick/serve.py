#!/usr/bin/env python3
"""The flick server: one page for fast judging on a phone, and the files behind it.

    python3 flick/serve.py --port 8812        (from the neolingo folder; any folder works)

Standard library only.  Binds 127.0.0.1 only (reach it from a phone with a tunnel such as
`tailscale serve`).  Serves exactly these routes and nothing else:

    GET  /                 flick/index.html
    GET  /decks            JSON list of the decks in var/flick/deck-*.json
    GET  /deck/<name>      that deck, each card carrying its stored judgement as "judged" (and its note as "note")
    POST /judge            {"deck", "id", "verdict", "note" (optional, one line, at most 1000 characters)}: appends
                           a line to var/flick/judgements.jsonl (the note only when there is one)
    GET  /tally/<name>     counts per verdict for that deck
    GET  /take/<tok>.wav   var/archive/takes/<tok>.wav          (tok = t + 16 hex digits)
    GET  /audio/<file>     var/flick/audio/<file>               (wav, mp3 or m4a, a plain file name)

Audio is served with HTTP Range support (iOS Safari will not play it otherwise).
Every file route is matched against a strict pattern on the raw request path, so nothing is ever
percent-decoded, joined or walked: `..`, `%2e%2e`, slashes and the like simply do not match.
"""
import argparse
import json
import os
import re
import socketserver
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                        # the neolingo folder
FLICK = ROOT / 'var' / 'flick'
TAKES = ROOT / 'var' / 'archive' / 'takes'
AUDIO = FLICK / 'audio'
JUDGEMENTS = FLICK / 'judgements.jsonl'
INDEX = HERE / 'index.html'

VERDICTS = ('good', 'bad', 'skip', 'a', 'b', 'same')
NAME_RE = r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}'
RE_DECK = re.compile(r'^/deck/(' + NAME_RE + r')$')
RE_TALLY = re.compile(r'^/tally/(' + NAME_RE + r')$')
RE_TAKE = re.compile(r'^/take/(t[0-9a-f]{16})\.wav$')
RE_AUDIO = re.compile(r'^/audio/([A-Za-z0-9._-]+\.(?:wav|mp3|m4a))$')
RE_RANGE = re.compile(r'^bytes=(\d*)-(\d*)$')
AUDIO_TYPES = {'.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4'}
MAX_BODY = 8192
MAX_NOTE = 1000                            # characters
CHUNK = 64 * 1024

PAGE_CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
            "media-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


# ---------------------------------------------------------------------------------------------
# decks and judgements
# ---------------------------------------------------------------------------------------------
def deck_path(name):
    if not isinstance(name, str) or not re.fullmatch(NAME_RE, name):
        return None
    p = FLICK / ('deck-' + name + '.json')
    return p if p.is_file() else None


def load_deck(name):
    """The deck as a dict, or None when there is no such deck; raises ValueError when it is unreadable."""
    p = deck_path(name)
    if p is None:
        return None
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError('deck %r is unreadable: %s' % (name, e))
    if not isinstance(d, dict) or not isinstance(d.get('cards'), list):
        raise ValueError('deck %r has no list of cards' % name)
    return d


def card_ids(deck):
    return [str(c['id']) for c in deck['cards'] if isinstance(c, dict) and 'id' in c]


class Judgements:
    """var/flick/judgements.jsonl: append-only; the last line per (deck, id) wins (its verdict and its note)."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.sig = None
        self.last = {}
        self.notes = {}

    def _refresh(self):                    # call with the lock held
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            self.last, self.sig = {}, None
            return
        sig = (st.st_mtime_ns, st.st_size)
        if sig == self.sig:
            return
        last, notes = {}, {}
        with open(self.path, encoding='utf-8') as f:
            for line in f:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue               # a torn or foreign line is ignored, never fatal
                if isinstance(o, dict) and isinstance(o.get('deck'), str) and 'id' in o and o.get('verdict') in VERDICTS:
                    last[(o['deck'], str(o['id']))] = o['verdict']
                    n = o.get('note')
                    notes[(o['deck'], str(o['id']))] = n if isinstance(n, str) else ''
        self.last, self.notes, self.sig = last, notes, sig

    def for_deck(self, name):
        with self.lock:
            self._refresh()
            return {i: v for (d, i), v in self.last.items() if d == name}

    def notes_for_deck(self, name):
        with self.lock:
            self._refresh()
            return {i: v for (d, i), v in self.notes.items() if d == name and v}

    def add(self, deck, cid, verdict, note=None):
        o = {'time': datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z'), 'deck': deck, 'id': cid, 'verdict': verdict}
        if note:
            o['note'] = note
        line = json.dumps(o, ensure_ascii=False) + '\n'
        with self.lock:
            FLICK.mkdir(parents=True, exist_ok=True)
            with open(self.path, 'ab') as f:
                if f.tell() > 0:           # a file that does not end in a newline would glue two lines together
                    with open(self.path, 'rb') as r:
                        r.seek(-1, os.SEEK_END)
                        if r.read(1) != b'\n':
                            f.write(b'\n')
                f.write(line.encode('utf-8'))
                f.flush()
                os.fsync(f.fileno())
            self.sig = None                # re-read next time


J = Judgements(JUDGEMENTS)


def list_decks():
    out = []
    for p in sorted(FLICK.glob('deck-*.json')):
        name = p.name[len('deck-'):-len('.json')]
        if not re.fullmatch(NAME_RE, name):
            continue
        try:
            d = load_deck(name)
        except ValueError:
            out.append({'name': name, 'title': name, 'cards': 0, 'judged': 0, 'error': 'unreadable'})
            continue
        if d is None:
            continue
        ids = set(card_ids(d))
        stored = J.for_deck(name)
        out.append({'name': name, 'title': d.get('title') or name, 'cards': len(d['cards']),
                    'judged': sum(1 for i in ids if i in stored), 'made': d.get('made'), 'config': d.get('config')})
    return out


# ---------------------------------------------------------------------------------------------
# the server
# ---------------------------------------------------------------------------------------------
class Server(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):                 # the stock version calls getfqdn(), which can stall for seconds
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[0], self.server_address[1]


class Handler(BaseHTTPRequestHandler):
    server_version = 'flick/1'
    protocol_version = 'HTTP/1.1'
    timeout = 120                          # an idle keep-alive connection is dropped after two minutes

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass                           # the browser gave up on a request (audio does this all the time)

    # ---- small helpers ----
    def _send(self, status, body=b'', ctype='text/plain; charset=utf-8', head=False, extra=()):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _json(self, obj, status=200, head=False):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8', head)

    def _not_found(self, head=False):
        self._send(404, b'not found\n', head=head)

    def _file(self, path, ctype, head, cache='no-cache'):
        """Serve a regular file with Range support.  `path` is already known to be inside its folder."""
        try:
            real = path.resolve(strict=True)
            if real.parent != path.parent.resolve() or not real.is_file():
                return self._not_found(head)     # a symlink out of the folder is not served
            f = open(real, 'rb')
        except OSError:
            return self._not_found(head)
        with f:
            st = os.fstat(f.fileno())
            size = st.st_size
            etag = '"%x-%x"' % (st.st_mtime_ns, size)
            base = [('Accept-Ranges', 'bytes'), ('ETag', etag), ('Cache-Control', cache),
                    ('X-Content-Type-Options', 'nosniff')]
            rng = self.headers.get('Range')
            start, end, status = 0, size - 1, 200
            if rng and size > 0:
                m = RE_RANGE.match(rng.strip())      # one range only; anything else is ignored (whole file)
                if m and (m.group(1) or m.group(2)):
                    a, b = m.groups()
                    if a == '':                      # suffix: the last b bytes
                        n = int(b)
                        if n == 0:
                            return self._range_bad(size, head)
                        start, end = max(0, size - n), size - 1
                    else:
                        start = int(a)
                        end = min(int(b), size - 1) if b else size - 1
                        if start >= size or end < start:
                            return self._range_bad(size, head)
                    status = 206
            if status == 200 and self.headers.get('If-None-Match') == etag:
                self.send_response(304)
                for k, v in base:
                    self.send_header(k, v)
                self.end_headers()
                return
            length = end - start + 1 if size > 0 else 0
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(length))
            if status == 206:
                self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
            for k, v in base:
                self.send_header(k, v)
            self.end_headers()
            if head or length == 0:
                return
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(CHUNK, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def _range_bad(self, size, head):
        self._send(416, b'range not satisfiable\n', head=head, extra=[('Content-Range', 'bytes */%d' % size)])

    # ---- routing ----
    def do_HEAD(self):
        self._guarded(self._route, True)

    def do_GET(self):
        self._guarded(self._route, False)

    def _guarded(self, fn, *args):
        try:
            fn(*args)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            raise
        except Exception as e:                      # a bug here must answer 500, not drop the connection silently
            self.log_error('internal error: %r', e)
            self.close_connection = True
            try:
                self._json({'ok': False, 'error': 'internal error'}, 500)
            except Exception:
                pass

    def _no(self):                                  # methods this server does not offer
        self.close_connection = True
        self._send(405, b'method not allowed\n', extra=[('Allow', 'GET, HEAD, POST')])

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _no

    def _route(self, head):
        path = urlsplit(self.path).path            # raw: never percent-decoded
        if path == '/':
            try:
                body = INDEX.read_bytes()
            except OSError:
                return self._send(500, b'flick/index.html is missing\n', head=head)
            return self._send(200, body, 'text/html; charset=utf-8', head, extra=[('Content-Security-Policy', PAGE_CSP)])
        if path == '/decks':
            return self._json(list_decks(), head=head)
        m = RE_DECK.match(path)
        if m:
            return self._deck(m.group(1), head)
        m = RE_TALLY.match(path)
        if m:
            return self._tally(m.group(1), head)
        m = RE_TAKE.match(path)
        if m:
            return self._file(TAKES / (m.group(1) + '.wav'), 'audio/wav', head, cache='private, max-age=3600')
        m = RE_AUDIO.match(path)
        if m:
            name = m.group(1)
            return self._file(AUDIO / name, AUDIO_TYPES[name[name.rfind('.'):]], head)
        return self._not_found(head)

    def _deck(self, name, head):
        try:
            d = load_deck(name)
        except ValueError as e:
            return self._json({'ok': False, 'error': str(e)}, 500, head)
        if d is None:
            return self._not_found(head)
        stored = J.for_deck(name)
        notes = J.notes_for_deck(name)
        cards = []
        for c in d['cards']:
            if isinstance(c, dict):
                c = dict(c)
                v = stored.get(str(c.get('id')))
                if v:
                    c['judged'] = v
                    if notes.get(str(c.get('id'))):
                        c['note'] = notes[str(c.get('id'))]
            cards.append(c)
        out = dict(d)
        out['name'] = name
        out['cards'] = cards
        self._json(out, head=head)

    def _tally(self, name, head):
        try:
            d = load_deck(name)
        except ValueError as e:
            return self._json({'ok': False, 'error': str(e)}, 500, head)
        if d is None:
            return self._not_found(head)
        ids = set(card_ids(d))
        stored = J.for_deck(name)
        counts = {v: 0 for v in VERDICTS}
        for i, v in stored.items():
            if i in ids:
                counts[v] += 1
        judged = sum(counts.values())
        self._json({'deck': name, 'title': d.get('title') or name, 'total': len(d['cards']), 'judged': judged,
                    'unjudged': len(d['cards']) - judged, 'counts': counts}, head=head)

    def do_POST(self):
        self._guarded(self._post)

    def _post(self):
        path = urlsplit(self.path).path
        if path != '/judge':
            self.close_connection = True           # the body is not read, so this connection cannot be reused
            return self._not_found()
        # a page on another site must not be able to post here: it cannot send JSON without a preflight (which
        # we never answer), and browsers that say so are refused outright
        if self.headers.get('Sec-Fetch-Site', '').lower() == 'cross-site':
            self.close_connection = True
            return self._json({'ok': False, 'error': 'cross-site request refused'}, 403)
        ctype = self.headers.get('Content-Type', '').split(';')[0].strip().lower()
        if ctype != 'application/json':
            self.close_connection = True
            return self._json({'ok': False, 'error': 'Content-Type must be application/json'}, 415)
        try:
            length = int(self.headers.get('Content-Length', ''))
        except ValueError:
            self.close_connection = True
            return self._json({'ok': False, 'error': 'Content-Length required'}, 411)
        if length < 0 or length > MAX_BODY:
            self.close_connection = True
            return self._json({'ok': False, 'error': 'body too large'}, 413)
        raw = self.rfile.read(length)
        try:
            o = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return self._json({'ok': False, 'error': 'body is not JSON'}, 400)
        if not isinstance(o, dict):
            return self._json({'ok': False, 'error': 'body must be an object'}, 400)
        deck, cid, verdict = o.get('deck'), o.get('id'), o.get('verdict')
        if verdict not in VERDICTS:
            return self._json({'ok': False, 'error': 'verdict must be one of ' + ', '.join(VERDICTS)}, 400)
        if not isinstance(deck, str) or not isinstance(cid, str):
            return self._json({'ok': False, 'error': 'deck and id must be strings'}, 400)
        note = o.get('note')
        if note is not None and not isinstance(note, str):
            return self._json({'ok': False, 'error': 'note must be a string'}, 400)
        note = ' '.join((note or '').split())        # one line: newlines and tabs become spaces
        if len(note) > MAX_NOTE:
            return self._json({'ok': False, 'error': 'note longer than %d characters' % MAX_NOTE}, 400)
        try:
            d = load_deck(deck)
        except ValueError as e:
            return self._json({'ok': False, 'error': str(e)}, 500)
        if d is None:
            return self._json({'ok': False, 'error': 'no such deck'}, 404)
        if cid not in card_ids(d):
            return self._json({'ok': False, 'error': 'no such card in that deck'}, 404)
        try:
            J.add(deck, cid, verdict, note or None)
        except OSError as e:
            return self._json({'ok': False, 'error': 'could not write: %s' % e.strerror}, 500)
        self._json({'ok': True})


def main():
    ap = argparse.ArgumentParser(description='Serve the flick judging page (127.0.0.1 only).')
    ap.add_argument('--port', type=int, default=8812)
    args = ap.parse_args()
    FLICK.mkdir(parents=True, exist_ok=True)
    try:
        srv = Server(('127.0.0.1', args.port), Handler)
    except OSError as e:
        sys.exit('flick: cannot listen on 127.0.0.1:%d: %s' % (args.port, e))
    print('flick: serving http://127.0.0.1:%d/  (decks in %s)' % (args.port, FLICK), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == '__main__':
    main()
