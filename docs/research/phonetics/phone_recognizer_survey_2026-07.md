# Phone-recognizer survey — candidates to beat the `fb` fallback

**Date:** 2026-07-01
**Method:** deep-research harness (6 search angles, 23 sources fetched, 25 claims
adversarially 3-vote verified, 24 confirmed / 1 killed).
**Feeds:** miolingo-0x9 (decision gate), miolingo-7w3 (root-cause: score must read
the waveform), miolingo-2yv (bake-off).
**Context:** the "accuracy channel" (`src/audio/phone_recognizer.py`) derives IPA
directly from audio. French is solved (`Cnam-LMSSC/wav2vec2-french-phonemizer`,
~0.015 weighted err). Every other language falls back to
`facebook/wav2vec2-lv-60-espeak-cv-ft` (`fb`) — a *fallback*, not a champion. This
survey asks, per language: is there a specialist that beats `fb`?

---

## Headline

The strongest answer is **not** a per-language zoo but a **single 2025 multilingual
model, ZIPA**, which beats the `fb` fallback class and — crucially — covers the two
product-critical languages Common Phone cannot (**Dutch and Portuguese**).

---

## Bake-off result (CP-FR, 150 utt, weighted metric) — 2026-07-01

Committed harness `research/phonetics/phone_poc/cp_eval.py` (miolingo-2yv), scoring
audio-derived IPA vs espeak-G2P reference with the app's `weighted_phone` metric
(mean 1 − similarity; lower = better):

| model | mean weighted error | vs prior 0x9 | status |
|-------|--------------------:|--------------|--------|
| **cnam** (French specialist, shipped) | **0.0126** | 0.015 ✓ | 150/150 clean |
| **fb** (multilingual fallback) | **0.0719** | 0.066 ✓ | 150/150 clean |
| pklumpp | — | — | **failed 150/150** |

**The specialist beats the fallback ~5.7× on real audio**, reproducing the earlier
scratch numbers → the reproducible harness is validated. Both *new* candidates were
non-drop-in: **ZIPA** is k2/Zipformer + undeclared licence (excluded by design);
**pklumpp** ships weights only (no processor/vocab on HF) → `AutoProcessor` fails.
pklumpp integration tracked as **miolingo-dky** (needs the author's 101-symbol vocab
+ hand-built processor).

---

## Candidate models

### ZIPA — lead candidate (universal)
- **IDs:** models `anyspeech/zipa-*` (HF); code `github.com/lingjzhu/zipa` (MIT);
  paper ACL 2025 `aclanthology.org/2025.acl-long.961/` / arXiv `2505.23170`.
- **Arch:** Zipformer, trained from scratch on IPAPack++ (17,132h). **CTC variant
  (ZIPA-CR)** exposes per-phone posteriors (needed for abstention); transducer
  variant (ZIPA-T) also exists.
- **Output:** native **IPA** directly from waveform; 127-symbol IPA unigram tokenizer.
- **Accuracy (controlled, same params):** ZIPA-CR-large (300M) **3.14 PFER** vs the
  `fb`-sibling `W2V2P-xlsr-53-ft` (300M) **11.88** — ~3.8× better. ZIPA-CR-small
  (**64M, ~256MB**) at 5.62 PFER still beats the 300M baseline → **on-device viable**.
- **Coverage:** seen-language benchmark includes `dut` (Dutch) and `por` (Portuguese).
- **Caveats:**
  1. Portuguese is a **single `por` head, no pt-BR/pt-PT split**; paper flags a
     Portuguese phone-set mismatch (é→[a]). May not serve both PT variants cleanly.
  2. **Licence unresolved:** code MIT, paper CC BY-NC-ND (non-commercial), **HF
     weights have *undeclared* licence metadata** → confirm commercial use with
     authors before shipping. ONNX fp32/fp16/int8 variants exist.

### pklumpp/Wav2Vec2_CommonPhone — specialist for the benchmarkable tier
- **ID:** `huggingface.co/pklumpp/Wav2Vec2_CommonPhone`.
- **Arch:** XLSR-53 + linear CTC over 101 IPA symbols + blank; IPA from audio.
- **Trained on:** the Common Phone corpus (Mozilla Common Voice, CC0).
- **Accuracy:** **9.2% avg PER** — EN 11.0, FR 9.9, DE 9.8, IT 9.1, ES 8.8, **RU 6.6**
  (self-reported, clean read speech). Far better than the 18.1% base-CP baseline.
- **Fit:** covers de/es/it/en + Russian (curiosity lang, its *best* language).

### Clementapa/wav2vec2-base-960h-phoneme-reco-dutch — weak Dutch fallback
- Emits espeak-convention IPA (phonemizer/espeak targets → zero-integration map).
- **20.8% test PER** (clean) — weak; **no licence stated** (deployment blocker).
- Use only if ZIPA's Dutch fails; prefer ZIPA.

### BranchShine — tiny on-device option
- 33.38M params (~134MB), raw-audio→IPA CTC (E-Branchformer). 3rd place (9.19% CER)
  behind both ZIPA CTC variants. Single unreplicated preprint (arXiv 2606.22824).
- Framed as a lightweight alternative if ZIPA-small is still too big.

### Allosaurus — universal fallback, licence risk
- 2000+ languages, per-language inventory masks, audio→IPA CTC. **GPL-3.0** —
  copyleft concern for a shipped desktop app (legal review / process isolation).
- Older/weaker than ZIPA (which uses it as the standard baseline).

### fb (`facebook/wav2vec2-lv-60-espeak-cv-ft`) — current fallback, characterized
- wav2vec2-large-lv60 phoneme-CTC, espeak-convention IPA from 16kHz via argmax over
  CTC logits, ~392-phoneme espeak vocab. A legitimate baseline, beaten by ZIPA.
- Because it already emits espeak-IPA, **any IPA-emitting replacement drops into the
  existing pipeline with minimal integration.**

---

## Per-language recommendation

> **Superseded / expanded by the 2026-07-07 specialist sweep below** (6-agent
> deep search across de/nl/es/it/pt-br/pt-pt/ru + a universal-model sweep). The
> table here is the original ZIPA-centric view; the sweep found **drop-in
> per-language specialists** that change the near-term plan. Read both.

| Tier | Language | Recommendation |
|------|----------|----------------|
| Product-critical | **nl / nl-be** | Adopt **ZIPA** (`dut`). Fallback: Clementapa (weak, 20.8% PER, no licence) — prefer ZIPA. |
| Product-critical | **pt-BR / pt-PT** | **ZIPA interim**, but single `por` head + é→[a] mismatch → likely needs a fine-tune or dedicated eval before trust. Weakest-covered need. |
| Benchmarkable | **de, es, it, en** | **pklumpp/Wav2Vec2_CommonPhone** (9.2% avg PER). Compare head-to-head with ZIPA on CP gold. |
| Curiosity | **ru** | pklumpp (6.6% PER — its best). |
| Done | **fr** | Keep **Cnam-LMSSC**. Nothing clearly superior found. |
| On-device tiebreak | any | **BranchShine** (33M) if ZIPA-small too big; 3rd in accuracy. |
| Universal fallback | any | **Allosaurus** viable but **GPL-3.0** — legal review needed. |

---

## Evaluation corpora for the no-gold languages (answers brief part c)

Common Phone = `{de, en, es, fr, it, ru}` only — **no nl, no pt**. To evaluate the
product-critical languages, build gold via forced alignment:

- **pt-BR:** **UFPAlign** (free Kaldi phone-level forced alignment for Brazilian
  Portuguese) + **CORAA NURC-SP** (~18h spontaneous BR speech).
- **nl / nl-be:** **JASMIN-CGN** (~90h Dutch/Flemish, incl. a Flemish nl-BE subset
  and — valuable — **non-native/L2 speech**); **IFADV + Dutch MLS** via WebMAUS.
- **General:** Common Voice + **Montreal Forced Aligner** (JRMeyer precomputed set).
- **Interim:** ZIPA's own `dut`/`por` test partitions work as a relative-ranking
  harness before true gold exists.

---

## Cross-cutting caveats

- The "44–45% IPA-CER for wav2vec2" figures in the BranchShine paper are **explicitly
  disclaimed by its authors** (baselines not retrained) — not `fb`'s true accuracy.
  The load-bearing evidence is the controlled **3.14 vs 11.88 PFER**.
- All PER/PFER figures are **clean read speech, self-reported** — expect degradation
  on the app's real **L2/accented** domain. No source validated posterior
  *calibration* quality empirically.
- Metrics mix **PFER** (feature distance) and **IPA-CER** (character error) — absolute
  magnitudes not directly comparable across papers.
- IPAPack++ "gold" is **G2P-normalized (PHOIBLE), not hand-annotated**; ranks models
  but is not a true phonetic ground truth for pt/nl. Common Phone IS hand/force-aligned
  gold, but only for its 6 languages.

---

## Open questions (logged on miolingo-0x9)

1. Does ZIPA's single `por` head handle pt-BR vs pt-PT acceptably, or do we need two
   specialists/heads given the BR/PT split and the é→[a] mismatch?
2. **Actual licence of the ZIPA HF weights** (undeclared) — commercial-use OK for a
   shipped desktop app?
3. How do ZIPA / pklumpp / `fb` compare on **accented/L2** audio (the app's real
   domain), not the clean read-speech benchmarks these numbers come from?
4. For pt-BR/nl, which real-audio eval to build first — CV+MFA, MLS(pt), JASMIN(nl),
   or purpose-collected L2 — and can ZIPA's `dut`/`por` partitions serve as interim?
5. Do any per-language **Meta MMS** phoneme heads beat `fb`, or is ZIPA strictly
   dominant (making the MMS branch moot)?

## Next step

Bake-off (miolingo-2yv): add **ZIPA-CR** and **pklumpp** to
`research/phonetics/phone_poc/bench.py`, score both vs `fb` on the existing Common
Phone French set with the **weighted_phone** metric; separately stand up a pt-BR
(UFPAlign) or nl (JASMIN) eval so the two gap languages stop being blind spots.

---

# Per-language specialist sweep — 2026-07-07

**Method:** 6 parallel deep-search agents (de · nl/nl-be · es+it · pt-br/pt-pt ·
ru · universal-multilingual), every model id + licence verified live against the
HuggingFace API. Goal: for each product language, find a **specialist that beats
the `fb` fallback**, preferring HF `AutoModelForCTC` drop-ins that emit
espeak-convention IPA (zero integration, like the shipped French `Cnam` model).

**The single biggest finding: the Cnam-LMSSC group (authors of our shipped French
model) also publish MIT-licensed Spanish and Italian phonemizers of the *identical*
architecture** — genuine two-line drop-ins. Spanish and Italian go from "fallback"
to "solved" for the cost of two dict entries.

## Consolidated decision table

| Lang | Best specialist | Licence | Integration | Reported acc. | Verdict |
|------|-----------------|---------|-------------|---------------|---------|
| **fr** | `Cnam-LMSSC/wav2vec2-french-phonemizer` *(shipped)* | MIT | drop-in, espeak-IPA | 0.013 weighted (our bake-off) | keep |
| **es** | `Cnam-LMSSC/wav2vec2-spanish-phonemizer` | **MIT** | **drop-in, espeak-IPA** | 2.94% PER (MLS-es) | **WIRE NOW** (2-line) + bench |
| **it** | `Cnam-LMSSC/wav2vec2-italian-phonemizer` | **MIT** | **drop-in, espeak-IPA** | 4.34% PER (MLS-it) | **WIRE NOW** (2-line) + bench |
| **pt-br** | `caiocrocha/wav2vec2-large-xlsr-53-phoneme-portuguese` | Apache-2.0 | drop-in, own 42-sym IPA (symbol-map check) | ~0.16 PER (CORAA, 10h thesis) | bench first, then wire |
| **de** | `HK0712/Wav2Vec2_German_IPA` | **UNDECLARED (blocker)** | drop-in, espeak-IPA; weak `wav2vec2-base` backbone | none published | licence-clear + bench; else `kgnlp/allophant` (Apache, custom pkg) |
| **nl / nl-be** | `Clementapa/wav2vec2-base-960h-phoneme-reco-dutch` | **UNDECLARED (blocker)** | drop-in, espeak-IPA; weak `base` backbone | 20.8% PER (CV-nl) | licence-clear + bench; academic HuBERT (Radboud, JASMIN, 23.1% PER) unreleased — email authors |
| **ru** | `pklumpp/Wav2Vec2_CommonPhone` | **CC0** | weights load, but **no processor/vocab on HF** (build = miolingo-dky); 101-sym → symbol map | 6.6% PER (its *best* lang) | dky reconstruct + bench |
| **pt-pt** | **none exists** | — | — | — | no EP phone specialist anywhere (INESC-ID CAMÕES is text-ASR); fallback or fine-tune |
| **en** | `pklumpp` (11% PER) or `bookbot/wav2vec2-ljspeech-gruut` (0.99% LJSpeech, gruut) | CC0 / Apache | symbol map | — | optional, low priority |

## Bench results — Common Phone + FLEURS (2026-07-07)

The sweep's recommendations were then **benched on real audio** (150 utt/lang,
`cp_eval.py` weighted_phone metric vs espeak-G2P reference; lower = better). **The
paper PERs mispredicted Spanish** — always bench:

| Lang | corpus | fb (lv-60) | **fb-xlsr** | specialist | winner |
|------|--------|-----------:|------------:|-----------:|--------|
| **es** | CP-es | 0.0603 | **0.0364** | cnam-es **0.0708** | **fallback** — specialist *loses* |
| **it** | CP-it | 0.0849 | 0.0645 | **cnam-it 0.0461** | **cnam-it specialist** |
| **de** | CP-de | 0.1141 | **0.0426** | hk-de **1.0** (empty output) | **fallback** — hk-de unusable |
| **pt-br** | FLEURS | 0.1542 | **0.1143** | caiocrocha 0.1156 | **fallback** — specialist ties, no gain |
| **nl** | FLEURS | 0.1447 | 0.1116 | **clementapa 0.086** | **clementapa specialist** |
| **ru** | CP-ru | 0.1333 | 0.1400 | **pklumpp 0.0733** | **pklumpp specialist** |
| fr *(prior)* | CP-fr | 0.0719 | — | **cnam 0.0126** | cnam specialist |

**`fb-xlsr` beat the old `lv-60` fb on all 5 benched languages** (es/it/de/pt-br/nl;
de biggest at 0.043 vs 0.114). The xlsr-53 fallback is the real workhorse — strong
enough that specialists only clear it for **fr** (0.013), **it** (0.046) and **nl**
(0.086). `hk-de` emits empty strings (placeholder student model → unusable);
`caiocrocha` pt-BR ties the fallback (a symbol map for its 42-sym inventory might
tip it, but no gain as-is). Net wiring: **fr/it/nl specialists + xlsr-53 fallback
for everything else**, `lv-60` retained as a selectable backstop.

### Final wiring (branch `claude/a2p-es-it-specialists`, `_VOICE_TO_MODEL`)

| voice | model | why |
|-------|-------|-----|
| fr (+fr-*) | Cnam french-phonemizer | specialist 0.013 |
| it | Cnam italian-phonemizer | specialist 0.046 |
| nl (+nl-be) | Clementapa dutch | specialist 0.086 (licence: clear before ship) |
| es/de/pt/pt-br/ru/en/… | **facebook/wav2vec2-xlsr-53-espeak-cv-ft** | fallback beat every specialist tested for these + beat lv-60 everywhere |
| *(backstop)* | facebook/wav2vec2-lv-60-espeak-cv-ft | previous default, kept selectable (miolingo-3ym) |

**ru now benched + wired (miolingo-dky closed):** pklumpp's HF repo is weights-only
with a custom class, so it's reconstructed in `src/audio/pklumpp_ctc.py` (vendored
class + the exact 101-symbol vocab from github.com/PKlumpp/phd_model; state dict
loaded directly, audio standardized, greedy CTC). It won ru **0.073 vs fb-xlsr 0.140**
and is wired as the `ru` default. Note ru is the *only* language where xlsr-53 did
not beat lv-60 (0.140 vs 0.133) — both fallbacks lose to pklumpp regardless.

Still open: **pt-pt** (no specialist exists), **en** (unbenched). ZIPA (all-lang
frontier) still needs the ONNX runtime path. The flyout model-selector (miolingo-3ym)
and load-on-demand/unload-on-switch lifecycle (miolingo-s06) are now implemented.

### Final wiring (all specialists benched on real audio)

`fr→cnam · it→cnam-it · nl→clementapa · ru→pklumpp · es/de/pt/pt-br/en→xlsr-53
fallback · lv-60 backstop`. The sidebar "🗣️ A2P Recognizer" expander lets a tester
override any language's model live and unload the large models.

**Two decisive outcomes:**
1. **`fb-xlsr` (xlsr-53-espeak) beats the old `lv-60` fb on both es and it** (and same
   loader/convention) → adopted as the new `_MULTILINGUAL_MODEL` default; `lv-60`
   retained as a selectable backstop.
2. **`cnam-es` truncates full sentences** (drops function words + trailing segments —
   e.g. `es mjembɾo ðel konsexo θjuðaðano estatal ðe poðemos` → `mjembɾo ðe konsexo
   θjuðaðao esals`) and loses to *both* fallbacks. Spanish therefore gets **no
   specialist** — it rides the improved fallback. The Cnam family is excellent for
   fr/it but **not uniformly** — the "same authors ∴ same quality" assumption failed.

Caveat: es/it/de have **no fold-map** entry yet, so their weighted scores use panphon
feature distance *without* allophony tolerance — relative ranking is sound, absolute
numbers would tighten with a mined fold-map (extend `espeak_mine.py`, cf. miolingo-als).

## Two universal levers (orthogonal to the per-language specialists)

1. **`facebook/wav2vec2-xlsr-53-espeak-cv-ft`** (Apache-2.0) — the XLSR-53,
   60-language sibling of our current LV-60 `fb`. **Same loader, same
   espeak-convention IPA → literally zero integration.** XLSR-53 transfers better
   cross-lingually than the English-centric LV-60, so a one-line swap of the
   `_MULTILINGUAL_MODEL` fallback likely lifts **every** non-specialist language at
   once (de, pt, pt-br, nl, ru). Needs only an A/B confirmation. **Cheapest
   broad-coverage win available.**
2. **ZIPA** (`anyspeech/zipa-*`) — the accuracy frontier: PFER 2.70 on seen langs,
   dominates `fb` across all 9, PHOIBLE IPA. **But** HF weight cards are
   licence-blank (code is MIT — archive the repo LICENSE as provenance) and it is
   Zipformer/k2 or **ONNX**, not `AutoModelForCTC`. Roadmap item: adopt only with an
   ONNX inference path. Best single-model universal replacement long-term.

## Integration taxonomy (how much work each tier is)

- **Zero integration (espeak-IPA, already consumed):** the `fb` family
  (`lv-60`, `xlsr-53`) and the **Cnam es/it/fr** specialists.
- **Drop-in but needs an IPA symbol-map:** `pklumpp` (101-sym), `caiocrocha`
  pt-br (42-sym), `bookbot`-gruut, `neurlang` ipa-whisper (seq2seq, not CTC).
- **Non-HF runtime required:** ZIPA (k2/ONNX), Allosaurus (GPL — blocked),
  XEUS/POWSM/PhoneticXEUS (ESPnet; licences undeclared / NC).

## Licence blockers (shipped commercial desktop app)

- **Clean:** Cnam es/it/fr (MIT), caiocrocha pt-br (Apache), pklumpp (CC0),
  both `fb` espeak variants (Apache), `kgnlp/allophant` (Apache), `bookbot` (Apache).
- **Undeclared → clear before shipping:** `HK0712` German, `Clementapa` Dutch,
  `snu-nia-12/*`, ZIPA HF weight cards, PhoneticXEUS, POWSM.
- **Hard blockers:** Meta MMS + SeamlessM4T + XEUS (CC-BY-NC), Allosaurus (GPL-3.0).
  MMS also emits orthographic text, not phones — doubly unusable.

## Recommended action ladder (fastest → slowest to "A2P for many languages")

1. **Now, ~free:** wire **es + it** Cnam specialists into `_VOICE_TO_MODEL`
   (`src/audio/phone_recognizer.py`). Clean-specialist coverage {fr} → {fr, es, it}.
2. **Now, ~free:** A/B **`xlsr-53-espeak`** vs the current `lv-60` fallback on
   pt/nl; if it wins, swap `_MULTILINGUAL_MODEL` — lifts all remaining langs at once.
3. **Bench-then-ship:** pt-br (`caiocrocha`, Apache) — verify the thesis PER on real
   audio, add symbol-map if needed.
4. **Licence-clear + bench:** de (`HK0712`) and nl (`Clementapa`) — open HF licence
   discussions in parallel; keep `allophant` (Apache) as the de fallback.
5. **Symbol-map tier:** finish **miolingo-dky** (pklumpp processor/vocab) → unlocks
   the CC0 best-in-class for ru (and a strong de/es/it/en comparator).
6. **Roadmap:** ZIPA via ONNX — single universal model, needs runtime work.
7. **Genuine gap:** pt-pt has **no** off-the-shelf specialist — fallback for now;
   a purpose-built EP fine-tune is the only path to a real pt-PT model.

## Eval corpora recap (for benching the above)

Common Phone = `{de,en,es,fr,it,ru}` gives hand/force-aligned gold for **es, it, de,
ru** head-to-heads *today* (run `research/phonetics/phone_poc/cp_eval.py --lang <l>`).
**pt-br:** CORAA / UFPAlign. **nl/nl-be:** JASMIN-CGN (incl. Flemish + L2). No gold
exists for **pt-pt**.

---

### Sources (primary)
- ZIPA: aclanthology.org/2025.acl-long.961 · arXiv 2505.23170 · github.com/lingjzhu/zipa
- pklumpp/Wav2Vec2_CommonPhone (HF) · Dieck 2022 Interspeech (Common Phone) · arXiv 2201.05912
- fb: huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft
- Clementapa Dutch (HF) · github.com/ASR-project/Multilingual-PR
- Allosaurus: github.com/xinjli/allosaurus · arXiv 2002.11800
- BranchShine: arXiv 2606.22824
- Corpora: UFPAlign (s13634-022-00844-9) · CORAA NURC-SP · JASMIN-CGN · JRMeyer CV forced alignments · WebMAUS (IFADV/MLS)

### Sources (2026-07-07 specialist sweep)
- Cnam-LMSSC phonemizers: huggingface.co/Cnam-LMSSC/wav2vec2-{spanish,italian,french}-phonemizer (MIT)
- pt-br: huggingface.co/caiocrocha/wav2vec2-large-xlsr-53-phoneme-portuguese (Apache-2.0, CORAA)
- de: huggingface.co/HK0712/Wav2Vec2_German_IPA (licence undeclared)
- nl: huggingface.co/Clementapa/wav2vec2-base-960h-phoneme-reco-dutch (licence undeclared) · Radboud CLST child-speech: arXiv 2406.07060 / 2506.11079 (unreleased)
- universal: huggingface.co/facebook/wav2vec2-xlsr-53-espeak-cv-ft (Apache-2.0) · huggingface.co/kgnlp/allophant (Apache, custom pkg) · POWSM arXiv 2510.24992 · ZIPA anyspeech/zipa-* (HF cards licence-blank; code MIT)
- pt-pt (no phone specialist): INESC-ID CAMÕES text-ASR, arXiv 2508.19721
