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

### Sources (primary)
- ZIPA: aclanthology.org/2025.acl-long.961 · arXiv 2505.23170 · github.com/lingjzhu/zipa
- pklumpp/Wav2Vec2_CommonPhone (HF) · Dieck 2022 Interspeech (Common Phone) · arXiv 2201.05912
- fb: huggingface.co/facebook/wav2vec2-lv-60-espeak-cv-ft
- Clementapa Dutch (HF) · github.com/ASR-project/Multilingual-PR
- Allosaurus: github.com/xinjli/allosaurus · arXiv 2002.11800
- BranchShine: arXiv 2606.22824
- Corpora: UFPAlign (s13634-022-00844-9) · CORAA NURC-SP · JASMIN-CGN · JRMeyer CV forced alignments · WebMAUS (IFADV/MLS)
