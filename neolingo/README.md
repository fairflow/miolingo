# neolingo

The first piece of Neolingo, a rebuild of the Miolingo pronunciation app: the
**environment**, i.e. the few questions the (separately compiled) engine asks
of the outside world, as a plain Python library in `env/`. It wraps Miolingo's
own code (espeak-ng target sounds, Whisper, the wav2vec2 phone recogniser, the
sound check, the panphon-based weighted phone distance) so that it can be
called from a long-running process without Streamlit; models are loaded once
and kept. `data/` holds small phrase and vocabulary lists per language and the
cost table, all extracted from Miolingo's own material.

## Run the check

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/check_env.py

It uses the Miolingo virtualenv (nothing is installed) and Miolingo's source
tree, found at `~/Software/working/miolingo/src` or at `$NEOLINGO_MIOLINGO_SRC`
(`env/_miolingo.py`). It never touches the network (`HF_HUB_OFFLINE=1`): a model
missing from the local cache is an error, not a download. All recordings in the
check are synthetic (espeak-ng) and written to `var/`, which is git-ignored.

Regenerate the data: `venv/bin/python neolingo/data/build_data.py`, then
`env.write_cost_table("neolingo/data/cost_table.json")`.

## Functions (`import env`)

    variants() -> list[dict]
    target_ipa(text, variant) -> list[list[str]]
    audible(wav_path) -> bool
    hear(wav_path, variant) -> {"text": str, "ipa": list[list[str]]}
    sounds(wav_path, target_ipa, variant) -> list[{"at","off","like", ...}]
    gloss(text, own_language, variant) -> str
    cost_table() -> dict          # also data/cost_table.json
    reference_score(heard, target, variant) -> dict   # Miolingo's own score, to test an engine against

## Not here yet

The engine, the host process that runs the engine and calls these functions,
and the page (user interface). Also not here: speech synthesis for the spoken
reference, storage, the vocabulary and history, and accuracy measurements of
the recognisers on real learners (only synthetic voices have been run).
