# Miolingo Help

Miolingo helps you learn a language by **practising pronunciation**: you hear a
word or phrase, record yourself saying it, and get a score plus a colour-coded
breakdown of which sounds matched.

Use the **sidebar** on the left to switch between Practice, Story, Vocabulary and
Settings.

---

## Getting started
1. Open **Settings** and set **Your language (native)** and the **Target
   language** (the language you're learning). Picking one that's already chosen in
   the other box simply swaps them — the two are always different.
2. Go to **Practice** or **Story**, load some material, and start practising.
3. The first time you record, macOS asks for **Microphone** and **Speech
   Recognition** permission — allow both (they're required for scoring).

---

## Practice
Quick practice over a list of words/phrases.

- **Load material** — "Open practice from vocabulary" (your saved words), "Load
  phrases…" (paste or load a file), or "Load a sample".
- **Hear it** — press the 🔊 speaker next to the word.
- **Record** — press **Record**, say the word, press **Stop**.
- **Check pronunciation** — Miolingo recognises your speech and scores it:
  - **Similarity %** and an **edit distance**.
  - **Phoneme match** — your sounds vs the target, colour-coded:
    **blue = substituted**, **green = extra**, **pink = missing**, plain = matched.
  - **Recognised** — the words Miolingo heard.
- **Capture to vocabulary** — save the word to your collection.
- **Prev / Next** — move through the list.

If you see *"nothing recognised"*, check Microphone + Speech Recognition
permission (Settings → Speech recognition diagnostics shows the live status), and
that the on-device speech model for your target language is installed.

## Story
Read a short story three ways, using the mode switch:

- **Full** — the whole story with translations.
- **Browse** — one phrase at a time with its translation; move with Prev/Next.
- **Practice** — record and score each phrase, exactly like Quick Practice.

Switching mode keeps your place; choosing a different scene starts at the top.

## Vocabulary
Your saved words.

- **Add a word** — type it and press Add.
- **Filter** / **sort** (A–Z, Recent, Oldest).
- **Autofill** — fills in a word's translation and pronunciation (IPA).
- **Edit** / **Delete** a word.
- **Import…** — paste or load a file (see *Import format* below).
- **Practise these** — send the (filtered) list to Practice.

## Settings
- **Languages** — your native language and the target language (dropdowns; they're
  always different — picking the other's value swaps them).
- **Speech** — the TTS voice engine and, for espeak, speech speed. **Test voice**
  speaks a sample.
- **Recognition** — choose the speech-recognition engine. *System* works offline.
  *Whisper* is more accurate but downloads a model on first use and needs the
  network that once.
- **Speech recognition diagnostics** — live status if recognition isn't working.

---

## Import format
Bulk-add words (Vocabulary → Import…) or phrases (Practice → Load phrases…) by
paste or file. The format:

- **First line** is a header **`(target, source)`** using language **codes**, e.g.
  `(fr, en)` — *target first* (the language of the words), source second. The
  target must match your current Target language.
- **Then one row per item**, fields separated by `|`:
  - vocabulary: `word | translation | ipa | source | url`
  - phrases: `text | translation | ipa`
- IPA may be wrapped in `[ ]`. Lines starting with `#` are comments. Blank lines
  are ignored. Up to 250 rows.

Example (learning French):
```
(fr, en)
bonjour | hello | [bɔ̃ʒuʁ]
merci | thank you | [mɛʁsi]
```

If nothing imports, Miolingo tells you why (usually the header's target doesn't
match your Target language).

---

## Tips
- The **Build** row in Settings shows the exact version you're running.
- Pronunciation scoring compares **sounds (IPA)**, not spelling — so a word spelt
  differently but said correctly still scores well.
