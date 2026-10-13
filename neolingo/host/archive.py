"""The archive: nothing is thrown away.  Under var/archive/ (git-ignored; the owner's own voice, never committed):

  takes/<token>.wav   every take uploaded, for good
  records.jsonl       one line at each Record press
  checks.jsonl        one line at each Check press that is a step
  judgements.jsonl    one line each time the owner judges a take (fair / harsh / generous); a later line supersedes

so that every recording can be replayed later as a test (tests/replay_archive.py).  Archiving never fails a press:
an error is logged and the press goes on."""
import json
import os
import re
import threading
import time

import env
from . import paths
from .log import log

_lock = threading.Lock()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _append(name, obj):
    with _lock:
        with open(paths.ARCHIVE / name, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def save_take(token, data):
    """Keep the uploaded bytes under archive/takes/ (written whole, then renamed)."""
    paths.ARCHIVE_TAKES.mkdir(parents=True, exist_ok=True)
    tmp = paths.ARCHIVE_TAKES / f".{token}.part"
    tmp.write_bytes(data)
    os.replace(tmp, paths.ARCHIVE_TAKES / f"{token}.wav")


def level(wav):
    """(duration in seconds, peak level 0..1) of a take; (None, None) if unreadable."""
    try:
        import soundfile as sf
        x, sr = sf.read(str(wav), dtype="float32", always_2d=True)
        return round(len(x) / sr, 3), (round(float(abs(x).max()), 4) if x.size else 0.0)
    except Exception:
        return None, None


def answer_of(answers, kind):
    """The (question, answer) of the first question of this kind answered in the request, or (None, None)."""
    for x in answers:
        if x["q"]["q"] == kind:
            return x["q"], x["a"]
    return None, None


def log_record(msg, reply, answers):
    try:
        token = msg.get("input")
        if not isinstance(token, str):
            return
        q, a = answer_of(answers, "audible")
        dur, peak = level(paths.ARCHIVE_TAKES / f"{token}.wav")
        _append("records.jsonl", {"time": now(), "take": token, "duration_s": dur, "peak": peak,
                                  "audible": a["audible"] if a else None, "step": bool(reply.get("step"))})
    except Exception as e:
        log(f"archive: record line failed: {type(e).__name__}: {e}")


def log_check(reply, answers, held_take, version):
    """One line for a Check press that is a step.  Fields the reply does not carry are recorded as null and named
    in "missing"."""
    try:
        scr = (reply.get("screens") or [{}])[0]
        body = scr.get("body") or {}
        phrase = body.get("phrase") or {}
        res = body.get("result") or {}
        hq, ha = answer_of(answers, "hear")
        sq, sa = answer_of(answers, "sounds")
        variant = (hq or sq or {}).get("variant") or (scr.get("settings") or {}).get("practised")
        token = (hq or sq or {}).get("take") or held_take
        row = (reply.get("write") or {}).get("row") or {}
        line = {
            "time": now(), "take": token, "variant": variant, "text": phrase.get("text"),
            "target": sq["target"] if sq else None,
            "hear": ha, "sounds": sa["flags"] if sa else None,
            "score": row.get("score"), "understood": row.get("understood"),
            "banner": res.get("banner"), "flagLines": res.get("flagLines"), "flags": res.get("flags"),
            "columns": res.get("columns"), "droppedFlags": reply.get("droppedFlags"),
            "result": res,                     # the whole result as the page gets it, so nothing in it is lost
            "version": version,
            "phone_model": env.variant(variant)["phone_model"] if variant else None,
            "whisper": env.hearing.WHISPER_SIZE,
        }
        missing = [k for k in ("target", "hear", "sounds", "columns", "droppedFlags", "banner") if line[k] is None]
        if missing:
            line["missing"] = missing
        _append("checks.jsonl", line)
    except Exception as e:
        log(f"archive: check line failed: {type(e).__name__}: {e}")


# ---- human judgements of the results (var/archive/judgements.jsonl) ----
VERDICTS = ("fair", "harsh", "generous")
TOKEN = re.compile(r"t[0-9a-f]{16}")             # the host's own take tokens
MAX_NOTE = 2000


def judge(take, verdict, note=None):
    """Record a judgement (a later line for the same take supersedes an earlier one).  ValueError if the token or the
    verdict is not valid.  Returns the line written."""
    if not isinstance(take, str) or not TOKEN.fullmatch(take):
        raise ValueError("bad take token")
    if verdict not in VERDICTS:
        raise ValueError("verdict must be one of " + ", ".join(VERDICTS))
    if note is not None and not isinstance(note, str):
        raise ValueError("note must be text")
    line = {"time": now(), "take": take, "verdict": verdict}
    note = (note or "").strip()
    if note:
        line["note"] = note[:MAX_NOTE]
    line["who"] = "me"
    _append("judgements.jsonl", line)
    return line


def read_lines(name):
    """The lines of an archive file that parse (a half-written last line is skipped)."""
    out = []
    try:
        with _lock:
            text = (paths.ARCHIVE / name).read_text("utf-8")
    except OSError:
        return out
    for l in text.splitlines():
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def judgements():
    """take -> the latest judgement line."""
    d = {}
    for j in read_lines("judgements.jsonl"):
        if isinstance(j, dict) and isinstance(j.get("take"), str):
            d[j["take"]] = j
    return d


def latest_judgement(take):
    return judgements().get(take) or {}


def listing(limit=50, before=None, variant=None, unjudged=False):
    """The archived checks, newest first, each joined with the latest judgement of its take (key "judgement", null if none).
    `before`: "time" or "time|take" of the last line already seen.  `variant` and `unjudged` filter.  Returns
    {"items": [...], "total": n, "judged": k, "next": before-for-the-next-page or null}, the counts over the lines of
    `variant` (all variants if none), judged or not."""
    js = judgements()
    rows = [l for l in read_lines("checks.jsonl") if isinstance(l, dict) and l.get("take")]
    if variant:
        rows = [l for l in rows if l.get("variant") == variant]
    total, judged = len(rows), sum(1 for l in rows if l["take"] in js)
    rows.sort(key=lambda l: (l.get("time") or "", l["take"]), reverse=True)
    if before:
        t, _, k = before.partition("|")
        rows = [l for l in rows if ((l.get("time") or ""), l["take"]) < (t, k or "\uffff")]
    if unjudged:
        rows = [l for l in rows if l["take"] not in js]
    page = rows[:limit]
    nxt = f"{page[-1].get('time') or ''}|{page[-1]['take']}" if len(rows) > limit else None
    items = [dict(l, judgement=js.get(l["take"])) for l in page]
    return {"items": items, "total": total, "judged": judged, "next": nxt}
