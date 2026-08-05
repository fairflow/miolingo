/-
  topology-teaching · the "proof" leg  (Lean 4 + Mathlib)
  =======================================================

  The toolkit reads one object three ways:

      images/two_holed_torus.png     the space, drawn            (image)
      src/surface_homology.py        its invariants, computed    (algebra)
      lean/TopologyTeaching/…        the same facts, checked     (proof)   ← here

  This is a STARTER STUB, written against a recent Mathlib (2025+).  It was NOT
  compiled in the environment that produced it, and Mathlib identifiers drift,
  so expect to nudge a name or two.  `exact?`, `apply?`, and loogle
  (https://loogle.lean-lang.org) find the current spelling, and the red
  squiggles say exactly where.  The mathematics is standard undergraduate
  point-set topology; only the API surface changes.

  Build (see lean/README.md):  lake update && lake exe cache get && lake build
-/
import Mathlib

namespace TopologyTeaching

open Set

/-- The torus as a space: the product of two circles, `S¹ × S¹`.

    `Circle` is Mathlib's unit circle in `ℂ` (older Mathlib spelled it `circle`).
    A toolchain-agnostic alternative is `AddCircle (1 : ℝ) × AddCircle (1 : ℝ)`,
    i.e. `(ℝ/ℤ)²`. -/
abbrev Torus : Type := Circle × Circle

/-! ### Part A — facts that should just check

Compactness and Hausdorffness of `S¹ × S¹` fall straight out of the instances
for the circle together with the instances for products. -/

example : CompactSpace Torus := inferInstance
example : T2Space Torus      := inferInstance

/-- The headline lemma quoted earlier, machine-checked in full generality:
    **a continuous image of a compact space is compact.** -/
theorem isCompact_range_of_compactSpace
    {X Y : Type*} [TopologicalSpace X] [TopologicalSpace Y] [CompactSpace X]
    {f : X → Y} (hf : Continuous f) : IsCompact (range f) := by
  rw [← image_univ]
  exact isCompact_univ.image hf

/-- Its payoff on the torus — the extreme value theorem: every continuous real
    "height function" on `T²` attains a maximum, because `T²` is compact. -/
theorem exists_max_on_torus (f : Torus → ℝ) (hf : Continuous f) :
    ∃ p, ∀ q, f q ≤ f p := by
  obtain ⟨p, -, hp⟩ := isCompact_univ.exists_forall_ge univ_nonempty hf.continuousOn
  exact ⟨p, fun q => hp q (mem_univ q)⟩

/-! ### Part B — exercises (replace each `sorry`)

All true, all undergraduate; the exercise is to *find* the Mathlib lemma. -/

/-- Exercise 1. The torus is connected.
    Hint: the circle is (path-)connected, and a product of connected spaces is
    connected. -/
example : ConnectedSpace Torus := by
  sorry

/-- Exercise 2. The torus is path-connected.
    Hint: `PathConnectedSpace` for the circle, then for products. -/
example : PathConnectedSpace Torus := by
  sorry

/-- Exercise 3. A continuous map out of the (compact) torus into a Hausdorff
    space is a closed map — the engine behind "continuous bijection from compact
    to Hausdorff is a homeomorphism".
    Hint: `IsCompact.isClosed`, and the compact→T2 closed-map lemma. -/
example {Y : Type*} [TopologicalSpace Y] [T2Space Y]
    {f : Torus → Y} (hf : Continuous f) : IsClosedMap f := by
  sorry

/-! ### Part C — the bridge to the *algebra* leg  (a project, not a one-liner)

`src/surface_homology.py` computes `H₁(T²) = ℤ²`.  Its homotopy-theoretic shadow
is `π₁(T²) ≅ ℤ × ℤ`, and `H₁` is its abelianisation (Hurewicz).  In Mathlib:

* `FundamentalGroup` lives in
  `Mathlib.AlgebraicTopology.FundamentalGroupoid.FundamentalGroup`;
* `π₁(S¹) ≅ ℤ` sits in the circle's homotopy theory — start there;
* `π₁(X × Y) ≅ π₁(X) × π₁(Y)` then gives `π₁(T²) ≅ ℤ × ℤ`.

A realistic target to build toward — **cracked in `Pi1Torus.lean`**, where the
assembly `π₁(T²) ≅ ℤ × ℤ` is proved outright from two ingredients (`π₁` of a
product, and `π₁(S¹) ≅ ℤ`):

    theorem fundamentalGroup_torus :
        FundamentalGroup Torus (1, 1) ≃* Multiplicative ℤ × Multiplicative ℤ

The **Klein bottle** has no off-the-shelf Mathlib type.  Model it as the
quotient of `ℝ²` (or `[0,1]²`) by `(x, 0) ~ (x, 1)` and `(0, y) ~ (1, 1 - y)`,
give it the quotient topology, and its fundamental group is `⟨a, b | a b a b⁻¹⟩`
— whose abelianisation `ℤ ⊕ ℤ/2` is exactly the torsion that
`surface_homology.py` prints.  Formalising the *non-orientability* is a genuine
project; the point-set facts (compact, connected) transfer almost verbatim from
the torus once the quotient is in place. -/

end TopologyTeaching
