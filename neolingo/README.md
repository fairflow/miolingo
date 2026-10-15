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
| test | `tests/check_signin.py` (sign-in, on a copy of the real database); `tests/check_host.py` (runs `tests/check_host_js.js` under node); `tests/check_store.py` (store, lists, test voices, the configuration; no models); `tests/check_flags.py`; `tests/check_ipa_exceptions.py`; `tests/check_data.py` (the data lint D1-D3, `data/README.md`); `tests/check_costs.py` (`NEOLINGO_COSTS`: the default adds exactly the vocalised-r pairs, a candidate transforms every entry). Each unit case is named by the fault it guards (`F1 13 Oct`) or `designed`; retired tests are in `tests/archive/` (its README says why) |

Endpoints: `GET /` (the page with `<script src="host.js">` inserted before its own script, at serve time),
`GET /host.js`, `GET /version`, `GET /wordlists`, `GET /take/<token>.wav` (the stored take; 404 if unknown), `POST /press`, `POST /take` (WAV body, answers `{"take": token}`), `GET /speak?text=&variant=&slow=`
(speech, cached under `var/speech/`; see below), `GET /lists`.
`GET /version` answers `slots`, `autosignin`, `page` and `changed` (first line of `page/CHANGES`), `engine` (the locus hash in `page/SOURCE`), `built`
(the engine binary's modification time), `instance` (`real`), `host` (this repository's short hash), `tts`, `started`.
`./update_page.sh` copies `index.html` and `CHANGES` from the locus repository and writes `SOURCE` (no restart needed).
**The page and the engine go together** (since 14 October the result carries `picture` in place of `columns` and `marked`, which the
page of 0.36 and before reads): run `./update_page.sh` only as part of moving the host to a newer engine ("Keeping it alive"), never
while the running host still runs the older engine. `NEOLINGO_PAGE=<dir>` makes a host serve the page files from another folder (a
scratch host can then try a newer page while the running host, from this folder, keeps its own).

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

Takes are never deleted (see the archive, below). `NEOLINGO_VAR` moves `var/` (the test uses it).

    ~/Software/working/miolingo/venv/bin/python neolingo/tests/check_host.py

Since 13 October the settings are a view of their own: `practised`, `own` and `slow` are steps only between `openSettings` and `closeSettings`. The page does that itself;
the tests change a setting through `Host.setting(which, value)` in `tests/check_host.py`, which opens and closes the settings around it.

The configuration also sends `significant: 42` (protocol 5; for the result's picture only, never the score: a substitution costing
this much or more is drawn `off`, less and not 0 `near`). The costs are raw panphon feature distances (thousandths), so the number is
the raw-cost equivalent of Miolingo's 340 on its stretched costs. And `unjudged` (protocol 5, engine `ad5a947` and later; an older
engine ignores it): per language the target sounds the recogniser cannot judge, taken from the cost table's `unreliable` lists (which
come from Miolingo's calibrated sound check): German y yː øː œ ɔø, English a eə iə ɒ ɔɪ əʊ ʊə, French none. Such a sound with no flag
at its place is drawn `unjudged` (grey italic, "not judged") and its heard sound taken as the target's.

**The German ü/ö rule** (the lab's `rec de`, `lab/RESULTS.md` "Recommendation"): the check itself never flags y yː øː œ
ɔø, so `env.sounds` flags one "likely off" (`like` the heard vowel) exactly when the free reading (the phone model's
greedy decode, aligned with the target as the lab aligns it) hears a different FULL vowel of German there and the
likelihood ratio log P(target with that vowel | audio) − log P(target | audio) is at least 2 (CTC likelihoods from the
same log-probabilities, `sound_check._nll`). The code is the lab's own (`lab.analyse.unreliable_subs`,
`lab.check.phones_from_tokens`, `lab.check.lr_from_lp`), called on the take in hand. With it, the German cost entries
of those five sounds against German full vowels are the plain panphon costs (the lab's "phoneme" cost mode), so that a
flagged ü heard as [u] is aligned and costed as the lab did (y→u costs 42: drawn `off`); unflagged, the engine does not
count it (V2, `unjudged`). `lab/check_verify_de.py` (a measurement, `python -m lab.check_verify_de`) compares `env.sounds` with the lab's analysis on the lab's cached
German items (18 of 18 agree on 14 October: 6 each of the owner's archived takes, near misses and positives; the rule fired on 9).
The host log's `flags:` line names each such flag with its ratio.

**Cost candidates** (the lab's third run, `lab/RESULTS-3.md`; 14 October): `NEOLINGO_COSTS=<name>` makes the host send
the costs of a candidate of `data/cost_candidates.json` (`host/engine_config.apply_candidate`); unset or `live`, the
file's entry `live`: since 14 October (the owner's go, 21:1x) today's costs and curve with the German vocalised r
free (espeak's [ɜ] and [ɐ] heard as [r] or [ɾ]: cost 0, shown as the target, the warning dropped; the third run's B),
and the SPLITS of `data/splits.json` (one target sound heard as two: German ɜ/ɐ heard as r or ɾ with a schwa, cost 0;
the engine of locus 977af82, `splits` in protocol section 5; no `offFloor`: measured and not taken, `lab/RESULTS-3.md`
"Follow-up"), reaching the real host at its next restart. `NEOLINGO_COSTS=plain` gives the configuration before 14
October 21:1x (rollback). An unknown name stops the host. A candidate may stretch
the substitution costs (Miolingo's min(1, (4c)^p)), floor them, stand for another insertion and deletion cost `I` (the
engine's own is fixed at 1000, so every substitution cost and `costOtherwise` are multiplied by 1000/I and the curve's
scale by (1000/I)^2: the same scores), multiply the curve's scale, and make pairs free (cost 0, shown as the target; the
sound check's warning for such a pair is dropped, as `NEOLINGO_EQUIV` does). `significant` moves with the costs.
`GET /version` reports `costs`. `run3` (insertion and deletion 900; German espeak [ɜ]/[ɐ] heard as [r]/[ɾ] free) runs on
a scratch host for trial: `NEOLINGO_VAR=var/candidate NEOLINGO_SLOTS=2 NEOLINGO_COSTS=run3
NEOLINGO_ENGINE=var/candidate/neolingo-engine-51ded95 ./run.sh --port 8811` (a copy of `var/` made as in step 1 below, and
a copy of the engine binary of the real host's update, so that a rebuild in locus does not change it), stopped by its
port. `GET /version` reports `host` as the commit the host STARTED from (read once at start; before 14 October it was the
folder's HEAD at the time of the request).

Choices a reader should know: the cost list sent to the engine is the whole matrix (about 18,600 entries, 1 MiB) with
per-variant overrides for tolerated pairs, accept weights and unreliable targets; `hear` gives the sounds as one word;
flags are mapped `like` -> `heardAs` (null when left out), one flag for each target sound a finding covers, `sound` taken from the
target the engine sent; the engine's `droppedFlags` is logged (a warning when not 0); `tests/check_segmentation.py` checks that
target, cost table and recogniser cut sounds the same way; an `unreliable` target costs 0 only against phones of the table (others cost `costOtherwise`).
The engine takes about 11 s to print its `{"ready":1}` line (the host waits for it, no timeout); the host start is about 12 s before it serves.

## Sign-in

The page shows one or more SLOTS; a slot is signed out or signed in as one learner (no password: a name is chosen or typed; protocol
section 6.2). The host starts the engine with `{"cmd":"start","slots":N,"store":[every learner]}`, so every learner of
`var/neolingo.sqlite` is registered and every slot is signed out.

| Switch | Default | Meaning |
|---|---|---|
| `NEOLINGO_SLOTS=N` | `1` | the number of session slots (1 to 8); `2` shows two sessions side by side, for testing two learners |
| `NEOLINGO_AUTOSIGNIN=name` | `me` | after a real start the host itself signs `name` in at slot 1 if registered, so the owner's page opens in the app as before; he can still sign out and register someone else. Empty: start signed out. The log says what was done |

`GET /version` reports `slots` and `autosignin`. A new database has no learner and the engine's `register` is not a step then, so
the host registers the first learner itself (the autosignin name, else `me`) and logs it.

**What is saved when.** History, vocabulary and practice lists are written at once. A change of a setting is NOT written: the
settings are written by `signOut` (`putSettings`), a new learner by `register` (`putLearner`).

- **Clean stop** (SIGTERM, SIGINT, or the host's own exit): the host sends `signOut` for every signed-in slot, applies the writes, then
  stops the engine. The log says `clean stop: signed out ...`. At the next start the auto sign-in returns to the app, so a normal
  restart (`pkill -TERM -f host.serve`) keeps the settings. `{"cmd":"start","fresh":true}` also signs out first.
- **Unclean stop** (`kill -9`, a crash, a power cut, or the engine dying and being restarted): the settings changed since sign-in are
  LOST (everything else was already written). Sign out in the app before such a stop if the settings matter.
- ONE SESSION PER LEARNER (engine of 14 October, locus `bf61d93`..`938dcd8`): Sign in as a learner signed in in another slot is
  refused ("“me” is already signed in."), and a signed-out slot's screen lists such names in `body.elsewhere` (the page marks them
  "signed in on another screen"). The host never starts the engine with a learner named twice (the engine refuses such a start too).
- Sign out and a change of the language practised are refused while a vocabulary form is open ("Save or cancel the open form
  first."). At a clean stop or a `fresh` start the host then closes the settings view if open, shows Vocabulary, Cancels each open
  form (its typed text lived only in the page, which the stop ends anyway) and signs out, so the settings are still saved; the log
  says `sign-out: slot N (u) had open form(s) ...: cancelled so that the settings are saved`.

The archive (`records.jsonl`, `checks.jsonl`, `judgements.jsonl`) carries `"uid"` on every new line (a judgement gets the uid of the
learner who made that take); lines from before count as `me`. `GET /archive?uid=` filters, items carry `uid`, and `/review`
shows the learner on each card with a learner filter. Nothing is recorded in a signed-out slot (the log says so).

**Guest** (the engine's `guest` press, offered in a signed-out slot): nothing is kept. The engine's replies carry `"write":null`; the host writes no
archive line, does not archive the take, deletes the guest's files under `var/takes/` at sign-out (and at a start or stop; `var/guest_takes.txt`
lists them meanwhile), logs `guest: take ... discarded`, and answers `GET /judgement?take=` with `{"guest":true}` so that `host.js` draws no judging controls.

## Testing with sound

**The archive.** Every take uploaded is kept for good under `var/archive/takes/<token>.wav` (`host/archive.py`). `var/archive/records.jsonl`
gets a line at each Record (time, take, duration, peak level, the `audible` answer) and `var/archive/checks.jsonl` one at each Check that is a
step: time, take, variant, phrase, the target sounds as the engine sent them, the host's answers (`hear`, `sounds`), score, understood, banner,
flag lines, flags, the result's `picture` (lines before 14 October: aligned `columns` instead), `droppedFlags`, the whole result, the versions,
the phone model and the Whisper size. `host.archive.columns_of(line)` reads either as columns by word (`target`, `heard`, `mark`), so the
replay and the studies treat old and new lines alike. Since 14 October the banner and the result's `heard.text` are the heard text AS SHOWN
(the phrase's spelling where its words were heard); the recogniser's own writing is in `hear.text`.
`tests/archive/reconstruct_archive.py` (run once, 13 October; archived) copies the takes of `var/takes/` into the archive and rebuilds lines marked `"reconstructed": true`
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
same buttons and note (a line since 14 October shows the engine's picture, drawn as the app draws it, with its legend, and the heard
text as shown beside what the recogniser wrote; an older line shows its two-row grid of columns); filters: variant and "not yet judged" (default on), "Load more" pages 50 at a time (`GET /archive?limit=&before=&variant=&unjudged=`
gives the lines joined with their latest judgement). `replay_archive.py` shows each take's judgement, counts them, and takes `--judged` (only judged takes);
it also reports, of the takes judged too harsh, how many now score higher.
**Flick** (`python3 flick/serve.py --port 8812`, standard library, 127.0.0.1): a page for judging cards fast on a phone
(right good, left bad, up skip), one deck per `var/flick/deck-<name>.json` (made by the lab: `lab/deck.py`,
`lab/costfit.py deck`), verdicts appended to `var/flick/judgements.jsonl`. Since 14 October a one-line note box under
the card (dictation works) is saved with the verdict (`"note"`, only when not empty; at most 1000 characters); a card
judged before shows its note again. Restart it by its port: `kill -TERM $(lsof -ti tcp:8812 -sTCP:LISTEN)`.
A candidate card may carry `old` (the score and picture of the live analysis) and `earlier` (the earlier verdict and
its note), drawn under the new picture.

**Test voices.** The takes listed in `var/archive/overseer_takes.txt` (first field of each non-comment line) were made by a Mac voice, not the owner. `GET /archive` gives
their items `"source":"test-voice"`; the review page labels them "Mac voice (test)" and has a "hide test voices" filter (default off; `hidetest=1`). Nothing is removed.

**Reference sweep**: `venv/bin/python neolingo/tests/reference_sweep.py [--engines gtts,say,espeak] [--langs en,fr,de] [--limit N]` makes every phrase of
`data/{en,fr,de}.json` with the host's speech code (gTTS uses the network the first time; results are cached), decodes it to 16 kHz mono under
`var/sweep/`, checks it as a learner's take, and writes `var/sweep/results.jsonl` and `var/sweep/report.txt` (not audible, not understood, score
distribution, the lowest scores, the differing sound pairs, left out and extra sounds, warnings by sound, timings). The voices are synthetic: the
report shows where the sources (espeak target, reference voice, recogniser) disagree, not how accurate the app is on learners.

**Symbol study** (ARCHIVED 15 October, its hypothesis refuted: `tests/archive/README.md`): `venv/bin/python neolingo/tests/archive/symbol_study.py evidence|measure|floor|targets`. `evidence` tabulates, per
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
only sqrt and linear); accuracy of the recognisers on real learners (only
synthetic voices have been run); no cleanup of `var/speech/`.

## Keeping it alive (written 2026-10-13, when the work was set down)

To have the host start at login and restart if it fails, run `./install_login_item.sh` ONCE yourself
(`./install_login_item.sh remove` undoes it). Without that, nothing starts it; after a reboot, from this folder:

    NEOLINGO_SLOTS=2 nohup ./run.sh --port 8810 >> var/host.log 2>&1 &

(`NEOLINGO_SLOTS=1`, or leaving it out, gives one session.) It answers at
http://127.0.0.1:8810/ after about a minute, when the recognisers are loaded;
`curl http://127.0.0.1:8810/version` says which page, engine and host it runs.
Stop it by its port, never by name, so that it signs every session out and
saves the settings: `kill -TERM $(lsof -ti tcp:8810 -sTCP:LISTEN)`.

It needs: the compiled engine at `~/Lean/locus/.lake/build/bin/neolingo`
(`cd ~/Lean/locus && lake build neolingo`; or set `NEOLINGO_ENGINE`), and the
Python of the Miolingo checkout (`~/Software/working/miolingo/venv`).

The learner's data is in `var/` and is NOT in git: `var/neolingo.sqlite`
(learners, settings, vocabulary, history, lists) and `var/archive/` (takes,
results, judgements). A copy made on 2026-10-13 is in
`~/neolingo-backups/2026-10-13/`. To back up again:

    sqlite3 var/neolingo.sqlite ".backup $HOME/neolingo-backups/<date>/neolingo.sqlite"
    cp -Rc var/archive $HOME/neolingo-backups/<date>/archive

To restore: stop the host, copy `neolingo.sqlite` and `archive/` back into
`var/` (or start the host with `NEOLINGO_VAR=<the backup folder>`), start it.

A copy made on 2026-10-14 (before the update to page 0.41) is in `~/neolingo-backups/2026-10-14/`.

### The update of the real host of 14 October (written 2026-10-14; performed 11:28: host 017176f, engine locus 51ded95, backup ~/neolingo-backups/2026-10-14-1122)

The running host serves `page/` from THIS folder and reads the Python code of this folder only when it starts: a
change committed here reaches the page at once (`page/`) and the engine's answers at the next restart (`host/`,
`env/`, `lab/`, `data/`). So nothing half-done is left uncommitted here, and `./update_page.sh` runs only in step 4.
The update carries the German ü/ö rule (`env.soundcheck.VERIFY_LANGS`, with its costs in `host/engine_config.py`)
and whatever engine and page locus main has then. From this folder, in a terminal:

1. **Back up `var/` first** (a second backup on the same day gets the time in its name):

        B="$HOME/neolingo-backups/$(date +%F)"; [ -e "$B" ] && B="$B-$(date +%H%M)"; mkdir -p "$B"
        sqlite3 var/neolingo.sqlite ".backup $B/neolingo.sqlite"
        cp -Rc var/archive "$B/archive"
        sqlite3 "$B/neolingo.sqlite" "PRAGMA integrity_check; SELECT COUNT(*) FROM settings; SELECT COUNT(*) FROM vocabulary; SELECT COUNT(*) FROM history;"
        wc -l var/archive/*.jsonl "$B"/archive/*.jsonl

   `integrity_check` must print `ok`, and the counts must be those of `var/` (`sqlite3 var/neolingo.sqlite` the same
   queries).
2. **The engine**: `cd ~/Lean/locus && git pull --rebase && lake build neolingo`, then there
   `.lake/build/bin/neolingo neocheck`, `.lake/build/bin/neolingo neoconform` and `python3 scripts/neolingo_conform.py`:
   each must end in `ok`. (The build replaces the binary by a new file, so the running engine is not disturbed; only
   the running host's `/version` "built" changes.) Note the locus hash: `git -C ~/Lean/locus rev-parse --short HEAD`.
3. **The host's tests here, against that engine** (Miolingo's venv python, `HF_HUB_OFFLINE=1`): `tests/check_store.py`,
   `tests/check_flags.py`, `tests/check_gloss.py`, `tests/check_ipa_exceptions.py`, `tests/check_verify_de.py`,
   `tests/check_signin.py`, `tests/check_host.py` must all pass; `tests/replay_archive.py` with `NEOLINGO_VAR` set to a
   copy of `var/` (made as in step 1) prints SAME / CHANGED: read the changes (score and picture changes on German
   takes with ü/ö are the rule's; other changes come from the engine's own changes, named in locus `docs/neolingo-page/CHANGES`).
   Optionally a scratch host first: `NEOLINGO_VAR=<copy> NEOLINGO_PAGE=<folder with the new index.html, CHANGES,
   SOURCE, and links to host.js and review.html> NEOLINGO_SLOTS=2 ./run.sh --port 8811`, stopped by its port.
4. **The page**: `./update_page.sh` (copies `index.html` and `CHANGES` from locus `docs/neolingo-page/`, writes
   `SOURCE`). From here until step 5 the running host serves the new page with the old engine: go straight on.
5. **Restart**: `kill -TERM $(lsof -ti tcp:8810 -sTCP:LISTEN)`, wait until `lsof -ti tcp:8810 -sTCP:LISTEN` prints
   nothing and `var/host.log` ends with `host stopped` (before it: `clean stop: signed out ...`), then
   `NEOLINGO_SLOTS=2 nohup ./run.sh --port 8810 >> var/host.log 2>&1 &`. (If `./install_login_item.sh` has been run,
   launchd restarts the host by itself: use `launchctl kill TERM gui/$(id -u)/io.miolingo.neolingo` instead; it was
   not installed on 14 October.) Never stop it by name.
6. **Check after the restart** (it serves after about 15 s; the recognisers load within a minute):
   - `curl -s http://127.0.0.1:8810/version`: `page` and `changed` are the first line of `page/CHANGES`, `engine` the
     locus hash of step 2 (`page/SOURCE`), `built` the time of the build, `host` this folder's new commit, `slots` 2,
     `autosignin` "me", `started` just now.
   - `var/host.log` since the restart: `engine started ... config (N cost entries ...)` and no `refused the
     configuration`; `start: 2 slot(s), signed out; ... learner(s) registered: ...` with every learner; `auto
     sign-in: me at slot 1 (done)`; `preloaded en-gb`, `fr-fr`, `de`; no `ERROR` and no `FAILED`.
   - The page `http://127.0.0.1:8810/`: the version beside the title is the new page; slot 1 is me's app; slot 2's
     name list marks "me · signed in on another screen", and Sign in as me there is refused.
   - One German Check (a phrase with ü or ö) shows the picture; `var/host.log` has its `flags:` line (with
     `German ü/ö rule: ...` when the rule fired) and `droppedFlags 0`.
   - `http://127.0.0.1:8810/review` shows the new line with its picture and the older lines with their grid.
   - The store is intact: the counts of step 1 again on `var/neolingo.sqlite` (a Check adds one history row).
7. **Record it**: commit `page/` (and anything else changed) here with the locus hash in the message, and push:
   `git push origin HEAD:refs/heads/neolingo` (never to main).

If something is wrong after step 5: stop the host by its port, `git checkout <the previous commit> -- page host env lab
data` here, copy the backup's `neolingo.sqlite` and `archive/` back into `var/` if the store was harmed, and start it
again. The engine binary of the previous locus commit is gone once rebuilt: an older engine with a newer page (or the
other way round) does not work, so roll back the page with the engine, or not at all.
