"""The combinations measured after the single changes (lab/run.py imports COMBOS).

Chosen from the single-change tables (lab/RESULTS.md):
  * "clean" = A-zero=equal + A5-unjudged: the two changes that only stop showing differences that cost nothing
    (a pair the table makes free; a sound the check calibration calls unreliable); near-miss detection that COSTS
    something is unchanged by them.
  * the verified heard rules on top of "clean": V1, V2, V3, and V4 at the thresholds where the single-change curve
    bends (tau 0 to 4); with V4 the extra heard sounds may be verified by the same test (ins lr).
  * German: the "phoneme" rule for ü/ö instead of "unjudged", on its own and with V4.
Costs and curve stay the live ones (raw, sqrt): B did not separate correct from wrong words (lab/RESULTS.md)."""
from __future__ import annotations

CLEAN = {"zero_equal": True, "unchecked": "unjudged"}

COMBOS = {"combo clean": dict(CLEAN)}
for rule in ("V1", "V2", "V3"):
    COMBOS[f"combo clean+{rule}"] = {**CLEAN, "heard": rule}
for tau in (0.0, 1.0, 2.0, 3.0, 4.0):
    COMBOS[f"combo clean+V4 tau={tau:g}"] = {**CLEAN, "heard": "V4", "tau": tau}
    COMBOS[f"combo clean+V4+ins tau={tau:g}"] = {**CLEAN, "heard": "V4", "tau": tau, "ins": "lr", "tau_ins": tau}
COMBOS["combo phoneme+zero"] = {"zero_equal": True, "unchecked": "phoneme"}
for tau in (1.0, 2.0):
    COMBOS[f"combo phoneme+zero+V4 tau={tau:g}"] = {"zero_equal": True, "unchecked": "phoneme", "heard": "V4", "tau": tau}
# second round (after the first combinations): V2 on top of "clean" with the extra heard sounds verified by the
# likelihood ratio; and, for German ü/ö, the phoneme rule confirmed by the likelihood ratio (A5-phoneme+lr)
for tau in (0.0, 2.0):
    COMBOS[f"combo clean+V2+ins tau={tau:g}"] = {**CLEAN, "heard": "V2", "ins": "lr", "tau_ins": tau}
for tu in (2.0, 4.0):
    PL = {"zero_equal": True, "unchecked": "phoneme_lr", "tau_unrel": tu}
    COMBOS[f"combo phoneme+lr{tu:g}+zero"] = dict(PL)
    COMBOS[f"combo phoneme+lr{tu:g}+zero+V2"] = {**PL, "heard": "V2"}
    COMBOS[f"combo phoneme+lr{tu:g}+zero+V2+ins tau=2"] = {**PL, "heard": "V2", "ins": "lr", "tau_ins": 2.0}
# the phone model under the recommended heard rule (C, with the calibration caveat: the check's thresholds were set
# with xlsr-53 for English and German and with Cnam for French)
from .common import LV60, XLSR  # noqa: E402
COMBOS["combo clean+V2 lv60"] = {**CLEAN, "heard": "V2", "model": {"en": LV60, "de": LV60, "fr": LV60}}
COMBOS["combo clean+V2 xlsr-fr"] = {**CLEAN, "heard": "V2", "model": {"fr": XLSR}}
COMBOS["combo phoneme+lr2+zero+V2 lv60"] = {"zero_equal": True, "unchecked": "phoneme_lr", "tau_unrel": 2.0,
                                           "heard": "V2", "model": {"en": LV60, "de": LV60, "fr": LV60}}

# THE RECOMMENDATION (lab/recommend.py explains it; lab/deck.py builds the deck from it).  One configuration per
# language; the understood rule is chosen on the D tables.
UNDERSTOOD = {"de": "free", "en": "free", "fr": "free"}
COMBOS["rec de"] = {"zero_equal": True, "unchecked": "phoneme_lr", "tau_unrel": 2.0, "heard": "V2",
                    "understood": UNDERSTOOD["de"]}
COMBOS["rec en"] = {**CLEAN, "heard": "V2", "understood": UNDERSTOOD["en"]}
COMBOS["rec fr"] = {**CLEAN, "heard": "V2", "understood": UNDERSTOOD["fr"]}
# third round: V2 judging substitutions only (deletions of the free reading all kept), because V2's loss of detection
# falls mostly on deletions
COMBOS["combo clean+V2 keep deletions"] = {**CLEAN, "heard": "V2", "keep_del": True}
COMBOS["combo phoneme+lr2+zero+V2 keep deletions"] = {"zero_equal": True, "unchecked": "phoneme_lr", "tau_unrel": 2.0,
                                                     "heard": "V2", "keep_del": True}
