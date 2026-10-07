"""창덕교(라멘교) 3D FACE 모델 생성 스크립트.

'01 라멘일반도 및 구조도' 의 일반도(1)(2) 치수·좌표·EL 로 교량 전체를
3DFACE 면으로 만들어 같은 도면 DXF 의 모형공간에 추가한다.

usage: python3 build_rahmen_3d.py <라멘일반도.dxf> <out.dxf> [<out_3d_only.dxf>]

좌표: 측량좌표(X=북, Y=동, EL) [m] ->
      CAD x = (Y - 209100)*1000 + 2630000, y = (X - 309130)*1000 + 70000, z = EL*1000 [mm]
"""
import math
import sys

import ezdxf
import numpy as np
from ezdxf import recover
from ezdxf.math.triangulation import mapbox_earcut_3d

# ---------------------------------------------------------------- 원자료
# 평면도 벽체 면 좌표 (X, Y) : top = Y 작은 쪽 끝, mid = 도로중심, bot = Y 큰 쪽 끝
O1 = [(309134.851049, 209119.768343), (309137.775481, 209130.494467), (309140.303276, 209139.765820)]
I1 = [(309135.587265, 209119.427295), (309138.509783, 209130.146398), (309141.035749, 209139.411044)]
I2 = [(309149.398394, 209113.619506), (309152.293418, 209124.237444), (309154.793157, 209133.405613)]
O2 = [(309150.149923, 209113.334623), (309153.043878, 209123.948640), (309155.542599, 209133.113076)]
# 슬래브 상면 EL (벽체 내측면 선상, top / 도로중심 / bot)
#  정면도(A1): 111.600(bot) 112.135(CL, 노면) 112.597(top)
#  정면도(A2): 112.056(top) 111.565(CL, 노면) 111.002(bot)
PAVE_T = 0.080
Z_I1 = (112.597, 112.135 - PAVE_T, 111.600)
Z_I2 = (112.056, 111.565 - PAVE_T, 111.002)

SLAB_T = 1.000
HAUNCH_V, HAUNCH_H = 0.300, 0.900
CORBEL = [(0.0, 0.8), (0.3, 0.8), (0.3, 1.1), (0.0, 1.4)]   # (외측 돌출, 슬래브상면 아래 깊이)
FOOT_BOT, FOOT_T, LEAN_T = 102.350, 1.000, 0.100
FOOT_HEEL, FOOT_TOE = 3.400, 1.000
PILE_D = 0.508
PILES = {1: (2.156, 6.7), 2: (2.135, 8.4)}                  # 벽체방향 간격, 길이
PILE_ROWS = (0.65, 2.60, 4.55)                              # 기초 뒷굽단부터
BARRIER = [(0.0, 0.0), (0.45, 0.0), (0.45, 0.193), (0.32, 0.37), (0.23, 1.18), (0.0, 1.18)]
MEDIAN_HALF = [(0.305, 0.0), (0.305, 0.123), (0.2865, 0.181), (0.22, 0.274),
               (0.1725, 0.3985), (0.0775, 1.3265), (0.0515, 1.35)]

Y0, X0, OX, OY = 209100.0, 309130.0, 2630000.0, 70000.0
NW, NX = 12, 16          # 폭/교축 방향 분할 수


def loc(p):
    X, Y = p
    return np.array([Y - Y0, X - X0], float)


O1, I1, I2, O2 = ([loc(p) for p in line] for line in (O1, I1, I2, O2))
T1, B1, T2, B2 = O1[0], O1[2], O2[0], O2[2]


def plan(xh, w):
    """xh: A1 외측면(0) ~ A2 외측면(1), w: top(0) ~ bot(1)"""
    a = T1 + (B1 - T1) * w
    b = T2 + (B2 - T2) * w
    return a + (b - a) * xh


def span_len(w):
    return float(np.linalg.norm(plan(1, w) - plan(0, w)))


def width(xh):
    return float(np.linalg.norm(plan(xh, 1) - plan(xh, 0)))


def xh_of(line):
    """벽체 면(top~bot)의 xh 를 w 의 1차식으로"""
    x0 = float(np.linalg.norm(line[0] - T1) / np.linalg.norm(T2 - T1))
    x1 = float(np.linalg.norm(line[2] - B1) / np.linalg.norm(B2 - B1))
    return lambda w: x0 + (x1 - x0) * w


XI1, XI2 = xh_of(I1), xh_of(I2)


def wmid(line):
    return float(np.linalg.norm(line[1] - line[0]) / np.linalg.norm(line[2] - line[0]))


WM1, WM2 = wmid(I1), wmid(I2)


def zline(zs, wm, w):
    return float(np.interp(w, [0, wm, 1], zs))


def zs(xh, w):
    """슬래브 상면 EL"""
    a, b = zline(Z_I1, WM1, w), zline(Z_I2, WM2, w)
    x1, x2 = XI1(w), XI2(w)
    return a + (b - a) * (xh - x1) / (x2 - x1)


def wcl(xh):
    return WM1 + (WM2 - WM1) * (xh - XI1(0.5)) / (XI2(0.5) - XI1(0.5))


def p3(xh, w, z):
    p = plan(xh, w)
    return np.array([p[0], p[1], z])


# ---------------------------------------------------------------- 메시
FACES = []   # (layer, [pts...])


def add_sweep(layer, sections, caps=True):
    n = len(sections[0])
    for a, b in zip(sections, sections[1:]):
        for i in range(n):
            j = (i + 1) % n
            FACES.append((layer, [a[i], a[j], b[j], b[i]]))
    if caps:
        for sec in (sections[0], sections[-1]):
            add_poly(layer, sec)


def add_poly(layer, pts):
    if len(pts) <= 4:
        FACES.append((layer, list(pts)))
        return
    for tri in mapbox_earcut_3d([ezdxf.math.Vec3(p) for p in pts]):
        FACES.append((layer, [np.array(v.xyz) for v in tri]))


def sweep_x(layer, prof, x0=0.0, x1=1.0, n=NX):
    """교축방향 sweep. prof(xh) -> [(s(폭방향 m, top 기준), dz)]"""
    secs = []
    for i in range(n + 1):
        xh = x0 + (x1 - x0) * i / n
        W = width(xh)
        secs.append([p3(xh, s / W, zs(xh, s / W) + dz) for s, dz in prof(xh, W)])
    add_sweep(layer, secs)


def sweep_w(layer, prof, n=NW):
    """폭방향 sweep. prof(w) -> [(xh, z)]"""
    add_sweep(layer, [[p3(xh, w, z) for xh, z in prof(w)] for w in np.linspace(0, 1, n + 1)])


def cyl(layer, c, r, z0, z1, n=16):
    ring = [np.array([c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)])
            for k in range(n)]
    add_sweep(layer, [[np.array([p[0], p[1], z]) for p in ring] for z in (z0, z1)])


# ---------------------------------------------------------------- 부재
def build():
    sweep_x("3DF-슬래브", lambda xh, W: [(0, -SLAB_T), (W, -SLAB_T), (W, 0), (0, 0)])

    def cl(xh, W):
        return wcl(xh) * W
    sweep_x("3DF-포장", lambda xh, W: [(0.45, 0), (cl(xh, W) - 0.305, 0),
                                      (cl(xh, W) - 0.305, PAVE_T), (0.45, PAVE_T)])
    sweep_x("3DF-포장", lambda xh, W: [(cl(xh, W) + 0.305, 0), (W - 0.45, 0),
                                      (W - 0.45, PAVE_T), (cl(xh, W) + 0.305, PAVE_T)])
    sweep_x("3DF-방호벽", lambda xh, W: BARRIER)
    sweep_x("3DF-방호벽", lambda xh, W: [(W - s, dz) for s, dz in BARRIER])
    med = [(-s, dz) for s, dz in MEDIAN_HALF] + [(s, dz) for s, dz in MEDIAN_HALF[::-1]]
    sweep_x("3DF-방호벽", lambda xh, W: [(cl(xh, W) + s, dz) for s, dz in med])

    ft = FOOT_BOT + FOOT_T
    for side in (1, 2):
        xi = XI1 if side == 1 else XI2
        xo = (lambda w: 0.0) if side == 1 else (lambda w: 1.0)
        sg = 1 if side == 1 else -1          # 경간 안쪽 방향(+xh) 부호
        L = span_len
        # 벽체
        sweep_w("3DF-벽체", lambda w: [(xo(w), ft), (xi(w), ft),
                                     (xi(w), zs(xi(w), w) - SLAB_T), (xo(w), zs(xo(w), w) - SLAB_T)])
        # 헌치 300x900
        sweep_w("3DF-벽체", lambda w: [(xi(w), zs(xi(w), w) - SLAB_T),
                                     (xi(w) + sg * HAUNCH_H / L(w), zs(xi(w) + sg * HAUNCH_H / L(w), w) - SLAB_T),
                                     (xi(w), zs(xi(w), w) - SLAB_T - HAUNCH_V)])
        # 접속슬래브 받침 코벨 (외측)
        sweep_w("3DF-벽체", lambda w: [(xo(w) - sg * o / L(w), zs(xo(w), w) - d) for o, d in CORBEL])
        # 기초 / 버림
        heel = lambda w, e=0.0: xo(w) - sg * (FOOT_HEEL + e) / L(w)
        toe = lambda w, e=0.0: xi(w) + sg * (FOOT_TOE + e) / L(w)
        sweep_w("3DF-기초", lambda w: [(heel(w), FOOT_BOT), (toe(w), FOOT_BOT), (toe(w), ft), (heel(w), ft)])
        sweep_w("3DF-기초", lambda w: [(heel(w, 0.1), FOOT_BOT - LEAN_T), (toe(w, 0.1), FOOT_BOT - LEAN_T),
                                     (toe(w, 0.1), FOOT_BOT), (heel(w, 0.1), FOOT_BOT)], n=1)
        # 강관말뚝 Φ508
        pitch, plen = PILES[side]
        wd = width(xo(0.5))
        for k in range(9):
            for r in PILE_ROWS:
                w = (0.65 + k * pitch) / wd
                xh = heel(w) + sg * r / L(w)
                cyl("3DF-말뚝", plan(xh, w), PILE_D / 2, FOOT_BOT - plen, FOOT_BOT)


LAYERS = {"3DF-슬래브": 8, "3DF-포장": 250, "3DF-방호벽": 9, "3DF-벽체": 5,
          "3DF-기초": 4, "3DF-말뚝": 6, "3DF-주기": 2}


def to_cad(p):
    return (p[0] * 1000 + OX, p[1] * 1000 + OY, p[2] * 1000)


def write(doc):
    msp = doc.modelspace()
    for name, color in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    for layer, pts in FACES:
        q = [to_cad(p) for p in pts]
        if len(q) == 3:
            q.append(q[2])
        msp.add_3dface(q, dxfattribs={"layer": layer})
    note = ("창덕교(라멘교) 3D FACE 모델 - 슬래브, 포장, 방호벽, 벽체(헌치·코벨), 기초, 강관말뚝\\P"
            "좌표: x=(Y-209100)×1000+2630000, y=(X-309130)×1000+70000, z=EL×1000 [mm]")
    m = msp.add_mtext(note, dxfattribs={"layer": "3DF-주기", "char_height": 500,
                                        "insert": (2640000, 102000, 0)})
    m.dxf.width = 45000


def main():
    build()
    print(f"3DFACE={len(FACES)}  span(top)={span_len(0):.3f} span(bot)={span_len(1):.3f} "
          f"width(A1)={width(0):.3f} width(A2)={width(1):.3f} wm={WM1:.3f}/{WM2:.3f}")
    doc, _ = recover.readfile(sys.argv[1])
    write(doc)
    doc.saveas(sys.argv[2])
    if len(sys.argv) > 3:
        d3 = ezdxf.new(doc.dxfversion)
        write(d3)
        d3.saveas(sys.argv[3])


if __name__ == "__main__":
    main()
