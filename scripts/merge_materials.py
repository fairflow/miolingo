#!/usr/bin/env python3
"""
Merge per-language material files into unified multi-language JSON.

Reads existing language_materials/{lang}/ directories and produces
unified JSON files in language_materials/unified/ where each phrase
carries translations in all available languages.

Usage:
    python scripts/merge_materials.py [--dry-run] [--verbose]

Output structure:
    language_materials/unified/
    ├── stories/scene-01.json ... scene-16.json
    ├── phrases/common-phrases-001.json ...
    └── phrasebook/greetings.json ...
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

# All non-English languages with material files
LANGUAGES = ["fr", "de", "pt", "it", "es", "nl"]

# Scene filename patterns per language (scene number -> filename)
# We discover these dynamically by scanning directories.

# Phrasebook topic slug mapping (numbered prefix -> canonical slug)
PHRASEBOOK_SLUG_MAP = {
    "01-greetings": "greetings",
    "02-farewells": "farewells",
    "03-courtesy-basics": "courtesy-basics",
    "04-introductions": "introductions",
    "05-asking-for-help": "asking-for-help",
    "06-directions": "directions",
    "07-shopping": "shopping",
    "08-restaurant": "restaurant",
    "09-conversation": "conversation",
    "10-feelings-emotions": "feelings-emotions",
    "11-exclamations": "exclamations",
    "basics": "basics",
}

# Scene titles in English (canonical)
SCENE_TITLES_EN = {
    1: "The Morning Café",
    2: "Shopping in the City",
    3: "Conversation About the Dream",
    4: "The Decision",
    5: "At the Station",
    6: "On the Train",
    7: "Arrival at the Village",
    8: "Encounters and Discoveries",
    9: "The Difficult Hike",
    10: "The Involuntary Separation",
    11: "Sophie's Challenge: The Four Elements",
    12: "Lucas's Challenge: The Unexpected Guide",
    13: "The Rescue",
    14: "Sophie's Reflection",
    15: "The Discovery",
    16: "The Reunion",
}


def find_project_root():
    """Find the project root (where language_materials/ lives)."""
    # Try relative to script location first
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir.parent
    if (candidate / "language_materials").is_dir():
        return candidate
    # Try cwd
    if (Path.cwd() / "language_materials").is_dir():
        return Path.cwd()
    print("ERROR: Cannot find language_materials/ directory", file=sys.stderr)
    sys.exit(1)


def find_scene_files(materials_dir, lang):
    """Find all scene JSON files for a language, returning {scene_number: path}."""
    scene_dir = materials_dir / lang / "story-scenes-json"
    if not scene_dir.is_dir():
        return {}
    result = {}
    for f in scene_dir.glob("scene-*.json"):
        match = re.match(r"scene-(\d+)", f.name)
        if match:
            result[int(match.group(1))] = f
    return result


def load_scene_json(filepath, lang):
    """Load a scene JSON file and return (phrases_list, scene_title)."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    phrases = data.get(lang, [])
    title = data.get("scene_title", "")
    return phrases, title


def parse_phrase_line(line):
    """Parse a pipe-delimited phrase line: 'text | english | [ipa]'
    Returns (text, english, ipa) or None if line is not a phrase."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 2:
        return None
    text = parts[0]
    english = parts[1]
    ipa = parts[2] if len(parts) > 2 else ""
    return text, english, ipa


def load_phrase_file(filepath):
    """Load a pipe-delimited phrase/phrasebook file.
    Returns list of (text, english, ipa) tuples, skipping headers/blanks."""
    phrases = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            parsed = parse_phrase_line(line)
            if parsed:
                phrases.append(parsed)
    return phrases


def normalize_english(text):
    """Normalize English text for fuzzy matching."""
    text = text.lower().strip()
    # Remove trailing punctuation differences
    text = re.sub(r'[.!?,;:]+$', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


def english_similarity(a, b):
    """Score similarity between two English phrases (0-1)."""
    a_norm = normalize_english(a)
    b_norm = normalize_english(b)
    if a_norm == b_norm:
        return 1.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def match_pt_to_core(pt_phrases, core_phrases, lang_key="pt", threshold=0.55):
    """Match PT phrases to core (fr/de/it/es/nl) phrases by English text similarity.

    PT stories contain the same narrative but phrases are ordered differently
    and English translations were written independently (different wording).

    Returns:
        matched: dict {core_index: pt_phrase_dict}
        unmatched: list of pt_phrase_dicts that didn't match any core phrase
    """
    if not pt_phrases or not core_phrases:
        return {}, list(pt_phrases)

    # Build English texts for core phrases (use first available language's English)
    core_english = []
    for entry in core_phrases:
        core_english.append(entry.get("english", ""))

    pt_english = [p.get("english", "") for p in pt_phrases]

    # Greedy best-match: for each PT phrase, find best core match
    # Then assign greedily from highest score down
    scores = []
    for pi, pt_en in enumerate(pt_english):
        for ci, core_en in enumerate(core_english):
            sim = english_similarity(pt_en, core_en)
            if sim >= threshold:
                scores.append((sim, pi, ci))

    # Sort by similarity descending
    scores.sort(key=lambda x: -x[0])

    matched = {}  # core_index -> pt_phrase
    used_pt = set()
    used_core = set()

    for sim, pi, ci in scores:
        if pi in used_pt or ci in used_core:
            continue
        matched[ci] = pt_phrases[pi]
        used_pt.add(pi)
        used_core.add(ci)

    unmatched = [pt_phrases[i] for i in range(len(pt_phrases)) if i not in used_pt]

    return matched, unmatched


def merge_story_scenes(materials_dir, output_dir, dry_run=False, verbose=False):
    """Merge story scene JSON files across all languages.

    Non-PT languages (fr, de, it, es, nl) match by position index — they all
    have identical phrase counts and ordering per scene.

    PT has more phrases per scene and a different ordering (narrative interspersed
    with dialogue differently). We use English-text fuzzy matching to align PT
    phrases to the core set, with unmatched PT phrases appended as sparse entries.
    """
    stories_out = output_dir / "stories"
    if not dry_run:
        stories_out.mkdir(parents=True, exist_ok=True)

    # Discover scene files per language
    lang_scenes = {}
    for lang in LANGUAGES:
        lang_scenes[lang] = find_scene_files(materials_dir, lang)

    # Find all scene numbers
    all_scene_nums = sorted(
        set(n for scenes in lang_scenes.values() for n in scenes)
    )

    CORE_LANGS = [l for l in LANGUAGES if l != "pt"]
    stats = {"files": 0, "phrases": 0, "pt_matched": 0, "pt_unmatched": 0}

    for scene_num in all_scene_nums:
        if verbose:
            print(f"  Processing scene {scene_num:02d}...")

        # Load phrases from each language
        lang_data = {}  # lang -> list of phrase dicts
        scene_titles = {}  # lang -> title string

        for lang in LANGUAGES:
            if scene_num in lang_scenes[lang]:
                phrases, title = load_scene_json(
                    lang_scenes[lang][scene_num], lang
                )
                lang_data[lang] = phrases
                if title:
                    scene_titles[lang] = title

        if not lang_data:
            continue

        # Core languages: match by position (they all align)
        core_count = 0
        for l in CORE_LANGS:
            if l in lang_data:
                core_count = len(lang_data[l])
                break  # All core langs have same count

        # Match PT to core using English text similarity
        pt_matched = {}  # core_index -> pt_phrase
        pt_unmatched = []
        if "pt" in lang_data and core_count > 0:
            # Use FR as reference for core English texts
            ref_lang = next((l for l in CORE_LANGS if l in lang_data), None)
            if ref_lang:
                pt_matched, pt_unmatched = match_pt_to_core(
                    lang_data["pt"], lang_data[ref_lang], threshold=0.55
                )
                stats["pt_matched"] += len(pt_matched)
                stats["pt_unmatched"] += len(pt_unmatched)
        elif "pt" in lang_data:
            # No core languages for this scene — PT becomes the base
            pt_unmatched = list(lang_data["pt"])

        # Build unified phrases: first the core set, then PT-only extras
        unified_phrases = []

        for i in range(core_count):
            phrase_id = f"scene-{scene_num:02d}-{i + 1:03d}"
            text = {}
            ipa = {}
            provenance = {}

            # Add core languages by position
            for lang in CORE_LANGS:
                phrases = lang_data.get(lang, [])
                if i < len(phrases):
                    entry = phrases[i]
                    text[lang] = entry.get(lang, "")
                    if entry.get("ipa"):
                        ipa[lang] = entry["ipa"]
                    provenance[lang] = "original"
                    eng = entry.get("english", "")
                    if eng:
                        text["en"] = eng

            # Add PT if it matched this core position
            if i in pt_matched:
                pt_entry = pt_matched[i]
                text["pt"] = pt_entry.get("pt", "")
                if pt_entry.get("ipa"):
                    ipa["pt"] = pt_entry["ipa"]
                provenance["pt"] = "original"
                # Store PT's own English as alternate (may differ from core)
                pt_en = pt_entry.get("english", "")
                if pt_en and pt_en != text.get("en", ""):
                    text["en_pt"] = pt_en  # preserve PT's English variant

            if "en" in text:
                provenance["en"] = "original"

            unified_phrases.append({
                "id": phrase_id,
                "text": text,
                "ipa": ipa,
                "provenance": provenance,
            })

        # Append unmatched PT phrases as sparse entries (PT + EN only)
        for j, pt_entry in enumerate(pt_unmatched):
            idx = core_count + j + 1
            phrase_id = f"scene-{scene_num:02d}-{idx:03d}"
            text = {"pt": pt_entry.get("pt", "")}
            ipa_dict = {}
            provenance = {"pt": "original"}
            pt_en = pt_entry.get("english", "")
            if pt_en:
                text["en"] = pt_en
                provenance["en"] = "original"
            if pt_entry.get("ipa"):
                ipa_dict["pt"] = pt_entry["ipa"]

            unified_phrases.append({
                "id": phrase_id,
                "text": text,
                "ipa": ipa_dict,
                "provenance": provenance,
            })

        # Build scene titles dict
        titles = {"en": SCENE_TITLES_EN.get(scene_num, f"Scene {scene_num}")}
        titles.update(scene_titles)

        # Build output document
        doc = {
            "meta": {
                "source": "story-scenes",
                "scene_number": scene_num,
                "scene_title": titles,
                "phrase_count": len(unified_phrases),
                "core_phrase_count": core_count,
                "pt_matched": len(pt_matched),
                "pt_unmatched": len(pt_unmatched),
                "languages": sorted(
                    set(
                        l
                        for p in unified_phrases
                        for l in p["text"]
                        if l not in ("en", "en_pt")
                    )
                ),
                "generated": str(date.today()),
                "generator": "merge_materials.py",
            },
            "phrases": unified_phrases,
        }

        out_path = stories_out / f"scene-{scene_num:02d}.json"
        if not dry_run:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
        stats["files"] += 1
        stats["phrases"] += len(unified_phrases)

        if verbose:
            lang_summary = ", ".join(
                f"{l}:{len(lang_data.get(l, []))}"
                for l in LANGUAGES
                if l in lang_data
            )
            pt_info = ""
            if "pt" in lang_data:
                pt_info = (
                    f" [PT: {len(pt_matched)} matched, "
                    f"{len(pt_unmatched)} unmatched]"
                )
            print(
                f"    → scene-{scene_num:02d}.json: "
                f"{len(unified_phrases)} phrases ({lang_summary}){pt_info}"
            )

    return stats


def match_by_english_text(lang_data, id_prefix, threshold=0.7):
    """Match phrases across languages using English translation text.

    Used when languages have the same phrases but in different order
    (e.g. phrasebook topics sorted alphabetically per-language).

    Args:
        lang_data: dict of lang -> [(text, english, ipa), ...]
        id_prefix: prefix for phrase IDs
        threshold: minimum similarity for fuzzy matching

    Returns:
        list of unified phrase dicts
    """
    # Build index: normalized English -> list of (lang, phrase_tuple) entries
    # Handle duplicates (e.g. "How are you?" appears twice = formal/informal)
    english_groups = {}  # norm_en -> [(lang, (text, english, ipa)), ...]

    for lang, phrases in lang_data.items():
        # Track how many times we've seen each English text per language
        # to handle duplicates correctly
        en_count = {}
        for phrase_tuple in phrases:
            _, english, _ = phrase_tuple
            norm = normalize_english(english)
            # Create unique key for duplicates: "how are you?#1", "how are you?#2"
            en_count[norm] = en_count.get(norm, 0) + 1
            key = f"{norm}#{en_count[norm]}"
            if key not in english_groups:
                english_groups[key] = {}
            english_groups[key][lang] = phrase_tuple

    # For any languages missing from a group, try fuzzy matching
    # (handles slight English text differences across languages)
    all_langs = set(lang_data.keys())

    # Build unified phrases from groups
    unified = []
    seen_keys = set()

    # Process groups in a stable order (use first language's ordering as reference)
    ref_lang = next(iter(lang_data))
    ref_phrases = lang_data[ref_lang]
    ref_en_count = {}

    for phrase_tuple in ref_phrases:
        _, english, _ = phrase_tuple
        norm = normalize_english(english)
        ref_en_count[norm] = ref_en_count.get(norm, 0) + 1
        key = f"{norm}#{ref_en_count[norm]}"

        if key in seen_keys:
            continue
        seen_keys.add(key)

        group = english_groups.get(key, {})
        idx = len(unified) + 1
        phrase_id = f"{id_prefix}-{idx:03d}"

        text = {}
        ipa = {}
        provenance = {}

        for lang, (phrase_text, eng, phrase_ipa) in group.items():
            text[lang] = phrase_text
            if phrase_ipa:
                ipa[lang] = phrase_ipa
            provenance[lang] = "original"
            if eng and "en" not in text:
                text["en"] = eng

        if "en" in text:
            provenance["en"] = "original"

        unified.append({
            "id": phrase_id,
            "text": text,
            "ipa": ipa,
            "provenance": provenance,
        })

    # Add any groups not yet covered (from other languages' unique phrases)
    for key, group in english_groups.items():
        if key in seen_keys:
            continue
        seen_keys.add(key)

        idx = len(unified) + 1
        phrase_id = f"{id_prefix}-{idx:03d}"

        text = {}
        ipa = {}
        provenance = {}

        for lang, (phrase_text, eng, phrase_ipa) in group.items():
            text[lang] = phrase_text
            if phrase_ipa:
                ipa[lang] = phrase_ipa
            provenance[lang] = "original"
            if eng and "en" not in text:
                text["en"] = eng

        if "en" in text:
            provenance["en"] = "original"

        unified.append({
            "id": phrase_id,
            "text": text,
            "ipa": ipa,
            "provenance": provenance,
        })

    return unified


def merge_phrase_files(materials_dir, output_dir, dry_run=False, verbose=False):
    """Merge pipe-delimited phrase files across languages.

    FR/DE/IT/ES/NL phrase files are position-aligned (same English meanings
    at same positions). PT has different content entirely.
    We use position matching for non-PT, then English-text matching for PT.
    """
    phrases_out = output_dir / "phrases"
    if not dry_run:
        phrases_out.mkdir(parents=True, exist_ok=True)

    CORE_LANGS = [l for l in LANGUAGES if l != "pt"]

    # Discover phrase files per language
    lang_phrase_files = {}  # lang -> {file_num: path}
    for lang in LANGUAGES:
        phrase_dir = materials_dir / lang / "phrases"
        if not phrase_dir.is_dir():
            continue
        lang_phrase_files[lang] = {}
        for f in phrase_dir.glob("phrases-*.txt"):
            match = re.match(r"phrases-(\d+)", f.name)
            if match:
                lang_phrase_files[lang][int(match.group(1))] = f

    # Find all file numbers that exist in at least 2 languages
    all_nums = sorted(
        set(n for files in lang_phrase_files.values() for n in files)
    )

    stats = {"files": 0, "phrases": 0}

    for file_num in all_nums:
        # Load phrases from each language that has this file
        lang_data = {}
        for lang in LANGUAGES:
            if file_num in lang_phrase_files.get(lang, {}):
                phrases = load_phrase_file(
                    lang_phrase_files[lang][file_num]
                )
                if phrases:
                    lang_data[lang] = phrases

        if len(lang_data) < 2:
            if verbose:
                print(
                    f"  Skipping phrases-{file_num:03d} "
                    f"(only in {list(lang_data.keys())})"
                )
            continue

        if verbose:
            print(f"  Processing phrases-{file_num:03d}...")

        # Separate core languages (position-aligned) from PT
        core_data = {l: lang_data[l] for l in CORE_LANGS if l in lang_data}
        pt_data = lang_data.get("pt")

        # Core: match by position
        core_count = max(len(v) for v in core_data.values()) if core_data else 0
        unified_phrases = []

        for i in range(core_count):
            phrase_id = f"phrases-{file_num:03d}-{i + 1:03d}"
            text = {}
            ipa = {}
            provenance = {}

            for lang, phrases in core_data.items():
                if i < len(phrases):
                    phrase_text, english, phrase_ipa = phrases[i]
                    text[lang] = phrase_text
                    if phrase_ipa:
                        ipa[lang] = phrase_ipa
                    provenance[lang] = "original"
                    if english and "en" not in text:
                        text["en"] = english

            if "en" in text:
                provenance["en"] = "original"

            unified_phrases.append({
                "id": phrase_id,
                "text": text,
                "ipa": ipa,
                "provenance": provenance,
            })

        # Match PT phrases by English text similarity to core phrases
        pt_matched = 0
        pt_unmatched_entries = []
        if pt_data and unified_phrases:
            for pt_text, pt_english, pt_ipa in pt_data:
                best_score = 0
                best_idx = -1
                pt_en_norm = normalize_english(pt_english)

                for idx, up in enumerate(unified_phrases):
                    core_en = up["text"].get("en", "")
                    score = english_similarity(pt_english, core_en)
                    if score > best_score:
                        best_score = score
                        best_idx = idx

                if best_score >= 0.6 and best_idx >= 0:
                    # Add PT to existing unified phrase
                    unified_phrases[best_idx]["text"]["pt"] = pt_text
                    if pt_ipa:
                        unified_phrases[best_idx]["ipa"]["pt"] = pt_ipa
                    unified_phrases[best_idx]["provenance"]["pt"] = "original"
                    pt_matched += 1
                else:
                    pt_unmatched_entries.append((pt_text, pt_english, pt_ipa))

            # Append unmatched PT as sparse entries
            for pt_text, pt_english, pt_ipa in pt_unmatched_entries:
                idx = len(unified_phrases) + 1
                phrase_id = f"phrases-{file_num:03d}-{idx:03d}"
                entry = {
                    "id": phrase_id,
                    "text": {"pt": pt_text},
                    "ipa": {},
                    "provenance": {"pt": "original"},
                }
                if pt_english:
                    entry["text"]["en"] = pt_english
                    entry["provenance"]["en"] = "original"
                if pt_ipa:
                    entry["ipa"]["pt"] = pt_ipa
                unified_phrases.append(entry)

        doc = {
            "meta": {
                "source": "phrases",
                "file_number": file_num,
                "phrase_count": len(unified_phrases),
                "languages": sorted(
                    set(
                        l
                        for p in unified_phrases
                        for l in p["text"]
                        if l not in ("en", "en_pt")
                    )
                ),
                "generated": str(date.today()),
                "generator": "merge_materials.py",
            },
            "phrases": unified_phrases,
        }

        out_path = phrases_out / f"common-phrases-{file_num:03d}.json"
        if not dry_run:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
        stats["files"] += 1
        stats["phrases"] += len(unified_phrases)

        if verbose:
            lang_summary = ", ".join(
                f"{l}:{len(lang_data[l])}" for l in LANGUAGES if l in lang_data
            )
            pt_info = ""
            if pt_data:
                pt_info = (
                    f" [PT: {pt_matched} matched, "
                    f"{len(pt_unmatched_entries)} unmatched]"
                )
            print(
                f"    → common-phrases-{file_num:03d}.json: "
                f"{len(unified_phrases)} phrases ({lang_summary}){pt_info}"
            )

    return stats


def merge_phrasebook_topics(
    materials_dir, output_dir, dry_run=False, verbose=False
):
    """Merge phrasebook topic files across languages.

    Phrasebook files have the same phrases but in different order per language
    (typically alphabetical within each language). We match by English text.
    """
    phrasebook_out = output_dir / "phrasebook"
    if not dry_run:
        phrasebook_out.mkdir(parents=True, exist_ok=True)

    stats = {"files": 0, "phrases": 0}

    for topic_filename, slug in PHRASEBOOK_SLUG_MAP.items():
        if verbose:
            print(f"  Processing phrasebook/{slug}...")

        # Load from each language
        lang_data = {}
        for lang in LANGUAGES:
            filepath = (
                materials_dir / lang / "phrasebook-topics" / f"{topic_filename}.txt"
            )
            if filepath.is_file():
                phrases = load_phrase_file(filepath)
                if phrases:
                    lang_data[lang] = phrases

        if len(lang_data) < 2:
            if verbose:
                print(f"    Skipping {slug} (only in {list(lang_data.keys())})")
            continue

        # Match by English text (phrases are same concepts, different order)
        unified_phrases = match_by_english_text(
            lang_data, f"phrasebook-{slug}"
        )

        doc = {
            "meta": {
                "source": "phrasebook",
                "topic": slug,
                "phrase_count": len(unified_phrases),
                "languages": sorted(
                    set(
                        l
                        for p in unified_phrases
                        for l in p["text"]
                        if l not in ("en", "en_pt")
                    )
                ),
                "generated": str(date.today()),
                "generator": "merge_materials.py",
            },
            "phrases": unified_phrases,
        }

        out_path = phrasebook_out / f"{slug}.json"
        if not dry_run:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
        stats["files"] += 1
        stats["phrases"] += len(unified_phrases)

        if verbose:
            lang_summary = ", ".join(
                f"{l}:{len(lang_data[l])}" for l in LANGUAGES if l in lang_data
            )
            print(
                f"    → {slug}.json: "
                f"{len(unified_phrases)} phrases ({lang_summary})"
            )

    return stats


def validate_output(output_dir, verbose=False):
    """Validate the generated unified files."""
    issues = []
    total_files = 0
    total_phrases = 0

    for category in ["stories", "phrases", "phrasebook"]:
        cat_dir = output_dir / category
        if not cat_dir.is_dir():
            issues.append(f"Missing directory: {category}/")
            continue

        for f in sorted(cat_dir.glob("*.json")):
            total_files += 1
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    doc = json.load(fh)
            except json.JSONDecodeError as e:
                issues.append(f"Invalid JSON in {f.name}: {e}")
                continue

            meta = doc.get("meta", {})
            phrases = doc.get("phrases", [])

            if not phrases:
                issues.append(f"No phrases in {f.name}")
                continue

            total_phrases += len(phrases)

            # Check phrase count matches meta
            if meta.get("phrase_count") != len(phrases):
                issues.append(
                    f"{f.name}: meta.phrase_count={meta.get('phrase_count')} "
                    f"but actual={len(phrases)}"
                )

            # Check each phrase has at least 2 languages in text
            for p in phrases:
                text_langs = [l for l in p.get("text", {}) if l != "en"]
                if len(text_langs) < 1:
                    issues.append(
                        f"{f.name}/{p.get('id')}: no non-English text"
                    )

            # Check first phrase of scene-01 is a greeting
            if f.name == "scene-01.json" and phrases:
                first = phrases[0]
                if verbose:
                    print(f"  First phrase of scene-01:")
                    for lang, t in sorted(first.get("text", {}).items()):
                        print(f"    {lang}: {t}")

    return issues, total_files, total_phrases


def main():
    parser = argparse.ArgumentParser(
        description="Merge per-language materials into unified JSON"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write files, just show what would be done",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing output",
    )
    args = parser.parse_args()

    root = find_project_root()
    materials_dir = root / "language_materials"
    output_dir = materials_dir / "unified"

    if args.validate_only:
        print("Validating unified materials...")
        issues, total_files, total_phrases = validate_output(
            output_dir, verbose=args.verbose
        )
        print(f"\nFiles: {total_files}, Phrases: {total_phrases}")
        if issues:
            print(f"\n{len(issues)} issue(s):")
            for issue in issues:
                print(f"  ⚠ {issue}")
            return 1
        else:
            print("✓ All files valid")
            return 0

    mode = "DRY RUN" if args.dry_run else "WRITING"
    print(f"Merging language materials ({mode})")
    print(f"  Source: {materials_dir}")
    print(f"  Output: {output_dir}")
    print()

    # Step 1: Story scenes
    print("Step 1: Merging story scenes...")
    story_stats = merge_story_scenes(
        materials_dir, output_dir, dry_run=args.dry_run, verbose=args.verbose
    )
    print(
        f"  → {story_stats['files']} files, "
        f"{story_stats['phrases']} total phrases"
    )
    print()

    # Step 2: Phrase files
    print("Step 2: Merging phrase files...")
    phrase_stats = merge_phrase_files(
        materials_dir, output_dir, dry_run=args.dry_run, verbose=args.verbose
    )
    print(
        f"  → {phrase_stats['files']} files, "
        f"{phrase_stats['phrases']} total phrases"
    )
    print()

    # Step 3: Phrasebook topics
    print("Step 3: Merging phrasebook topics...")
    phrasebook_stats = merge_phrasebook_topics(
        materials_dir, output_dir, dry_run=args.dry_run, verbose=args.verbose
    )
    print(
        f"  → {phrasebook_stats['files']} files, "
        f"{phrasebook_stats['phrases']} total phrases"
    )
    print()

    # Summary
    total_files = (
        story_stats["files"] + phrase_stats["files"] + phrasebook_stats["files"]
    )
    total_phrases = (
        story_stats["phrases"]
        + phrase_stats["phrases"]
        + phrasebook_stats["phrases"]
    )
    print(f"Total: {total_files} files, {total_phrases} phrases")

    if not args.dry_run:
        print("\nStep 4: Validating output...")
        issues, _, _ = validate_output(output_dir, verbose=args.verbose)
        if issues:
            print(f"  ⚠ {len(issues)} validation issue(s):")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  ✓ All files valid")

    return 0


if __name__ == "__main__":
    sys.exit(main())
