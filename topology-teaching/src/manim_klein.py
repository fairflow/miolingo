"""
Gluing a square into a Klein bottle  (Manim Community).

Same construction as the torus, but the word is  a b a b⁻¹  — the two a-edges
are glued with a FLIP (antiparallel), not in parallel. That single reversal is
the whole difference:
    Step 1 : glue the two sides  b        ->  a cylinder   (exactly as the torus)
    Step 2 : glue the two ends   a, flipped ->  the tube must pass through itself
The result is a Klein bottle, shown here as its figure-8 immersion in R^3.
The flip is what forces  2a = 0  in homology, giving the torsion:
    H_1(K) = Z (+) Z/2        (compare the torus, H_1 = Z^2)

Render:  manim -qm manim_klein.py KleinGluing
"""
from manim import *
import numpy as np

W = H = 4.0
r = 0.72
RES = (40, 40)

# maroon surface, to read as a different object from the teal torus
SURF = dict(u_range=[0, 1], v_range=[0, 1], resolution=RES,
            fill_opacity=0.9, stroke_width=0.5,
            checkerboard_colors=[MAROON_E, MAROON_D], stroke_color=MAROON_E)
A_COL, B_COL = BLUE_D, ORANGE


def flat(s, t):
    return np.array([W * (s - 0.5), H * (t - 0.5), 0.0])


def cyl(s, t):
    th = TAU * s
    return np.array([r * np.sin(th), H * (t - 0.5), -r * np.cos(th)])


def klein(s, t):                       # figure-8 immersion of the Klein bottle
    u, v = TAU * t, TAU * s            # u: main loop (a, flipped) ; v: cross-section
    cu2, su2 = np.cos(u / 2), np.sin(u / 2)
    ru = 2.4 + cu2 * np.sin(v) - su2 * np.sin(2 * v)
    p = np.array([ru * np.cos(u), ru * np.sin(u), su2 * np.sin(v) + cu2 * np.sin(2 * v)])
    return 0.82 * p


class KleinGluing(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=0, theta=-90 * DEGREES)
        title = Text("Gluing a square into a Klein bottle", font_size=32).to_edge(UP)
        self.add_fixed_in_frame_mobjects(title)

        surf = Surface(lambda u, v: flat(u, v), **SURF)
        TL, TR = flat(0, 1), flat(1, 1)
        BL, BR = flat(0, 0), flat(1, 0)

        def dedge(p0, p1, col, flip=False):
            body = Line(p0, p1, color=col, stroke_width=10)
            mid, d = (p0 + p1) / 2, normalize(p1 - p0)
            if flip:
                d = -d
            tip = Arrow(mid - 0.55 * d, mid + 0.55 * d, color=col, buff=0,
                        stroke_width=10, max_tip_length_to_length_ratio=0.6)
            return VGroup(body, tip)

        aB = dedge(BL, BR, A_COL)                 # a  ->
        aT = dedge(TL, TR, A_COL, flip=True)      # a  <-   (THE FLIP)
        bL, bR = dedge(BL, TL, B_COL), dedge(BR, TR, B_COL)   # b : both up (parallel)
        edges = VGroup(aB, aT, bL, bR)
        la = VGroup(Text("a", color=A_COL, font_size=30).next_to((BL + BR) / 2, DOWN, 0.15),
                    Text("a", color=A_COL, font_size=30).next_to((TL + TR) / 2, UP, 0.15))
        lb = VGroup(Text("b", color=B_COL, font_size=30).next_to((BL + TL) / 2, LEFT, 0.15),
                    Text("b", color=B_COL, font_size=30).next_to((BR + TR) / 2, RIGHT, 0.15))
        word = Text("word:  a b a b⁻¹    (top a is flipped vs the torus)",
                    font_size=24).to_edge(DOWN)
        self.add_fixed_in_frame_mobjects(word)

        self.play(Write(title))
        self.play(FadeIn(surf), *[Create(e) for e in edges], FadeIn(la), FadeIn(lb), FadeIn(word))
        self.wait(1.4)

        # Step 1 : glue sides b -> cylinder
        step1 = Text("Step 1 — glue the two sides  b   →  cylinder", font_size=25).to_edge(DOWN)
        self.play(FadeOut(word), FadeOut(la), FadeOut(lb))
        self.remove(word)
        self.add_fixed_in_frame_mobjects(step1)
        self.move_camera(phi=66 * DEGREES, theta=-72 * DEGREES, run_time=1.5,
                         added_anims=[FadeIn(step1)])
        self.play(Transform(surf, Surface(lambda u, v: cyl(u, v), **SURF)),
                  FadeOut(edges), run_time=3)
        self.wait(0.5)

        # Step 2 : glue ends a WITH A FLIP -> figure-8 immersion (self-intersecting)
        step2 = Text("Step 2 — glue ends  a  with a flip  →  the tube passes through itself",
                     font_size=23).to_edge(DOWN)
        self.remove(step1)
        self.add_fixed_in_frame_mobjects(step2)
        klein_surf = Surface(lambda u, v: klein(u, v), **SURF)
        self.play(FadeIn(step2), FadeTransform(surf, klein_surf), run_time=2.6)
        self.wait(0.4)

        aloop = ParametricFunction(lambda t: klein(0.0, t), t_range=[0, 1], color=A_COL, stroke_width=7)
        bloop = ParametricFunction(lambda s: klein(s, 0.25), t_range=[0, 1], color=B_COL, stroke_width=7)
        self.play(Create(aloop), Create(bloop))
        self.wait(0.3)

        legend = VGroup(
            Text("a  flips  →  non-orientable", color=A_COL, font_size=24),
            Text("H₁(K) = ℤ ⊕ ℤ/2", font_size=28),
            Text("2a = 0  (the flip)  →  torsion ℤ/2", font_size=22),
            Text("χ = 0", font_size=24),
            Text("(figure-8 immersion in ℝ³)", font_size=19, color=GREY_B),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.16).to_corner(UL)
        self.remove(step2)
        self.add_fixed_in_frame_mobjects(legend)
        self.play(FadeOut(title), FadeIn(legend))

        self.begin_ambient_camera_rotation(rate=0.45)
        self.wait(6)
        self.stop_ambient_camera_rotation()
        self.wait(0.4)
