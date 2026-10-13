"""One-off: put the takes that were kept before the archive existed INTO the archive.

    <miolingo venv python> tests/reconstruct_archive.py

Copies var/takes/*.wav to var/archive/takes/ (the originals stay; a file already there is left alone).  For each
take, a line of var/archive/checks.jsonl is reconstructed, marked "reconstructed": true, when the host log
(var/host.log) and the history table of var/neolingo.sqlite (opened READ-ONLY) agree on one: the log says which
take was asked about (`question hear`) just before the `write appendRow` line, which has the time and the
target / recognised / score of the history row.  What the history row holds is used (variant, target text,
recognised text, heard sounds as the engine grouped them, score, understood, flags); the target sounds are
recomputed from the text; banner, flag lines, columns, droppedFlags, the answer of `sounds` and the versions
were not kept and are recorded as null.  Safe to run again: lines already present (same take) are skipped.
"""
import json
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from host import paths        # noqa: E402
import env                    # noqa: E402
from host import archive      # noqa: E402


def main():
    paths.make_dirs()
    n_copied = 0
    for p in sorted(paths.TAKES.glob("*.wav")):
        dst = paths.ARCHIVE_TAKES / p.name
        if not dst.exists():
            shutil.copy2(p, dst)
            n_copied += 1
    kept = {p.stem for p in paths.ARCHIVE_TAKES.glob("*.wav")}
    print(f"takes copied into the archive: {n_copied}; the archive now holds {len(kept)}")

    db = sqlite3.connect(f"file:{paths.DB}?mode=ro", uri=True)
    rows = db.execute("SELECT variant, target, recognised, ipa, score, understood, flags FROM history "
                      "WHERE uid=? ORDER BY seq", (paths.UID,)).fetchall()
    db.close()
    lines = paths.LOG.read_text("utf-8").splitlines()
    last_take, appends = None, []
    for ln in lines:
        m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) question hear \{\"take\": \"(t[0-9a-f]{16})\"", ln)
        if m:
            last_take = m.group(2)
        m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) write appendRow: history row: (.*) / (.*) / (\d+)%$", ln)
        if m:
            appends.append((m.group(1), last_take, m.group(2), m.group(3), int(m.group(4))))
    print(f"history rows: {len(rows)}; appendRow lines in the log: {len(appends)}")

    path = paths.ARCHIVE / "checks.jsonl"
    have = set()
    if path.exists():
        have = {json.loads(l)["take"] for l in path.read_text("utf-8").splitlines() if l.strip()}
    i, made, skipped = 0, 0, []
    for (when, take, target, recog, score) in appends:
        while i < len(rows) and (rows[i][1], rows[i][2], rows[i][4]) != (target, recog, score):
            i += 1
        if i >= len(rows):
            skipped.append((when, target, "no matching history row"))
            i = 0           # later lines may still match from the start
            continue
        v, t, r, ipa, sc, u, fl = rows[i]
        i += 1
        if take not in kept:
            skipped.append((when, target, f"take {take} no longer on disk"))
            continue
        if take in have:
            continue
        tm = time.strptime(when, "%Y-%m-%d %H:%M:%S")
        iso = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.mktime(tm)))
        line = {"time": iso, "take": take, "variant": v, "text": t,
                "target": env.target_ipa(t, v), "hear": {"text": r, "ipa": json.loads(ipa)}, "sounds": None,
                "score": sc, "understood": bool(u), "banner": None, "flagLines": None, "flags": json.loads(fl),
                "columns": None, "droppedFlags": None, "result": None, "version": None,
                "phone_model": env.variant(v)["phone_model"], "whisper": env.hearing.WHISPER_SIZE,
                "reconstructed": True,
                "missing": ["sounds", "banner", "flagLines", "columns", "droppedFlags", "version"],
                "note": "text is the history row's (lower case); target sounds recomputed; phone model and Whisper "
                        "size are today's settings"}
        archive._append("checks.jsonl", line)
        made += 1
    print(f"reconstructed check lines written: {made}")
    for s in skipped:
        print("  not reconstructed:", s)


if __name__ == "__main__":
    main()
