"""Write the Whisper job files from the data sets:  <python> -m lab.jobs [sets...]   -> var/lab/jobs/<set>.jsonl"""
from __future__ import annotations

import sys

from . import datasets, understood
from .common import LAB, write_jsonl


def main():
    want = sys.argv[1:] or ["archive", "reference", "nearmiss", "positive", "cp", "cpflip"]
    its = datasets.all_items()
    for s in want:
        sel = [i for i in its if i["set"] == s]
        if not sel:
            print(s, "no items")
            continue
        write_jsonl(LAB / "jobs" / f"{s}.jsonl", [understood.whisper_job(i) for i in sel])
        print(s, len(sel), "jobs")


if __name__ == "__main__":
    main()
