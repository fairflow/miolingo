"""
Forced alignment of the KNOWN target text (HANDOFF "Settled"): Montreal Forced
Aligner 3.x called by subprocess, `mfa align_one ... --output_format json`.

MFA lives in its own conda env (conda-forge only). Configure how to invoke it:
  MIO_MFA_CMD      command prefix, default "mfa"
                   (e.g. "conda run -n mfa mfa", or a full path to the env's mfa --
                   then also put that env's bin/ on PATH, MFA needs its openfst/kaldi tools)
  MIO_MFA_MODELS   dir holding <acoustic>/ (or <acoustic>.zip) and <dictionary>.dict;
                   if unset, model names are passed through and MFA resolves its own
                   downloaded models (mfa model download ...).
Measured on a cloud container: ~11 s per call cold (process start + model load);
measure on the M4 before optimising (a server-mode aligner is the obvious next step).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional

from realised_phone.inventory import norm_ipa
from realised_phone.model import AlignedInterval, Alignment

_SILENCE = {"", "sil", "sp", "spn", "<eps>"}
_VOWELS = set("aeiouãẽĩõũəɛɔɪʊæɑ")


class AlignmentError(RuntimeError):
    pass


def words_of(text: str) -> list[str]:
    """Tokenise target text the way the dictionary is keyed: lowercase words."""
    t = unicodedata.normalize("NFC", text.lower())
    return re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)*", t)


def parse_mfa_json(data: dict, source_id: str = "", version: str = "",
                   status: str = "") -> Alignment:
    """MFA JSON (tiers.words / tiers.phones, entries [start, end, label]) -> Alignment.
    Silences are dropped; phones get word_index by time containment."""
    tiers = data["tiers"]
    words = [AlignedInterval(float(s), float(e), lab)
             for s, e, lab in tiers["words"]["entries"] if lab not in _SILENCE]
    phones = []
    for s, e, lab in tiers["phones"]["entries"]:
        if lab in _SILENCE:
            continue
        mid = (float(s) + float(e)) / 2
        wi = next((i for i, w in enumerate(words) if w.start <= mid < w.end), None)
        phones.append(AlignedInterval(float(s), float(e), norm_ipa(lab), wi))
    return Alignment(words=words, phones=phones, source_id=source_id,
                     version=version, status=status)


def mfa_align(wav_path: str, text: str, acoustic_model: str, dictionary: str,
              *, source_id: str = "", version: str = "", status: str = "",
              timeout: float = 120.0) -> Alignment:
    cmd_prefix = shlex.split(os.environ.get("MIO_MFA_CMD", "mfa"))
    am, dic = _resolve_models(acoustic_model, dictionary)
    with tempfile.TemporaryDirectory(prefix="mio_mfa_") as td:
        txt = Path(td) / "utt.txt"
        txt.write_text(" ".join(words_of(text)), encoding="utf-8")
        out = Path(td) / "utt.json"
        cmd = cmd_prefix + ["align_one", str(wav_path), str(txt), dic, am, str(out),
                            "--output_format", "json", "--quiet"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError as e:
            raise AlignmentError(f"MFA not found ({cmd_prefix[0]}); set MIO_MFA_CMD") from e
        except subprocess.TimeoutExpired as e:
            raise AlignmentError(f"MFA timed out after {timeout}s") from e
        if proc.returncode != 0 or not out.exists():
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
            raise AlignmentError("MFA align_one failed: " + " | ".join(tail))
        al = parse_mfa_json(json.loads(out.read_text(encoding="utf-8")),
                            source_id, version, status)
    al.oov = [w for w in words_of(text) if w not in {x.label for x in al.words}]
    return al


def _resolve_models(acoustic_model: str, dictionary: str) -> tuple[str, str]:
    models = os.environ.get("MIO_MFA_MODELS")
    if not models:
        return acoustic_model, dictionary
    m = Path(models)
    am = str(m / acoustic_model) if (m / acoustic_model).exists() else str(m / f"{acoustic_model}.zip")
    return am, str(m / f"{dictionary}.dict")


def mfa_align_batch(items: list[dict], acoustic_model: str, dictionary: str,
                    cache_dir: Optional[str] = None, jobs: int = 4,
                    timeout: float = 6 * 3600.0) -> dict[str, Alignment]:
    """Align many utterances with ONE `mfa align` run (model loaded once) --
    for evaluation/calibration, where align_one's per-call start-up dominates.

    items: [{"id", "wav", "text"}]; ids must be filesystem-safe and unique.
    Each utterance gets its own speaker directory so MFA's per-speaker
    adaptation never mixes utterances. Results are cached as
    <cache_dir>/<acoustic_model>/<id>.json (MFA JSON) and reused.
    Returns {id: Alignment}; utterances MFA could not align are absent.
    """
    cache = Path(cache_dir) / acoustic_model if cache_dir else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    done = lambda it: cache and ((cache / f"{it['id']}.json").exists()  # noqa: E731
                                 or (cache / f"{it['id']}.failed").exists())
    todo = [it for it in items if not done(it)]
    if todo:
        am, dic = _resolve_models(acoustic_model, dictionary)
        cmd_prefix = shlex.split(os.environ.get("MIO_MFA_CMD", "mfa"))
        with tempfile.TemporaryDirectory(prefix="mio_mfa_batch_") as td:
            corpus, out = Path(td) / "corpus", Path(td) / "out"
            for it in todo:
                d = corpus / it["id"]
                d.mkdir(parents=True)
                (d / f"{it['id']}.wav").symlink_to(Path(it["wav"]).resolve())
                (d / f"{it['id']}.lab").write_text(" ".join(words_of(it["text"])), encoding="utf-8")
            cmd = cmd_prefix + ["align", str(corpus), dic, am, str(out), "--output_format", "json",
                                "-j", str(jobs), "--clean", "--quiet"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            msg = (proc.stderr or proc.stdout or "").strip()
            # MFA exits non-zero when NO utterance aligns (e.g. a batch of only
            # previously-failed ones: "try a larger beam"); that is per-utterance
            # failure, not a broken setup -- anything else is raised.
            if proc.returncode != 0 and "beam" not in msg:
                raise AlignmentError("MFA align failed: " + " | ".join(msg.splitlines()[-3:]))
            for it in todo:
                f = out / it["id"] / f"{it['id']}.json"
                if f.exists() and cache:
                    (cache / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                elif f.exists():
                    it["_json"] = f.read_text(encoding="utf-8")
                elif cache:                     # remember: don't retry every run
                    (cache / f"{it['id']}.failed").write_text(msg[-500:], encoding="utf-8")
    result = {}
    for it in items:
        raw = (cache / f"{it['id']}.json").read_text(encoding="utf-8") if cache and \
            (cache / f"{it['id']}.json").exists() else it.pop("_json", None)
        if raw:
            al = parse_mfa_json(json.loads(raw))
            al.oov = [w for w in words_of(it["text"]) if w not in {x.label for x in al.words}]
            result[it["id"]] = al
    return result


def context_of(alignment: Alignment, i: int) -> str:
    """Phonological context of phone i (spec "Context"): word_initial, post_nls,
    onset_cluster, intervocalic, coda, other."""
    ph = alignment.phones
    p = ph[i]
    prev = ph[i - 1] if i > 0 and ph[i - 1].word_index == p.word_index else None
    nxt = ph[i + 1] if i + 1 < len(ph) and ph[i + 1].word_index == p.word_index else None
    # previous phone across a word boundary (for "un rato", "el ruido")
    prev_any = ph[i - 1] if i > 0 else None
    is_v = lambda q: q is not None and q.label[:1] in _VOWELS  # noqa: E731
    if prev is None:
        if prev_any is not None and prev_any.label in ("n", "l", "s"):
            return "post_nls"
        return "word_initial"
    if prev.label in ("n", "l", "s"):
        return "post_nls"
    if not is_v(prev) and is_v(nxt):
        return "onset_cluster"
    if is_v(prev) and is_v(nxt):
        return "intervocalic"
    if nxt is None or not is_v(nxt):
        return "coda"
    return "other"


def window(interval: AlignedInterval, pad: float = 0.0,
           total: Optional[float] = None) -> tuple[float, float]:
    s = max(0.0, interval.start - pad)
    e = interval.end + pad
    return (s, min(e, total) if total else e)
