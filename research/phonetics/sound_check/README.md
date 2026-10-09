# Sound check: calibration on native speakers (2026-10-09)

`src/scoring/sound_check.py` gives per-sound feedback for any target language. It uses the
method from `research/phonetics/mdd/README.md`. That learner-English benchmark found:

- the recognizer ranks real errors below accepted sounds 92% of the time (AUC 0.92) with xlsr-53;
- at a 5% false-flag rate it catches about 60% of real errors.

This folder holds the per-language calibration, made with `scripts/sound_check/calibrate.py`.

**Data:** Common Phone native speakers. The dev and test splits contain different people.

- German and English: 400 dev / 400 test, and 300 / 300.
- Spanish and French: 300 / 300 each.

**What calibration sets:**

- **Inventory:** the sounds espeak produces for the language.
- **Learned acceptance:** variants that natives use for at least 10% of a sound, at weight 0.7.
  - Omissions are never learned this way; only the hand-written lists can accept them.
  - The known English-speaker errors are never auto-accepted.
- **Unreliable sounds:** sounds where 35% or more of natives' own productions score below 0.5.
  These are shown grey as "not judged".
- **Thresholds:** set so that about 6% of native sounds are "worth checking" and about 2% are
  "probably off".

**Simulated English-speaker errors:** the expected IPA is changed to a typical English
substitution while the native audio is kept. Detection is then measured on the changed sound.
This is a proxy with the roles reversed; it is not learner speech.

| | native sounds flagged (test) | not judged | simulated English-speaker errors flagged |
|---|---|---|---|
| **German** | 6.5% | ü/ö/eu (y yː øː œ ɔø) | r→ɹ 99%, ich→ick 96%, ach→ack 98%, z→English z 93%, w→English w 100%, st/sp→s 97%, ee/oo diphthongs 100% |
| Spanish | 6.9% | eɪ | r→ɹ 99–100%, o→oʊ 100%, b→v 80% |
| French | 5.9% | (length mark) | r→ɹ 100%, tu→tout 100%, eu→"er" 100% |
| English | 6.3% | several British diphthongs | (no list) |

**Caveats**

- Nothing here has been tested on real learners of these languages. The English learner
  benchmark is the only real-learner evidence.
- German ü/ö are not judged: the recognizer misjudges natives' own ü/ö.
- English is calibrated with espeak's `en` voice (British) against mostly American Common Phone
  speakers.
- espeak's own synthetic German also collects flags, e.g. [b] heard as [m]. Synthetic speech is
  out of the model's domain, so demos with TTS voices are not a fair test.
