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
| test | `tests/check_host.py` (runs `tests/check_host_js.js` under node); `tests/check_store.py` (store, lists, test voices; no models); `tests/check_flags.py` |

Endpoints: `GET /` (the page with `<script src="host.js">` inserted before its own script, at serve time),
`GET /host.js`, `GET /version`, `GET /wordlists`, `GET /take/<token>.wav` (the stored take; 404 if unknown), `POST /press`, `POST /take` (WAV body, answers `{"take": token}`), `GET /speak?text=&variant=&slow=`
(speech, cached under `var/speech/`; see below), `GET /lists`.
`GET /version` answers `page` and `changed` (first line of `page/CHANGES`), `engine` (the locus hash in `page/SOURCE`), `built`
(the engine binary's modification time), `instance` (`real`), `host` (this repository's short hash), `tts`, `started`.
`./update_page.sh` copies `index.html` and `CHANGES` from the locus repository and writes `SOURCE` (no restart needed).

Speech: `NEOLINGO_TTS` = `gtts` (default; Google's text-to-speech through the `gtts` package, MP3, the only network use; falls back
to `say`, and the log says which answered) | `say` (WAV). **espeak-ng is not a voice** (the owner, 13 October 2026: "so horrible to hear that we won't go there
again"); it stays the source of the target sounds and the tests' synthetic voice. If both voices fail, `GET /speak` answers 503 with `{"err": ...}`
and `host.js`'s `speak()` rejects with that text, for the page to show. `host.js` plays whatever content type comes back.

**A reload loses nothing.** The page sends `{"cmd":"start"}` when it loads. If the engine process is alive and holds the session (it does from the
host's own start until the engine is restarted), the host answers with the engine's present state (`{"cmd":"state"}`): the list, the place, the
recording held and the result are as they were. A real new start happens only when the host starts, or the engine was restarted. For testing,
`{"cmd":"start","fresh":true}` does the old thing (the stored data are untouched). Tested in `tests/check_host.py` (phrase 3 of 5 with a recording held, then a
Check, each followed by a reload).

**Stored practice lists** (engine side being built; written to this text, protocol additions below). `start` sends each learner's `"lists":[{"lang":L,
"items":[{"text":...,"gloss":...}]}]` beside vocab, history and settings (`[]` when none); the new write `{"kind":"putList","uid":U,"lang":L,"items":[...]}` replaces
that learner's list for L in one transaction. SQLite table `lists (uid, lang, position, text, gloss, PRIMARY KEY (uid, lang, position))`, created if missing
(an existing database keeps working: tested on a database made without it). An unknown write kind is logged as `ERROR UNKNOWN WRITE KIND ... NOT APPLIED` and the
reply carries `"hostWarning"`. The engine of 13 October 15:19 does not yet know `putList`; the host's side is tested as a unit (`tests/check_store.py`) and
the engine accepts `"lists":[]` in `start`.

**Word lists.** `GET /wordlists` answers `[{name, lang, words}]` from `data/words_{en,fr,de}.json` (sources in `data/README.md`), `window.NeolingoHost.wordLists()`
resolves to it; the page offers them under "Upload a list of words"; the model's `upload` asks the host `fill(word, own, variant)` for each word and `fill`
answers from `data/gloss.json` (`env.gloss`). Words with an apostrophe or a hyphen are not offered: the model's upload drops or changes them.

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

**Human judgements.** `var/archive/judgements.jsonl` has one line a judgement: `time`, `take`, `verdict` (`fair`, `harsh` or `generous`), an optional
`note`, `who` (`"me"`); a later line for the same take supersedes an earlier one. `POST /judge` `{"take","verdict","note"}` writes one (token and verdict
validated); `GET /judgement?take=` returns the latest or `{}`. The app page, once it calls the host's `judgeResult(take, element)` hook (protocol section 8),
shows "Was this result fair?" with Fair / Too harsh / Too generous and a note under each result. **The switch:** `NEOLINGO_JUDGING=0` in the host's
environment hides it (default on); `GET /version` reports `"judging": true|false`. **The review page**, `http://127.0.0.1:8810/review` (`page/review.html`; a test
tool, not part of the app), lists the archived checks newest first with the banner, target and heard sounds, warnings, a Play button, a waveform and the
same buttons and note; filters: variant and "not yet judged" (default on), "Load more" pages 50 at a time (`GET /archive?limit=&before=&variant=&unjudged=`
gives the lines joined with their latest judgement). `replay_archive.py` shows each take's judgement, counts them, and takes `--judged` (only judged takes);
it also reports, of the takes judged too harsh, how many now score higher.
**Test voices.** The takes listed in `var/archive/overseer_takes.txt` (first field of each non-comment line) were made by a Mac voice, not the owner. `GET /archive` gives
their items `"source":"test-voice"`; the review page labels them "Mac voice (test)" and has a "hide test voices" filter (default off; `hidetest=1`). Nothing is removed.

**Reference sweep**: `venv/bin/python neolingo/tests/reference_sweep.py [--engines gtts,say,espeak] [--langs en,fr,de] [--limit N]` makes every phrase of
`data/{en,fr,de}.json` with the host's speech code (gTTS uses the network the first time; results are cached), decodes it to 16 kHz mono under
`var/sweep/`, checks it as a learner's take, and writes `var/sweep/results.jsonl` and `var/sweep/report.txt` (not audible, not understood, score
distribution, the lowest scores, the differing sound pairs, left out and extra sounds, warnings by sound, timings). The voices are synthetic: the
report shows where the sources (espeak target, reference voice, recogniser) disagree, not how accurate the app is on learners.

**Symbol study**: `venv/bin/python neolingo/tests/symbol_study.py evidence|measure|floor|targets` (rerun as the archive grows). `evidence` tabulates, per
language, the differing aligned pairs (target -> heard) of the sweep (both voices) and of the owner's live takes (separate column, never
evidence for inclusion) with the pair's panphon cost, its present cost and whether Miolingo's tables tolerate it, writes `var/study/symbol_pairs.md`
and regenerates `data/symbol_equivalents.json` (committed: symbol pairs and counts only) by a mechanical rule stated at the top of that file.
**The switch:** `NEOLINGO_EQUIV=1` makes the host enter each included pair as a tolerated pair (cost 0, target -> heard only) for its language and
drop the sound-check warnings whose (sound, sounded like) is such a pair; default `0` (nothing changes). `measure` (loads the models, about 6 GB:
run one such process at a time, preferably with `NEOLINGO_VAR` pointing at a scratch copy of `sweep/` and `archive/`) runs the sweep, the whole archive and
wrong-reference controls with the switch off and on in one process and writes `var/study/measure.md`; `floor` reports the voiced seconds that
`env.audible` measures for the sweep, the owner's takes and the silence / hiss / click cases; `targets` lists phrases that both voices score under 90.

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

HTTPS (needed for the microphone off the Mac); the microphone path (`host.js` `record`) and the drawing and playing of takes (`showTake`, `playTake`) are untested in a browser; `judgeResult` is tested only under node with a fake DOM (and called by hand in a desktop browser pane), not inside the real app page;
the page does not yet call `speak`, `lists` or `wordLists` (they work from the console); the stretched score curve (the engine has
only sqrt and linear); the sign-in and more than one learner; accuracy of the recognisers on real learners (only
synthetic voices have been run); no cleanup of `var/speech/`.
