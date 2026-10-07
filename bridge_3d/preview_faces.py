"""3DFACE 미리보기 PNG: preview_faces.py in.dxf out.png [elev azim]"""
import sys
import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

doc = ezdxf.readfile(sys.argv[1])
elev, azim = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (25, -130)
fig = plt.figure(figsize=(14, 10)); ax = fig.add_subplot(projection="3d")
polys, cols, pts = [], [], []
for f in doc.modelspace().query("3DFACE"):
    q = [tuple(v) for v in f.wcs_vertices()]
    polys.append(q); pts += q
    cols.append([c / 255 for c in ezdxf.colors.aci2rgb(doc.layers.get(f.dxf.layer).color)])
ax.add_collection3d(Poly3DCollection(polys, facecolors=cols, edgecolor=(0, 0, 0, .2), linewidths=.2))
xs, ys, zs = zip(*pts)
c = [(max(a) + min(a)) / 2 for a in (xs, ys, zs)]
r = max(max(a) - min(a) for a in (xs, ys, zs)) / 2
ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off()
fig.savefig(sys.argv[2], dpi=110, bbox_inches="tight")
