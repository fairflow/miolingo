"""Every archived take through the host's own code and a scratch engine, the whole result kept: for showing that a
change of the host's code changes nothing (run before and after, then `compare`).

    NEOLINGO_VAR=<a copy of var/> <python> -m lab.replay_dump run OUT.json      (NEOLINGO_ENGINE: the engine binary)
    <python> -m lab.replay_dump compare A.json B.json

`run` uses tests/replay_archive.py's driver (ArchiveEnvironment answering from env: audible, hear, sounds with the
German ü/ö rule; a fresh neohost session per take; Check pressed) and writes {take: the result} (score, understood,
flags, flag lines, banner, picture as columns, the host's answers to hear and sounds, droppedFlags).  `compare` lists
the takes whose results differ, field by field."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cmd_run(out):
    if not os.environ.get("NEOLINGO_VAR"):
        sys.exit("set NEOLINGO_VAR to a copy of var/ (the replay reads its archive)")
    sys.path.insert(0, str(ROOT / "tests"))
    import replay_archive as ra
    lines = [json.loads(l) for l in (ra.paths.ARCHIVE / "checks.jsonl").read_text("utf-8").splitlines() if l.strip()]
    eng = ra.Engine(ra.build_config())
    eng.env = ra.ArchiveEnvironment()
    res, t0 = {}, time.perf_counter()
    for l in lines:
        try:
            res[l["take"]] = ra.replay_one(eng, None, l)
        except Exception as e:                  # noqa: BLE001
            res[l["take"]] = {"error": f"{type(e).__name__}: {e}"}
            eng.restart()
    eng.proc.terminate()
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=0), "utf-8")
    print(f"{len(res)} takes -> {out} ({time.perf_counter() - t0:.0f} s)")


def cmd_compare(a, b):
    A = json.loads(Path(a).read_text("utf-8"))
    B = json.loads(Path(b).read_text("utf-8"))
    same, diff = 0, []
    for t in sorted(set(A) | set(B)):
        x, y = A.get(t), B.get(t)
        if x == y:
            same += 1
            continue
        keys = sorted(k for k in set(x or {}) | set(y or {}) if (x or {}).get(k) != (y or {}).get(k))
        diff.append((t, keys))
    print(f"{same} SAME, {len(diff)} different")
    for t, keys in diff:
        print(f"  {t}: {', '.join(keys)}")
    return not diff


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "run":
        cmd_run(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "compare":
        sys.exit(0 if cmd_compare(sys.argv[2], sys.argv[3]) else 1)
    else:
        sys.exit(__doc__)
