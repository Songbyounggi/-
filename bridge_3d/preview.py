"""3DSOLID(ACIS) 를 다시 읽어 등각 미리보기 PNG 생성: preview.py in.dxf out.png [elev azim]"""
import sys
import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from ezdxf.acis import api as acis

doc = ezdxf.readfile(sys.argv[1])
elev, azim = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (28, -125)
fig = plt.figure(figsize=(16, 10))
ax = fig.add_subplot(projection="3d")
pts = []
for s in doc.modelspace().query("3DSOLID"):
    color = ezdxf.colors.aci2rgb(doc.layers.get(s.dxf.layer).color)
    for body in acis.load_dxf(s):
        for mesh in acis.mesh_from_body(body):
            polys = [[mesh.vertices[i] for i in f] for f in mesh.faces]
            pts.extend(mesh.vertices)
            ax.add_collection3d(Poly3DCollection(
                [[(v.x, v.y, v.z) for v in p] for p in polys],
                facecolor=[c / 255 for c in color], edgecolor=(0, 0, 0, 0.15), linewidths=0.2))
xs, ys, zs = zip(*((p.x, p.y, p.z) for p in pts))
cx, cy, cz = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2
r = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2
ax.set_xlim(cx - r, cx + r); ax.set_ylim(cy - r, cy + r); ax.set_zlim(cz - r * 0.45, cz + r * 0.45)
ax.set_box_aspect((1, 1, 0.45)); ax.view_init(elev, azim); ax.set_axis_off()
fig.savefig(sys.argv[2], dpi=110, bbox_inches="tight")
