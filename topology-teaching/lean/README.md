# The proof leg — Lean 4 + Mathlib

The third reading of the toolkit's objects: **proof**. `TopologyTeaching/Surfaces.lean`
models the torus as `Circle × Circle` and machine-checks the point-set facts,
then leaves graded exercises and a sketched bridge to the homology that
`../src/surface_homology.py` computes.

> ⚠️ **Not compiled in CI.** This stub is written against a recent Mathlib
> (2025+) but was not built in the environment that generated it. Mathlib names
> drift — if something is red, `exact?` / `apply?` / [loogle](https://loogle.lean-lang.org)
> will find the current spelling. The maths is standard; only the API moves.

## What's proved vs. left open

| Part | Content |
|------|---------|
| **A — proved** | `T²` is compact and Hausdorff; continuous image of a compact space is compact; the extreme-value theorem on `T²`. |
| **B — exercises** | `T²` is connected; path-connected; a continuous map out of `T²` into a Hausdorff space is closed. (Replace each `sorry`.) |
| **C — project** | The bridge to the algebra leg: `π₁(T²) ≅ ℤ²` (abelianises to the computed `H₁ = ℤ²`); and the Klein bottle as a quotient, with `π₁ = ⟨a,b | abab⁻¹⟩` and torsion `ℤ ⊕ ℤ/2`. |

## Setup

Needs [`elan`](https://github.com/leanprover/elan) (the Lean toolchain manager).

```bash
cd lean
lake update                       # resolves + pins Mathlib
cp .lake/packages/mathlib/lean-toolchain ./lean-toolchain   # match Mathlib's toolchain
lake exe cache get                # fetch prebuilt Mathlib oleans (fast)
lake build                        # build this library
```

If you'd rather start from a known-good scaffold, `lake new tt math` creates a
Mathlib project with the toolchain already aligned — then drop
`TopologyTeaching/Surfaces.lean` into it.

## Why this leg

For a tutor coming from proof theory it's the differentiator: the same surface,
drawn, computed, **and** formally verified. It also seeds a distinctive
exercise style — hand a student the picture and the homology, and have them
discover the Mathlib lemma that proves the point-set half.
