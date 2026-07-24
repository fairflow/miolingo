"""
Gluing a square into a torus  (Manim Community).

The fundamental polygon  a b a^-1 b^-1  is folded in two steps:
    Step 1 : glue the two sides  b   ->  a cylinder
    Step 2 : glue the two ends   a   ->  a torus
The two identified edges survive as the two generating loops of H_1(T^2):
    a  ->  meridian (around the tube)      b  ->  longitude (around the hole)

Render:
    manim -qm manim_torus.py TorusGluing
"""
from manim import *
import numpy as np

W = H = 4.0                     # square side
r = 0.72                        # tube radius on the final torus
R = 2.05                        # hole (major) radius
RES = (32, 32)

# neutral surface colour; edges/loops keep the a=blue, b=orange story
SURF = dict(u_range=[0, 1], v_range=[0, 1], resolution=RES,
            fill_opacity=0.95, stroke_width=0.5,
            checkerboard_colors=[TEAL_E, TEAL_D], stroke_color=TEAL_E)

A_COL, B_COL = BLUE_D, ORANGE


def flat(s, t):
    return np.array([W * (s - 0.5), H * (t - 0.5), 0.0])


def cyl(s, t):                  # roll the width (s) into a tube whose axis is +y
    th = TAU * s
    return np.array([r * np.sin(th), H * (t - 0.5), -r * np.cos(th)])


def tor(s, t):                  # s -> meridian (a), t -> longitude (b)
    th, ph = TAU * s, TAU * t
    return np.array([(R + r * np.cos(th)) * np.cos(ph),
                     (R + r * np.cos(th)) * np.sin(ph),
                     r * np.sin(th)])


class TorusGluing(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=0, theta=-90 * DEGREES)

        title = Text("Gluing a square into a torus", font_size=34).to_edge(UP)
        self.add_fixed_in_frame_mobjects(title)

        surf = Surface(lambda u, v: flat(u, v), **SURF)

        # ---- coloured directed edges of the fundamental polygon -------------
        TL, TR = flat(0, 1), flat(1, 1)
        BL, BR = flat(0, 0), flat(1, 0)

        def dedge(p0, p1, col):                       # thick edge + mid arrow
            body = Line(p0, p1, color=col, stroke_width=10)
            mid, d = (p0 + p1) / 2, normalize(p1 - p0)
            tip = Arrow(mid - 0.55 * d, mid + 0.55 * d, color=col, buff=0,
                        stroke_width=10, max_tip_length_to_length_ratio=0.6)
            return VGroup(body, tip)

        aT, aB = dedge(BL, BR, A_COL), dedge(TL, TR, A_COL)   # a: bottom & top -> +x
        bL, bR = dedge(BL, TL, B_COL), dedge(BR, TR, B_COL)   # b: left & right -> +y
        edges = VGroup(aT, aB, bL, bR)
        la = VGroup(Text("a", color=A_COL, font_size=30).next_to(BR / 2 + BL / 2, DOWN, 0.15),
                    Text("a", color=A_COL, font_size=30).next_to(TR / 2 + TL / 2, UP, 0.15))
        lb = VGroup(Text("b", color=B_COL, font_size=30).next_to(BL / 2 + TL / 2, LEFT, 0.15),
                    Text("b", color=B_COL, font_size=30).next_to(BR / 2 + TR / 2, RIGHT, 0.15))

        cap = Text("word:  a b a⁻¹ b⁻¹", font_size=26).to_edge(DOWN)
        self.add_fixed_in_frame_mobjects(cap)

        self.play(Write(title))
        self.play(FadeIn(surf), *[Create(e) for e in edges], FadeIn(la), FadeIn(lb), FadeIn(cap))
        self.wait(1.2)

        # ---- Step 1 : glue sides b -> cylinder ------------------------------
        step1 = Text("Step 1 — glue the two sides  b   →  cylinder",
                     font_size=26).to_edge(DOWN)
        self.play(FadeOut(cap), FadeOut(la), FadeOut(lb))
        self.remove(cap)
        self.add_fixed_in_frame_mobjects(step1)
        self.move_camera(phi=66 * DEGREES, theta=-78 * DEGREES, run_time=1.5,
                         added_anims=[FadeIn(step1)])
        self.play(Transform(surf, Surface(lambda u, v: cyl(u, v), **SURF)),
                  FadeOut(edges), run_time=3)

        bseam = ParametricFunction(lambda t: cyl(0, t), t_range=[0, 1], color=B_COL, stroke_width=8)
        aC0 = ParametricFunction(lambda s: cyl(s, 0), t_range=[0, 1], color=A_COL, stroke_width=8)
        aC1 = ParametricFunction(lambda s: cyl(s, 1), t_range=[0, 1], color=A_COL, stroke_width=8)
        self.play(Create(bseam), Create(aC0), Create(aC1))
        self.wait(0.8)

        # ---- Step 2 : glue ends a -> torus ----------------------------------
        step2 = Text("Step 2 — glue the two ends  a   →  torus",
                     font_size=26).to_edge(DOWN)
        self.remove(step1)
        self.add_fixed_in_frame_mobjects(step2)
        self.play(FadeIn(step2),
                  Transform(surf, Surface(lambda u, v: tor(u, v), **SURF)),
                  Transform(bseam, ParametricFunction(lambda t: tor(0, t), t_range=[0, 1],
                                                      color=B_COL, stroke_width=8)),
                  Transform(aC0, ParametricFunction(lambda s: tor(s, 0), t_range=[0, 1],
                                                    color=A_COL, stroke_width=8)),
                  Transform(aC1, ParametricFunction(lambda s: tor(s, 1), t_range=[0, 1],
                                                    color=A_COL, stroke_width=8)),
                  run_time=3.2)
        self.play(FadeOut(aC1))          # the two a-ends now coincide -> one meridian
        self.wait(0.4)

        # ---- the two generators of H_1 --------------------------------------
        legend = VGroup(
            Text("a  =  meridian", color=A_COL, font_size=26),
            Text("b  =  longitude", color=B_COL, font_size=26),
            Text("H₁(T²) = ℤ² = ⟨a, b⟩", font_size=28),
            Text("χ = 0", font_size=26),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.2).to_corner(UL)
        self.remove(step2)
        self.add_fixed_in_frame_mobjects(legend)
        self.play(FadeOut(title), FadeIn(legend))

        self.begin_ambient_camera_rotation(rate=0.4)
        self.wait(7)
        self.stop_ambient_camera_rotation()
        self.wait(0.4)
