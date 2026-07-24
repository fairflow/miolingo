"""
Fundamental polygon  <->  homology     (image <-> algebra, in one object)
=========================================================================

A closed surface is given by an *edge word*: a 2n-gon whose sides are glued
in pairs.  Each side carries a letter (which edge it becomes) and an arrow
(orientation).  Torus = a b a^-1 b^-1, Klein bottle = a b a b^-1, etc.

From that single combinatorial datum we:
  1. glue the polygon's corners  -> the 0-cells (vertices)
  2. read off the distinct letters -> the 1-cells (edges)
  3. take the polygon itself       -> the single 2-cell (face)
build the cellular chain complex  C2 --d2--> C1 --d1--> C0,
and compute homology over Z with the integer Smith normal form (exact,
pure-Python: no rounding, so it sees torsion like the Z/2 in RP^2).

The picture drawn is *not* a separate illustration -- it is the very same
edge word, coloured and arrowed.  Read the arrows -> predict the gluing ->
the algebra confirms it; read the homology -> sketch the arrows back.
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ----------------------------------------------------------------------
# 1.  Exact linear algebra over Z:  integer Smith normal form.
#     Returns the (absolute) non-zero diagonal invariant factors d_i, so
#     coker = Z^n / im  ~=  (+) Z/d_i   (+)  Z^free.
# ----------------------------------------------------------------------
def smith_invariant_factors(matrix):
    A = [[int(x) for x in row] for row in matrix]
    rows = len(A)
    cols = len(A[0]) if rows else 0
    factors = []
    t = 0
    while t < rows and t < cols:
        # pick the smallest-magnitude non-zero entry in the sub-block as pivot
        piv = None
        for i in range(t, rows):
            for j in range(t, cols):
                if A[i][j] != 0 and (piv is None or abs(A[i][j]) < abs(A[piv[0]][piv[1]])):
                    piv = (i, j)
        if piv is None:
            break
        A[t], A[piv[0]] = A[piv[0]], A[t]                       # pivot -> (t,t)
        for r in range(rows):
            A[r][t], A[r][piv[1]] = A[r][piv[1]], A[r][t]
        p = A[t][t]
        cleared = True
        for i in range(t + 1, rows):                            # clear column t
            if A[i][t]:
                q = A[i][t] // p
                for j in range(t, cols):
                    A[i][j] -= q * A[t][j]
                if A[i][t]:
                    cleared = False
        for j in range(t + 1, cols):                            # clear row t
            if A[t][j]:
                q = A[t][j] // p
                for i in range(t, rows):
                    A[i][j] -= q * A[i][t]
                if A[t][j]:
                    cleared = False
        if not cleared:
            continue                                            # remainder left: redo t (gcd step)
        factors.append(abs(p))
        t += 1
    return [d for d in factors if d != 0]


# ----------------------------------------------------------------------
# 2.  Edge word  ->  cell complex  ->  homology.
# ----------------------------------------------------------------------
class UF:
    def __init__(self, n):
        self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def build_complex(word):
    """word: list of (letter, sign).  Returns cells + boundary maps + info."""
    L = len(word)
    # each side i runs from corner i to corner (i+1) along the CCW boundary;
    # the *letter's* own tail/head depend on the sign (orientation).
    ends = []                       # (tail_corner, head_corner) of the letter on side i
    for i, (_, s) in enumerate(word):
        i0, i1 = i, (i + 1) % L
        ends.append((i0, i1) if s == 1 else (i1, i0))

    letters = sorted({lt for lt, _ in word})
    occ = {lt: [] for lt in letters}
    for i, (lt, _) in enumerate(word):
        occ[lt].append(i)

    uf = UF(L)                      # glue corners according to paired sides
    for lt, sides in occ.items():
        if len(sides) == 2:
            (t0, h0), (t1, h1) = ends[sides[0]], ends[sides[1]]
            uf.union(t0, t1)
            uf.union(h0, h1)

    reps = sorted({uf.find(i) for i in range(L)})
    vid = {r: k for k, r in enumerate(reps)}
    def vclass(corner):
        return vid[uf.find(corner)]

    V, E, F = len(reps), len(letters), 1

    d1 = [[0] * E for _ in range(V)]           # C1 -> C0 : columns are edges
    for j, lt in enumerate(letters):
        t, h = ends[occ[lt][0]]
        d1[vclass(h)][j] += 1
        d1[vclass(t)][j] -= 1

    d2 = [[0] for _ in range(E)]               # C2 -> C1 : one column (the face)
    for j, lt in enumerate(letters):
        d2[j][0] = sum(s for l2, s in word if l2 == lt)

    inv1 = smith_invariant_factors(d1)
    inv2 = smith_invariant_factors(d2)
    r1, r2 = len(inv1), len(inv2)

    betti = [V - r1, (E - r1) - r2, F - r2]    # b0, b1, b2
    tors  = [[], [d for d in inv2 if d > 1], []]   # torsion of H_k from d_{k+1}

    return dict(word=word, letters=letters, V=V, E=E, F=F,
                euler=V - E + F, betti=betti, torsion=tors,
                vclass=[vclass(i) for i in range(L)], ends=ends)


def homology_str(b, tors):
    parts = []
    if b == 1:
        parts.append("ℤ")
    elif b > 1:
        parts.append(f"ℤ^{b}")
    parts += [f"ℤ/{d}" for d in tors]
    return " ⊕ ".join(parts) if parts else "0"


def word_str(word):
    return " ".join(lt + ("" if s == 1 else "⁻¹") for lt, s in word)


# ----------------------------------------------------------------------
# 3.  The picture IS the edge word: coloured, arrowed, corners numbered
#     by which vertex-class they glue to.
# ----------------------------------------------------------------------
EDGE_COLOR = {"a": "#0072B2", "b": "#D55E00", "c": "#009E73",
              "d": "#CC79A7", "e": "#E69F00", "f": "#56B4E9"}


def bezier(P0, C, P1, n=64):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * P0 + 2 * (1 - t) * t * C + t ** 2 * P1


def draw_surface(ax, name, info):
    word = info["word"]
    L = len(word)
    ang = np.deg2rad(90 - 180 / L + np.arange(L) * 360 / L)
    P = np.c_[np.cos(ang), np.sin(ang)]        # corner coordinates

    for i, (lt, s) in enumerate(word):
        P0, P1 = P[i], P[(i + 1) % L]
        mid = 0.5 * (P0 + P1)
        if L == 2:                              # draw a bigon as a lens
            C = mid + np.array([0, 0.6 if i == 0 else -0.6])
        else:
            C = mid
        col = EDGE_COLOR.get(lt, "#444444")
        pts = bezier(P0, C, P1)
        ax.plot(pts[:, 0], pts[:, 1], color=col, lw=4, solid_capstyle="round", zorder=2)

        # orientation arrowhead near the middle, pointing tail -> head
        tail, _ = info["ends"][i]
        fwd = (tail == i)
        k = len(pts) // 2
        a, b = (pts[k - 3], pts[k + 3]) if fwd else (pts[k + 3], pts[k - 3])
        ax.annotate("", xy=b, xytext=a, zorder=3,
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=0, mutation_scale=22))

        lab = C * 1.16 if L == 2 else mid * 1.22
        ax.text(lab[0], lab[1], lt, color=col, fontsize=15, fontweight="bold",
                ha="center", va="center", zorder=4)

    # corners: numbered by vertex-class -> shows which corners are identified
    for i in range(L):
        ax.plot(*P[i], "o", ms=13, mfc="white", mec="black", mew=1.4, zorder=5)
        ax.text(P[i, 0], P[i, 1], str(info["vclass"][i]), fontsize=8.5,
                ha="center", va="center", zorder=6)

    b = info["betti"]; t = info["torsion"]
    title = (f"{name}\nword:  {word_str(word)}\n"
             f"$H_0$={homology_str(b[0], t[0])}   "
             f"$H_1$={homology_str(b[1], t[1])}   "
             f"$H_2$={homology_str(b[2], t[2])}\n"
             f"V={info['V']}  E={info['E']}  F={info['F']}   "
             f"χ={info['euler']}")
    ax.set_title(title, fontsize=11, linespacing=1.5)
    ax.set_xlim(-1.7, 1.7); ax.set_ylim(-1.7, 1.7)
    ax.set_aspect("equal"); ax.axis("off")


# ----------------------------------------------------------------------
# 4.  Run it on the standard classification-of-surfaces zoo.
# ----------------------------------------------------------------------
SURFACES = [
    ("Sphere  $S^2$",            [("a", 1), ("a", -1)]),
    ("Projective plane  $\\mathbb{R}P^2$",
                                 [("a", 1), ("a", 1)]),
    ("Torus  $T^2$",             [("a", 1), ("b", 1), ("a", -1), ("b", -1)]),
    ("Klein bottle  $K$",        [("a", 1), ("b", 1), ("a", 1), ("b", -1)]),
    ("Genus-2  $\\Sigma_2$",     [("a", 1), ("b", 1), ("a", -1), ("b", -1),
                                  ("c", 1), ("d", 1), ("c", -1), ("d", -1)]),
]

print("=" * 66)
for name, word in SURFACES:
    info = build_complex(word)
    b, t = info["betti"], info["torsion"]
    plain = name.replace("$", "").replace("\\mathbb{R}P^2", "RP^2").replace("\\Sigma_2", "genus-2")
    print(f"{plain:24s}  word = {word_str(word)}")
    print(f"    V={info['V']} E={info['E']} F={info['F']}   Euler chi = {info['euler']}")
    print(f"    H0 = {homology_str(b[0], t[0])}")
    print(f"    H1 = {homology_str(b[1], t[1])}   (= abelianised pi_1)")
    print(f"    H2 = {homology_str(b[2], t[2])}")
    if info["V"] == 1:
        print(f"    pi_1 = < {','.join(info['letters'])} | {word_str(word)} >")
    print("-" * 66)

# figure: one coloured fundamental polygon per surface + a notation key
fig, axes = plt.subplots(2, 3, figsize=(15, 10))
axes = axes.ravel()
for ax, (name, word) in zip(axes, SURFACES):
    draw_surface(ax, name, build_complex(word))

key = axes[5]
key.axis("off")
key.set_title("How to read each tile", fontsize=12, fontweight="bold")
key.text(0.02, 0.86,
         "• colour  = which edge two sides become when glued\n"
         "• arrow   = orientation; a matched pair is glued\n"
         "            head→head and tail→tail\n"
         "• number  = vertex-class a corner glues to\n"
         "            (same number = same point)\n\n"
         "Read arrows → predict the surface → the algebra\n"
         "confirms it.  Read $H_1$ → sketch the arrows back.\n\n"
         "All homology is computed over ℤ by exact integer\n"
         "Smith normal form, so torsion (the ℤ/2 in $\\mathbb{R}P^2$\n"
         "and the Klein bottle) is seen, not rounded away.",
         fontsize=10.5, va="top", linespacing=1.5, transform=key.transAxes)

fig.suptitle("Fundamental polygon  ⟷  homology   (one object, read two ways)",
             fontsize=15, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96])
_here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(_here, "..", "images", "surface_homology.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=150, facecolor="white")
print("saved", out)
