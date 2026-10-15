# Retired host tests

Archived on 15 October 2026 under locus `docs/neolingo-test-design.md` (section 4, "Dropped or slimmed"; P8: nothing
retired without a line naming its replacement; archive, never delete). They are not run at an update of the real host.
Each still runs from `neolingo/` as `<miolingo venv python> tests/archive/<name>.py`.

- `symbol_study.py`: retired because its hypothesis was REFUTED. It held that the low scores of the reference voices
  came from target and recogniser writing one sound with different symbols, and entered such pairs as tolerated
  (`NEOLINGO_EQUIV=1`). Its own measurement (13 October 15:39, `var/study/measure.md`) left the English reference
  phrases under 90 at 21 of 48 (Google's voice) and 26 (the Mac's) with the switch on. No replacement:
  `data/symbol_equivalents.json` and `NEOLINGO_EQUIV` (default off) stay; reference voices are now measured by the lab.
- `reconstruct_archive.py`: retired as a ONE-OFF. On 13 October it put the takes kept before the archive existed
  into `var/archive/` (lines marked `"reconstructed": true`); that is done, and every take since is archived as it
  is made (`host/archive.py`). No replacement needed.

Moved, not retired: `check_verify_de.py` (the German ü/ö rule against the lab's analysis) is a measurement, now
`lab/check_verify_de.py`, run as `python -m lab.check_verify_de` when the rule or the German phone model changes.
