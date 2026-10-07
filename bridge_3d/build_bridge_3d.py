"""덕진천교 3D 솔리드 모델 생성 스크립트.

도면(교량일반도/받침배치도, 교대일반도, 교각구조도, PSC Beam도, 상부배치도)에서
추출한 치수와 받침 좌표로 교량 전체를 ACIS 3DSOLID 로 만들어
일반도(교대 일반도) DXF 의 모형공간에 추가한다.

usage: python3 build_bridge_3d.py <일반도.dxf> <out.dxf> [<out_3d_only.dxf>]

좌표: 측량좌표(X=북, Y=동, EL) [m] ->
      CAD x = (Y - 209150)*1000 + 135000, y = (X - 309030)*1000 + 30000, z = EL*1000 [mm]
"""
import math
import sys

import ezdxf
import numpy as np
from ezdxf import recover
from ezdxf.acis import api as acis
from ezdxf.render import MeshBuilder
from ezdxf.sections.acdsdata import new_acds_data_section

# ---------------------------------------------------------------- 원자료 (m)
# 받침 좌표표 (교량 일반도) : 번호 1..8 = 1번 거더(좌측, 높은 쪽) .. 8번 거더
SHOE = {
    "A1": [(309037.4886, 209209.4165, 112.8595), (309039.5321, 209211.0758, 112.7032),
           (309041.5763, 209212.7355, 112.5468), (309043.6212, 209214.3956, 112.3904),
           (309045.6668, 209216.0562, 112.2339), (309047.7131, 209217.7172, 112.0773),
           (309049.7602, 209219.3788, 111.9206), (309051.8081, 209221.0408, 111.7638)],
    "P1a": [(309056.7770, 209181.4179, 112.6985), (309058.7938, 209183.0587, 112.5426),
            (309060.8106, 209184.6996, 112.3867), (309062.8274, 209186.3405, 112.2308),
            (309064.8443, 209187.9814, 112.0749), (309066.8611, 209189.6223, 111.9189),
            (309068.8779, 209191.2632, 111.7630), (309070.8947, 209192.9041, 111.6071)],
    "P1b": [(309057.4443, 209180.5975, 112.6823), (309059.4615, 209182.2378, 112.5253),
            (309061.4788, 209183.8782, 112.3692), (309063.4960, 209185.5186, 112.2131),
            (309065.5132, 209187.1589, 112.0570), (309067.5305, 209188.7992, 111.9009),
            (309069.5478, 209190.4396, 111.7448), (309071.5650, 209192.0799, 111.5887)],
    "A2": [(309080.9243, 209156.0141, 112.0775), (309082.9648, 209157.6769, 111.9118),
           (309085.0059, 209159.3404, 111.7459), (309087.0475, 209161.0044, 111.5797),
           (309089.0898, 209162.6691, 111.4131), (309091.1326, 209164.3344, 111.2453),
           (309093.1761, 209166.0003, 111.0780), (309095.2202, 209167.6669, 110.9104)],
}
# 슬래브 모서리/중심선 좌표 (L = 1번 거더측 끝, C = 도로중심, R = 8번 거더측 끝)
DECK = {
    "A1": {"L": (309036.745334, 209209.602530), "C": (309045.361013, 209216.594211),
           "R": (309052.806609, 209222.636363)},
    "P1": {"L": (309056.683492, 209180.660175), "C": (309065.178268, 209187.569682),
           "R": (309072.509376, 209193.532681)},
    "A2": {"L": (309080.979878, 209155.226314), "C": (309089.583937, 209162.234078),
           "R": (309097.019571, 209168.290194)},
}
DECK_W = 20.400
CL_FROM_L = 10.950            # 450+1500+3250+3250+2195+305
SLAB_T, PAVE_T = 0.240, 0.080
SLAB_TOP_ABOVE_SHOE = 2.460   # 횡단면도: 거더하면 ~ 슬래브상면
GIRDER_LEN = 34.934           # 상부배치도 PSC BEAM 길이

# PSC I 거더 단면 (H=2.20m) : (반폭, 높이) 하단부터
GIRDER_HALF = [(0.360, 0.000), (0.360, 0.250), (0.110, 0.490), (0.110, 1.890),
               (0.380, 2.000), (0.380, 2.200)]
# 방호벽 (외측) : (s=외측면에서 안쪽 거리, dz=슬래브상면 기준)
BARRIER = [(0.0, 0.0), (0.45, 0.0), (0.45, 0.205), (0.33, 0.38), (0.26, 1.18), (0.0, 1.18)]
# 중앙분리대 반단면
MEDIAN_HALF = [(0.305, 0.0), (0.305, 0.123), (0.2865, 0.181), (0.22, 0.274),
               (0.1725, 0.3985), (0.0775, 1.3265), (0.0515, 1.35)]

# 교대 A1 (교대 일반도) ------------------------------------------------------
AB_LEN = 21.191                      # 벽체 길이 (사각 방향)
AB_END8_TO_SHOE8, AB_END1_TO_SHOE1 = 1.682, 1.068
AB_SHOE_V = 0.800 + 0.610            # 벽체 배면 ~ 받침 중심
A1_FOOT_BOT = 101.982
A1_SEAT = (111.570, 112.666)         # (8번측 끝, 1번측 끝)
A1_TOP = (114.439, 115.614)
FOOT_T, FOOT_HEEL, FOOT_TOE = 2.100, 4.100, 2.100
WALL_T, PARA_V0, PARA_V1, BRACKET_DROP = 2.200, 0.300, 0.800, 1.030
WING_T = 0.500
PILE_D, PILE_L = 0.508, 7.300
PILE_U = [0.678 + 1.520 * i for i in range(14)]
PILE_V = [-FOOT_HEEL + v for v in (0.65, 2.55, 3.85, 5.15, 6.45, 7.75)]
LEAN_T = 0.100

# 교각 P1 (교각 구조도, 도면좌표 mm) -------------------------------------------
COP_W = 2.500
COP_TOP = (-81720.0, -82812.0)       # u=-10 (1번측), u=+10 (8번측)
COP_BOT = [(10.0, -84062), (6.5, -85312), (4.5, -85312), (3.5, -84812),
           (-3.5, -84812), (-4.5, -85312), (-6.5, -85312), (-10.0, -84062)]
COL_U, COL_D = 5.5, 1.800
PF_B, PF_TOP, PF_BOT = 6.600, -93312.0, -95312.0

# ---------------------------------------------------------------- 좌표 변환
Y0, X0, OX, OY = 209150.0, 309030.0, 135000.0, 30000.0


def loc(X, Y, Z=0.0):
    """측량좌표 -> 로컬 m (x=동, y=북, z=EL)"""
    return np.array([Y - Y0, X - X0, Z], float)


def to_cad(p):
    return (p[0] * 1000 + OX, p[1] * 1000 + OY, p[2] * 1000)


Z = np.array([0.0, 0.0, 1.0])


def unit(v):
    return v / np.linalg.norm(v)


def hperp(d):
    """수평면 내 d 에 직각 (좌측)"""
    return unit(np.array([-d[1], d[0], 0.0]))


# ---------------------------------------------------------------- 메시 -> 솔리드
def sweep(sections, closed_caps=True):
    """동일 점수의 단면 폴리곤 리스트를 이어 닫힌 메시 생성"""
    n = len(sections[0])
    verts, faces = [], []
    for sec in sections:
        verts.extend(np.asarray(p, float) for p in sec)
    for k in range(len(sections) - 1):
        a0, b0 = k * n, (k + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces.append([a0 + i, a0 + j, b0 + j])
            faces.append([a0 + i, b0 + j, b0 + i])
    if closed_caps:
        faces.append(list(range(n))[::-1])
        last = (len(sections) - 1) * n
        faces.append([last + i for i in range(n)])
    # 외향 법선 보장 (부호 체적)
    vol = 0.0
    V = verts
    for f in faces:
        for t in range(1, len(f) - 1):
            vol += np.dot(V[f[0]], np.cross(V[f[t]], V[f[t + 1]]))
    if vol < 0:
        faces = [f[::-1] for f in faces]
    return verts, faces


def prism(base, vec):
    base = [np.asarray(p, float) for p in base]
    return sweep([base, [p + vec for p in base]])


def circle(c, r, n=24):
    return [c + np.array([r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), 0])
            for i in range(n)]


def box(c, ax, ay, lx, ly, z0, z1):
    """중심 c(수평), 수평축 ax/ay, 길이 lx/ly, z0~z1"""
    ax, ay = unit(ax), unit(ay)
    base = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        p = c + ax * sx * lx / 2 + ay * sy * ly / 2
        base.append(np.array([p[0], p[1], z0]))
    return prism(base, np.array([0, 0, z1 - z0]))


SOLIDS = []   # (layer, verts, faces)


def add(layer, mesh):
    SOLIDS.append((layer, *mesh))


# ---------------------------------------------------------------- 기하 계산
S = {k: [loc(*p) for p in v] for k, v in SHOE.items()}
D = {k: {s: loc(*p) for s, p in v.items()} for k, v in DECK.items()}


def circle3(p1, p2, p3):
    (x1, y1), (x2, y2), (x3, y3) = p1[:2], p2[:2], p3[:2]
    a = np.array([[x2 - x1, y2 - y1], [x3 - x1, y3 - y1]]) * 2
    b = np.array([x2**2 - x1**2 + y2**2 - y1**2, x3**2 - x1**2 + y3**2 - y1**2])
    c = np.linalg.solve(a, b)
    return c, float(np.linalg.norm(np.array([x1, y1]) - c))


def arc_pt(cen, r, pa, pb, t):
    a0 = math.atan2(pa[1] - cen[1], pa[0] - cen[0])
    a1 = math.atan2(pb[1] - cen[1], pb[0] - cen[0])
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    a = a0 + da * t
    return np.array([cen[0] + r * math.cos(a), cen[1] + r * math.sin(a), 0.0])


EDGE = {s: circle3(D["A1"][s], D["P1"][s], D["A2"][s]) for s in "LCR"}


# 슬래브 상면: 경간별 평면 z = a + b x + c y (받침 + 2.46 m)
def fit_plane(pts):
    A = np.array([[1, p[0], p[1]] for p in pts])
    z = np.array([p[2] + SLAB_TOP_ABOVE_SHOE for p in pts])
    coef, *_ = np.linalg.lstsq(A, z, rcond=None)
    return coef, float(np.abs(A @ coef - z).max())


PLANE1, RES1 = fit_plane(S["A1"] + S["P1a"])
PLANE2, RES2 = fit_plane(S["P1b"] + S["A2"])


def zplane(c, p):
    return c[0] + c[1] * p[0] + c[2] * p[1]


def deck_section(span, t):
    a, b = ("A1", "P1") if span == 1 else ("P1", "A2")
    L = arc_pt(*EDGE["L"], D[a]["L"], D[b]["L"], t)
    R = arc_pt(*EDGE["R"], D[a]["R"], D[b]["R"], t)
    if (span == 1 and t == 1.0) or (span == 2 and t == 0.0):
        zf = lambda p: 0.5 * (zplane(PLANE1, p) + zplane(PLANE2, p))
    else:
        c = PLANE1 if span == 1 else PLANE2
        zf = lambda p: zplane(c, p)
    return L, R, zf


def deck_sections(profile_fn, n=36):
    """profile_fn(W, sc) -> [(s, dz)] ; 경간1+2 연속 sweep 단면"""
    secs = []
    for span in (1, 2):
        for i in range(n + 1):
            if span == 2 and i == 0:
                continue
            t = i / n
            L, R, zf = deck_section(span, t)
            W = float(np.linalg.norm(R - L))
            e = (R - L) / W
            sc = CL_FROM_L / DECK_W * W
            sec = []
            for s, dz in profile_fn(W, sc):
                p = L + e * s
                sec.append(np.array([p[0], p[1], zf(p) + dz]))
            secs.append(sec)
    return secs


def build_superstructure():
    add("3D-상부-슬래브", sweep(deck_sections(
        lambda W, sc: [(0, -SLAB_T), (W, -SLAB_T), (W, 0), (0, 0)])))
    add("3D-상부-포장", sweep(deck_sections(
        lambda W, sc: [(0.45, 0), (sc - 0.305, 0), (sc - 0.305, PAVE_T), (0.45, PAVE_T)])))
    add("3D-상부-포장", sweep(deck_sections(
        lambda W, sc: [(sc + 0.305, 0), (W - 0.45, 0), (W - 0.45, PAVE_T), (sc + 0.305, PAVE_T)])))
    add("3D-상부-방호벽", sweep(deck_sections(lambda W, sc: BARRIER)))
    add("3D-상부-방호벽", sweep(deck_sections(
        lambda W, sc: [(W - s, dz) for s, dz in BARRIER])))
    med = [(-s, dz) for s, dz in MEDIAN_HALF] + [(s, dz) for s, dz in MEDIAN_HALF[::-1]]
    add("3D-상부-방호벽", sweep(deck_sections(lambda W, sc: [(sc + s, dz) for s, dz in med])))

    # PSC 거더 (받침 상면 = 거더 하면, 받침 사이 직선)
    girders = []
    for a, b, plane in (("A1", "P1a", PLANE1), ("P1b", "A2", PLANE2)):
        for P, Q in zip(S[a], S[b]):
            d = unit(Q - P)
            w = hperp(d)
            up = unit(np.cross(d, w))
            if up[2] < 0:
                up = -up
            ov = (GIRDER_LEN - np.linalg.norm(Q - P)) / 2
            sec = [(-hw, h) for hw, h in GIRDER_HALF] + [(hw, h) for hw, h in GIRDER_HALF[::-1]]
            s0 = [P - d * ov + w * y + up * h for y, h in sec]
            s1 = [Q + d * ov + w * y + up * h for y, h in sec]
            add("3D-상부-거더", sweep([s0, s1]))
            girders.append((P, Q, plane))

    # 가로보 : 받침선(단부) 2개 + 경간중앙 1개, 인접 거더 사이
    for k in (0, 8):
        span = girders[k:k + 8]
        for f, thick, lift in ((0.0, 0.40, 0.30), (0.5, 0.30, 0.50), (1.0, 0.40, 0.30)):
            for g in range(7):
                P1_, Q1_, plane = span[g]
                P2_, Q2_, _ = span[g + 1]
                A = P1_ + (Q1_ - P1_) * f
                B = P2_ + (Q2_ - P2_) * f
                ab = unit(np.array([B[0] - A[0], B[1] - A[1], 0]))
                A2_ = A + ab * 0.11
                B2_ = B - ab * 0.11
                d = unit((Q1_ - P1_) + (Q2_ - P2_))
                dh = unit(np.array([d[0], d[1], 0]))
                poly = [np.array([A2_[0], A2_[1], A[2] + lift]),
                        np.array([B2_[0], B2_[1], B[2] + lift]),
                        np.array([B2_[0], B2_[1], zplane(plane, B2_) - SLAB_T]),
                        np.array([A2_[0], A2_[1], zplane(plane, A2_) - SLAB_T])]
                poly = [p - dh * thick / 2 for p in poly]
                add("3D-상부-가로보", prism(poly, dh * thick))


# ---------------------------------------------------------------- 받침 / 하부
def shoe_axis(pts):
    u = unit(pts[0] - pts[7])          # 8번 -> 1번 방향
    u[2] = 0
    return unit(u)


def build_abutment(name, toward):
    shoes = S[name]
    u_dir = shoe_axis(shoes)                     # 8번측 -> 1번측
    n = hperp(u_dir)
    if np.dot(n, toward - shoes[3]) < 0:         # 경간쪽(+v)
        n = -n
    # 원점: 8번측 벽체 끝, 벽체 배면
    o = shoes[7] - u_dir * AB_END8_TO_SHOE8 - n * AB_SHOE_V
    o = np.array([o[0], o[1], 0.0])
    u_sh = [float(np.dot(p - o, u_dir)) for p in shoes]

    if name == "A1":
        seat, top, fb = A1_SEAT, A1_TOP, A1_FOOT_BOT
    else:
        # A2: A1 과 동일 형상, 받침고/받침-기초 높이를 A1 에서 가져와 맞춤
        s_lin = np.polyfit(u_sh, [p[2] for p in shoes], 1)
        seat = (np.polyval(s_lin, 0) - HSHOE, np.polyval(s_lin, AB_LEN) - HSHOE)
        top = (seat[0] + A1_TOP[0] - A1_SEAT[0], seat[1] + A1_TOP[1] - A1_SEAT[1])
        fb = seat[0] - (A1_SEAT[0] - A1_FOOT_BOT)
    ft = fb + FOOT_T

    def P(u, v, z):
        p = o + u_dir * u + n * v
        return np.array([p[0], p[1], z])

    lay = "3D-교대"
    # 기초 + 버림
    add(lay, prism([P(0, -FOOT_HEEL, fb), P(AB_LEN, -FOOT_HEEL, fb), P(AB_LEN, WALL_T + FOOT_TOE, fb),
                    P(0, WALL_T + FOOT_TOE, fb)], np.array([0, 0, FOOT_T])))
    add(lay, prism([P(-0.1, -FOOT_HEEL - 0.1, fb - LEAN_T), P(AB_LEN + 0.1, -FOOT_HEEL - 0.1, fb - LEAN_T),
                    P(AB_LEN + 0.1, WALL_T + FOOT_TOE + 0.1, fb - LEAN_T),
                    P(-0.1, WALL_T + FOOT_TOE + 0.1, fb - LEAN_T)], np.array([0, 0, LEAN_T])))

    # 벽체+흉벽 : 단면(v,z)을 u 방향으로 sweep (seat/top 선형 변화)
    def wall_sec(u):
        t = u / AB_LEN
        Sz = seat[0] + (seat[1] - seat[0]) * t
        Tz = top[0] + (top[1] - top[0]) * t
        vz = [(0, ft), (WALL_T, ft), (WALL_T, Sz), (PARA_V1, Sz), (PARA_V1, Tz),
              (PARA_V0, Tz), (PARA_V0, Tz - BRACKET_DROP), (0, Tz - BRACKET_DROP)]
        return [P(u, v, z) for v, z in vz]
    add(lay, sweep([wall_sec(0.0), wall_sec(AB_LEN)]))

    # 날개벽 (양단, 뒤채움측 기초 뒷굽 위)
    for u0, tz in ((0.0, top[0]), (AB_LEN - WING_T, top[1])):
        add(lay, prism([P(u0, -FOOT_HEEL, ft), P(u0 + WING_T, -FOOT_HEEL, ft),
                        P(u0 + WING_T, 0, ft), P(u0, 0, ft)], np.array([0, 0, tz - ft])))

    # 강관말뚝 Φ508 L=7.3m
    for u in PILE_U:
        for v in PILE_V:
            c = P(u, v, fb - PILE_L)
            add("3D-교대-말뚝", prism(circle(c, PILE_D / 2, 16), np.array([0, 0, PILE_L])))

    # 받침(받침+받침대) 블록
    for p in shoes:
        add("3D-받침", box(p, u_dir, n, 0.60, 0.60, p[2] - HSHOE, p[2]))
    return o, u_dir, n


def build_pier():
    pa, pb = S["P1a"], S["P1b"]
    allp = pa + pb
    c = np.mean(allp, axis=0)
    c[2] = 0
    u_dir = unit(np.array([*(pb[7] + pa[7] - pb[0] - pa[0])[:2], 0]))   # 1번측(-u) -> 8번측(+u)
    v_dir = hperp(u_dir)
    u_of = lambda p: float(np.dot(p - c, u_dir))
    top_d = lambda u: COP_TOP[0] + (u + 10) / 20 * (COP_TOP[1] - COP_TOP[0])
    K = float(np.mean([(p[2] - HSHOE) * 1000 - top_d(u_of(p)) for p in allp]))
    el = lambda zd: (zd + K) / 1000

    def P(u, v, z):
        p = c + u_dir * u + v_dir * v
        return np.array([p[0], p[1], z])

    lay = "3D-교각"
    uz = [(-10.0, el(COP_TOP[0])), (10.0, el(COP_TOP[1]))] + [(u, el(z)) for u, z in COP_BOT]
    add(lay, sweep([[P(u, -COP_W / 2, z) for u, z in uz], [P(u, COP_W / 2, z) for u, z in uz]]))
    for su in (-COL_U, COL_U):
        add(lay, prism(circle(P(su, 0, el(PF_TOP)), COL_D / 2, 32),
                       np.array([0, 0, el(-85312) - el(PF_TOP)])))
        add(lay, box(P(su, 0, 0), u_dir, v_dir, PF_B, PF_B, el(PF_BOT), el(PF_TOP)))
        add(lay, box(P(su, 0, 0), u_dir, v_dir, PF_B + 0.2, PF_B + 0.2,
                     el(PF_BOT) - LEAN_T, el(PF_BOT)))
    for p in allp:
        add("3D-받침", box(p, u_dir, v_dir, 0.60, 0.50, p[2] - HSHOE, p[2]))
    return el


# A1 받침 높이 (받침상면 - 교좌면)
def _a1_hshoe():
    shoes = S["A1"]
    u_dir = shoe_axis(shoes)
    o = shoes[7] - u_dir * AB_END8_TO_SHOE8
    vals = []
    for p in shoes:
        u = float(np.dot(p - o, u_dir))
        seat = A1_SEAT[0] + (A1_SEAT[1] - A1_SEAT[0]) * u / AB_LEN
        vals.append(p[2] - seat)
    return float(np.mean(vals))


HSHOE = _a1_hshoe()

LAYERS = {"3D-상부-거더": 30, "3D-상부-슬래브": 8, "3D-상부-포장": 250, "3D-상부-방호벽": 9,
          "3D-상부-가로보": 40, "3D-받침": 1, "3D-교대": 5, "3D-교대-말뚝": 6, "3D-교각": 3}


def build_all():
    build_superstructure()
    build_abutment("A1", S["P1a"][3])
    build_abutment("A2", S["P1b"][3])
    el = build_pier()
    return el


def write(doc):
    msp = doc.modelspace()
    if doc.dxfversion >= "AC1027" and not doc.acdsdata.is_valid:
        # LibreDWG 변환본에는 ACDSDATA 섹션이 없어 SAB(ACIS) 데이터가 저장되지 않음
        doc.acdsdata = new_acds_data_section(doc)
    for name, color in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    for layer, verts, faces in SOLIDS:
        mb = MeshBuilder()
        mb.vertices = [ezdxf.math.Vec3(to_cad(v)) for v in verts]
        mb.faces = [tuple(f) for f in faces]
        body = acis.body_from_mesh(mb)
        solid = msp.add_3dsolid(dxfattribs={"layer": layer})
        acis.export_dxf(solid, [body])
    if "3D-주기" not in doc.layers:
        doc.layers.add("3D-주기", color=2)
    note = ("덕진천교 3D 솔리드 모델 (상부: PSC Beam 8@, 슬래브, 방호벽, 포장, 가로보 / "
            "하부: 교대 A1·A2, 교각 P1, 말뚝, 받침)\\P"
            "좌표: x=(Y-209150)×1000+135000, y=(X-309030)×1000+30000, z=EL×1000 [mm]")
    msp.add_mtext(note, dxfattribs={"layer": "3D-주기", "char_height": 600,
                                    "insert": (138000, 104000, 0)}).dxf.width = 60000


def main():
    src, out = sys.argv[1], sys.argv[2]
    build_all()
    print(f"solids={len(SOLIDS)} plane residual: span1={RES1:.3f} span2={RES2:.3f} "
          f"shoe+pedestal={HSHOE:.3f} m")
    for s in "LCR":
        print("edge", s, "R=%.3f" % EDGE[s][1])
    doc, _ = recover.readfile(src)
    write(doc)
    doc.saveas(out)
    if len(sys.argv) > 3:
        d3 = ezdxf.new(doc.dxfversion)
        write(d3)
        d3.saveas(sys.argv[3])


if __name__ == "__main__":
    main()
