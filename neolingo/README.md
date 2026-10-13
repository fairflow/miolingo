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

## The host

`host/serve.py` is one long-running Python process: it starts the compiled engine
(`/Users/matthew/Lean/locus/.lake/build/bin/explore neohost`, override with `NEOLINGO_ENGINE`), sends it the
configuration, keeps the store in SQLite, answers the engine's five questions from `env`, and serves the page.
Protocol: `docs/neolingo-host-protocol.md` in the locus repository.

    ./run.sh [--port 8800]          # same as: <miolingo venv python> -m host.serve --preload --port 8800   (from neolingo/)
    nohup ./run.sh >> var/host.log 2>&1 &

Bound to 127.0.0.1 only. The microphone needs a secure context: `http://127.0.0.1:8800/` on the Mac works; other
machines need HTTPS (not arranged here).

| What | Where |
|---|---|
| host, split: store / engine + environment / config / speech | `host/store.py`, `host/engine.py`, `host/engine_config.py`, `host/speech.py` |
| the page, UNCHANGED copy of locus `docs/neolingo-page/index.html` | `page/index.html`; the locus commit it came from: `page/SOURCE` |
| the host's own script: `window.NeolingoHost.record / speak / lists` | `page/host.js` |
| store (3 tables of protocol section 4), takes, speech cache, log | `var/neolingo.sqlite`, `var/takes/`, `var/speech/`, `var/host.log` (git-ignored) |
| test | `tests/check_host.py` |

Endpoints: `GET /` (the page with `<script src="host.js">` inserted before its own script, at serve time),
`GET /host.js`, `GET /version`, `POST /press`, `POST /take` (WAV body, answers `{"take": token}`), `GET /speak?text=&variant=&slow=`
(macOS `say` + `afconvert`, else `espeak-ng`; cached by hash), `GET /lists`.
One learner, uid `me`, no sign-in. Takes older than a day are deleted at start. `NEOLINGO_VAR` moves `var/` (the test uses it).

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/check_host.py

Choices a reader should know: the cost list sent to the engine is the whole matrix (about 19,500 entries, 1 MiB) with
per-variant overrides for tolerated pairs, accept weights and unreliable targets; `hear` gives the sounds as one word;
flags are mapped `like` -> `heardAs` (null when left out); the engine drops a flag whose sound is not the target's at `at`
(each answer logs how many); an `unreliable` target costs 0 only against phones of the table (others cost `costOtherwise`).
The engine takes about 10 s to print its first line; the host start is about 12 s before it serves.

## Not here yet

HTTPS (needed for the microphone off the Mac); the microphone path (`host.js` `record`) is untested in a browser;
the page does not yet call `speak` or `lists` (they work from the console); the stretched score curve (the engine has
only sqrt and linear); the sign-in and more than one learner; accuracy of the recognisers on real learners (only
synthetic voices have been run); no cleanup of `var/speech/`.
