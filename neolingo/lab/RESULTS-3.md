# Neolingo lab, third run: costs against the owner's verdicts (2026-10-14 21:08 BST)

The third run of the bench (`lab/costfit.py`; the first two: `lab/RESULTS.md`).  Question: are the live costs out of proportion (an added sound costs 1000 thousandths, a substitution the check calls off can cost 42), and does another set of costs agree better with the owner's verdicts?  Also: the German vocalised r (B), length (C), "understood" on three takes (D), and a candidate host and deck (F).  The live analysis is the lab's `rec de` / `rec en` / `rec fr` (V2 with the German ü/ö rule), what the real host runs since 14 October 11:28.  For this run only the owner's notes were read by hand to sort his takes into causes; no note is quoted here.

**Amended brief (14 October, evening)**: the order of the two "Wie lange dauert die Überweisung?" takes is reported, not a guard; the verdicts are treated as noisy: of the candidates not separated from the best, the one with the fewest parameters is chosen, and the takes that decide between candidates are counted; his remark about the warning lines is a display matter (for the language lane), not evidence about costs.


## Recommendation

1. **Keep the live costs as the default.  The verdicts do not separate any cost change from them.**  Of 56 judged takes that a cost can bear on, 21 change their agreement under some candidate at all; the other 35 agree (or disagree) under every one. The best in-sample agreement, **indel 800, scale ×0.75** (47/56 against live 41/56), is the maximum over 2160 candidates, so its 6:0 deciding takes against live (p = 0.0312) are not evidence; 472 candidates are not separated from it.  The rule (fewest parameters among them) picks **indel 900** (45/56; against live 4:0 (sign test p = 0.125)).  Applied with each take left out, the same rule agrees on **41/56** held-out takes, live on 41: no gain out of sample.  Chosen on the takes of 13 October, the rule picks live (2/7 on 14 October, live 2).

2. **As data, for trial only**: `NEOLINGO_COSTS=run3` (`data/cost_candidates.json`): insertion and deletion 900 instead of 1000 (the third run's choice: the fewest parameters among the candidates the owner's verdicts do not separate from the best), and German espeak [ɜ]/[ɐ] heard as [r]/[ɾ] free (B).  The insertion and deletion cost of 900 is given as data (every substitution cost times 1000/900, the curve's scale times (1000/900)^2: the same scores; the engine's own 1000 is untouched).  Unset, the host sends today's configuration byte for byte.  It runs on the candidate host (port 8811) and is the deck "candidate".

3. **Needs an engine change (reported, not made)**: a floor on the substitutions the check flags *likely off* only (the engine's costs do not see a flag's level).  It raises the near-miss AUC in all three languages (Miolingo's stretch raises German and English only, and agrees less): at a floor of 250, German 0.741 → 0.746, English 0.737 → 0.741, French 0.800 → 0.805, and more with a higher floor (table A3); the verdicts do not separate it either (44/56, against live 3:0, p = 0.25).  The same floor on EVERY substitution (what data can do) lowers the AUC and the agreement.  B's one-to-two rule for the vocalised r is the other engine change (below).

4. **Understood (D)**: keep the live rule (below).


**The two takes** (first, judged harsh / second, judged generous): live 86 / 95; indel 900 87 / 95; indel 800, scale ×0.75 87 / 94; `run3` 87 / 95.  With B's one-to-two rule (an engine change) the first take is 100: its only difference is the [r] beside espeak's [ɜ] in "dauert".  Making the second take score below the first by costs alone needs its three substitutions (62 + 42 + 250 thousandths, raw) to outweigh one insertion: a floor of about 250 with the curve's scale doubled, or Miolingo's stretch; neither is supported by the other verdicts.


## The verdicts

Learner takes with a verdict in the app (or on the review page; the last line wins) or flicked "good" on the deck of 14 October with no app verdict: 77 (fair 35, generous 5, good 12, harsh 25). Excluded, the cause being one no cost can fix: 21.  Included: 56 (fair 32, generous 5, good 11, harsh 8).  Flicks "bad" with no app verdict have no direction and are not counted (they are in the deck).

Agreement, per take, against the score he judged (for an app verdict the score the app showed him then; for a flick the card's score, today's live analysis): harsh = the new score is higher; generous = lower; fair or flick good = within 3 points.  Read literally (every take against TODAY's live score): live 43/56, indel 900 46, indel 800, scale ×0.75 46.


### Exclusions

| take | language | phrase | verdict | cause |
|---|---|---|---|---|
| `t42d936847f737257` | fr | et vous? | harsh | cut |
| `tb04d902ac8cd948c` | de | entschuldigen sie | harsh | artefact |
| `tf643f69ceac5c363` | de | und ihnen? | harsh | whisper |
| `t698f309611ca82f7` | de | oui | harsh | wrong-language |
| `t40d744904c5b09ee` | de | bonsoir | fair | wrong-language |
| `t309e11c9266ac008` | de | geradeaus | harsh | artefact |
| `t859484532bb31584` | de | geradeaus | harsh | display |
| `t0389573fa9a3259e` | de | ja | harsh | artefact |
| `tdd8c8fdf73aef07b` | de | Ich bin allergisch gegen Erdnüsse | harsh | target |
| `tcce1e0e938376149` | de | Ich bin allergisch gegen Erdnüsse | harsh | target |
| `tcbdd329ccd8bf363` | de | Ich bin allergisch gegen Erdnüsse | harsh | target |
| `tc99e694dafcbfa2b` | de | Ich bin allergisch gegen Erdnüsse | fair | target |
| `t08be428fc63c7522` | de | Entschuldigen Sie | harsh | warnings |
| `t89361d5898b8ec57` | de | Einen schönen Abend noch | harsh | whisper |
| `tf9e1a1605ba75fc3` | de | Einverstanden | harsh | artefact |
| `t3c9b76d436e3e4d3` | de | Ich weiß nicht | harsh | warnings |
| `t2160614fae687b2f` | fr | Tu t'appelles comment? | harsh | warnings |
| `t58aaefcc520b11f5` | en | And you? (formal) | harsh | data |
| `t1033c77e57778da5` | de | bankkarte | harsh | target |
| `t9960c7f218cd1343` | de | bankkarte | good | target |
| `t34daef706e341932` | de | bankkarte | fair | target |

- **cut**: the recording was cut off: the missing sound is not in the audio
- **artefact**: recogniser artefact: a sound heard that was not said, or a distinction the recogniser does not hear
- **target**: the target (espeak's reading) differs from what the reference voice says, which the learner copied
- **whisper**: Whisper's transcription failed (not understood) while the sounds were right; the score is not in question
- **wrong-language**: a phrase of another language practised in this one
- **data**: a data error in the phrase (a bracketed note read as part of it)
- **warnings**: the verdict is about the warnings or the display; the score is 100 already
- **display**: the verdict is about the display (punctuation of the heard text), not the score

The owner's flick of the two German "Ihnen" takes and "Einen schönen Abend noch" as not understood is D's question; they are excluded here as Whisper's (or kept as fair where his verdict was fair).


## A. Costs fitted to the verdicts

Grid: Miolingo's stretch (none, p = 0.6) × floor F on every substitution (0, 100, 200, 250, 300, 340, 400, 500) × insertion and deletion I (1000, 900, 800, 700, 600, 500, 400) × the German vocalised r free (no, yes) × the curve's scale S (0.5, 0.6, 0.75, 0.9, 1, 1.25, 1.5, 2, 2.5, 3, 4): 2464 candidates.  Guard: the near-miss AUC (P(a correct word scores above a near miss)) may not fall by more than 0.02 in any language: 2160 pass.  Every candidate was run over every item of the learner takes, near misses, positives, reference phrases and natives (`lab.costfit grid`, `guards`).

### A1. Candidates

| candidate | agree | fair | harsh | generous | flick good | AUC de | AUC en | AUC fr | two takes |
|---|---|---|---|---|---|---|---|---|---|
| (takes of each kind) | 56 | 32 | 8 | 5 | 11 | | | | |
| live | 41/56 | 27 | 3 | 0 | 11 | 0.741 | 0.737 | 0.800 | 86 / 95 |
| indel 900 | 45/56 | 28 | 6 | 0 | 11 | 0.741 | 0.737 | 0.800 | 87 / 95 |
| indel 800, scale ×0.75 | 47/56 | 29 | 6 | 1 | 11 | 0.742 | 0.736 | 0.799 | 87 / 94 |
| scale ×1.25 | 45/56 | 28 | 6 | 0 | 11 | 0.742 | 0.737 | 0.800 | 88 / 95 |
| floor 100 | 44/56 | 28 | 3 | 2 | 11 | 0.737 | 0.736 | 0.800 | 86 / 94 |
| indel 800 | 42/56 | 27 | 6 | 0 | 9 | 0.742 | 0.737 | 0.799 | 89 / 95 |
| indel 700 | 41/56 | 27 | 6 | 0 | 8 | 0.742 | 0.736 | 0.799 | 90 / 95 |
| indel 500 | 40/56 | 26 | 6 | 0 | 8 | 0.746 | 0.736 | 0.799 | 93 / 95 |
| floor 250 | 37/56 | 24 | 3 | 3 | 7 | 0.724 | 0.734 | 0.786 | 86 / 79 |
| floor 250, scale ×2 | 45/56 | 27 | 6 | 1 | 11 | 0.724 | 0.733 | 0.786 | 90 / 85 |
| floor 340, scale ×2.5 | 44/56 | 26 | 6 | 1 | 11 | 0.727 | 0.732 | 0.783 | 91 / 85 |
| stretch 0.6 | 34/56 | 23 | 3 | 3 | 5 | 0.750 | 0.741 | 0.800 | 86 / 75 |
| stretch 0.6, scale ×2.5 | 39/56 | 22 | 6 | 3 | 8 | 0.750 | 0.741 | 0.800 | 91 / 84 |
| stretch 0.6, indel 900, scale ×4 | 41/56 | 27 | 6 | 2 | 6 | 0.752 | 0.745 | 0.799 | 94 / 87 |
| vocal r | 41/56 | 27 | 3 | 0 | 11 | 0.741 | 0.737 | 0.800 | 86 / 95 |
| indel 900, vocal r | 45/56 | 28 | 6 | 0 | 11 | 0.741 | 0.737 | 0.800 | 87 / 95 |

Notes: **stretch 0.6** is Miolingo's min(1, (4c)^0.6); alone it agrees less (34) and with any scale it does not reach live's agreement.  **floor 250, scale ×2** is the data change that puts the second take below the first; it agrees on 45 but lowers the AUC in all three languages.  **vocal r** changes no verdict take's agreement (B).

### A2. The takes that decide

The 21 takes whose agreement changes under some eligible candidate (the other 35 are fixed under all):

| take | language | phrase | verdict | score judged | live | indel 900 |
|---|---|---|---|---|---|---|
| `t91e13c3eb34c2e86` | fr | bonne soirée | fair | 62 | 68 | 68 |
| `tcbea80baecdae344` | de | entschuldigen sie | fair | 98 | 98 | 98 |
| `td203986f3b255854` | de | Und Ihnen? | fair | 99 | 99 | 99 |
| `tf3ab0dee985c5c9d` | de | Achtung | harsh | 98 | 98 | 98 |
| `te13be8a36018725f` | fr | Tu t'appelles comment? | harsh | 95 | 95 | 95 |
| `t72305991c0ad6fae` | de | toiletten | good | 96 | 96 | 96 |
| `t0e2e1be04e83a52e` | de | toiletten | good | 72 | 72 | 75 |
| `t14b6c44cabbfb277` | de | toiletten | good | 73 | 73 | 75 |
| `t42cad1c439ec9c90` | de | toiletten | good | 87 | 87 | 87 |
| `t17d25b1c5fdc4fed` | de | toiletten | harsh | 76 | 75 | 78 |
| `t2c9f16e83bff3d1e` | de | toiletten | fair | 78 | 74 | 76 |
| `tf4271fe6a6c45ebb` | de | toiletten | good | 96 | 96 | 96 |
| `t30b7d23f48e5548b` | de | toiletten | fair | 99 | 99 | 99 |
| `t737cf648627a74bd` | de | verkehrsmittel | good | 99 | 99 | 99 |
| `t97569fb5790c6a3e` | de | verkehrsmittel | fair | 99 | 99 | 99 |
| `t6b6b94a7d43a5430` | fr | Je ne comprends pas | fair | 81 | 81 | 83 |
| `td85047e6a4b91fc9` | fr | Je ne comprends pas | generous | 76 | 76 | 78 |
| `tbcc8a66aba1bce95` | fr | Quelqu'un a utilisé ma carte sans autorisation | harsh | 88 | 88 | 90 |
| `t0452ed787ee338ed` | en | Where is the bus stop? | generous | 75 | 75 | 76 |
| `tfb3a25d80bc8603f` | de | Wie lange dauert die Überweisung? | harsh | 86 | 86 | 87 |
| `t800f08aee9bac6a0` | de | Wie lange dauert die Überweisung? | generous | 95 | 95 | 95 |

Between indel 900 and live the deciding takes are 4: `t17d25b1c5fdc4fed`, `t2c9f16e83bff3d1e`, `tbcc8a66aba1bce95`, `tfb3a25d80bc8603f`.

### A3. A floor on *likely off* substitutions only (engine change; approximated)

Approximated on the live alignment (the reconstruction gives every live score exactly: 0 mismatches): the live substitutions, each at a sound flagged off costing at least F, plus I per insertion or deletion, scale S.  Same rule.  The chosen: F 0, I 900, S 1 (45/56); with a floor: F 250, I 1000, S 1 (44); best F 340, I 900, S 1 (47, against live 6:0).  Leave-one-out 41/56 (live 41).

| F (likely off only), I = 1000, S = 1 | AUC de | AUC en | AUC fr | agree |
|---|---|---|---|---|
| 0 | 0.741 | 0.737 | 0.800 | 41 |
| 250 | 0.746 | 0.741 | 0.805 | 44 |
| 340 | 0.750 | 0.741 | 0.805 | 43 |
| 400 | 0.753 | 0.741 | 0.805 | 42 |
| 500 | 0.755 | 0.741 | 0.805 | 41 |
| 600 | 0.756 | 0.742 | 0.804 | 41 |
| 800 | 0.761 | 0.746 | 0.803 | 41 |

### A4. `run3` (the trial candidate) on the guard sets, against live

| language | AUC | near misses detected (costing) | reference =100 | reference diff | natives mean | natives =100 | natives diff |
|---|---|---|---|---|---|---|---|
| German | 0.741 → 0.741 | 89.1% → 89.1% | 67.4% → 67.4% | 0.62 → 0.59 | 86.9 → 87.9 | 18.1% → 18.1% | 3.25 → 3.21 |
| English | 0.737 → 0.737 | 67.7% → 67.7% | 85.0% → 85.0% | 0.28 → 0.28 | 90.7 → 91.3 | 35.3% → 35.0% | 1.60 → 1.62 |
| French | 0.800 → 0.800 | 95.6% → 95.6% | 79.9% → 79.9% | 0.33 → 0.33 | 93.5 → 94.1 | 52.0% → 52.0% | 1.31 → 1.31 |

Validation: the real engine given the configuration the host builds with `NEOLINGO_COSTS=run3` and the lab's answers (`lab.costfit validate`; `var/lab/validate/engine-candidate-run3.md`): equal **5230**, different **15** (8 of them in the score); the same harness on today's configuration: equal 5230, different 15 (8 in the score). The differences are the lab's, not the candidate's: the lab keeps an unflagged edit at a German sound the check cannot judge (such as the [ɔ] of "eu", cut from [ɔø]), the engine's V2 undoes it; and a few English pictures where a flag says "left out" at a substituted sound.  The nine takes of 14 October replayed end to end through the host's own environment with `NEOLINGO_COSTS=run3` (`tests/replay_archive.py` on a copy of the archive) give the lab's scores.


## B. German vocalised r

espeak writes German -er as [ɜ] (or [ɐ]); a learner who sounds the r is heard [r] or [ɾ], often with a [ə]. **Pairs (data)**: ɜ→r, ɜ→ɾ, ɐ→r, ɐ→ɾ cost 0 and are shown as the target (their warning dropped), as ɾ→r already is.  **One-to-two (engine rule)**: a target ɜ/ɐ heard as a schwa-like sound with an [r]/[ɾ] beside it (or the other way round) is the target; the extra sound is dropped.

| German | reference =100 | reference diff | natives mean | natives =100 | natives diff | near misses detected | AUC |
|---|---|---|---|---|---|---|---|
| live | 67.4% | 0.625 | 86.92 | 18.1% | 3.249 | 89.1% | 0.7414 |
| pairs | 67.4% | 0.590 | 86.97 | 18.1% | 3.205 | 89.1% | 0.7414 |
| pairs + 1:2 | 67.4% | 0.590 | 87.19 | 18.5% | 3.185 | 89.1% | 0.7414 |

Learner takes changed: pairs 4 (Ich bin allergisch gegen Erdnüsse 69 → 69, differences 6 → 5 (×2); Ich bin allergisch gegen Erdnüsse 71 → 71, differences 5 → 4; Ich bin allergisch gegen Erdnüsse 71 → 72, differences 4 → 3); with the one-to-two rule 5 (Ich bin allergisch gegen Erdnüsse 69 → 69, differences 6 → 5 (×2); Ich bin allergisch gegen Erdnüsse 71 → 71, differences 5 → 4; Ich bin allergisch gegen Erdnüsse 71 → 72, differences 4 → 3; Wie lange dauert die Überweisung? 86 → 100, differences 1 → 0).

**The alignment in the first take**: heard [d a ʊ r ə t] for [d a ʊ ɜ t].  With the pairs alone the alignment is still one insertion: "r added, ɜ = ə" and "ɜ = r, ə added" both cost 1000 and the engine's tie-break (pairs first, from the end) keeps the first; the score stays 86.  Only the one-to-two rule removes it.  In "allergisch" (heard [ɛ r] for [ɜ]) the pairs re-align ɜ with [r] and leave an added [ɛ]: one difference fewer in the picture, the same insertion; that word's espeak target is itself the cause (excluded above).


## C. Length

**Now**: a length mark is part of the sound (README "Length"); a long and a short vowel are a pair of the cost table at the panphon distance of the length feature, lowered by the accept lists: German iː→i 8, i→iː 42, a→aː 13, ɑː→a 25; English iː→i and uː→u 0 (Miolingo's accept list at full weight), i→iː 13.  Under V2 a length-only difference of the free reading counts only where the sound check flags that sound; the replay's "only length marks differ" names a heard reading that changed only in its marks.  Of the free reading's length-only differences V2 keeps (kept / all):

| set | German | English | French |
|---|---|---|---|
| reference phrases | 0 / 12 | 0 / 8 | 0 / 1 |
| natives | 9 / 84 | 0 / 34 | 2 / 4 |
| near misses | 23 / 38 | 4 / 23 | 0 / 0 |
| positives | 4 / 25 | 0 / 22 | 1 / 3 |
| learner takes | 9 / 14 | 0 / 2 | 0 / 0 |

**Counting them** (every length-only difference kept, at the table's cost), against live:

| language | reference diff | natives diff | natives =100 | near misses detected | AUC |
|---|---|---|---|---|---|
| German | 0.625 → 0.632 | 3.249 → 3.418 | 18.1% → 17.7% | 89.1% → 89.3% | 0.7414 → 0.7412 |
| English | 0.275 → 0.292 | 1.597 → 1.660 | 35.3% → 34.7% | 68.8% → 69.1% | 0.7369 → 0.7378 |
| French | 0.326 → 0.326 | 1.313 → 1.313 | 52.0% → 52.0% | 95.6% → 95.6% | 0.8002 → 0.8002 |

Learner takes changed: 1 (bankkonto 100 → 100, differences 0 → 1).  Not separated: a few more differences shown, no detection gained.  "Excuse me" (heard [m i] for [m iː]) stays 100 either way: English iː→i costs 0 by the accept list, and even at the panphon cost (42) one length difference moves a nine-sound phrase by one point.  A length difference that matters needs a cost of its own (data, but a decision about the accept lists, not measured here).


## D. Understood: free OR teacher-forced (m = 0) on the three takes

| take | phrase | Whisper heard | live | either m = 0 | margin log P(phrase) − log P(own) |
|---|---|---|---|---|---|
| `t89361d5898b8ec57` | Einen schönen Abend noch | Ein unscherner Abend noch. | False | True | 2.389 |
| `tf643f69ceac5c363` | und ihnen? | Und innen? | False | False | -1.93 |
| `td203986f3b255854` | Und Ihnen? | und einen. | False | False | -0.632 |

One of the three flips at m = 0; m = 2 would flip all three.  Near misses taken as understood (INFLATION) and correct words understood, live → m = 0:

| language | near misses (inflation) | positives | reference phrases |
|---|---|---|---|
| German | 1.2% → 2.3% | 68.0% → 70.7% | 95.1% → 97.2% |
| English | 1.6% → 2.1% | 75.9% → 78.4% | 100.0% → 100.0% |
| French | 1.9% → 3.1% | 53.8% → 59.2% | 92.4% → 93.8% |

German at larger margins: inflation m = 0: 2.3%, m = 1: 3.1%, m = 2: 6.3%; positives m = 0: 70.7%, m = 1: 76.3%, m = 2: 81.5%.

Learner takes that flip at m = 0: 4 (et vous? (harsh), bonne soirée (fair), Einen schönen Abend noch (harsh), bisschen (unjudged)).  The gain is one of the three takes for a doubling of German inflation: keep the live rule.


## What needs an engine change

- A floor on *likely off* substitutions only (A3): the score would read the flag's level.
- B's one-to-two rule for the vocalised r.
- An insertion or deletion cost other than 1000 does NOT: it is given as data (the scale trick above).


## Caveats

- **Few verdicts, one learner**: 56 takes, 21 of them able to move; a verdict is one of three words and often about something else than the score (the owner, 14 October).
- **Reference score**: an app verdict judged the score shown THEN; for the takes of 13 October that was the engine before V2, so V2 alone moved some of them (common to every candidate).
- **Excluded by hand**: the causes come from reading his notes; a different reading moves a few takes.
- **AUC guard** on synthetic near misses (one edit, voices), not learners.
- **A3 is approximated** on the live alignment; B's one-to-two rule is the lab's emulation of an engine rule.


## Commands (from `neolingo/`, Miolingo's venv python, `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`)

    $PY -m lab.costfit grid                 # the learner takes under every combination (seconds)
    $PY -m lab.costfit guards --top 999     # every combination over the guard sets (about 15 min)
    $PY -m lab.costfit fit                  # agreement, the rule, leave-one-out -> var/lab/run3/fit.json
    $PY -m lab.costfit offfloor             # A3
    $PY -m lab.costfit extras               # B, C, D
    $PY -m lab.costfit validate --name run3 # the host's candidate configuration on the real engine
    $PY -m lab.costfit deck --name run3     # var/flick/deck-candidate.json
    $PY -m lab.costfit report               # this file
    NEOLINGO_COSTS=run3 ...                 # a host with the candidate (default: live)

