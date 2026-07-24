import os
import numpy as np
from skimage import measure
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.colors as mcolors

# ----------------------------------------------------------------------
# A genus-2 surface (two-holed torus) built as ONE connected manifold.
#
# Two ring-shaped tubes (each an approximate signed-distance field to a
# circle) are fused with a smooth-minimum union.  The rings are placed so
# their tubes overlap in a single neck near the origin, so the result is a
# single connected surface with two holes: the connected sum of two tori,
# i.e. a genus-2 surface.  It is NOT two separate doughnuts.
# ----------------------------------------------------------------------

R = 1.0     # major radius of each ring
a = 0.42    # tube (minor) radius
c = 1.0     # each ring centred at x = +/- c  (centrelines tangent at origin)
k = 0.28    # smooth-union blend width -> fused neck

def ring_sdf(X, Y, Z, cx):
    # approximate signed distance to a circle of radius R centred at (cx,0,0)
    q = np.sqrt((X - cx) ** 2 + Y ** 2) - R
    return np.sqrt(q ** 2 + Z ** 2) - a

def smooth_union(d1, d2, k):
    h = np.clip(0.5 + 0.5 * (d2 - d1) / k, 0.0, 1.0)
    return d2 * (1 - h) + d1 * h - k * h * (1 - h)

# sampling grid (fine in x,y ; thin in z since the surface is flat there)
nx, ny, nz = 260, 200, 90
xs = np.linspace(-2.6, 2.6, nx)
ys = np.linspace(-1.7, 1.7, ny)
zs = np.linspace(-0.7, 0.7, nz)
dx = xs[1] - xs[0]; dy = ys[1] - ys[0]; dz = zs[1] - zs[0]

X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
F = smooth_union(ring_sdf(X, Y, Z, +c), ring_sdf(X, Y, Z, -c), k)

verts, faces, normals, _ = measure.marching_cubes(F, level=0.0, spacing=(dx, dy, dz))
verts += np.array([xs[0], ys[0], zs[0]])  # shift into real coordinates
print("triangles:", len(faces))

# outward normals from the analytic field gradient (F increases outward),
# evaluated at each triangle centroid -> robust, sign-unambiguous.
def field(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    return smooth_union(ring_sdf(x, y, z, +c), ring_sdf(x, y, z, -c), k)

C = verts[faces].mean(axis=1)
e = 1e-3
gx = field(C + [e, 0, 0]) - field(C - [e, 0, 0])
gy = field(C + [0, e, 0]) - field(C - [0, e, 0])
gz = field(C + [0, 0, e]) - field(C - [0, 0, e])
fn = np.stack([gx, gy, gz], axis=1)
fn /= (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-9)

# ----- camera & back-face culling -----
# matplotlib's 3D uses painter's algorithm; drawing only the camera-facing
# triangles removes the hidden back sheet that otherwise bleeds through.
elev, azim = 40.0, -62.0
er, ar = np.radians(elev), np.radians(azim)
cam = np.array([np.cos(er) * np.cos(ar), np.cos(er) * np.sin(ar), np.sin(er)])
front = (fn @ cam) > -0.05
tris = verts[faces][front]
fn = fn[front]
print("front-facing:", front.sum())

# ----- two-light Lambert shading -----
L1 = np.array([-0.4, -0.5, 0.75]);  L1 /= np.linalg.norm(L1)   # key light
L2 = np.array([0.6, 0.35, 0.35]);   L2 /= np.linalg.norm(L2)   # fill light
diff = 0.34 + 0.72 * np.clip(fn @ L1, 0, 1) + 0.22 * np.clip(fn @ L2, 0, 1)

base = np.array(mcolors.to_rgb('#4aa6c0'))   # clean teal surface
colors = np.clip(diff[:, None] * base[None, :], 0, 1)
spec = np.clip(fn @ L1, 0, 1) ** 20          # soft specular highlight
colors = np.clip(colors + 0.30 * spec[:, None], 0, 1)

# ----- draw -----
fig = plt.figure(figsize=(9, 6), dpi=220)
ax = fig.add_subplot(111, projection='3d')
mesh = Poly3DCollection(tris, facecolors=colors, linewidths=0)
mesh.set_edgecolor(None)
mesh.set_zsort('average')
ax.add_collection3d(mesh)

ax.set_xlim(-2.6, 2.6); ax.set_ylim(-1.7, 1.7); ax.set_zlim(-1.45, 1.45)
ax.set_box_aspect((5.2, 3.4, 2.9))
ax.view_init(elev=elev, azim=azim)
ax.set_axis_off()
fig.patch.set_facecolor('white')
plt.tight_layout(pad=0)
_here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(_here, '..', 'images', 'two_holed_torus.png')
os.makedirs(os.path.dirname(out), exist_ok=True)
plt.savefig(out, bbox_inches='tight', pad_inches=0.15, facecolor='white')
print("saved", out)
