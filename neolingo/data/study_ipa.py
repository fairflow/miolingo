"""Evidence, not input: where does the IPA of Miolingo's translation material differ from `env.target_ipa` (espeak)?

    venv/bin/python neolingo/data/study_ipa.py

For 200 sampled single-word dictionary entries per language (fixed seed) that carry IPA (fr: fr/words/dictionary-complete.txt,
de: de/words/..., en: en/words/..., British), both transcriptions are cut into sounds with env.phones_of (stress marks and
punctuation removed, as target_ipa does) and aligned; the report lists the differing pairs "material -> espeak" with counts.
Written to var/study/ipa_material_vs_espeak.txt (var/ is git-ignored and nothing from it is committed).  The material's IPA
is NOT used for scoring: the target sounds come from espeak, one source.  Nothing is changed on this account."""
from __future__ import annotations

import collections
import difflib
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import env                                     # noqa: E402
import materials                               # noqa: E402

VARIANT = {"fr": "fr-fr", "de": "de", "en": "en-gb"}
N = 200


def sounds(ipa: str) -> list[str]:
    return env.phones_of(env.norm_word(ipa.replace(" ", "")))


def main():
    out = []
    for lang in ("fr", "de", "en"):
        rows = [r for r in materials.sources() if r["src"] == "dict" and r["lang"] == lang and r["ipa"]
                and r["text"].isalpha() and len(r["text"]) >= 2]
        random.Random(20261013).shuffle(rows)
        rows = rows[:N]
        pairs, same, examples = collections.Counter(), 0, []
        for r in rows:
            mat = sounds(r["ipa"])
            tgt = env.target_ipa(r["text"], VARIANT[lang])
            tgt = [p for w in tgt for p in w]
            if mat == tgt:
                same += 1
                continue
            sm = difflib.SequenceMatcher(None, mat, tgt, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    continue
                pairs[("".join(mat[i1:i2]) or "-", "".join(tgt[j1:j2]) or "-")] += 1
            if len(examples) < 15:
                examples.append((r["text"], "".join(mat), "".join(tgt)))
        out.append(f"== {lang} ({VARIANT[lang]}): {len(rows)} entries sampled from {rows[0]['file']}")
        out.append(f"identical sound sequences: {same} of {len(rows)} ({100 * same // len(rows)}%)")
        out.append(f"differing places: {sum(pairs.values())}; distinct pairs {len(pairs)}")
        out.append("material -> espeak : count   ('-' = nothing)")
        out += [f"  {a} -> {b} : {n}" for (a, b), n in pairs.most_common()]
        out.append("examples (word, material, espeak):")
        out += [f"  {w}  {m}  {t}" for w, m, t in examples]
        out.append("")
    dest = HERE.parent / "var" / "study"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "ipa_material_vs_espeak.txt").write_text("\n".join(out), "utf-8")
    print("\n".join(o for o in out if o.startswith(("==", "identical", "differing")) ))


if __name__ == "__main__":
    main()
