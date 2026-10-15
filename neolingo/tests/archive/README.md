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

- `check_host_before_h1.py`: the full `check_host.py` of 14 October (88 checks), retired in part on 15 October.
  REPLACED by H1, `tests/check_suite.py` (the generated suite through the host's own driver): `can` before a press,
  the result's picture and fields, the long vowel kept, the vocabulary and the word-list upload; and by
  `check_signin.py`: the reload, the fresh start, the store across a restart. The slimmed `tests/check_host.py` (57
  checks) keeps what neither reaches: the host's endpoints, takes, Checks with the real recognisers (droppedFlags 0),
  the archive, judgements, the review page, speech, host.js. Dropped without a replacement: the share of word-list
  words with an English meaning (a data measurement; the meanings themselves are `check_gloss.py`'s).

Moved, not retired: `check_verify_de.py` (the German ü/ö rule against the lab's analysis) is a measurement, now
`lab/check_verify_de.py`, run as `python -m lab.check_verify_de` when the rule or the German phone model changes.
