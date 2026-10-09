"""
Sound check panel (src/scoring/sound_check.py): shows which sounds of the target
were probably off, with what was probably said instead. Shown for every language
whose recognizer supports it; the sidebar toggle "Sound check" turns it off.
"""

from __future__ import annotations

import html

import streamlit as st

COLOURS = {"ok": "#2e7d32", "check": "#ef6c00", "off": "#c62828", "unchecked": "#9e9e9e"}


def _word_html(phones, word_ipa):
    if not phones:
        return f"<span style='opacity:.6'>{html.escape(word_ipa)}</span>"
    out = []
    for p in phones:
        tip = ("sounds right" if p["level"] == "ok" else
               "can't be judged reliably yet" if p["level"] == "unchecked" else
               f"probably said [{p['heard']}]" if p.get("heard") and p["heard"] != "∅" else
               "probably left out" if p.get("heard") == "∅" else "unclear")
        style = (f"color:{COLOURS[p['level']]};font-weight:{'700' if p['level'] in ('check', 'off') else '400'};"
                 + ("text-decoration:underline wavy;" if p["level"] == "off" else ""))
        out.append(f"<span title='{html.escape(tip)} ({p['p_ok']:.0%})' style='{style}'>"
                   f"{html.escape(p['phone'])}</span>")
    return "".join(out)


def render(result: dict, key_prefix: str = "practice") -> None:
    sc = (result or {}).get("sound_check")
    if not sc:
        return
    st.markdown("#### 🎯 Sound check *(beta)*")
    if sc.get("error"):
        st.caption(f"Sound check unavailable: {sc['error']}")
        return
    if sc.get("note"):
        st.caption(f"Sound check: {sc['note']}")
        return
    words_ipa = sc.get("words") or []
    by_word = {}
    for p in sc.get("phones") or []:
        by_word.setdefault(p["word_index"], []).append(p)
    text_words = (result.get("target") or "").split()
    show_text = len(text_words) == len(words_ipa)
    cells = []
    for wi, w in enumerate(words_ipa):
        label = html.escape(text_words[wi]) if show_text else ""
        cells.append("<span style='display:inline-block;margin:0 .6em .4em 0;text-align:center'>"
                     f"<span style='font-size:1.25em;font-family:serif'>{_word_html(by_word.get(wi), w)}</span>"
                     f"<br><span style='font-size:.8em;opacity:.7'>{label}</span></span>")
    st.markdown("".join(cells), unsafe_allow_html=True)

    flagged = [p for p in sc.get("phones") or [] if p["level"] in ("check", "off")]
    if not flagged:
        st.success("Every sound was recognised as expected.")
    else:
        flagged.sort(key=lambda p: p["p_ok"])
        lines = []
        for p in flagged[:5]:
            w = text_words[p["word_index"]] if show_text and p["word_index"] < len(text_words) else \
                (words_ipa[p["word_index"]] if p["word_index"] < len(words_ipa) else "")
            what = ("probably off" if p["level"] == "off" else "worth checking")
            heard = ("" if not p.get("heard") else
                     " — sounded left out" if p["heard"] == "∅" else f" — sounded like **[{p['heard']}]**")
            lines.append(f"- **[{p['phone']}]** in *{w}*: {what}{heard}")
        st.markdown("\n".join(lines))
    if sc.get("unchecked"):
        st.caption("Grey sounds (" + ", ".join(f"[{u}]" for u in sc["unchecked"]) +
                   ") can't be judged reliably yet: the listening model also misjudges native speakers on them.")
    rate = sc.get("native_flag_rate")
    st.caption(
        "Green = sounded as expected; orange = worth checking; red = probably off; grey = not judged. "
        "Hover a sound for details. This is a listening model's best guess, not a verdict"
        + (f" — it also flags about {rate:.0%} of sounds from native speakers." if rate else
           " — not yet calibrated for this language.")
    )
