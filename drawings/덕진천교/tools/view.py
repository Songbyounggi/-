"""평행투영 + 화가 알고리즘 음영 뷰"""
import math
import numpy as np


def subdivide(v, edges, maxlen):
    """긴 사각형/다각형 면을 깊이정렬용으로 분할 (분할선은 숨김)"""
    n = len(v)
    if n != 4:
        return [(v, edges)]
    l01 = np.linalg.norm(v[1] - v[0]); l12 = np.linalg.norm(v[2] - v[1])
    na = max(1, int(math.ceil(max(l01, np.linalg.norm(v[2] - v[3])) / maxlen)))
    nb = max(1, int(math.ceil(max(l12, np.linalg.norm(v[3] - v[0])) / maxlen)))
    if na == 1 and nb == 1:
        return [(v, edges)]
    out = []
    P = lambda a, b: (v[0] * (1 - a) + v[1] * a) * (1 - b) + (v[3] * (1 - a) + v[2] * a) * b
    for i in range(na):
        for j in range(nb):
            a0, a1, b0, b1 = i / na, (i + 1) / na, j / nb, (j + 1) / nb
            q = [P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1)]
            e = [edges[0] and j == 0, edges[1] and i == na - 1, edges[2] and j == nb - 1, edges[3] and i == 0]
            out.append((np.array(q), e))
    return out


def camera(azim_deg, elev_deg):
    az, el = math.radians(azim_deg), math.radians(elev_deg)
    # 시선 방향 (카메라 → 대상)
    d = np.array([math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), -math.sin(el)])
    d = -d
    d = np.array([-math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), -math.sin(el)])
    right = np.cross(d, [0, 0, 1.0]); right /= np.linalg.norm(right)
    up = np.cross(right, d)
    return d, right, up


def project(parts, azim, elev, zscale=1.0, maxlen=2.5, light=(-0.4, -0.6, 0.85)):
    d, right, up = camera(azim, elev)
    L = np.array(light, float); L /= np.linalg.norm(L)
    polys = []
    for p in parts:
        if not p.in_view:
            continue
        base = np.array(p.color, float)
        for v, e in p.faces:
            v = v.copy(); v[:, 2] *= zscale
            # 법선 (뉴웰)
            nrm = np.zeros(3)
            for i in range(len(v)):
                a, b = v[i], v[(i + 1) % len(v)]
                nrm += np.array([(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])])
            nn = np.linalg.norm(nrm)
            if nn < 1e-12:
                continue
            nrm /= nn
            if nrm @ d > 0:
                nrm = -nrm          # 카메라쪽 법선
            sh = 0.50 + 0.50 * max(0.0, nrm @ L)
            col = tuple(int(min(255, c * sh)) for c in base)
            for q, qe in subdivide(v, e, maxlen):
                depth = float(np.mean(q @ d)) - p.bias
                xy = np.c_[q @ right, q @ up]
                polys.append((depth, xy, qe, col, p.layer))
    polys.sort(key=lambda t: -t[0])     # 먼 것부터
    return polys


def preview_png(polys, path, size=16, edge=True):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    xs = np.concatenate([p[1][:, 0] for p in polys]); ys = np.concatenate([p[1][:, 1] for p in polys])
    w, h = xs.max() - xs.min(), ys.max() - ys.min()
    fig = plt.figure(figsize=(size, size * h / w)); ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(xs.min(), xs.max()); ax.set_ylim(ys.min(), ys.max()); ax.set_aspect("equal"); ax.axis("off")
    z = 0
    for depth, xy, e, col, _ in polys:
        z += 1
        ax.add_patch(Polygon(xy, closed=True, fc=np.array(col) / 255, ec=np.array(col) / 255, lw=0.15, zorder=z))
        if edge:
            for i in range(len(xy)):
                if e[i]:
                    j = (i + 1) % len(xy)
                    ax.plot([xy[i, 0], xy[j, 0]], [xy[i, 1], xy[j, 1]], color=(0.2, 0.2, 0.2), lw=0.3, zorder=z + 0.5)
    fig.savefig(path, dpi=110, facecolor="white"); plt.close(fig)
