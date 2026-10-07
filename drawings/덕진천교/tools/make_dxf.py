import sys
import numpy as np
import ezdxf
from ezdxf.enums import TextEntityAlignment
import bridge3d as B
import view as V

OUT = sys.argv[1]
SRC = sys.argv[2]          # 일반도 DXF (DWG→DXF 변환본)
parts = B.build()
MM = 1000.0


def tri_fan(v):
    if len(v) <= 4:
        return [v]
    return [[v[0], v[i], v[i + 1]] for i in range(1, len(v) - 1)]


# ================= 1) 3D 모델 DXF =================
m = ezdxf.new("R2018", setup=True)
m.header["$INSUNITS"] = 4
for p in parts:
    if p.layer not in m.layers:
        m.layers.add(p.layer, true_color=ezdxf.colors.rgb2int(p.color))
    pf = m.modelspace().add_polyface(dxfattribs={"layer": p.layer})
    faces = []
    for v, _ in p.faces:
        for f in tri_fan([tuple(q) for q in v]):
            faces.append([(x * MM, y * MM, z * MM) for x, y, z in f])
    pf.append_faces(faces)
    pf.optimize()
txt = m.modelspace().add_text(
    "덕진천교 3D 모델 - 원점(0,0)=P1 중심 X=309065.178 Y=209187.570, X축=동(Y좌표), Y축=북(X좌표), Z=EL, 단위 mm",
    height=700, dxfattribs={"layer": "3D-주기"})
txt.set_placement((-35000, -30000, 95000 * 1.0))
m.saveas(OUT + "/덕진천교_3D모델.dxf")

# ================= 2) 일반도에 조감도 시트 추가 =================
doc = ezdxf.readfile(SRC)
# LibreDWG 변환본의 미해결 MATERIAL 참조 복구
for nm in ("ByBlock", "ByLayer", "Global"):
    if isinstance(doc.materials.object_dict.get(nm), str):
        doc.materials.object_dict.discard(nm)
        doc.materials.new(nm)
msp = doc.modelspace()
FR0 = np.array([36354.85695774907, 32441.17064970678])     # 기존 도각 삽입점
DX = 90000.0                                                # 우측 신규 시트
O = FR0 + np.array([DX, 0])
W, H = 84100.0, 59400.0
for name, col in (("3D-조감도-음영", 8), ("3D-조감도-외곽선", 250), ("3D-조감도-주기", 3)):
    if name not in doc.layers:
        doc.layers.add(name, color=col)
if "도각(도화)-구조" in doc.blocks:
    msp.add_blockref("도각(도화)-구조", tuple(O), dxfattribs={"xscale": 100, "yscale": 100, "zscale": 100})


def text(s, p, h, layer, style, align=TextEntityAlignment.MIDDLE_CENTER):
    t = msp.add_text(s, height=h, dxfattribs={"layer": layer, "style": style})
    t.set_placement(tuple(p), align=align)
    return t


def put_view(polys, box, labels=None, outline=True):
    """box=(x0,y0,x1,y1) 도면 좌표에 맞춤 배치"""
    xs = np.concatenate([q[1][:, 0] for q in polys]); ys = np.concatenate([q[1][:, 1] for q in polys])
    sx = (box[2] - box[0]) / (xs.max() - xs.min()); sy = (box[3] - box[1]) / (ys.max() - ys.min())
    k = min(sx, sy)
    cx = (box[0] + box[2]) / 2 - k * (xs.max() + xs.min()) / 2
    cy = (box[1] + box[3]) / 2 - k * (ys.max() + ys.min()) / 2
    T = lambda xy: (cx + k * xy[0], cy + k * xy[1])
    for depth, xy, e, col, layer in polys:
        pts = [T(q) for q in xy]
        tc = ezdxf.colors.rgb2int(col)
        for f in tri_fan(pts):
            if len(f) == 4:
                f = [f[0], f[1], f[3], f[2]]           # SOLID 정점 순서
            msp.add_solid(f, dxfattribs={"layer": "3D-조감도-음영", "true_color": tc})
        if outline:
            for i in range(len(pts)):
                if e[i]:
                    msp.add_line(pts[i], pts[(i + 1) % len(pts)], dxfattribs={"layer": "3D-조감도-외곽선", "color": 250, "lineweight": 13})
    return T, k


# --- 시트 제목 (기존 도면 체계 동일 레이어/스타일)
text("교량 3D 조감도", O + (78578.539 - FR0[0], 87687.843 - FR0[1]), 1000, "TITLE-TEXT", "TB_TEXT")
text("( 덕진천교 )", O + (78578.539 - FR0[0], 86187.843 - FR0[1]), 700, "TITLE-TEXT", "TB_TEXT")
# 표제란
text("교량 3D 조감도", O + (114278.539 - FR0[0], 36787.843 - FR0[1]), 450, "TITLE-TEXT", "TB_TEXT")
text("( 덕진천교 )", O + (114278.539 - FR0[0], 36087.843 - FR0[1]), 350, "TITLE-TEXT", "TB_TEXT")
text("NONE", O + (103878.539 - FR0[0], 36187.843 - FR0[1]), 450, "TITLE-TEXT", "TB_TEXT")

# --- 주 조감도 (A1 → A2, 좌측 하방에서)
VIEWS = [
    ("조감도 (1)", "남서측 상공에서 본 전경", 240, 22, (O[0] + 4000, O[1] + 25500, O[0] + 80000, O[1] + 50500)),
    ("조감도 (2)", "북동측 상공에서 본 전경", 55, 25, (O[0] + 4000, O[1] + 6500, O[0] + 41000, O[1] + 22000)),
    ("조감도 (3)", "남서측 저각도 (하부구조)", 215, 6, (O[0] + 43500, O[1] + 6500, O[0] + 66500, O[1] + 22000)),
]
anchors = {
    "A1": np.array([*B.SA1.p0, 104.5]), "A2": np.array([*B.SA2.p0, 106.0]),
    "P1": np.array([*B.SP1.p0, 104.0]),
}
for title, sub, az, el, box in VIEWS:
    polys = V.project(parts, az, el)
    T, k = put_view(polys, box)
    text(title, ((box[0] + box[2]) / 2, box[3] + 1600), 700, "CZ-TEX1", "A_STANDARD")
    text(sub + "  S = NONE", ((box[0] + box[2]) / 2, box[3] + 700), 400, "CZ-TEX2", "A_STANDARD")
    d, right, up = V.camera(az, el)
    for lab, p3 in anchors.items():
        xy = T((p3 @ right, p3 @ up))
        h = 600 if k > 600 else 450
        text(lab, (xy[0], xy[1] - (2200 if el > 0 else -2200) * (k / 1000)), h, "3D-조감도-주기", "A_STANDARD")

# --- 부재 범례 + 노트
lx, ly = O[0] + 68500, O[1] + 21500
text("범   례", (lx + 3500, ly), 500, "CZ-TEX2", "A_STANDARD")
legend = [("슬래브/포장", (95, 95, 98)), ("방호벽·중분대", (235, 235, 228)), ("PSC 거더 (L=35m, H=2.2m)", (215, 210, 196)),
          ("가로보", (190, 190, 185)), ("교대·교각·기초", (180, 180, 175)), ("교량받침", (70, 70, 75)),
          ("강관말뚝 φ508", (150, 120, 95))]
for i, (nm, col) in enumerate(legend):
    y = ly - 1000 - i * 750
    msp.add_solid([(lx, y - 250), (lx + 900, y - 250), (lx, y + 250), (lx + 900, y + 250)],
                  dxfattribs={"layer": "3D-조감도-음영", "true_color": ezdxf.colors.rgb2int(col)})
    msp.add_lwpolyline([(lx, y - 250), (lx + 900, y - 250), (lx + 900, y + 250), (lx, y + 250)], close=True,
                       dxfattribs={"layer": "3D-조감도-외곽선", "color": 250})
    text(nm, (lx + 1200, y), 350, "CZ-TEX2", "A_STANDARD", TextEntityAlignment.MIDDLE_LEFT)

notes = [
    "노트 사항",
    "1. 본 조감도는 교량받침 좌표(받침 배치도) 및 PSC BEAM도, 슬래브 일반도,",
    "   교대·교각 일반도의 치수를 기준으로 작성한 3D 형상의 투영도임.",
    f"2. 평면선형 R={B.RAD:.0f}m(선형중심 좌표로 역산), 2경간 PSC BEAM교",
    "   (L=35.106+35.140m), 폭원 20.400m, PSC 거더 8주 @2.600.",
    "3. 3D 모델 원본: 덕진천교_3D모델.dxf (POLYFACE, 단위 mm)",
    "   원점 = P1 중심 (X=309065.178, Y=209187.570), Z = EL.",
    "4. 철근, 배수시설, 신축이음장치, 접속슬래브 등 세부는 표현 생략.",
]
for i, s in enumerate(notes):
    text(s, (O[0] + 4000, O[1] + 3800 - i * 0 if False else O[1] + 5200 - i * 520), 380 if i else 450,
         "CZ-TEX2", "A_STANDARD", TextEntityAlignment.MIDDLE_LEFT)
doc.audit()   # 변환 시 남은 무효 사전 참조 정리
doc.saveas(OUT + "/덕진천교_일반도_3D조감도.dxf")
print("ok", B.RAD)
