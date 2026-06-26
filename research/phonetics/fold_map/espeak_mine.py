#!/usr/bin/env python3
"""
Mine espeak-ng phoneme inventories + allophony fold-map for the miolingo
weighted phone-distance scorer (beads miolingo-ark).

Two tracks, per the inventory-mining research:

  Track A (binary, authoritative for *which* phones occur and their IPA):
    run `espeak-ng -v LANG -q --ipa --sep=' '` over the app's own phrasebooks
    to build an empirical IPA inventory, and probe individual espeak phoneme
    names via `[[name]]` to resolve each to its realized IPA.

  Track B (source, authoritative for *allophony structure*):
    parse phsource/ phoneme-table inheritance (base -> base1 -> base2 -> lang)
    and harvest ChangePhoneme / ChangeIf* directives + same-IPA variants.

The two are merged into a Tier-1+2 fold-map (see beads decision): mechanical
variants AND context-predictable native allophony (reduction, devoicing,
positional realization) collapse to one tolerated class; genuine phoneme
substitutions do not. The fold-map is CONTEXT-FREE (a tolerated pair is
tolerated everywhere) -- a deliberate first-cut simplification; panphon
weighting in the scorer (miolingo-8f0) handles graded distance for the rest.

Cross-dialect realizations (pt-BR <-> pt-PT) are NOT folded: each language is
mined independently.

Output (overwrite, deterministic):
  espeak_fold_map.json  (beside this script)

Usage:
  python scripts/espeak_mine.py [--phsource DIR] [--espeak BIN] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]   # research/phonetics/fold_map/ -> repo root
DEFAULT_PHSRC = Path.home() / "Software/working/adaptive-text/espeak-ng/phsource"
DEFAULT_OUT = Path(__file__).resolve().parent / "espeak_fold_map.json"
MATERIALS = REPO / "language_materials"

# voice -> (phoneme-table, phrasebook text key)
LANGS = {
    "pt":    ("pt",    "portuguese"),   # Brazilian Portuguese
    "pt-pt": ("pt-pt", "portuguese"),   # European Portuguese (corpus shared w/ pt)
    "fr":    ("fr",    "french"),
    "nl":    ("nl",    "dutch"),
    "en":    ("en-rp", "english"),
}

# Allophony directives that represent *predictable native* realization (Tier 2).
# ChangePhoneme = context-conditioned substitution; ChangeIf{Unstressed,
# NotStressed,Diminished} = reduction. Stressed-only changes are excluded as
# they target the *more* careful realization, not a tolerance.
TIER2_RULES = {"ChangePhoneme", "ChangeIfUnstressed",
               "ChangeIfNotStressed", "ChangeIfDiminished"}

STRESS_MARKS = "ˈˌ"  # primary / secondary stress -- strip before folding


# --------------------------------------------------------------------------
# Track B: parse phsource
# --------------------------------------------------------------------------
def parse_master(phsrc: Path) -> dict:
    """{table: [parent|None, include_file|None]} from phsource/phonemes."""
    tables, cur = {}, None
    for line in (phsrc / "phonemes").read_text("utf-8", "replace").splitlines():
        m = re.match(r"^\s*phonemetable\s+(\S+)\s+(\S+)", line)
        if m:
            cur, parent = m.group(1), m.group(2)
            tables[cur] = ["base" if parent == "base" else parent, None]
            continue
        m = re.match(r"^\s*include\s+(\S+)", line)
        if m and cur:
            tables[cur][1] = m.group(1)
    return tables


def chain(table: str, tables: dict) -> list[str]:
    """Root-to-leaf table chain."""
    seq, seen, t = [], set(), table
    while t and t not in seen:
        seen.add(t)
        seq.append(t)
        parent = tables.get(t, [None, None])[0]
        if parent in (None, "base", t):
            if t != "base":
                seq.append("base")
            break
        t = parent
    return list(reversed(seq))


def _decode_ipa(tok: str) -> str:
    return re.sub(r"U\+([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), tok)


def parse_phonemes(path: Path) -> dict:
    """{name: {ipa, change:[(rule,target_name)], virtual}} from a ph_* file."""
    if not path.exists():
        return {}
    text = path.read_text("utf-8", "replace")
    out = {}
    for blk in re.split(r"^phoneme\s+", text, flags=re.M)[1:]:
        name = blk.split()[0]
        body = blk.partition("endphoneme")[0]
        info = {"ipa": None, "change": [], "virtual": False}
        for raw in body.splitlines():
            line = raw.split("//", 1)[0].strip()
            if not line:
                continue
            if line.startswith("virtual"):
                info["virtual"] = True
            m = re.match(r"^ipa\s+(\S+)", line)
            if m:
                info["ipa"] = _decode_ipa(m.group(1))
            m = re.search(r"(ChangePhoneme|ChangeIf\w*)\(([^)]*)\)", line)
            if m and m.group(2) not in ("NULL", ""):
                info["change"].append((m.group(1), m.group(2).split("/")[-1]))
        out[name] = info
    return out


def resolve_table(table: str, tables: dict, phsrc: Path) -> dict:
    """Merge inheritance chain; child overrides parent by phoneme name."""
    merged = {}
    for t in chain(table, tables):
        inc = tables.get(t, [None, None])[1]
        if inc:
            merged.update(parse_phonemes(phsrc / inc))
    return merged


# --------------------------------------------------------------------------
# Track A: binary probing
# --------------------------------------------------------------------------
def _strip_stress(s: str) -> str:
    return "".join(c for c in s if c not in STRESS_MARKS)


def espeak_ipa(espeak: str, voice: str, text: str) -> str:
    """Raw `--ipa --sep=' '` output for text (or [[phonemes]])."""
    r = subprocess.run([espeak, "-v", voice, "-q", "--ipa", "--sep= ", text],
                       capture_output=True, text=True)
    return r.stdout.strip()


def probe_name(espeak: str, voice: str, name: str, cache: dict) -> str:
    """Realized IPA of a single espeak phoneme name, stress-stripped."""
    if name in cache:
        return cache[name]
    out = _strip_stress(espeak_ipa(espeak, voice, f"[[{name}]]")).strip()
    # a single phoneme should yield a single segment; keep as-is otherwise
    cache[name] = out
    return out


def corpus_inventory(espeak: str, voice: str, key: str) -> dict:
    """Empirical {ipa_segment: count} over the language's phrasebook."""
    counts: dict[str, int] = {}
    pb = MATERIALS / voice.split("-")[0] / "phrasebook_complete.json"
    if not pb.exists():
        return counts
    phrases = json.loads(pb.read_text("utf-8")).get("phrases", [])
    for entry in phrases:
        text = entry.get(key) or entry.get("portuguese") or ""
        if not text:
            continue
        ipa = espeak_ipa(espeak, voice, text)
        for seg in ipa.split():
            seg = _strip_stress(seg)
            if seg:
                counts[seg] = counts.get(seg, 0) + 1
    return counts


# --------------------------------------------------------------------------
# Merge into fold-map
# --------------------------------------------------------------------------
def mine_language(voice, table, key, tables, phsrc, espeak):
    merged = resolve_table(table, tables, phsrc)
    inv_counts = corpus_inventory(espeak, voice, key)
    inventory = set(inv_counts)

    cache: dict[str, str] = {}
    # Pairwise tolerated substitutions, keyed by the unordered IPA pair so a
    # pair attested by several rules is merged. Deliberately NOT transitive:
    # X->schwa and Y->schwa tolerate X~schwa and Y~schwa but never X~Y, which
    # would otherwise collapse whole vowel systems and erase real minimal pairs.
    pairs: dict[tuple, set] = {}
    elisions = []  # target is deletion -- recorded for the scorer, not folded

    for name, info in merged.items():
        if info["virtual"]:
            continue
        from_ipa = probe_name(espeak, voice, name, cache)
        for rule, tgt in info["change"]:
            if rule not in TIER2_RULES:
                continue
            to_ipa = probe_name(espeak, voice, tgt, cache)
            if not to_ipa:                      # deletion / silence
                if from_ipa:
                    elisions.append({"from": from_ipa, "name": name, "rule": rule})
                continue
            if not from_ipa or from_ipa == to_ipa:
                continue
            # Tier 2 tolerance only if the pair touches phones the language emits
            if from_ipa in inventory or to_ipa in inventory:
                key2 = tuple(sorted((from_ipa, to_ipa)))
                pairs.setdefault(key2, set()).add(f"{name}--{rule}-->{tgt}")

    # Tier 1: espeak phoneme names realizing to the *same* IPA already collapse
    # in the binary output -- nothing to fold. Surfaced for audit only.
    same_ipa: dict[str, list[str]] = {}
    for name in merged:
        if merged[name]["virtual"]:
            continue
        ipa = cache.get(name) or probe_name(espeak, voice, name, cache)
        if ipa and ipa in inventory:
            same_ipa.setdefault(ipa, []).append(name)
    tier1_audit = {k: sorted(v) for k, v in same_ipa.items() if len(v) > 1}

    tolerated = [{"pair": list(p), "sources": sorted(src)}
                 for p, src in sorted(pairs.items())]

    return {
        "table": table,
        "chain": chain(table, tables),
        "inventory": sorted(inventory),
        "inventory_counts": dict(sorted(inv_counts.items(),
                                        key=lambda kv: -kv[1])),
        "tolerated_pairs": tolerated,
        "elision_candidates": elisions,
        "tier1_same_ipa_audit": dict(sorted(tier1_audit.items())),
    }


def espeak_version(espeak: str) -> str:
    r = subprocess.run([espeak, "--version"], capture_output=True, text=True)
    return r.stdout.strip().split("\n")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phsource", type=Path, default=DEFAULT_PHSRC)
    ap.add_argument("--espeak", default="espeak-ng")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.phsource.exists():
        sys.exit(f"phsource not found: {args.phsource}")

    tables = parse_master(args.phsource)
    out = {
        "_meta": {
            "generated_by": "scripts/espeak_mine.py",
            "espeak_version": espeak_version(args.espeak),
            "phsource": str(args.phsource),
            "policy": "tier1+2 (mechanical variants + context-predictable "
                      "native allophony; cross-dialect NOT folded)",
            "note": "fold-map is context-free; canonical[seg] -> class rep. "
                    "Stress marks stripped. elision_candidates are deletions, "
                    "recorded for the scorer to optionally discount, not folded.",
        }
    }
    for voice, (table, key) in LANGS.items():
        out[voice] = mine_language(voice, table, key, tables,
                                   args.phsource, args.espeak)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                        "utf-8")
    print(f"wrote {args.out}")
    for voice in LANGS:
        r = out[voice]
        print(f"  {voice:6} inv={len(r['inventory']):3}  "
              f"tolerated_pairs={len(r['tolerated_pairs']):2}  "
              f"elisions={len(r['elision_candidates']):2}")


if __name__ == "__main__":
    main()
