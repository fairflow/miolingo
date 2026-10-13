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

    ./run.sh [--port 8810]          # same as: <miolingo venv python> -m host.serve --preload --port 8810   (from neolingo/)
    nohup ./run.sh >> var/host.log 2>&1 &

Bound to 127.0.0.1 only. The microphone needs a secure context: `http://127.0.0.1:8810/` on the Mac works; other
machines need HTTPS (not arranged here).

| What | Where |
|---|---|
| host, split: store / engine + environment / config / speech | `host/store.py`, `host/engine.py`, `host/engine_config.py`, `host/speech.py` |
| the page, UNCHANGED copy of locus `docs/neolingo-page/index.html` | `page/index.html`; the locus commit it came from: `page/SOURCE` |
| the host's own script: `window.NeolingoHost.record / speak / lists / playTake / showTake` (showTake: waveform drawn from the WAV parsed in the browser, peaks cached by token) | `page/host.js` |
| store (3 tables of protocol section 4), takes, speech cache, log | `var/neolingo.sqlite`, `var/takes/`, `var/speech/`, `var/host.log` (git-ignored) |
| test | `tests/check_host.py` (runs `tests/check_host_js.js` under node) |

Endpoints: `GET /` (the page with `<script src="host.js">` inserted before its own script, at serve time),
`GET /host.js`, `GET /version`, `GET /take/<token>.wav` (the stored take; 404 if unknown), `POST /press`, `POST /take` (WAV body, answers `{"take": token}`), `GET /speak?text=&variant=&slow=`
(speech, cached under `var/speech/`; see below), `GET /lists`.
`GET /version` answers `page` and `changed` (first line of `page/CHANGES`), `engine` (the locus hash in `page/SOURCE`), `built`
(the engine binary's modification time), `instance` (`real`), `host` (this repository's short hash), `tts`, `started`.
`./update_page.sh` copies `index.html` and `CHANGES` from the locus repository and writes `SOURCE` (no restart needed).

Speech: `NEOLINGO_TTS` = `gtts` (default; Google's text-to-speech through the `gtts` package, MP3, the only network use; falls back
to `say`, then `espeak`, and the log says which answered) | `say` | `espeak` (both WAV). `host.js` plays whatever content type comes back.

One learner, uid `me`, no sign-in. Takes are never deleted (see the archive, below). `NEOLINGO_VAR` moves `var/` (the test uses it).

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/check_host.py

Choices a reader should know: the cost list sent to the engine is the whole matrix (about 18,600 entries, 1 MiB) with
per-variant overrides for tolerated pairs, accept weights and unreliable targets; `hear` gives the sounds as one word;
flags are mapped `like` -> `heardAs` (null when left out), one flag for each target sound a finding covers, `sound` taken from the
target the engine sent; the engine's `droppedFlags` is logged (a warning when not 0); `tests/check_segmentation.py` checks that
target, cost table and recogniser cut sounds the same way; an `unreliable` target costs 0 only against phones of the table (others cost `costOtherwise`).
The engine takes about 11 s to print its `{"ready":1}` line (the host waits for it, no timeout); the host start is about 12 s before it serves.

## Testing with sound

**The archive.** Every take uploaded is kept for good under `var/archive/takes/<token>.wav` (`host/archive.py`). `var/archive/records.jsonl`
gets a line at each Record (time, take, duration, peak level, the `audible` answer) and `var/archive/checks.jsonl` one at each Check that is a
step: time, take, variant, phrase, the target sounds as the engine sent them, the host's answers (`hear`, `sounds`), score, understood, banner,
flag lines, flags, aligned columns, `droppedFlags`, the whole result, the versions, the phone model and the Whisper size.
`tests/reconstruct_archive.py` (run once) copies the takes of `var/takes/` into the archive and rebuilds lines marked `"reconstructed": true`
from the host log and the history table (opened read-only); they lack the banner, columns and the like.

**Replay**, the regression test with real sound: `venv/bin/python neolingo/tests/replay_archive.py [--variant V] [--since YYYY-MM-DD] [--limit N]`
runs each archived take through `env.audible / hear / sounds` and a scratch engine session and prints SAME or CHANGED (with what) a take;
exit code 1 if anything changed. A change is not always a fault: a better recogniser or a new rule changes results; read it, then decide.

**Reference sweep**: `venv/bin/python neolingo/tests/reference_sweep.py [--engines gtts,say,espeak] [--langs en,fr,de] [--limit N]` makes every phrase of
`data/{en,fr,de}.json` with the host's speech code (gTTS uses the network the first time; results are cached), decodes it to 16 kHz mono under
`var/sweep/`, checks it as a learner's take, and writes `var/sweep/results.jsonl` and `var/sweep/report.txt` (not audible, not understood, score
distribution, the lowest scores, the differing sound pairs, left out and extra sounds, warnings by sound, timings). The voices are synthetic: the
report shows where the sources (espeak target, reference voice, recogniser) disagree, not how accurate the app is on learners.

All outputs stay under `var/` (git-ignored; the archive holds the owner's own voice and must never be committed).

## Length

Length marks are KEPT (owner's decision, 13 October 2026; the engine's `norm` removes only stress marks and punctuation): a long
sound is another sound, "iː" is not "i" (German "Ihnen" [iːnən] against "innen" [ɪnən]). A length mark (ː, ˑ) is always attached to its
sound as ONE string, in `target_ipa`, `hear`, the sound check's flags and the cost table alike. `env.join_length` is the one function
that does it (called at the end of `phones_of`, which every path uses): a lone "ː" from a recogniser, or from the cutter, is joined to
the sound before it, and dropped if there is none. The cost table has the long sounds as keys (37 of its 168 sounds), costed as any
other pair by panphon's weighted feature distance (it has a `long` feature) with Miolingo's accept and tolerated entries for the
language kept as they are; nothing is tuned. Of the two phone models, the multilingual xlsr-53 espeak model (English, German) has 48
tokens carrying ː and writes length; the French specialist has only a lone "ː" token. `tests/check_segmentation.py` checks all of this.

## Not here yet

HTTPS (needed for the microphone off the Mac); the microphone path (`host.js` `record`) and the drawing and playing of takes (`showTake`, `playTake`) are untested in a browser;
the page does not yet call `speak` or `lists` (they work from the console); the stretched score curve (the engine has
only sqrt and linear); the sign-in and more than one learner; accuracy of the recognisers on real learners (only
synthetic voices have been run); no cleanup of `var/speech/`.
