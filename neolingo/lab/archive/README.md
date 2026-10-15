# lab/archive

Superseded lab code, kept for the record. Nothing outside this folder imports it, and it is not meant to run from here.

- `engine_py.py`: the Python copy of the engine's scoring (`norm`, `dist`, `align` with its tie-break, `score`, `byWord`, `columnsFrom`, the cost lookup and the curve). Archived 15 October. Replaced by the engine itself: the `align` command (protocol section 2, locus 0041de3; `lab/align.py` in the lab, `Engine.align` on the host's own connection for the German ü/ö rule) for alignments and distances, and `neolingo batch` (`lab/batch.py`, with its `alignment` field) for the judgement.
- `validate.py`: the first run's checks of `engine_py.py` against the stored archive lines and the compiled engine. Archived with it; `python -m lab.batch compare` (the lab against batch) and `lab/replay_dump.py` (the archive replayed through the host's code, before and after a change) do that work now.
