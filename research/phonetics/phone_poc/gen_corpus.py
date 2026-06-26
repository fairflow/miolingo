#!/usr/bin/env python3
"""
Generate the synthesized ground-truth test corpus for the phone-recognizer benchmark.

For each item we:
  - synthesize audio with espeak (the espeak that is actually installed: v1.48.04)
  - record the espeak reference IPA (--ipa=3 => '_'-separated phones)
  - resample to 16kHz mono WAV via ffmpeg (models want 16kHz)

We also generate DELIBERATE-ERROR cases by synthesizing a *different* word/spelling
than the "intended" target, so we have ground-truth wrong pronunciations, plus matched
CORRECT cases to test for false alarms.

Output: corpus.json  +  audio/*.wav  (both raw and _16k.wav)
"""
import json
import subprocess
import os

ESPEAK = "espeak"
FFMPEG = "/opt/local/bin/ffmpeg"
HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(HERE, "audio")
os.makedirs(AUDIO, exist_ok=True)


def espeak_ipa(text, voice):
    """Reference IPA as a list of phone tokens (stress marks stripped)."""
    out = subprocess.run(
        [ESPEAK, "-v", voice, "--ipa=3", "-q", text],
        capture_output=True, text=True,
    ).stdout.strip()
    # --ipa=3 separates phones with '_'; words separated by spaces.
    toks = []
    for chunk in out.split():
        for p in chunk.split("_"):
            p = p.strip()
            # strip stress/length diacritics that espeak emits as separate marks
            p = p.replace("ˈ", "").replace("ˌ", "").replace("ː", "")
            if p:
                toks.append(p)
    return toks, out


def synth(text, voice, wav_path):
    subprocess.run([ESPEAK, "-v", voice, "-w", wav_path, text],
                   capture_output=True)
    wav16 = wav_path.replace(".wav", "_16k.wav")
    subprocess.run([FFMPEG, "-y", "-i", wav_path, "-ar", "16000", "-ac", "1",
                    wav16], capture_output=True)
    return wav16


# Corpus design.
# kind = "correct"  : audio matches the intended word; expect low PER, no error flag
# kind = "error"    : audio synthesized from a MISpronounced spelling; the intended
#                     reference is the CORRECT word -> recognizer output should DIFFER
#                     from intended ref (i.e. the error should be detectable).
ITEMS = [
    # ---- Portuguese (pt-pt) correct ----
    dict(id="pt_ola",      voice="pt-pt", intended="olá",     spoken="olá",     kind="correct"),
    dict(id="pt_obrigado", voice="pt-pt", intended="obrigado",spoken="obrigado",kind="correct"),
    dict(id="pt_casa",     voice="pt-pt", intended="casa",    spoken="casa",    kind="correct"),
    dict(id="pt_gato",     voice="pt-pt", intended="gato",    spoken="gato",    kind="correct"),
    dict(id="pt_verde",    voice="pt-pt", intended="verde",   spoken="verde",   kind="correct"),
    # ---- Portuguese (pt-br) correct ----
    dict(id="ptbr_cachorro", voice="pt-br", intended="cachorro", spoken="cachorro", kind="correct"),
    dict(id="ptbr_obrigado", voice="pt-br", intended="obrigado", spoken="obrigado", kind="correct"),
    # ---- French (fr-fr) correct ----
    dict(id="fr_bonjour", voice="fr-fr", intended="bonjour", spoken="bonjour", kind="correct"),
    dict(id="fr_merci",   voice="fr-fr", intended="merci",   spoken="merci",   kind="correct"),
    dict(id="fr_chat",    voice="fr-fr", intended="chat",    spoken="chat",    kind="correct"),
    dict(id="fr_rouge",   voice="fr-fr", intended="rouge",   spoken="rouge",   kind="correct"),
    dict(id="fr_eau",     voice="fr-fr", intended="eau",     spoken="eau",     kind="correct"),

    # ---- DELIBERATE ERRORS ----
    # intended word vs a spoken spelling that yields a wrong vowel/consonant.
    # pt: "casa" intended, learner says "caza"->same; use vowel error: intended "gato" said "guto"
    dict(id="err_pt_gato_guto", voice="pt-pt", intended="gato", spoken="guto", kind="error",
         note="wrong stressed vowel a->u"),
    # pt: intended "verde" but said "vorde" (e->o)
    dict(id="err_pt_verde_vorde", voice="pt-pt", intended="verde", spoken="vorde", kind="error",
         note="wrong vowel e->o"),
    # fr: intended "merci" but said "marci" (e->a)
    dict(id="err_fr_merci_marci", voice="fr-fr", intended="merci", spoken="marci", kind="error",
         note="wrong vowel"),
    # fr: intended "rouge" but said "rooge"-> approximate; use "louge" (r->l, common L2 error)
    dict(id="err_fr_rouge_louge", voice="fr-fr", intended="rouge", spoken="louge", kind="error",
         note="r->l substitution"),
    # fr: intended "chat" but said "char" (final consonant added / different)
    dict(id="err_fr_chat_char", voice="fr-fr", intended="chat", spoken="char", kind="error",
         note="t vs r ending"),
]


def main():
    corpus = []
    for it in ITEMS:
        # Reference IPA is for the INTENDED word (what the learner is trying to say).
        ref_phones, ref_raw = espeak_ipa(it["intended"], it["voice"])
        # The audio is synthesized from the SPOKEN spelling.
        spoken_phones, spoken_raw = espeak_ipa(it["spoken"], it["voice"])
        wav = os.path.join(AUDIO, it["id"] + ".wav")
        wav16 = synth(it["spoken"], it["voice"], wav)
        rec = dict(it)
        rec.update(
            ref_phones=ref_phones, ref_raw=ref_raw,
            spoken_phones=spoken_phones, spoken_raw=spoken_raw,
            wav16=wav16,
        )
        corpus.append(rec)
        print(f"{it['id']:24s} {it['voice']} intended={it['intended']!r} "
              f"spoken={it['spoken']!r}  ref=/{' '.join(ref_phones)}/  "
              f"spoken_ipa=/{' '.join(spoken_phones)}/")
    with open(os.path.join(HERE, "corpus.json"), "w") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(corpus)} items to corpus.json")


if __name__ == "__main__":
    main()
