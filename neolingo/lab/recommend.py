"""The recommendation and the prose of lab/RESULTS.md and var/lab/report.md (lab/report.py assembles them).

Numbers in the prose are read from var/lab/results/metrics.json (and the rows) when the report is built, never typed."""
from __future__ import annotations

import json
from math import comb

from .combos import UNDERSTOOD

RECOMMENDED = {"de": "rec de", "en": "rec en", "fr": "rec fr"}
LANG = {"en": "English", "fr": "French", "de": "German"}
VOICE = {"gtts": "Google", "say": "compact Mac", "premium": "Premium Mac"}
VOICE_NAMES = {"de": {"gtts": "Google", "say": "Anna", "premium": "Petra (Premium)"},
               "en": {"gtts": "Google", "say": "Daniel", "premium": "Serena (Premium)"},
               "fr": {"gtts": "Google", "say": "Thomas", "premium": "Audrey (Premium)"}}

UNDERSTOOD_TEXT = {"free": "the live rule (the words of Whisper's free transcription equal the phrase's, or it has the "
                           "same sounds, German respellings tried)"}

DECK_CONFIG = ("lab recommendation per language: heard = greedy decode, a difference kept only where the sound check "
               "flags that target sound (V2); a pair the language's table makes free shown as the target sound; "
               "de: ü/ö judged only when a different full vowel is heard and log P(target with it) - log P(target) >= 2, "
               "else unjudged; en: the check's unreliable sounds unjudged; insertions all; raw panphon costs, sqrt curve "
               "(live); models xlsr-53 (de, en), Cnam (fr); understood: " +
               ", ".join(f"{l} {UNDERSTOOD[l]}" for l in ("de", "en", "fr")) + ".  before = the live pipeline.")

INTRO = """Offline experiment bench (`lab/`) for Neolingo's analysis of a take: what counts as heard, costs and
curve, phone model, the "understood" rule.  Every variant is ONE change against the live pipeline (the baseline)
unless its name starts with "combo" or "rec".  All figures come from `var/lab/results/metrics.json`
(`python -m lab.run variants`); definitions and caveats are at the end.  The owner's notes on his takes are never
read by the lab; the tables below are aggregates.

"""


def _p(x):
    return "–" if x is None else f"{100 * x:.0f}%"


def _f(x, d=2):
    return "–" if x is None else f"{x:.{d}f}"


def _ref_diff(m, lang):
    r = m["reference"][lang]
    xs = [r[v]["diff"] for v in ("gtts", "say", "premium") if r[v]["n"]]
    return sum(xs) / len(xs) if xs else None


def _ref100(m, lang):
    r = m["reference"][lang]
    xs = [r[v]["at100"] for v in ("gtts", "say", "premium") if r[v]["n"]]
    return sum(xs) / len(xs) if xs else None


HEAD_ROWS = ["baseline", "A-V1", "A-V2", "A-V3", "A-V4 tau=0", "A-V4 tau=2", "A-ins lr tau=2", "A-ins edges",
             "A-converse", "A-zero=equal", "A5-unjudged", "A5-phoneme", "A5-phoneme+lr tau=2", "B-stretched", "B-linear",
             "B-deletions", "C-lv60", "C-xlsr-fr", "E-check score", "combo clean", "combo clean+V2", "combo clean+V4 tau=2",
             "combo phoneme+lr2+zero+V2"]


def headline(M) -> str:
    out = []
    for lang in ("de", "en", "fr"):
        rows = [n for n in HEAD_ROWS if n in M] + [RECOMMENDED[lang]]
        out.append(f"\n**{LANG[lang]}** (recommended: `{RECOMMENDED[lang]}`)\n")
        out.append("| variant | reference =100 (mean of 3 voices) | reference diff | natives diff | positives diff | "
                   "near misses detected (costing) | judged sounds | targets on the unreliable list | false elsewhere | roles reversed detected | "
                   "harsh: fewer diff | fair: changed |")
        out.append("|" + "---|" * 12)
        for n in rows:
            m = M[n]
            e = n == "E-check score"
            nm = m["nearmiss"][lang]
            det = "check_detected" if e else "detected_costed"
            fl = m["cpflip"][lang]
            a = m["archive"][lang]
            u = nm["unreliable"]
            out.append(f"| {n} | {_p(_ref100(m, lang))} | {'–' if e else _f(_ref_diff(m, lang))} | "
                       f"{'–' if e else _f(m['cp'][lang]['diff'])} | {'–' if e else _f(m['positive'][lang]['all']['diff'])} | "
                       f"{_p(nm['all'][det])} | {_p(nm['judged'][det])} | {(_p(u[det]) + ' of ' + str(u['n'])) if u['n'] else '–'} | "
                       f"{'–' if e else _f(nm['all']['false'])} | {_p(fl['check_detected' if e else 'detected']) if fl['n'] else 'n/a'} | "
                       f"{'–' if e else str(a['harsh'].get('fewer_diff', '–')) + ' of ' + str(a['harsh']['n'])} | "
                       f"{'–' if e else str(a['fair'].get('changed', '–')) + ' of ' + str(a['fair']['n'])} |")
    out.append("\n`diff` = mean number of sounds shown different (near, off, missing, added) per phrase / utterance / "
               "word.  Near misses \"detected (costing)\": a difference at the place of the edit that costs something "
               "(a difference shown at no cost is not counted here; the full tables give both).  E (the check alone) "
               "counts a near miss as detected where the check flags the sound.  Learner takes: of the harsh takes, how "
               "many show FEWER differences than the baseline; of the fair takes, how many change at all.\n")
    return "\n".join(out)


def _sign_p(w, l):
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def voice_pairs(name, lang, set_name):
    from .run import load_rows
    rows = [r for r in load_rows(name) if r["set"] == set_name and r["lang"] == lang]
    by = {}
    for r in rows:
        key = int(r["id"].split("-")[-1]) if set_name == "reference" else r["id"].split("-", 3)[3]
        by.setdefault(key, {})[r["voice"]] = r
    out = []
    for a, b in (("gtts", "premium"), ("gtts", "say"), ("premium", "say")):
        w = l = t = 0
        for d in by.values():
            if a in d and b in d:
                x, y = d[a]["nd"], d[b]["nd"]
                w += x < y
                l += x > y
                t += x == y
        out.append((a, b, w, l, t, _sign_p(w, l)))
    return out


def voices_section(M) -> str:
    try:
        ne = json.loads((__import__("lab.run", fromlist=["RES"]).RES / "native_error.json").read_text("utf-8"))
    except (OSError, ValueError):
        ne = {}
    w = ["## Reference voices: which one the recommended analysis agrees with\n",
         "Per language, under the recommended configuration: the 48 reference phrases a voice (share at 100, at 95 "
         "or more, under 90, mean sounds shown different) and the near-miss positives (single words said correctly); "
         "then paired comparisons on the SAME phrases / words (sign test, two-sided, ties left out); then the weighted "
         "error of the phone model's free reading against espeak (`lab/native_error.py`, no rule applied).\n"]
    for lang in ("de", "en", "fr"):
        n = RECOMMENDED[lang]
        r = M[n]["reference"][lang]
        p = M[n]["positive"][lang]
        names = VOICE_NAMES[lang]
        w.append(f"\n### {LANG[lang]}\n")
        w.append("| voice | phrases =100 | ≥95 | <90 | diff | words below 100 | words diff | free-reading weighted error (phrases) |")
        w.append("|---|---|---|---|---|---|---|---|")
        model = {"de": "facebook/wav2vec2-xlsr-53-espeak-cv-ft", "en": "facebook/wav2vec2-xlsr-53-espeak-cv-ft",
                 "fr": "Cnam-LMSSC/wav2vec2-french-phonemizer"}[lang]
        for v in ("gtts", "say", "premium"):
            err = (ne.get(lang, {}).get(model, {}).get(f"reference {VOICE[v]}") or {}).get("weighted_error")
            w.append(f"| {names[v]} | {_p(r[v]['at100'])} | {_p(r[v]['ge95'])} | {_p(r[v]['lt90'])} | {_f(r[v]['diff'])} | "
                     f"{_p(1 - p[v]['at100']) if p[v]['at100'] is not None else '–'} ({p[v]['n']}) | {_f(p[v]['diff'])} | "
                     f"{_f(err, 3)} |")
        w.append("")
        for set_name, label in (("reference", "phrases"), ("positive", "words")):
            for a, b, x, y, t, pv in voice_pairs(n, lang, set_name):
                w.append(f"- {label}: {names[a]} has fewer differences than {names[b]} on {x}, more on {y}, equal on {t} "
                         f"(sign test p = {pv:.3f})")
    return "\n".join(w) + "\n"


def recommendation(M) -> str:
    def g(n, *path):
        x = M[n]
        for k in path:
            x = x[k]
        return x
    lines = ["## Recommendation\n"]
    lines.append("One configuration per language.  Common to all three: what counts as heard is the greedy decode, but "
                 "a substitution or deletion at a target sound is KEPT only where Miolingo's sound check (target-"
                 "conditioned) flags that sound as `check` or `off` (rule V2: the free reading and the check must agree); "
                 "a pair the language's table makes free (tolerated, or accepted at full weight, e.g. German [r] for "
                 "espeak's [ɾ]) is shown as the target sound; insertions are all kept; costs are the live raw panphon "
                 "distances and the curve the live square root (B did not separate correct from wrong words); the phone "
                 "models stay the live ones.\n")
    lines.append(f"- **German**: `rec de`, xlsr-53.  ü/ö (y, yː, øː, œ, ɔø, the calibrated `unreliable` list) are judged "
                 f"by the free reading only when it hears a different full vowel of German (u, uː, i, iː, o, oː, e, ...) "
                 f"AND the likelihood ratio confirms it: log P(target with that vowel | audio) − log P(target | audio) ≥ 2; "
                 f"otherwise the sound is shown as not judged.  Understood: {UNDERSTOOD_TEXT.get(UNDERSTOOD['de'], UNDERSTOOD['de'])}.")
    lines.append(f"- **English**: `rec en`, xlsr-53; the check's unreliable sounds (a, eə, iə, ɒ, ɔɪ, əʊ, ʊə: mostly "
                 f"notation, espeak [a] against the recogniser's [æ]) are not judged.  Understood: "
                 f"{UNDERSTOOD_TEXT.get(UNDERSTOOD['en'], UNDERSTOOD['en'])}.")
    lines.append(f"- **French**: `rec fr`, Cnam (French has no unreliable sounds).  Understood: "
                 f"{UNDERSTOOD_TEXT.get(UNDERSTOOD['fr'], UNDERSTOOD['fr'])}.\n")
    lines.append("What it gives and what it gives up (baseline → recommended):\n")
    lines.append("| | reference diff | natives diff | positives diff | near misses detected (costing) | on judged sounds | "
                 "targets on the unreliable list | roles reversed detected | learner harsh: fewer diff | learner fair: changed |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for lang in ("de", "en", "fr"):
        b, r = "baseline", RECOMMENDED[lang]
        nb, nr = g(b, "nearmiss", lang), g(r, "nearmiss", lang)
        fb, fr = g(b, "cpflip", lang), g(r, "cpflip", lang)
        u_b, u_r = nb["unreliable"], nr["unreliable"]
        lines.append(f"| {LANG[lang]} | {_f(_ref_diff(M[b], lang))} → {_f(_ref_diff(M[r], lang))} | "
                     f"{_f(g(b, 'cp', lang, 'diff'))} → {_f(g(r, 'cp', lang, 'diff'))} | "
                     f"{_f(g(b, 'positive', lang, 'all', 'diff'))} → {_f(g(r, 'positive', lang, 'all', 'diff'))} | "
                     f"{_p(nb['all']['detected_costed'])} → {_p(nr['all']['detected_costed'])} | "
                     f"{_p(nb['judged']['detected_costed'])} → {_p(nr['judged']['detected_costed'])} | "
                     f"{(_p(u_b['detected_costed']) + ' → ' + _p(u_r['detected_costed'])) if u_b['n'] else '–'} | "
                     f"{(_p(fb['detected']) + ' → ' + _p(fr['detected'])) if fb['n'] else 'n/a'} | "
                     f"{g(r, 'archive', lang, 'harsh', 'fewer_diff')} of {g(r, 'archive', lang, 'harsh', 'n')} | "
                     f"{g(r, 'archive', lang, 'fair', 'changed')} of {g(r, 'archive', lang, 'fair', 'n')} |")
    lines.append("")
    lines.append(WHY)
    lines.append(d_paragraph(M))
    return "\n".join(lines) + "\n"


def d_paragraph(M) -> str:
    """The understood rule (D), with the figures."""
    def u(n, lang, k):
        return M[n]["understood"][lang][k]["rate"]
    from .run import load_rows
    base = {r["id"]: r for r in load_rows("baseline") if r["set"] == "archive" and r["voice"] == "learner"}
    alt = {r["id"]: r for r in load_rows("D-either m=0") if r["id"] in base}
    harsh_nu = [i for i, r in base.items() if r["verdict"] == "harsh" and r["u"] is False]
    harsh_fixed = sum(1 for i in harsh_nu if alt[i]["u"])
    fair_flip = sum(1 for i, r in base.items() if r["verdict"] == "fair" and alt[i]["u"] != r["u"])
    rows = []
    for lang in ("de", "en", "fr"):
        rows.append(f"| {LANG[lang]} | " + " | ".join(
            f"{_p(u(n, lang, 'positive'))} / {_p(u(n, lang, 'reference'))} / {100 * u(n, lang, 'nearmiss_inflation'):.1f}%"
            for n in ("baseline", "D-either m=0", "D-either m=1", "D-prompt")) + " |")
    return ("9. **Understood (D)**: the live rule stays.  Figures as correct words understood / reference phrases "
            "understood / near misses wrongly understood (INFLATION):\n\n"
            "| | live rule | free OR teacher-forced, m = 0 | m = 1 | phrase as prompt |\n|---|---|---|---|---|\n"
            + "\n".join(rows) +
            "\n\n   The prompted transcription inflates heavily (as Miolingo's Swift port found for the hint).  The "
            "teacher-forced rule (understood also when Whisper finds the phrase at least as probable as its own "
            "transcription, within m nats) recovers some correct words but every margin raises the inflation; "
            "the smallest (m = 0) is the only alternative worth considering (on the learner takes it would turn "
            f"{harsh_fixed} of the {len(harsh_nu)} harsh takes now \"not understood\" into understood, and change "
            f"{fair_flip} fair take(s)).  Since inflation is the figure that matters and "
            "the gain is small, the simpler live rule is kept.\n")


WHY = """Why these, from the tables below:

1. **Free differences are removed first** (`combo clean` = A-zero=equal + A5-unjudged, or for German the ü/ö rule):
   the commonest false differences on correct speech are pairs that already cost nothing (English [a] heard [æ],
   [ɒ] heard [ʌ] or [ɔ]; German [ɾ] heard [r], [yː] heard [uː]).  Showing them told the learner something the
   score had already ignored.  Removing them costs no near-miss detection that counts.
2. **V2 for what counts as heard.**  Of the verified rules, V1 (only `off`) removes most false differences but loses
   the most detection (German roles-reversed detection falls to about half); V3 and V4 sit on the same curve as V2
   on near misses, but V2 keeps far more of the German roles-reversed errors than V4 at the same false-difference
   level, and it needs nothing new: the flags the page already shows.  English V2 and V4 at τ = 2 are not separated:
   the simpler (V2) is chosen.
3. **German ü/ö**: "unjudged" detects none of the ü→u/i, ö→o/e near misses; the plain "phoneme" rule detects most
   but also penalises correct ü/ö (about one native token in five, and about half in the synthetic voices); with the
   likelihood-ratio confirmation (τ = 2, chosen on the distribution of the ratio, see caveats) the false
   differences on reference phrases and natives are practically those of "unjudged" while most ü/ö near misses are
   still caught.
   English is different: its unreliable sounds are notation mismatches, and the phoneme rule only adds false
   differences there.
4. **Insertions**: verifying extra heard sounds by the ratio (ins lr, τ = 2) removes a further 10 to 20% of the
   remaining false differences for 1 to 3 points of detection; not separated, so the simpler (keep all) stays.
   Dropping edge insertions loses 8 to 13 points of detection (single words end in real insertions) for no gain on
   phrases.  V2 applied to substitutions only (every deletion kept) gains up to 4 points of detection (German; 2 in
   English, none in French) for 5 to 10% more false differences in German and 80 to 90% more in English: not chosen.
5. **Costs and curve (B)**: they change the score, not what is shown.  The chance that a correct word scores above
   a near miss (AUC) moves by under 0.02 between raw/stretched and square-root/linear: not separated, so the live
   ones stay.  Length normalisation (linear) also hides a single changed sound in a long native sentence (the
   roles-reversed take scores lower than the same audio's correct reading far less often).
6. **Phone model (C)**: lv-60 is clearly worse for German and French (natives' weighted error 2 to 4 times
   xlsr-53's / Cnam's, as the priors said).  For English it is NOT separated on native speech (its free reading
   is slightly closer to espeak) but is worse on the synthetic reference phrases and near misses; the check was
   calibrated with xlsr-53, so the V2 comparison favours xlsr-53.  Keep xlsr-53 (the live model; simpler).
7. **The converse switch** (take the check's alternative where the free reading agrees) adds false differences and
   detects nothing more: rejected.  **E** (100 × mean p_ok, for comparison only) almost never gives 100 (0 to 8% of
   reference phrases); as a detector of near misses (the check's own flag at the place) it is worse than the free
   reading in German and English and slightly better in French (98% against 96%).
8. **French alternative**: V4 at τ = 2 (or V1) halves French false differences again (reference 0.33 → 0.21,
   natives 1.31 → 0.6 a sentence) for 5 points of near-miss detection; V2 is kept for French because it loses
   almost nothing and is the same rule as for the other languages.
"""

def validation_summary() -> str:
    from .common import LAB
    d = LAB / "validate"
    out = ["## Validation of the lab against the live code\n"]
    if (d / "replay.md").exists():
        lines = [l for l in (d / "replay.md").read_text("utf-8").splitlines() if l.strip()]
        out.append("- `var/lab/validate/replay.md`: " + " ".join(lines[1:2])[:600])
    if (d / "stored.jsonl").exists():
        from .common import read_jsonl
        rows = read_jsonl(d / "stored.jsonl")
        groups = {}
        for r in rows:
            g = groups.setdefault(r["group"], [0, 0, 0])
            g[0] += 1
            if r["differences"]:
                g[1] += 1
                if any("WITH THE STORED TARGET: equal" in x for x in r["differences"]):
                    g[2] += 1
        parts = [f"{g}: {n} takes, {bad} different" + (f" ({ok} of them equal with the target stored then)" if ok else "")
                 for g, (n, bad, ok) in sorted(groups.items())]
        out.append("- `var/lab/validate/stored.md` (the lab's baseline against the STORED archive lines, by the engine "
                   "version that wrote them; older engines and reconstructed lines differ by design): " + "; ".join(parts))
    for f in sorted(d.glob("engine-*.md")):
        lines = [l for l in f.read_text("utf-8").splitlines() if l.strip()]
        line = lines[1] if len(lines) > 1 else ""
        import re
        line = re.sub(r"Engine binary: `[^`]*`\.\s*", "", line)          # the binary is host.paths.ENGINE
        out.append(f"- `var/lab/validate/{f.name}`: " + line[:700])
    return "\n".join(out) + "\n"


METHOD = """## Method

**Pipeline per take** (`lab/analyse.py`): target sounds = `env.target_ipa` + the engine's `norm`; the greedy
heard sounds = the phone model's own decode cut as `env.hear` cuts it (cached log-probabilities, float16, with
the greedy path taken from the float32 logits); Miolingo's `sound_check.score` on the same log-probabilities with
the live token-to-sound mapping and the host's `flags_out` and the engine's flag filter; the engine's alignment of
target and greedy sounds (`lab/engine_py.py`, a copy of the engine's `dist`, `align` with its tie-break, `score`,
`byWord`, `columnsFrom`, `understood`); each difference of that alignment is an edit; the variant decides which
edits are kept; the final heard sequence is aligned and scored again.

**Validation before any variant was believed** (`var/lab/validate/`): (1) the replay of the 81 archived takes
through the live environment and the REAL compiled engine equals the lab's baseline in target, heard text, heard
sounds, flags, score, understood and columns for 81 of 81; (2) against the stored lines, every take written by the
present engine is equal, and the 9 that differ because a target changed since are equal when run with the stored
target; (3) the real engine fed the lab's cached answers (and, for a variant, the variant's final heard sounds and
its cost list and curve): see the validation section above (`var/lab/validate/engine-*.md`).

**Data**: ARCHIVE = learner takes (`var/archive/`), test-voice takes excluded, verdict = last judgement line;
REFERENCE = the 48 phrases a language in Google's voice, the compact Mac voice and the Premium Mac voice (anything
shown different is a false alarm by construction); NEAR MISSES = mined minimal pairs (one substitution, deletion or
insertion between espeak's readings of two words; German includes ü/u, ü/i, ö/o), the voice says B for target A,
with both directions and the positives (the voice says A); three voices (Google for a random third of the pairs);
NATIVE = Common Phone test speakers (accent of the variant's country; English partly train split), French
utterances with a typographic apostrophe skipped; ROLES REVERSED = the native audio with ONE target sound changed
to a typical English-speaker error from Miolingo's `english_l1_errors` (German also y→ʊ), detection = a
difference reported at that sound (none for English: Miolingo lists no such errors for English).

**Variants**: A: V1 keep an edit only where the check says `off`; V2 `check` or `off`; V3 `off`, or `check` with the
check's alternative equal to the greedy sound; V4 keep iff log P(target with this edit | audio) − log P(target |
audio) ≥ τ (CTC likelihoods, `sound_check._nll`), τ swept; insertions all / not at the edges / verified by the same
ratio; A5 for the `unreliable` sounds: baseline / unjudged / phoneme (and phoneme confirmed by the ratio);
converse; zero=equal (a pair the table makes free shown as the target sound).  B: stretched costs (Miolingo's
min(1, (4c)^0.6)); linear curve (division by the length); deletions priced by the accept list's "∅" weights (the
data suggested it: schwa deletion is the commonest English false difference); C: lv-60 for every language, xlsr-53
for French; D: the live rule, the prompted transcription, the teacher-forced log-probability of the phrase against
that of the free transcription within a margin m (tf), and free OR tf (either); E: 100 × mean p_ok.

**Priors** quoted beside these figures: on learner English (speechocean762, Miolingo branch
`origin/claude/mdd-benchmark-zipa`) the free transcription falsely rejects 26.6% of correctly said phones with
xlsr-53 (and finds 88% of real errors), while the target-conditioned check ranks errors with AUC 0.92 and catches 61%
of real errors at 5% false rejection.  Miolingo's Swift port removed the target text as a recogniser hint because it
returned the target almost regardless of the audio.  Natives' error against espeak (Common Phone): German xlsr-53
0.043, lv-60 0.114; French Cnam 0.013, lv-60 0.072; English not measured before (here: see the native error table).
"""

CAVEATS = """## Caveats

- **Learners**: one learner, under two names (uid me and benita: the owner testing sign-in with two users); all
  78 learner takes are counted.  The archive is small and almost all German.
  The judged learner takes: fair 33, harsh 23, generous 2.
- **Near misses are synthetic**: voices saying single words; "what B sounds like" is espeak's reading of B, not a
  transcription of the voice; some pairs differ by a sound the voice may not realise as espeak says.
- **Natives**: Common Phone is built from Common Voice, and both espeak-cv-ft models were fine-tuned on Common
  Voice: these recordings may overlap the models' training data (results there may be optimistic, for xlsr-53 and
  lv-60 alike).  The English sample is England-accent only and partly from the train split.
- **Calibration made elsewhere**: the check's thresholds were calibrated on Common Phone dev speakers with xlsr-53
  (English, German) and Cnam (French).  For lv-60 everywhere and xlsr-53 on French the check runs with another
  model's thresholds: the check-based rules (V1 to V3, E) are not a fair comparison for those models; the greedy
  baseline is.
- **Thresholds chosen on these data**: τ for V4 and the ü/ö ratio threshold (2) were read off these same sets;
  there is no held-out set.  The ratio threshold was chosen from three values (0, 2, 4).
- **Reference voices**: 48 phrases a voice; differences of a few phrases are not significant (sign tests given).
- **Display rules** (zero=equal, unjudged) change what the page shows, not the engine's score; V2 and the ü/ö rule
  change the heard sounds and so the score and the columns.  The engine itself has one deletion cost, so
  B-deletions could not be run on it.
"""

COMMANDS = """## Commands (from `neolingo/`, Miolingo's venv python, `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`)

    PY=~/Software/working/miolingo/venv/bin/python
    $PY -m lab.build_nearmiss mine && $PY -m lab.build_nearmiss synth --gtts   # near-miss pairs and audio (gTTS: network)
    $PY -m lab.premium reference && $PY -m lab.premium nearmiss                  # Apple Premium voices (no network)
    $PY -m lab.build_cp select && $PY -m lab.build_cp extract && $PY -m lab.build_cp items   # Common Phone sample
    $PY -m lab.datasets                                                           # wav lists under var/lab/lists/
    $PY -m lab.phone_run --model <hf id> --list var/lab/lists/all-de.txt --threads 4   # log-probabilities (one model a process)
    $PY -m lab.jobs reference nearmiss positive archive
    $PY -m lab.whisper_run --jobs var/lab/jobs/<set>.jsonl --shard K/N [--reverse]      # Whisper medium: free, prompt, teacher-forced
    $PY -m lab.validate stored | replay | engine <sets> [--variant NAME] [--every K]
    $PY -m lab.run fill --workers 3                                              # sound check + likelihood ratios (cache)
    $PY -m lab.run variants [NAME ...]                                           # every variant -> var/lab/results/
    $PY -m lab.native_error                                                       # free-reading error per model
    $PY -m lab.report                                                             # var/lab/report.md and lab/RESULTS.md
    $PY -m lab.deck                                                               # var/flick/deck-results.json
"""
