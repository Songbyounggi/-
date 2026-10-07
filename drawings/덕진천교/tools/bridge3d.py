"""덕진천교 3D 형상 생성 (단위: m, 좌표: E=Y측량좌표, N=X측량좌표, Z=EL)
근거 도면: 교량받침배치도(받침좌표), PSC BEAM도, 슬래브 일반도, 교대/교각 일반도
"""
import math
import numpy as np

# ---------------- 원자료 (교량받침 좌표표, 받침배치도) ----------------
# (X=북, Y=동, EL)
A1 = [(309037.4886, 209209.4165, 112.8595), (309039.5321, 209211.0758, 112.7032),
      (309041.5763, 209212.7355, 112.5468), (309043.6212, 209214.3956, 112.3904),
      (309045.6668, 209216.0562, 112.2339), (309047.7131, 209217.7172, 112.0773),
      (309049.7602, 209219.3788, 111.9206), (309051.8081, 209221.0408, 111.7638)]
P1F = [(309056.7770, 209181.4179, 112.6985), (309058.7938, 209183.0587, 112.5426),
       (309060.8106, 209184.6996, 112.3867), (309062.8274, 209186.3405, 112.2308),
       (309064.8443, 209187.9814, 112.0749), (309066.8611, 209189.6223, 111.9189),
       (309068.8779, 209191.2632, 111.7630), (309070.8947, 209192.9041, 111.6071)]
P1B = [(309057.4443, 209180.5975, 112.6823), (309059.4615, 209182.2378, 112.5253),
       (309061.4788, 209183.8782, 112.3692), (309063.4960, 209185.5186, 112.2131),
       (309065.5132, 209187.1589, 112.0570), (309067.5305, 209188.7992, 111.9009),
       (309069.5478, 209190.4396, 111.7448), (309071.5650, 209192.0799, 111.5887)]
A2 = [(309080.9243, 209156.0141, 112.0775), (309082.9648, 209157.6769, 111.9118),
      (309085.0059, 209159.3404, 111.7459), (309087.0475, 209161.0044, 111.5797),
      (309089.0898, 209162.6691, 111.4131), (309091.1326, 209164.3344, 111.2453),
      (309093.1761, 209166.0003, 111.0780), (309095.2202, 209167.6669, 110.9104)]
# 선형 중심 (받침배치도)
CL_A1 = (309045.361013, 209216.594211)
CL_P1 = (309065.178268, 209187.569682)
CL_A2 = (309089.583937, 209162.234078)
ROAD_EL_A1_CL = 114.982            # 교대 일반도(1) 정면도 "℄ OF ROAD (EL.114.982)"

ORIGIN = np.array([209187.569682, 309065.178268])   # P1 중심 (E, N)


def en(p):
    """(X북, Y동) -> 로컬 (e, n) [m]"""
    return np.array([p[1], p[0]]) - ORIGIN


def pt3(p):
    v = en(p)
    return np.array([v[0], v[1], p[2]])


A1p, P1Fp, P1Bp, A2p = [np.array([pt3(p) for p in g]) for g in (A1, P1F, P1B, A2)]

# ---------------- 단면 치수 ----------------
GIRDER_H = 2.2
SLAB_T = 0.24
PAVE_T = 0.08
OVERHANG = 1.1                      # (20.400-18.200)/2
GIRDER_EXT = 0.40                   # 받침 중심 ~ 거더 단부
# PSC I형 거더 중앙부 단면 (폭방향 y, 높이 z) - PSC BEAM도 '중앙부'
GIRDER_SEC = [(-0.36, 0.0), (0.36, 0.0), (0.36, 0.25), (0.11, 0.49), (0.11, 1.89), (0.38, 2.0),
              (0.38, 2.2), (-0.38, 2.2), (-0.38, 2.0), (-0.11, 1.89), (-0.11, 0.49), (-0.36, 0.25)]
GIRDER_CAP = [[0, 1, 2, 11], [11, 2, 3, 10], [10, 3, 4, 9], [9, 4, 5, 8], [8, 5, 6, 7]]  # 볼록 분할
# 방호벽 단면 (외측면 0 → 내측 +, 슬래브 상면 기준 높이) - 슬래브 일반도 방호벽 상세
BARRIER = [(0.0, 0.0), (0.42, 0.0), (0.42, 0.205), (0.35, 0.38), (0.23, 1.18), (0.0, 1.18)]
# 중분대 (중심 기준 좌우 대칭)
MEDIAN = [(-0.305, 0.0), (0.305, 0.0), (0.305, 0.155), (0.18, 0.33), (0.075, 1.35),
          (-0.075, 1.35), (-0.18, 0.33), (-0.305, 0.155)]


# ---------------- 메쉬 컨테이너 ----------------
class Part:
    def __init__(self, name, layer, color):
        self.name, self.layer, self.color = name, layer, color
        self.bias = 0.0      # 화가 알고리즘 깊이 보정 (+ 이면 나중에 그림)
        self.in_view = True
        self.faces = []      # list of (verts Nx3, edge_mask list[bool])  edge i = v[i]->v[i+1]

    def face(self, verts, edges=None):
        v = np.asarray(verts, float)
        if edges is None:
            edges = [True] * len(v)
        self.faces.append((v, list(edges)))


PARTS = []


def part(name, layer, color):
    p = Part(name, layer, color)
    PARTS.append(p)
    return p


def box(p, base, u, v, w, dims, z0, z1_fn=None, z1=None):
    """u,v 평면 직사각형(중심 base, 반폭 dims) 을 z0~z1 로 압출. z1_fn(xy)로 경사 상면 가능"""
    a, b = dims
    corners = [base - a * u - b * v, base + a * u - b * v, base + a * u + b * v, base - a * u + b * v]
    prism(p, corners, z0, z1_fn if z1_fn else (lambda q: z1))


def prism(p, poly, zbot, ztop, bot_fn=None):
    """평면 다각형(볼록) 수직 압출. zbot/ztop: 상수 또는 함수"""
    zb = (lambda q: zbot) if not callable(zbot) else zbot
    zt = (lambda q: ztop) if not callable(ztop) else ztop
    n = len(poly)
    top = [np.array([q[0], q[1], zt(q)]) for q in poly]
    bot = [np.array([q[0], q[1], zb(q)]) for q in poly]
    p.face(top)
    p.face(bot[::-1])
    for i in range(n):
        j = (i + 1) % n
        p.face([bot[i], bot[j], top[j], top[i]])


def cylinder(p, c, r, z0, z1, n=16):
    pts = [c + r * np.array([math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)]) for k in range(n)]
    top = [np.array([q[0], q[1], z1]) for q in pts]
    bot = [np.array([q[0], q[1], z0]) for q in pts]
    p.face(top)
    p.face(bot[::-1])
    for i in range(n):
        j = (i + 1) % n
        p.face([bot[i], bot[j], top[j], top[i]], [True, False, True, False])


def sweep(p, frames, profile, closed=True, caps=None):
    """frames: [(origin3, ydir3, zdir3)] 단면 profile [(y,z)] 을 연결. 중간 분할선은 숨김"""
    rings = [[o + y * yd + z * zd for (y, z) in profile] for (o, yd, zd) in frames]
    m = len(profile)
    nseg = len(rings) - 1
    for k in range(nseg):
        for i in range(m if closed else m - 1):
            j = (i + 1) % m
            p.face([rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]],
                   [k == 0, True, k == nseg - 1, True])
    if caps:
        for idxs in caps:
            # 단면 볼록 분할: 내부 분할선 숨김
            for r, rev in ((rings[0], True), (rings[-1], False)):
                vs = [r[i] for i in idxs]
                ed = []
                for a in range(len(idxs)):
                    i, j = idxs[a], idxs[(a + 1) % len(idxs)]
                    ed.append(abs(i - j) in (1, m - 1))
                if rev:
                    vs = vs[::-1]
                    ed = ed[::-1][1:] + ed[::-1][:1]
                p.face(vs, ed)


# ---------------- 선형 (원곡선 적합) ----------------
def circle3(a, b, c):
    a, b, c = map(np.asarray, (a, b, c))
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    ux = ((a @ a) * (b[1] - c[1]) + (b @ b) * (c[1] - a[1]) + (c @ c) * (a[1] - b[1])) / d
    uy = ((a @ a) * (c[0] - b[0]) + (b @ b) * (a[0] - c[0]) + (c @ c) * (b[0] - a[0])) / d
    cen = np.array([ux, uy])
    return cen, float(np.linalg.norm(a - cen))


cA1, cP1, cA2 = en(CL_A1), en(CL_P1), en(CL_A2)
CEN, RAD = circle3(cA1, cP1, cA2)
ang = lambda q: math.atan2(q[1] - CEN[1], q[0] - CEN[0])
th_A1, th_A2 = ang(cA1), ang(cA2)
SGN = 1 if ((th_A2 - th_A1 + math.pi) % (2 * math.pi) - math.pi) > 0 else -1


def roff(q):
    """반경방향 오프셋 (외측 +)"""
    return float(np.linalg.norm(np.asarray(q[:2]) - CEN) - RAD)


def on_curve(th, d):
    return CEN + (RAD + d) * np.array([math.cos(th), math.sin(th)])


def rdir(th):
    return np.array([math.cos(th), math.sin(th)])


# ---------------- 받침면 평면 (경간별 최소자승) ----------------
def fit_plane(pts):
    A = np.c_[np.ones(len(pts)), pts[:, 0], pts[:, 1]]
    return np.linalg.lstsq(A, pts[:, 2], rcond=None)[0]


PL1 = fit_plane(np.vstack([A1p, P1Fp]))
PL2 = fit_plane(np.vstack([P1Bp, A2p]))


def side_of_p1(q):
    """P1 지지선 기준 A1측이면 True"""
    u = support_dir(np.vstack([P1Fp, P1Bp]))
    nrm = np.array([-u[1], u[0]])
    return np.sign((np.asarray(q[:2]) - cP1) @ nrm) == np.sign((cA1 - cP1) @ nrm)


def support_dir(pts):
    d = pts[-1, :2] - pts[0, :2]
    return d / np.linalg.norm(d)


def z_brg(q):
    c = PL1 if side_of_p1(q) else PL2
    return c[0] + c[1] * q[0] + c[2] * q[1]


DECK_ADD = ROAD_EL_A1_CL - z_brg(cA1)          # 받침면 → 노면 (거더+헌치+슬래브+포장)
HAUNCH = DECK_ADD - GIRDER_H - SLAB_T - PAVE_T


def z_road(q):
    return z_brg(q) + DECK_ADD


def z_slab_top(q):
    return z_road(q) - PAVE_T


# ---------------- 데크 경계 ----------------
d_g1 = np.mean([roff(p) for p in np.vstack([A1p[:1], P1Fp[:1], P1Bp[:1], A2p[:1]])])
d_g8 = np.mean([roff(p) for p in np.vstack([A1p[-1:], P1Fp[-1:], P1Bp[-1:], A2p[-1:]])])
s18 = np.sign(d_g8 - d_g1)
D_EDGE_1 = d_g1 - s18 * OVERHANG
D_EDGE_8 = d_g8 + s18 * OVERHANG


class Support:
    def __init__(self, pts, toward):
        self.pts = pts
        self.p0 = pts[:, :2].mean(axis=0)
        self.u = support_dir(pts)
        n = np.array([-self.u[1], self.u[0]])
        self.n_out = n if (toward - self.p0) @ n < 0 else -n     # 교량 바깥쪽(배면) 방향

    def line_hit(self, d, shift):
        """반경오프셋 d 곡선과 (지지선 + shift*n_out) 교점의 각도"""
        base = self.p0 + shift * self.n_out
        f = lambda th: (on_curve(th, d) - base) @ self.n_out
        th0 = ang(self.p0)
        a, b = th0 - 0.3, th0 + 0.3
        for _ in range(80):
            m = (a + b) / 2
            if np.sign(f(a)) == np.sign(f(m)):
                a = m
            else:
                b = m
        return (a + b) / 2

    def s_of(self, q):
        return (np.asarray(q[:2]) - self.p0) @ self.u


SA1 = Support(A1p, cP1)
SA2 = Support(A2p, cP1)
SP1 = Support(np.vstack([P1Fp, P1Bp]), cA1)
DECK_END = 0.50       # 받침중심 → 슬래브 단부 (신축이음)


def deck_grid(d_list, nseg=70):
    """각 반경오프셋에 대해 A1 단부~A2 단부 사이 곡선 점열"""
    out = []
    for d in d_list:
        t0, t1 = SA1.line_hit(d, DECK_END), SA2.line_hit(d, DECK_END)
        out.append([on_curve(t0 + (t1 - t0) * k / nseg, d) for k in range(nseg + 1)])
    return out


# ---------------- 부재 생성 ----------------
def build():
    PARTS.clear()
    lo, hi = sorted([D_EDGE_1, D_EDGE_8])
    sgn_in = 1   # lo 쪽 방호벽 내측은 +d 방향

    # 슬래브 (상면/하면/측면)
    slab = part("슬래브", "3D-슬래브", (205, 205, 200))
    slab_top = part("슬래브 상면", "3D-슬래브", (205, 205, 200))
    slab_top.in_view = False          # 포장·방호벽에 가려짐 (조감도 투영 제외)
    ds = list(np.linspace(lo, hi, 9))
    G = deck_grid(ds)
    nrow, ncol = len(ds), len(G[0])
    T = [[np.array([*q, z_slab_top(q)]) for q in row] for row in G]
    B = [[np.array([*q, z_slab_top(q) - SLAB_T]) for q in row] for row in G]
    for i in range(nrow - 1):
        for k in range(ncol - 1):
            slab_top.face([T[i][k], T[i][k + 1], T[i + 1][k + 1], T[i + 1][k]], [k == 0, i == nrow - 2, k == ncol - 2, i == 0])
            slab.face([B[i][k], B[i + 1][k], B[i + 1][k + 1], B[i][k + 1]], [i == 0, k == ncol - 2, i == nrow - 2, k == 0])
    for i in (0, nrow - 1):
        for k in range(ncol - 1):
            slab.face([B[i][k], B[i][k + 1], T[i][k + 1], T[i][k]], [True, k == ncol - 2, True, k == 0])
    for k in (0, ncol - 1):
        for i in range(nrow - 1):
            slab.face([B[i][k], B[i + 1][k], T[i + 1][k], T[i][k]], [True, i == nrow - 2, True, i == 0])

    # 방호벽 / 중분대 / 포장
    def rail(name, d_base, prof, inward):
        pr = part(name, "3D-방호벽", (235, 235, 228))
        row = deck_grid([d_base])[0]
        frames = []
        for k, q in enumerate(row):
            th = ang(q)
            o = np.array([*q, z_slab_top(q)])
            y = np.array([*(rdir(th) * inward), 0.0])
            frames.append((o, y, np.array([0, 0, 1.0])))
        caps = [list(range(len(prof)))] if len(prof) <= 6 else [[0, 1, 2, 7], [7, 2, 3, 6], [6, 3, 4, 5]]
        sweep(pr, frames, prof, caps=caps)
        return pr

    rail("방호벽(좌)", lo, BARRIER, 1)
    rail("방호벽(우)", hi, BARRIER, -1)
    rail("중분대", 0.0, MEDIAN, 1)
    pave = part("포장", "3D-포장", (95, 95, 98))
    pave.bias = 0.6
    for a, b in ((lo + 0.42, -0.305), (0.305, hi - 0.42)):
        g = deck_grid([a, b])
        for k in range(len(g[0]) - 1):
            q = [g[0][k], g[0][k + 1], g[1][k + 1], g[1][k]]
            pave.face([np.array([*v, z_road(v)]) for v in q], [k == 0, True, k == len(g[0]) - 2, True])

    # 차선 표시 (노면 위 얇은 띠, 3m 도색 / 5m 간격)
    lane = part("차선", "3D-차선", (250, 250, 250))
    lane.bias = 1.2
    # 길어깨선(실선) / 차로경계선(점선)
    for d, dashed in ((lo + 0.42 + 1.5, False), (lo + 0.42 + 1.5 + 3.25, True),
                      (0.305 + 2.195, False), (0.305 + 2.195 + 3.25, True)):
        g = deck_grid([d - 0.075, d + 0.075], 600)
        seglen = np.linalg.norm(g[0][1] - g[0][0])
        on = max(1, int(round((3.0 if dashed else 2.0) / seglen)))
        off = max(1, int(round(5.0 / seglen))) if dashed else 0
        k = 0
        while k < len(g[0]) - 1:
            k2 = min(len(g[0]) - 1, k + on)
            q = [g[0][k], g[0][k2], g[1][k2], g[1][k]]
            lane.face([np.array([*v, z_road(v) + 0.01]) for v in q], [False] * 4)
            k = k2 + off

    # PSC 거더
    gir = part("PSC 거더", "3D-거더", (215, 210, 196))
    spans = [(A1p, P1Fp), (P1Bp, A2p)]
    for (S0, S1) in spans:
        for i in range(8):
            a, b = S0[i], S1[i]
            t = (b[:2] - a[:2]) / np.linalg.norm(b[:2] - a[:2])
            L = np.linalg.norm(b[:2] - a[:2])
            y = np.array([-t[1], t[0], 0.0])
            frames = []
            for s in np.linspace(-GIRDER_EXT, L + GIRDER_EXT, 24):
                xy = a[:2] + t * s
                z = a[2] + (b[2] - a[2]) * s / L
                frames.append((np.array([*xy, z]), y, np.array([0, 0, 1.0])))
            sweep(gir, frames, GIRDER_SEC, caps=GIRDER_CAP)

    # 가로보 (지점부, 중앙부)
    xb = part("가로보", "3D-가로보", (190, 190, 185))

    def crossbeam(S0, S1, frac, thick, height, top_drop=0.0):
        for i in range(7):
            pa = S0[i] + (S1[i] - S0[i]) * frac
            pb = S0[i + 1] + (S1[i + 1] - S0[i + 1]) * frac
            t = (S1[i][:2] - S0[i][:2]);
            t = t / np.linalg.norm(t)
            v = (pb[:2] - pa[:2])
            L = np.linalg.norm(v)
            vu = v / L
            a0 = pa[:2] + vu * 0.11
            a1 = pb[:2] - vu * 0.11
            poly = [a0 - t * thick / 2, a1 - t * thick / 2, a1 + t * thick / 2, a0 + t * thick / 2]
            zt = lambda q, pa=pa, pb=pb, a0=a0, L=L, vu=vu: pa[2] + (pb[2] - pa[2]) * ((q - pa[:2]) @ vu) / L + GIRDER_H - top_drop
            zb = lambda q, zt=zt: zt(q) - height
            prism(xb, poly, zb, zt)

    L1 = np.linalg.norm(P1Fp[0, :2] - A1p[0, :2])
    L2 = np.linalg.norm(A2p[0, :2] - P1Bp[0, :2])
    crossbeam(A1p, P1Fp, -0.0 / L1, 0.5, 0.70)                 # 신축이음부 0.70m (슬래브 일반도 NOTE 9)
    crossbeam(A1p, P1Fp, 0.5, 0.30, 1.95)
    crossbeam(P1Bp, A2p, 0.5, 0.30, 1.95)
    crossbeam(P1Bp, A2p, 1.0, 0.5, 0.70)
    # P1 연속지점부 가로보 (전·후열 사이 일체)
    for i in range(7):
        q = [P1Fp[i, :2], P1Fp[i + 1, :2], P1Bp[i + 1, :2], P1Bp[i, :2]]
        c = np.mean(q, axis=0)
        q = [c + (v - c) * np.array([1, 1]) for v in q]
        # 전후 0.35m 확장
        tF = (P1Fp[i, :2] - P1Bp[i, :2]); tF = tF / np.linalg.norm(tF)
        poly = [q[0] + tF * 0.35, q[1] + tF * 0.35, q[2] - tF * 0.35, q[3] - tF * 0.35]
        zt = lambda v: z_brg(v) + GIRDER_H
        prism(xb, poly, lambda v: zt(v) - 1.95, zt)

    # 교량받침 + 받침대
    brg = part("교량받침", "3D-받침", (70, 70, 75))
    ped = part("받침 기초부", "3D-하부", (175, 175, 170))
    SEAT_DROP = 0.35
    for S, sup in ((A1p, SA1), (P1Fp, SP1), (P1Bp, SP1), (A2p, SA2)):
        for p in S:
            c = p[:2]
            box(brg, c, sup.u, sup.n_out, 0, (0.30, 0.30), p[2] - 0.15, z1=p[2])
            box(ped, c, sup.u, sup.n_out, 0, (0.42, 0.42), p[2] - SEAT_DROP, z1=p[2] - 0.15)

    # ---------------- 교대 ----------------
    sub = part("교대", "3D-교대", (180, 180, 175))
    pil = part("말뚝", "3D-말뚝", (150, 120, 95))
    ftg = part("기초", "3D-기초", (165, 165, 158))

    def abutment(sup, ftop, fthk, toe, heel, piles, pile_L, pile_ds, pile_rows):
        u, n = sup.u, sup.n_out
        # 슬래브 단부선과 데크 양단 교점 → 교대 폭
        e_lo = on_curve(sup.line_hit(lo, 0), lo)
        e_hi = on_curve(sup.line_hit(hi, 0), hi)
        s_lo, s_hi = sorted([sup.s_of(e_lo), sup.s_of(e_hi)])
        s_lo -= 0.25
        s_hi += 0.25
        P = lambda s, m: sup.p0 + u * s + n * m
        front, back, parapet = -0.79, 1.41, 0.91
        seat = lambda q: z_brg(q) - SEAT_DROP
        road = lambda q: z_road(q)
        # 기초
        prism(ftg, [P(s_lo, front - toe), P(s_hi, front - toe), P(s_hi, back + heel), P(s_lo, back + heel)],
              ftop - fthk, ftop)
        # 벽체 (교좌면까지)
        prism(sub, [P(s_lo, front), P(s_hi, front), P(s_hi, parapet), P(s_lo, parapet)], ftop, seat)
        # 흉벽
        prism(sub, [P(s_lo, parapet), P(s_hi, parapet), P(s_hi, back), P(s_lo, back)], ftop, road)
        # 날개벽 (도로 접선방향, 길이 10m)
        for s_end, d_edge in ((s_lo, None), (s_hi, None)):
            th = ang(P(s_end, back))
            tang = np.array([-math.sin(th), math.cos(th)])
            if tang @ n < 0:
                tang = -tang
            side = np.sign(s_end - (s_lo + s_hi) / 2)
            inner = -u * side   # 벽 두께는 교량 안쪽으로
            w0 = P(s_end, back) - n * 0.0
            w0 = P(s_end, front + 0.0) + inner * 0.0
            # 날개벽은 흉벽 배면에서 시작
            st = P(s_end, back)
            en_ = st + tang * 10.0
            t_in = np.array([-tang[1], tang[0]])
            if t_in @ inner < 0:
                t_in = -t_in
            poly = [st, en_, en_ + t_in * 0.5, st + t_in * 0.5]
            ztop = lambda q: road(q) + 0.0
            L0 = st
            zbot = lambda q, L0=L0, tang=tang: ftop + max(0.0, ((q - L0) @ tang)) / 10.0 * (road(L0) - 3.0 - ftop) \
                if ((q - L0) @ tang) > 0.5 else ftop
            # 날개벽을 6분할하여 하면 경사 표현
            for k in range(6):
                a0, a1 = k / 6, (k + 1) / 6
                q = [st + (en_ - st) * a0, st + (en_ - st) * a1, st + (en_ - st) * a1 + t_in * 0.5, st + (en_ - st) * a0 + t_in * 0.5]
                zb0 = ftop + (road(st) - 3.0 - ftop) * max(0, a0 - 0.15) / 0.85
                zb1 = ftop + (road(st) - 3.0 - ftop) * max(0, a1 - 0.15) / 0.85
                top = [np.array([*v, ztop(v)]) for v in q]
                bot = [np.array([*q[0], zb0]), np.array([*q[1], zb1]), np.array([*q[2], zb1]), np.array([*q[3], zb0])]
                sub.face(top, [False, True, False, True] if 0 < k < 5 else [k == 0, True, k == 5, True])
                sub.face(bot[::-1])
                for i in range(4):
                    j = (i + 1) % 4
                    if (i == 3 and k > 0) or (i == 1 and k < 5):
                        continue
                    sub.face([bot[i], bot[j], top[j], top[i]])
        # 말뚝
        ns, nr = piles
        s_mid = (s_lo + s_hi) / 2
        for a in range(ns):
            s = s_mid + (a - (ns - 1) / 2) * pile_ds
            for m in pile_rows:
                cylinder(pil, P(s, m), 0.254, ftop - fthk - pile_L, ftop - fthk, 12)

    # A1: 기초 8.4m (전면 2.1 / 벽체 2.2 / 배면 4.1), 두께 2.1, EL.101.982, 말뚝 14x6 φ508 L=7.3m
    abutment(SA1, 101.982, 2.1, 2.1, 4.1, (14, 6), 7.3, 1.52,
             [1.41 + 4.1 - 0.65 - k for k in (0, 1.9, 3.2, 4.5, 5.8, 7.1)])
    # A2: 기초 6.9m (1.5 / 2.2 / 3.2), 두께 1.5, EL.104.150, 말뚝 14x4 φ508 L=6.7m
    abutment(SA2, 104.150, 1.5, 1.5, 3.2, (14, 4), 6.7, 1.53,
             [1.41 + 3.2 - 1.5 - 1.3 * k for k in range(4)])

    # ---------------- 교각 P1 ----------------
    pier = part("교각", "3D-교각", (182, 182, 176))
    u, n = SP1.u, SP1.n_out
    sb = [SP1.s_of(p) for p in np.vstack([P1Fp, P1Bp])]
    s0, s1 = min(sb) - 0.9, max(sb) + 0.9
    pc = SP1.p0 + n * ((np.vstack([P1Fp, P1Bp])[:, :2] - SP1.p0) @ n).mean()
    P = lambda s, m: pc + u * s + n * m
    top = lambda q: z_brg(q) - SEAT_DROP if False else (PL1[0] + PL1[1] * q[0] + PL1[2] * q[1] + PL2[0] + PL2[1] * q[0] + PL2[2] * q[1]) / 2 - SEAT_DROP
    Lc = s1 - s0
    prof = [(0.0, 1.25), (3.5, 2.5), (Lc - 3.5, 2.5), (Lc, 1.25)]   # (s, 깊이)
    for (sa, da), (sb_, db) in zip(prof[:-1], prof[1:]):
        poly = [P(s0 + sa, -1.25), P(s0 + sb_, -1.25), P(s0 + sb_, 1.25), P(s0 + sa, 1.25)]

        def zb(q, sa=sa, sb_=sb_, da=da, db=db):
            s = (q - pc) @ u - s0
            f = (s - sa) / (sb_ - sa)
            return top(q) - (da + (db - da) * f)
        prism(pier, poly, zb, top)
    FBOT = 98.083
    for sc in (s0 + 4.5, s1 - 4.5):
        c = P(sc, 0)
        cb = top(c) - 2.5
        cylinder(pier, c, 0.9, FBOT + 2.0, cb, 24)
        box(ftg, c, u, n, 0, (3.3, 3.3), FBOT, z1=FBOT + 2.0)
    return PARTS


if __name__ == "__main__":
    build()
    print("R=", RAD, "haunch=", HAUNCH, "edges", D_EDGE_1, D_EDGE_8)
    for p in PARTS:
        print(p.name, len(p.faces))
