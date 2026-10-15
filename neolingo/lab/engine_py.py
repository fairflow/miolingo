"""The engine's scoring, copied into Python so that a variant costs no engine process.

SUPERSEDED (15 October) for everything the engine itself decides by `lab/batch.py` (`neolingo batch`, the engine's own
`judgeWith`; locus a4c5878): lab/engine_measure.py uses it, and `python -m lab.batch compare` checks this copy against
it (var/lab/batch/compare.md: the scores agree except where the lab's own V2 emulation keeps an unflagged edit at a
German sound the check cannot judge, the columns except where the lab marks `unjudged` by the check's token rather than
by the engine's list).  NOT archived yet, because two users remain: the host's German ü/ö rule (env/soundcheck.py calls
lab.analyse.unreliable_subs, which aligns with `align` and `Costs` here, on every German check of the real host) and
the lab's experimental rules and the third run's cost grid (lab/analyse.py, lab/costfit.py: an alignment and a
distance per item for thousands of candidate configurations).

Copied from locus `Miolingo/Neo.lean` (`norm`, `words`, `understood`, `readings`, `sameSounds`, `dist`, `score`,
`align` with its tie-break, `byWord`, `columnsFrom`) and `Neolingo.lean` (`Cfg.tables`: the cost lookup and the curve).
The costs are exactly the entries the live host sends: `host.engine_config.build_costs(data/cost_table.json)`.
`lab/validate.py` checks this copy against the stored archive lines and against the real compiled engine.

Cost of hearing u for t (thousandths): 0 if t == u, else the entry for the language, else the generic entry, else
`costOtherwise` (1000).  Insertion and deletion 1000.
Curve "sqrt":   score = 100 - min(100, (100 d + D div 2) div D),  D = floor(sqrt(scale n)),  scale 2250000
Curve "linear": score = 100 - min(100, d div (10 n))            (the engine's other curve: division by the length)
n = the longer of the two lengths."""
from __future__ import annotations

import json
import math
from functools import lru_cache

from .common import DATA

INDEL = 1000
SIGNIFICANT = 340          # Miolingo's _SIGNIFICANT, in thousandths
SCALE = 2250000


# ------------------------------------------------------------------ norm, words, understood
def no_sound(c: str) -> bool:
    return c in "ˈˌ" or (ord(c) < 128 and not c.isalpha()) or c in "‿‖"


def norm(ipa):
    """The engine's `norm`: stress marks and punctuation removed; empty sounds and empty words dropped."""
    out = []
    for w in ipa or []:
        ww = ["".join(c for c in ph if not no_sound(c)) for ph in w]
        ww = [p for p in ww if p]
        if ww:
            out.append(ww)
    return out


def flat(ipa):
    return [p for w in ipa or [] for p in w]


def _lower_c(c: str) -> str:
    o = ord(c)
    if "A" <= c <= "Z":
        return c.lower()
    if 0xC0 <= o <= 0xDE and o != 0xD7:
        return chr(o + 32)
    if o == 0x152:
        return chr(0x153)
    if o == 0x178:
        return chr(0xFF)
    return c


def _is_word_char(c: str) -> bool:
    o = ord(c)
    ascii_alnum = o < 128 and c.isalnum()
    return ascii_alnum or (o >= 0xC0 and o != 0xD7 and o != 0xF7 and not (0x2000 <= o <= 0x206F))


def words(s: str) -> list[str]:
    """The engine's `words`: lower case; every character that is not a letter or a digit becomes a space; split."""
    return [w for w in "".join(_lower_c(c) if _is_word_char(c) else " " for c in s).split(" ") if w]


def understood_words(target_text: str, recognised: str) -> bool:
    return words(target_text) == words(recognised)


def _respell(a, b, c, cs):
    out, i = [], 0
    while i < len(cs):
        if i + 1 < len(cs) and cs[i] == a and cs[i + 1] == b:
            out.append(c)
            i += 2
        else:
            out.append(cs[i])
            i += 1
    return out


_KINDS = [[("a", "e", "ä"), ("A", "e", "Ä")], [("o", "e", "ö"), ("O", "e", "Ö")],
          [("u", "e", "ü"), ("U", "e", "Ü")], [("s", "s", "ß")]]


def readings(variant: str, text: str) -> list[str]:
    if variant.split("-")[0] != "de":
        return [text]
    acc = [list(text)]
    for k in _KINDS:
        more = []
        for l in acc:
            x = l
            for (a, b, c) in k:
                x = _respell(a, b, c, x)
            more.append(x)
        acc = acc + more
    out = []
    for l in acc:
        s = "".join(l)
        if s not in out:
            out.append(s)
    return out


def same_sounds(target_ipa_fn, variant: str, target, recognised: str) -> bool:
    """`target_ipa_fn(text, variant)` is the environment's targetIpa (lab: env.target_ipa, cached)."""
    tf = flat(target)
    for t in readings(variant, recognised):
        r = flat(norm(target_ipa_fn(t, variant)))
        if r and r == tf:
            return True
    return False


def understood(target_ipa_fn, variant: str, phrase: str, target, recognised: str) -> bool:
    return understood_words(phrase, recognised) or same_sounds(target_ipa_fn, variant, target, recognised)


# ------------------------------------------------------------------ costs
@lru_cache(maxsize=None)
def _host_entries():
    import env  # noqa: F401
    from host.engine_config import build_costs
    table = json.loads((DATA / "cost_table.json").read_text("utf-8"))
    generic, by_lang = {}, {}
    for e in build_costs(table):
        if "lang" in e:
            by_lang.setdefault(e["lang"], {})[(e["target"], e["heard"])] = e["cost"]
        elif "variant" in e:
            raise RuntimeError("variant-scoped cost entries are not expected from the host")
        else:
            generic[(e["target"], e["heard"])] = e["cost"]
    return generic, by_lang, table["unknown_cost"], table


def cost_table():
    return _host_entries()[3]


def stretch(c: int, p: float = 0.6) -> int:
    """Miolingo's stretched substitution cost: min(1, (4 c)^0.6), c a fraction; here in thousandths (0 stays 0).
    `p` the exponent (0.6 is Miolingo's; the third run of the lab tries others)."""
    if c <= 0:
        return 0
    return min(1000, round(1000 * (4 * c / 1000) ** p))


def transform(c: int, tx) -> int:
    """The third run's cost candidates (lab/costfit.py), applied to one substitution cost c (thousandths), in order:
    stretch with exponent p (None: none), a floor F on a cost that is not 0, then the factor k (the "scale trick":
    every substitution cost times k = 1000 / I and the curve's scale times k^2 give exactly the scores of an
    insertion and deletion cost of I with the engine's fixed 1000).  tx = ("tx", p, F, k, extra zero pairs)."""
    _tag, p, F, k, _extra = tx
    if c <= 0:
        return 0
    if p:
        c = stretch(c, p)
    if F:
        c = max(c, F)
    return round(c * k) if k != 1 else c


class Costs:
    """cost(t, u) for one language under a cost variant.

    kind      "raw" (the live host: panphon feature distance) | "stretched" (Miolingo's accuracy curve applied to
              the same entries) | ("tx", p, F, k, extra): the third run's candidates (`transform`), `extra` a frozenset
              of (target, heard) pairs that cost 0 (the German vocalised r, lab/costfit.py)
    unrel     "zero" (the live host: an `unreliable` target costs 0 against every sound of the table) |
              "phoneme" (lab variant: such a target costs 0 only against sounds that are NOT in `phoneme_set`; against a
              sound of that set it costs the plain panphon entry)"""

    def __init__(self, lang: str, kind: str = "raw", unrel: str = "zero", phoneme_set=frozenset()):
        self.lang, self.kind, self.unrel = lang, kind, unrel
        self.generic, by_lang, self.other, table = _host_entries()
        self.over = by_lang.get(lang, {})
        L = table["langs"].get(lang, {})
        self.unreliable = set(L.get("unreliable", []))
        self.accept = {(t, h) for t, d in (L.get("accept") or {}).items() for h in d}
        self.accept |= {(a, b) for a, b in L.get("tolerated", [])} | {(b, a) for a, b in L.get("tolerated", [])}
        self.phoneme_set = frozenset(phoneme_set)
        self._memo: dict = {}
        # lab variant "del_accept": leaving out t costs 1000 x (1 - w), w the weight of "∅" on t's accept list
        self.del_weight = {t: d["∅"] for t, d in (L.get("accept") or {}).items() if "∅" in d}

    def dele(self, t: str) -> int:
        """Deletion cost of target sound t under the del_accept variant (the engine itself: always 1000)."""
        w = self.del_weight.get(t)
        c = INDEL if w is None else round(INDEL * (1000 - w) / 1000)
        return stretch(c) if self.kind == "stretched" else c

    def raw(self, t: str, u: str) -> int:
        if t == u:
            return 0
        if self.unrel == "phoneme" and t in self.unreliable and u in self.phoneme_set:
            return self.generic.get((t, u), self.other)
        c = self.over.get((t, u))
        if c is None:
            c = self.generic.get((t, u), self.other)
        return c

    def __call__(self, t: str, u: str) -> int:
        k = (t, u)
        c = self._memo.get(k)
        if c is None:
            c = self.raw(t, u)
            if self.kind == "stretched":
                c = stretch(c)
            elif isinstance(self.kind, tuple):
                c = 0 if k in self.kind[4] else transform(c, self.kind)
            self._memo[k] = c
        return c

    def accepted_any(self, t: str, u: str) -> bool:
        """(t, u) is a tolerated pair or on the language's accept list, at any weight."""
        return (t, u) in self.accept

    def accepted(self, t: str, u: str) -> bool:
        """The language's table lowers this pair (a tolerated pair, an accept weight, an unreliable target)."""
        return t != u and (t, u) in self.over and self.raw(t, u) < self.generic.get((t, u), self.other)


# ------------------------------------------------------------------ dist, align, score
def _indel(_t):
    return INDEL


def dist_rows(cost, ts, us, dele=None):
    """`dele(t)`: the cost of leaving target sound t out (default: the engine's one deletion cost, 1000; a lab
    variant gives some sounds a lower one)."""
    dele = dele or _indel
    rows = [[j * INDEL for j in range(len(us) + 1)]]
    for t in ts:
        prev = rows[-1]
        dt = dele(t)
        cur = [prev[0] + dt]
        for j, u in enumerate(us, 1):
            cur.append(min(prev[j - 1] + cost(t, u), prev[j] + dt, cur[j - 1] + INDEL))
        rows.append(cur)
    return rows


def dist(cost, ts, us, dele=None) -> int:
    return dist_rows(cost, ts, us, dele)[-1][-1]


def align(cost, ts, us, dele=None):
    """ONE least-cost alignment, the engine's tie-break: paired first, then a target sound left out, then an extra
    heard sound.  -> [(target or None, heard or None)]."""
    D = dist_rows(cost, ts, us, dele)
    dele = dele or _indel
    i, j, acc = len(ts), len(us), []
    while i or j:
        if i and j and D[i][j] == D[i - 1][j - 1] + cost(ts[i - 1], us[j - 1]):
            acc.append((ts[i - 1], us[j - 1]))
            i, j = i - 1, j - 1
        elif i and D[i][j] == D[i - 1][j] + dele(ts[i - 1]):
            acc.append((ts[i - 1], None))
            i -= 1
        elif j:
            acc.append((None, us[j - 1]))
            j -= 1
        else:
            acc.append((ts[i - 1], None))
            i -= 1
    acc.reverse()
    return acc


def curve(d: int, n: int, kind: str = "sqrt", scale: int = SCALE) -> int:
    if kind == "linear":
        return 100 if n == 0 else 100 - min(100, d // (10 * n))
    D = math.isqrt(n * scale)
    return 100 if D == 0 else 100 - min(100, (d * 100 + D // 2) // D)


def score(cost, ts, us, kind: str = "sqrt", scale: int = SCALE) -> int:
    return curve(dist(cost, ts, us), max(len(ts), len(us)), kind, scale)


def by_word(target, al):
    """The columns by the target's words (`byWord`): an extra heard sound goes with the word of the nearest PAIRED
    column before it (the first word when there is none)."""
    lens = [len(w) for w in target]

    def word_of(k):
        tot = 0
        for w, n in enumerate(lens):
            tot += n
            if k < tot:
                return w
        return len(lens) - 1

    k, lastw, tagged = 0, 0, []
    for (t, u) in al:
        if t is not None and u is not None:
            w = word_of(k)
            tagged.append((w, (t, u)))
            k, lastw = k + 1, w
        elif t is not None:
            tagged.append((word_of(k), (t, u)))
            k += 1
        else:
            tagged.append((lastw, (t, u)))
    return [[c for (w, c) in tagged if w == g] for g in range(max(1, len(lens)))]


def columns_from(flags, cols):
    """The columns with the marks of the flags, as the page gets them: [{"target", "heard", "mark"}] by word."""
    out, k = [], 0
    for g in cols:
        row = []
        for (t, u) in g:
            if t is not None:
                f = next((f for f in flags if f["at"] == k), None)
                row.append({"target": t, "heard": u, "mark": (2 if f["off"] else 1) if f else 0})
                k += 1
            else:
                row.append({"target": t, "heard": u, "mark": 0})
        out.append(row)
    return out


def keep_flags(flags, target):
    """The engine keeps a flag only where it names a sound of the target at its place."""
    tf = flat(target)
    return [f for f in flags if 0 <= f["at"] < len(tf) and tf[f["at"]] == f["sound"]]
