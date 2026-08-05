/-
  Part C bridge (a crack)  ·  π₁(T²) ≅ ℤ × ℤ
  ===========================================

  The "project" leg promised in `Surfaces.lean`, taken as far as an honest
  scaffold.  NOT compiled here — treat every Mathlib name as a hypothesis to
  confirm with `exact?` / loogle.  Confidence is annotated per step.

  Standard strategy:

      π₁(T²) = π₁(S¹ × S¹)  ≅  π₁(S¹) × π₁(S¹)  ≅  ℤ × ℤ.

  Two ingredients do the real work; the assembly between them is pure algebra
  and is proved outright below (no `sorry`), so the crack genuinely *reduces*
  the theorem to (P) and (C):

      (P)  π₁(X × Y) ≅ π₁(X) × π₁(Y)     -- Mathlib has the groupoid version
      (C)  π₁(S¹) ≅ ℤ                     -- the crux
-/
import Mathlib
import TopologyTeaching.Surfaces

namespace TopologyTeaching

/-! ### Ingredient (P) — π₁ of a product

`Mathlib.AlgebraicTopology.FundamentalGroupoid.Product` proves the *groupoid*
statement: the fundamental groupoid of a product is the product of the
fundamental groupoids (look for `FundamentalGroupoid.prodToProdTop` and the
equivalence around it).  Taking automorphisms of the basepoint turns that
equivalence of groupoids into the group isomorphism below — a few `Aut` / `Equiv`
glue lemmas are all that should be missing.

Confidence: **medium** (the groupoid equivalence exists; packaging as a
`MulEquiv` of `FundamentalGroup`s is the work). -/
theorem fundamentalGroup_prod
    {X Y : Type*} [TopologicalSpace X] [TopologicalSpace Y] (x : X) (y : Y) :
    FundamentalGroup (X × Y) (x, y) ≃*
      FundamentalGroup X x × FundamentalGroup Y y := by
  sorry

/-! ### Ingredient (C) — π₁(S¹) ≅ ℤ

The crux.  The route is the exponential covering `ℝ → S¹` and Mathlib's
covering-space theory (`Mathlib.Topology.Covering`); monodromy along it is the
`ℤ`.  Whether a ready-made `FundamentalGroup Circle 1 ≃* Multiplicative ℤ`
already exists depends on your Mathlib — if it does, `exact?` will find it;
if not, this is the real project.

Confidence: **low** that a one-liner exists; **high** that the ingredients
(the covering map, `IsCoveringMap`, path lifting) are all present to build it. -/
theorem fundamentalGroup_circle :
    FundamentalGroup Circle 1 ≃* Multiplicative ℤ := by
  sorry

/-! ### Assembly — proved outright from (P) and (C)

This is the payoff of the crack: given the two ingredients, `π₁(T²) ≅ ℤ × ℤ`
is a one-liner in pure group theory (`MulEquiv.prodCongr`, `MulEquiv.trans`).
Recall `Torus := Circle × Circle` and the basepoint `(1, 1)`. -/
theorem fundamentalGroup_torus :
    FundamentalGroup Torus (1, 1) ≃* Multiplicative ℤ × Multiplicative ℤ :=
  (fundamentalGroup_prod (1 : Circle) (1 : Circle)).trans
    (fundamentalGroup_circle.prodCongr fundamentalGroup_circle)

/-
  Matching the algebra leg.  `surface_homology.py` prints `H₁(T²) = ℤ²`.
  Since `π₁(T²)` is abelian, it equals its own abelianisation, so Hurewicz
  gives `H₁ ≅ π₁`; the theorem above is therefore exactly that `ℤ²`, written
  multiplicatively as `Multiplicative ℤ × Multiplicative ℤ`.  Image, algebra,
  and proof now name the same group.
-/

end TopologyTeaching
