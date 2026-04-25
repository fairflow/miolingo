"""
IPA symbol reference tables for learner-facing tooltips.

Maps target languages to the handful of symbols a beginner will encounter
most often. Used by Quick Practice "What's this?" tooltips (see
docs/dev-docs/IPA_LEARNING_DESIGN.md § 4.2).

Each entry is a dict with:
    - 'symbol': IPA symbol or cluster
    - 'sound': plain-English description
    - 'example': word demonstrating the symbol (target language)
    - 'hint': optional cross-linguistic comparison (English, Spanish, etc.)
"""

# Sourced from docs/app-docs/IPA_PRIMER.md
IPA_QUICK_REFERENCE = {
    'pt': {
        'name': 'Brazilian Portuguese',
        'symbols': [
            {'symbol': 'ɐ̃ ẽ ĩ õ ũ', 'sound': 'nasal vowels', 'example': 'bem [bẽj̃], bom [bõ]', 'hint': 'like French nasal vowels'},
            {'symbol': 'ɛ vs e', 'sound': 'open vs closed e', 'example': 'pé [pɛ] vs pês [pes]', 'hint': '"bed" vs "bay"'},
            {'symbol': 'ɔ vs o', 'sound': 'open vs closed o', 'example': 'pó [pɔ] vs pôs [pos]', 'hint': '"thought" vs "note"'},
            {'symbol': 'ʒ ʃ', 'sound': 'zh, sh', 'example': 'já [ʒa], chá [ʃa]', 'hint': '"measure", "shoe"'},
            {'symbol': 'dʒ tʃ', 'sound': 'soft d/t before i', 'example': 'dia [ˈdʒiɐ], tia [ˈtʃiɐ]', 'hint': '"jeans", "cheap"'},
            {'symbol': 'ɲ ʎ', 'sound': 'soft nh / lh', 'example': 'manhã [maˈɲɐ̃], olho [ˈoʎu]', 'hint': 'Spanish ñ, Italian gl'},
            {'symbol': 'ʁ vs ɾ', 'sound': 'strong R / tapped R', 'example': 'carro [ˈkaʁu] vs caro [ˈkaɾu]', 'hint': 'French r vs Spanish r'},
        ]
    },
    'fr': {
        'name': 'French',
        'symbols': [
            {'symbol': 'ɑ̃ ɛ̃ ɔ̃ œ̃', 'sound': 'nasal vowels', 'example': 'blanc, vin, bon, un', 'hint': 'different mouth shapes'},
            {'symbol': 'ʁ', 'sound': 'French r (uvular)', 'example': 'rouge [ʁuʒ]', 'hint': 'gargled, not rolled'},
            {'symbol': 'y', 'sound': 'tight "ee" with rounded lips', 'example': 'tu [ty]', 'hint': 'say "ee" then purse lips'},
            {'symbol': 'ø œ', 'sound': 'rounded front vowels', 'example': 'peu [pø], peur [pœʁ]', 'hint': '"uh" with rounded lips'},
            {'symbol': 'ə', 'sound': 'schwa', 'example': 'le [lə]', 'hint': 'the "e" in English "the"'},
            {'symbol': 'ɲ', 'sound': 'palatal gn', 'example': 'gagner [gaˈɲe]', 'hint': '"ny" in canyon'},
        ]
    },
    'en': {
        'name': 'English',
        'symbols': [
            {'symbol': 'ə', 'sound': 'schwa', 'example': 'about [əˈbaʊt]', 'hint': 'most common English vowel'},
            {'symbol': 'θ ð', 'sound': '"th" unvoiced / voiced', 'example': 'think [θɪŋk], this [ðɪs]', 'hint': 'different letters in IPA'},
            {'symbol': 'ʃ ʒ', 'sound': 'sh / zh', 'example': 'she [ʃiː], measure [ˈmɛʒə]', 'hint': ''},
            {'symbol': 'tʃ dʒ', 'sound': 'ch / j', 'example': 'cheap [tʃiːp], job [dʒɒb]', 'hint': ''},
            {'symbol': 'ɪ ʊ', 'sound': 'lax i / u', 'example': 'kit [kɪt], foot [fʊt]', 'hint': 'shorter than ee / oo'},
        ]
    },
    'it': {
        'name': 'Italian',
        'symbols': [
            {'symbol': 'ʎ', 'sound': 'palatal l (gli)', 'example': 'famiglia [faˈmiʎʎa]', 'hint': 'like Spanish ll'},
            {'symbol': 'ɲ', 'sound': 'palatal n (gn)', 'example': 'sogno [ˈsoɲɲo]', 'hint': 'Spanish ñ'},
            {'symbol': 'ʦ ʣ', 'sound': 'ts / dz', 'example': 'grazie [ˈgraʦie]', 'hint': ''},
            {'symbol': 'ʃ', 'sound': 'sh (sc before i/e)', 'example': 'scienza [ʃˈʃɛntsa]', 'hint': ''},
        ]
    },
    'es': {
        'name': 'Spanish',
        'symbols': [
            {'symbol': 'ɲ', 'sound': 'ñ', 'example': 'señor [seˈɲor]', 'hint': 'like Italian gn'},
            {'symbol': 'ʎ', 'sound': 'll (Castilian)', 'example': 'calle [ˈkaʎe]', 'hint': 'like Italian gli'},
            {'symbol': 'x', 'sound': 'j (jota)', 'example': 'jardín [xarˈðin]', 'hint': 'like Scottish "loch"'},
            {'symbol': 'θ', 'sound': 'c/z (Castilian)', 'example': 'cinco [ˈθinko]', 'hint': 'English "think"'},
            {'symbol': 'β ð ɣ', 'sound': 'soft b, d, g', 'example': 'haber [aˈβer]', 'hint': 'between vowels'},
        ]
    },
    'de': {
        'name': 'German',
        'symbols': [
            {'symbol': 'x', 'sound': 'ch (after a/o/u)', 'example': 'Buch [buːx]', 'hint': 'like Scottish "loch"'},
            {'symbol': 'ç', 'sound': 'ch (after i/e)', 'example': 'ich [ɪç]', 'hint': 'softer than x'},
            {'symbol': 'ʁ', 'sound': 'r (uvular)', 'example': 'rot [ʁoːt]', 'hint': 'like French r'},
            {'symbol': 'ʃ', 'sound': 'sch', 'example': 'Schule [ˈʃuːlə]', 'hint': 'English "shoe"'},
            {'symbol': 'y', 'sound': 'ü', 'example': 'über [ˈyːbɐ]', 'hint': 'say "ee" with rounded lips'},
        ]
    },
    'nl': {
        'name': 'Dutch',
        'symbols': [
            {'symbol': 'x', 'sound': 'ch/g', 'example': 'goed [xut]', 'hint': 'like Scottish "loch"'},
            {'symbol': 'ʏ', 'sound': 'u (short)', 'example': 'huis [hʏys]', 'hint': 'like German ü'},
            {'symbol': 'œy', 'sound': 'ui', 'example': 'huis [hœys]', 'hint': 'diphthong'},
            {'symbol': 'ɛi', 'sound': 'ij/ei', 'example': 'zijn [zɛin]', 'hint': 'like English "ay"'},
        ]
    },
}


def get_ipa_quick_reference(lang_code: str) -> dict:
    """
    Get the quick reference for a target language.

    Args:
        lang_code: Language code (pt, fr, en, it, es, de, nl)

    Returns:
        Dictionary with 'name' and 'symbols' (list of dicts), or None if not found.
    """
    return IPA_QUICK_REFERENCE.get(lang_code)


def format_ipa_tooltip(lang_code: str, max_symbols: int = 5) -> str:
    """
    Format an IPA quick reference tooltip as markdown text.

    Args:
        lang_code: Language code (pt, fr, en, it, es, de, nl)
        max_symbols: Maximum number of symbols to include

    Returns:
        Markdown string suitable for st.info() or st.expander()
    """
    ref = get_ipa_quick_reference(lang_code)
    if not ref:
        return f"No quick reference available for language code: {lang_code}"

    lines = [f"**{ref['name']} — Common IPA symbols you'll see:**\n"]
    for sym in ref['symbols'][:max_symbols]:
        line = f"- **{sym['symbol']}** — {sym['sound']}"
        if sym.get('example'):
            line += f" (*{sym['example']}*)"
        if sym.get('hint'):
            line += f" · {sym['hint']}"
        lines.append(line)

    if len(ref['symbols']) > max_symbols:
        lines.append(f"\n*...and {len(ref['symbols']) - max_symbols} more. See the full IPA guide in the sidebar.*")

    return '\n'.join(lines)
