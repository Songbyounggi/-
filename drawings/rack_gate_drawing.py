"""랙형 일체식 문비(수동 랙식 개폐기 일체형 수문) 일반도 생성 스크립트.

같은 형상 정의로 DXF(CAD 편집용)와 SVG(미리보기/출력용)를 함께 만든다.
모든 좌표는 실제 치수(mm)이며, 도곽은 A3(420x297) 1:20 기준(8400x5940)이다.

    pip install ezdxf
    python3 rack_gate_drawing.py
"""
import math
import os

import ezdxf
from ezdxf.enums import TextEntityAlignment

SCALE = 20
SHEET_W, SHEET_H = 420 * SCALE, 297 * SCALE
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
NAME = "랙형_일체식_문비_일반도"

LAYERS = {
    # name: (aci color, linetype, svg stroke color, svg stroke width[paper mm], dash[paper mm])
    "OUT": (7, "CONTINUOUS", "#000000", 0.45, None),
    "THIN": (8, "CONTINUOUS", "#000000", 0.18, None),
    "HID": (2, "DASHED", "#333333", 0.2, (2.0, 1.0)),
    "CEN": (1, "CENTER", "#c00000", 0.15, (6.0, 1.0, 1.0, 1.0)),
    "PHA": (6, "PHANTOM", "#7a1fa2", 0.18, (6.0, 1.0, 1.0, 1.0, 1.0, 1.0)),
    "DIM": (3, "CONTINUOUS", "#006400", 0.15, None),
    "TXT": (7, "CONTINUOUS", "#000000", 0.2, None),
    "HAT": (8, "CONTINUOUS", "#777777", 0.1, None),
    "SEC": (5, "CONTINUOUS", "#000000", 0.3, None),
    "FRM": (7, "CONTINUOUS", "#000000", 0.6, None),
}


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Sheet:
    def __init__(self):
        self.doc = ezdxf.new("R2010", setup=True)
        self.doc.units = ezdxf.units.MM
        self.doc.styles.new("KOR", dxfattribs={"font": "malgun.ttf"})
        for name, (color, lt, *_rest) in LAYERS.items():
            self.doc.layers.add(name, color=color, linetype=lt)
        self.doc.header["$LTSCALE"] = SCALE
        self.msp = self.doc.modelspace()
        self.svg = []

    # --- primitives -------------------------------------------------------
    def _style(self, layer):
        _, _, col, w, dash = LAYERS[layer]
        s = f'stroke="{col}" stroke-width="{w * SCALE:.1f}" fill="none"'
        if dash:
            s += ' stroke-dasharray="' + " ".join(f"{d * SCALE:.0f}" for d in dash) + '"'
        return s

    def line(self, x1, y1, x2, y2, layer="OUT"):
        self.msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})
        self.svg.append(
            f'<line x1="{x1:.1f}" y1="{SHEET_H - y1:.1f}" x2="{x2:.1f}" y2="{SHEET_H - y2:.1f}" {self._style(layer)}/>'
        )

    def poly(self, pts, layer="OUT", closed=True):
        self.msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer})
        p = " ".join(f"{x:.1f},{SHEET_H - y:.1f}" for x, y in pts)
        tag = "polygon" if closed else "polyline"
        self.svg.append(f'<{tag} points="{p}" {self._style(layer)}/>')

    def rect(self, x, y, w, h, layer="OUT"):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], layer)

    def circle(self, cx, cy, r, layer="OUT"):
        self.msp.add_circle((cx, cy), r, dxfattribs={"layer": layer})
        self.svg.append(f'<circle cx="{cx:.1f}" cy="{SHEET_H - cy:.1f}" r="{r:.1f}" {self._style(layer)}/>')

    def hatch(self, pts, kind="CONC"):
        """kind: CONC(콘크리트), STEEL(강재 단면 45도), SOLID(얇은 단면 채움)"""
        h = self.msp.add_hatch(color=8, dxfattribs={"layer": "HAT"})
        if kind == "SOLID":
            h.set_solid_fill(color=8)
        elif kind == "CONC":
            h.set_pattern_fill("AR-CONC", scale=1.0)
        else:
            h.set_pattern_fill("ANSI31", scale=SCALE * 0.5)
        h.paths.add_polyline_path(pts, is_closed=True)
        p = " ".join(f"{x:.1f},{SHEET_H - y:.1f}" for x, y in pts)
        fill = {"CONC": "url(#conc)", "STEEL": "url(#steel)", "SOLID": "#555555"}[kind]
        self.svg.append(f'<polygon points="{p}" fill="{fill}" stroke="none"/>')

    def text(self, x, y, t, h=50, align="left", valign="bottom", rot=0, layer="TXT", bold=False):
        key = {"bottom": "BOTTOM", "middle": "MIDDLE", "top": "TOP"}[valign] + "_" + {
            "left": "LEFT", "center": "CENTER", "right": "RIGHT"}[align]
        self.msp.add_text(
            t, height=h, rotation=rot, dxfattribs={"layer": layer, "style": "KOR"}
        ).set_placement((x, y), align=TextEntityAlignment[key])
        anchor = {"left": "start", "center": "middle", "right": "end"}[align]
        base = {"bottom": "auto", "middle": "central", "top": "hanging"}[valign]
        tr = f' transform="rotate({-rot} {x:.1f} {SHEET_H - y:.1f})"' if rot else ""
        fw = ' font-weight="bold"' if bold else ""
        self.svg.append(
            f'<text x="{x:.1f}" y="{SHEET_H - y:.1f}" font-size="{h * 1.25:.0f}" text-anchor="{anchor}" '
            f'dominant-baseline="{base}"{fw}{tr}>{esc(t)}</text>'
        )

    # --- annotations ------------------------------------------------------
    def _tick(self, x, y):
        d = 1.2 * SCALE
        self.line(x - d, y - d, x + d, y + d, "DIM")

    def hdim(self, x1, x2, y_obj, y_dim, label=None):
        ext = 1.5 * SCALE * (1 if y_dim > y_obj else -1)
        gap = 1.0 * SCALE * (1 if y_dim > y_obj else -1)
        for x in (x1, x2):
            self.line(x, y_obj + gap, x, y_dim + ext, "DIM")
            self._tick(x, y_dim)
        self.line(x1 - 30, y_dim, x2 + 30, y_dim, "DIM")
        self.text((x1 + x2) / 2, y_dim + 15, label or f"{abs(x2 - x1):,.0f}", 50, "center")

    def vdim(self, y1, y2, x_obj, x_dim, label=None):
        ext = 1.5 * SCALE * (1 if x_dim > x_obj else -1)
        gap = 1.0 * SCALE * (1 if x_dim > x_obj else -1)
        for y in (y1, y2):
            self.line(x_obj + gap, y, x_dim + ext, y, "DIM")
            self._tick(x_dim, y)
        self.line(x_dim, y1 - 30, x_dim, y2 + 30, "DIM")
        self.text(x_dim - 15, (y1 + y2) / 2, label or f"{abs(y2 - y1):,.0f}", 50, "center", rot=90)

    def balloon(self, px, py, bx, by, num):
        r = 45
        ang = math.atan2(py - by, px - bx)
        self.line(bx + r * math.cos(ang), by + r * math.sin(ang), px, py, "THIN")
        self.circle(px, py, 8, "THIN")
        self.circle(bx, by, r, "THIN")
        self.text(bx, by, str(num), 50, "center", "middle")

    def view_title(self, cx, y, title, scale="S=1:20"):
        self.text(cx, y, title, 100, "center", bold=True)
        self.line(cx - 450, y - 25, cx + 450, y - 25, "OUT")
        self.line(cx - 450, y - 45, cx + 450, y - 45, "THIN")
        self.text(cx, y - 70, scale, 50, "center", "top")

    def save(self):
        self.doc.saveas(os.path.join(OUT_DIR, NAME + ".dxf"))
        defs = (
            '<defs>'
            '<pattern id="conc" patternUnits="userSpaceOnUse" width="120" height="120">'
            '<path d="M0,120 L120,0" stroke="#999" stroke-width="3"/>'
            '<circle cx="30" cy="35" r="6" fill="#999"/><circle cx="85" cy="80" r="4" fill="#999"/>'
            '<path d="M70,20 l14,4 l-10,10 z" fill="none" stroke="#999" stroke-width="3"/></pattern>'
            '<pattern id="steel" patternUnits="userSpaceOnUse" width="40" height="40">'
            '<path d="M0,40 L40,0" stroke="#666" stroke-width="3"/></pattern>'
            '</defs>'
        )
        body = "\n".join(self.svg)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" '
            f'viewBox="0 0 {SHEET_W} {SHEET_H}" font-family="Malgun Gothic, NanumGothic, '
            f'Noto Sans CJK KR, WenQuanYi Zen Hei, sans-serif">\n{defs}\n'
            f'<rect width="{SHEET_W}" height="{SHEET_H}" fill="#fff"/>\n{body}\n</svg>\n'
        )
        with open(os.path.join(OUT_DIR, NAME + ".svg"), "w", encoding="utf-8") as f:
            f.write(svg)


# ---------------------------------------------------------------------------
# 설계 치수 (mm)
B = 1000          # 순경간(통수폭)
LEAF_W = 1100     # 문비 폭
LEAF_H = 1100     # 문비 높이
LIFT = 1000       # 양정
WALL_H = 1500     # 측벽 높이
FRAME_TOP = 2400  # 가이드 프레임 상단(상부 빔 하단)
BEAM_H = 150      # H-150x150
HOUSE = (350, 300, 250)   # 개폐기 본체 W x H x D
RACK = 50                 # 랙 바 □50
RACK_BOT = 1150
RACK_LEN = 1800
PIPE_TOP = FRAME_TOP + BEAM_H + HOUSE[1] + 1250
GIRDERS = [(20, 145), (380, 505), (700, 825), (975, 1100)]   # 수평 주형 하단/상단
STIFF_U = (-250, 0, 250)
FR_IN, FR_OUT = B / 2, B / 2 + 75      # 가이드 프레임(ㄷ-150x75) 정면 폭 75
GROOVE = B / 2 + 150                   # 측벽 홈(2차 콘크리트) 경계
WALL_OUT = 900
SILL = 75


def front_view(s, ox, oy):
    P = lambda u, v: (ox + u, oy + v)

    # 콘크리트(바닥 + 측벽, 가이드 프레임 홈 제외)
    conc = [(-WALL_OUT, WALL_H), (-WALL_OUT, -300), (WALL_OUT, -300), (WALL_OUT, WALL_H),
            (FR_OUT, WALL_H), (FR_OUT, -SILL), (-FR_OUT, -SILL), (-FR_OUT, WALL_H)]
    s.hatch([P(*p) for p in conc], "CONC")
    s.poly([P(*p) for p in conc], "OUT")
    s.line(*P(-WALL_OUT - 150, 0), *P(-FR_OUT, 0), "THIN")  # 바닥면 표시(G.L)
    s.line(*P(-GROOVE, -SILL), *P(-GROOVE, WALL_H), "HID")
    s.line(*P(GROOVE, -SILL), *P(GROOVE, WALL_H), "HID")
    s.text(*P(FR_OUT + 40, WALL_H + 20), "측벽 콘크리트", 45)

    # 실 빔(매립)
    s.rect(*P(-FR_OUT, -SILL), 2 * FR_OUT, SILL, "OUT")
    s.hatch([P(-FR_OUT, -SILL), P(FR_OUT, -SILL), P(FR_OUT, 0), P(-FR_OUT, 0)], "STEEL")

    # 가이드 프레임
    for sg in (-1, 1):
        x0 = min(sg * FR_IN, sg * FR_OUT)
        s.rect(*P(x0, -SILL), 75, FRAME_TOP + SILL, "OUT")
        # 앵커 (측벽 매립)
        for v in (250, 750, 1250):
            s.line(*P(sg * FR_OUT, v), *P(sg * (FR_OUT + 220), v), "HID")
            s.line(*P(sg * (FR_OUT + 220), v - 25), *P(sg * (FR_OUT + 220), v + 25), "HID")
    for u in (-300, 300):  # 실 빔 앵커
        s.line(*P(u, -SILL), *P(u, -260), "HID")

    # 문비 (닫힘 위치)
    hw = LEAF_W / 2
    s.line(*P(-FR_IN, LEAF_H), *P(FR_IN, LEAF_H), "OUT")
    for sg in (-1, 1):
        s.line(*P(sg * FR_IN, LEAF_H), *P(sg * hw, LEAF_H), "HID")
        s.line(*P(sg * hw, 0), *P(sg * hw, LEAF_H), "HID")
    s.line(*P(-FR_IN, 0), *P(FR_IN, 0), "OUT")
    for v0, v1 in GIRDERS:
        for v in (v0, v1):
            s.line(*P(-FR_IN, v), *P(FR_IN, v), "OUT")
        s.line(*P(-FR_IN, v0 + 8), *P(FR_IN, v0 + 8), "THIN")
        s.line(*P(-FR_IN, v1 - 8), *P(FR_IN, v1 - 8), "THIN")
    for (a0, a1), (b0, b1) in zip(GIRDERS, GIRDERS[1:]):
        for u in STIFF_U:
            s.rect(*P(u - 5, a1), 10, b0 - a1, "OUT")
    # 하부 수밀고무
    s.line(*P(-FR_IN, 15), *P(FR_IN, 15), "HID")

    # 연결 러그 + 핀
    s.poly([P(-60, LEAF_H), P(60, LEAF_H), P(60, LEAF_H + 90), P(30, LEAF_H + 120),
            P(-30, LEAF_H + 120), P(-60, LEAF_H + 90)], "OUT")
    s.circle(*P(0, LEAF_H + 70), 15, "OUT")

    # 랙 바 (치형 표시)
    rt = RACK_BOT + RACK_LEN
    hidden_from = FRAME_TOP
    s.line(*P(-RACK / 2, LEAF_H + 120), *P(-RACK / 2, hidden_from), "OUT")
    s.line(*P(RACK / 2, LEAF_H + 120), *P(RACK / 2, hidden_from), "OUT")
    for v in range(LEAF_H + 150, hidden_from, 40):
        s.line(*P(RACK / 2 - 12, v), *P(RACK / 2, v), "THIN")
    s.poly([P(-RACK / 2, hidden_from), P(-RACK / 2, rt), P(RACK / 2, rt), P(RACK / 2, hidden_from)],
           "HID", closed=False)

    # 상부 빔 H-150x150
    s.rect(*P(-650, FRAME_TOP), 1300, BEAM_H, "OUT")
    s.line(*P(-650, FRAME_TOP + 10), *P(650, FRAME_TOP + 10), "THIN")
    s.line(*P(-650, FRAME_TOP + BEAM_H - 10), *P(650, FRAME_TOP + BEAM_H - 10), "THIN")
    for sg in (-1, 1):
        for u in (sg * 610, sg * 540):
            s.circle(*P(u, FRAME_TOP + BEAM_H / 2), 9, "THIN")

    # 개폐기 본체 + 핸들
    hb = FRAME_TOP + BEAM_H
    s.rect(*P(-225, hb), 450, 20, "OUT")
    s.rect(*P(-HOUSE[0] / 2, hb + 20), HOUSE[0], HOUSE[1] - 20, "OUT")
    s.line(*P(-HOUSE[0] / 2, hb + 200), *P(HOUSE[0] / 2, hb + 200), "THIN")
    hc = hb + 150
    s.rect(*P(HOUSE[0] / 2, hc - 12), 80, 24, "OUT")            # 핸들 축
    s.rect(*P(HOUSE[0] / 2 + 80, hc - 250), 40, 500, "OUT")     # 핸들(측면)
    s.rect(*P(HOUSE[0] / 2 + 120, hc + 170), 90, 30, "OUT")     # 손잡이
    s.line(*P(-80, hc), *P(HOUSE[0] / 2 + 260, hc), "CEN")

    # 랙 커버 파이프
    ptop = hb + HOUSE[1]
    s.rect(*P(-57, ptop), 114, PIPE_TOP - ptop, "OUT")
    s.rect(*P(-70, PIPE_TOP), 140, 30, "OUT")
    s.line(*P(0, LEAF_H - 100), *P(0, PIPE_TOP + 120), "CEN")

    # 개방 위치(가상선)
    s.rect(*P(-hw, LIFT), LEAF_W, LEAF_H, "PHA")
    s.line(*P(-RACK / 2, rt + LIFT), *P(RACK / 2, rt + LIFT), "PHA")
    s.text(*P(-hw + 30, LIFT + LEAF_H - 80), "문비 전개 시(가상선)", 45, layer="TXT")

    # 단면 표시 A-A
    for v, va in ((-380, "top"), (PIPE_TOP + 160, "bottom")):
        s.line(*P(0, v), *P(0, v + (80 if va == "top" else -80)), "OUT")
        s.line(*P(0, v), *P(-140, v), "OUT")
        s.poly([P(-140, v), P(-100, v + 15), P(-100, v - 15)], "OUT")
        s.text(*P(-170, v), "A", 70, "right", "middle", bold=True)

    # 치수
    s.hdim(ox - B / 2, ox + B / 2, oy, oy - 520, "1,000 (순경간)")
    s.hdim(ox - hw, ox + hw, oy, oy - 640, "1,100 (문비 폭)")
    s.hdim(ox - WALL_OUT, ox + WALL_OUT, oy - 300, oy - 760)
    s.vdim(oy, oy + LEAF_H, ox - WALL_OUT, ox - 1020, "1,100 (문비 높이)")
    s.vdim(oy, oy + WALL_H, ox - WALL_OUT, ox - 1160)
    s.vdim(oy, oy + FRAME_TOP, ox - WALL_OUT, ox - 1300)
    s.vdim(oy - 300, oy, ox - WALL_OUT, ox - 1020)
    s.vdim(oy + LEAF_H, oy + LEAF_H + LIFT, ox + hw, ox + 1300, "1,000 (양정)")
    s.vdim(oy + FRAME_TOP, oy + PIPE_TOP + 30, ox + 650, ox + 1300)
    s.vdim(oy, oy + FRAME_TOP, ox + WALL_OUT, ox + 1420)

    # 품번
    s.balloon(*P(-380, 260), *P(-760, 2000), 1)
    for (pu, pv, bv, n) in [
        (400, 600, 260, 2), (250, 300, 560, 3), (537, 1800, 1850, 4),
        (420, 1200, 1250, 13), (25, 1650, 1600, 8),
        (500, 2475, 2475, 6), (285, 2900, 2950, 7), (57, 3600, 3600, 9), (300, -37, -400, 5),
    ]:
        s.balloon(*P(pu, pv), *P(1060, bv), n)
    s.balloon(*P(-FR_OUT - 160, 750), *P(-760, 2200), 12)

    s.view_title(ox, oy - 950, "정 면 도 (하류측에서 봄)")


def side_view(s, ox, oy):
    """단면 A-A : z(가로) 상류 -> 하류, v(세로) 높이"""
    P = lambda z, v: (ox + z, oy + v)

    # 바닥 콘크리트 + 실 빔
    floor = [(-700, 0), (-60, 0), (-60, -SILL), (90, -SILL), (90, 0), (700, 0), (700, -300), (-700, -300)]
    s.hatch([P(*p) for p in floor], "CONC")
    s.poly([P(*p) for p in floor], "OUT")
    s.rect(*P(-60, -SILL), 150, SILL, "OUT")
    s.hatch([P(-60, -SILL), P(90, -SILL), P(90, 0), P(-60, 0)], "STEEL")
    # 측벽 윤곽(단면 뒤쪽, 보이는 선)
    s.rect(*P(-700, 0), 1400, WALL_H, "THIN")
    s.line(*P(-700, WALL_H), *P(700, WALL_H), "OUT")

    # 가이드 프레임(뒤쪽)
    s.rect(*P(-60, 0), 150, FRAME_TOP, "THIN")

    # 문비: 스킨플레이트 + 주형 단면
    s.hatch([P(-5, 0), P(4, 0), P(4, LEAF_H), P(-5, LEAF_H)], "SOLID")
    s.rect(*P(-5, 0), 9, LEAF_H, "SEC")
    for v0, v1 in GIRDERS:
        h = v1 - v0
        sec = [(4, v0), (129, v0), (129, v0 + h), (121, v0 + h), (121, v0 + 6),
               (12, v0 + 6), (12, v0 + h), (4, v0 + h)]
        s.hatch([P(*p) for p in sec], "SOLID")
        s.poly([P(*p) for p in sec], "SEC")
    # 하부 수밀고무
    s.rect(*P(-25, 0), 20, 100, "OUT")
    s.hatch([P(-25, 0), P(-5, 0), P(-5, 100), P(-25, 100)], "STEEL")

    # 러그, 랙 바
    s.rect(*P(-10, LEAF_H), 50, 120, "OUT")
    s.circle(*P(15, LEAF_H + 70), 15, "OUT")
    rt = RACK_BOT + RACK_LEN
    s.line(*P(-10, LEAF_H + 120), *P(-10, FRAME_TOP), "OUT")
    s.line(*P(40, LEAF_H + 120), *P(40, FRAME_TOP), "OUT")
    s.poly([P(-10, FRAME_TOP), P(-10, rt), P(40, rt), P(40, FRAME_TOP)], "HID", closed=False)

    # 상부 빔 H-150x150 단면
    b = FRAME_TOP
    hsec = [(-60, b), (90, b), (90, b + 10), (18.5, b + 10), (18.5, b + 140), (90, b + 140),
            (90, b + 150), (-60, b + 150), (-60, b + 140), (11.5, b + 140), (11.5, b + 10), (-60, b + 10)]
    s.hatch([P(*p) for p in hsec], "SOLID")
    s.poly([P(*p) for p in hsec], "SEC")

    # 개폐기 + 핸들(정면으로 보임)
    hb = FRAME_TOP + BEAM_H
    s.rect(*P(-145, hb), 320, 20, "OUT")
    s.rect(*P(15 - HOUSE[2] / 2, hb + 20), HOUSE[2], HOUSE[1] - 20, "OUT")
    hc = hb + 150
    s.circle(*P(15, hc), 250, "OUT")
    s.circle(*P(15, hc), 222, "OUT")
    s.circle(*P(15, hc), 40, "OUT")
    for a in range(0, 360, 90):
        r = math.radians(a + 45)
        for d in (-8, 8):
            ox2 = d * math.cos(r + math.pi / 2)
            oy2 = d * math.sin(r + math.pi / 2)
            s.line(*P(15 + 40 * math.cos(r) + ox2, hc + 40 * math.sin(r) + oy2),
                   *P(15 + 222 * math.cos(r) + ox2, hc + 222 * math.sin(r) + oy2), "OUT")
    s.circle(*P(15, hc + 236), 18, "OUT")
    s.line(*P(15 - 300, hc), *P(15 + 300, hc), "CEN")

    ptop = hb + HOUSE[1]
    s.rect(*P(15 - 57, ptop), 114, PIPE_TOP - ptop, "OUT")
    s.rect(*P(15 - 70, PIPE_TOP), 140, 30, "OUT")
    s.line(*P(15, LEAF_H - 100), *P(15, PIPE_TOP + 120), "CEN")

    # 개방 위치
    s.rect(*P(-5, LIFT), 134, LEAF_H, "PHA")

    # 수위, 흐름
    wl = 1300
    s.line(*P(-680, wl), *P(-20, wl), "THIN")
    s.poly([P(-450, wl), P(-480, wl + 45), P(-420, wl + 45)], "OUT")
    s.text(*P(-400, wl + 15), "설계수위", 45)
    s.line(*P(-650, -420), *P(-350, -420), "OUT")
    s.poly([P(-350, -420), P(-400, -400), P(-400, -440)], "OUT")
    s.text(*P(-500, -400), "흐름", 45, "center")
    s.text(*P(-600, 1700), "상류측", 60, "center", bold=True)
    s.text(*P(600, 1700), "하류측", 60, "center", bold=True)

    # 치수
    s.hdim(ox - 5, ox + 129, oy + LEAF_H, oy - 150 - 470, "134")
    s.hdim(ox - 60, ox + 90, oy - SILL, oy - 760, "150 (프레임)")
    s.vdim(oy, oy + LEAF_H, ox - 700, ox - 800)
    s.vdim(oy + FRAME_TOP, oy + hb, ox + 90, ox + 450, "150")
    s.vdim(oy + hb, oy + ptop, ox + 175, ox + 450, "300")

    s.balloon(*P(-25, 50), *P(-450, 450), 11)
    s.balloon(*P(-1, 600), *P(-450, 700), 1)
    s.balloon(*P(129, 760), *P(450, 760), 2)

    s.view_title(ox, oy - 950, "단 면 도  A - A")


def plan_view(s, ox, oy):
    """평면도 : u(가로), z(세로, 상류가 위)"""
    P = lambda u, z: (ox + u, oy - z)

    for sg in (-1, 1):
        wall = [(sg * WALL_OUT, -400), (sg * WALL_OUT, 400), (sg * B / 2, 400), (sg * B / 2, 90 + 30),
                (sg * GROOVE, 90 + 30), (sg * GROOVE, -60 - 30), (sg * B / 2, -60 - 30), (sg * B / 2, -400)]
        s.hatch([P(*p) for p in wall], "CONC")
        s.poly([P(*p) for p in wall], "OUT")
        # 가이드 프레임 ㄷ-150x75 (홈 쪽 개방)
        c = [(sg * FR_OUT, -60), (sg * FR_OUT, 90), (sg * FR_IN, 90), (sg * FR_IN, 83.5),
             (sg * (FR_OUT - 6.5), 83.5), (sg * (FR_OUT - 6.5), -53.5), (sg * FR_IN, -53.5), (sg * FR_IN, -60)]
        s.hatch([P(*p) for p in c], "SOLID")
        s.poly([P(*p) for p in c], "SEC")
        # 측부 수밀고무(P형)
        s.circle(*P(sg * (LEAF_W / 2 - 15), -20), 13, "HID")

    # 문비(상부 빔 아래 - 숨은선)
    hw = LEAF_W / 2
    s.rect(*P(-hw, 129), LEAF_W, 134, "HID")
    s.line(*P(-hw, 4), *P(hw, 4), "HID")

    # 상부 빔
    s.rect(*P(-650, 90), 1300, 150, "OUT")
    for sg in (-1, 1):
        for u in (sg * 610, sg * 540):
            for z in (-30, 60):
                s.circle(*P(u, z), 9, "THIN")
    # 개폐기 + 핸들(측면)
    s.rect(*P(-HOUSE[0] / 2, 15 + HOUSE[2] / 2), HOUSE[0], HOUSE[2], "OUT")
    s.rect(*P(HOUSE[0] / 2, 15 + 12), 80, 24, "OUT")
    s.rect(*P(HOUSE[0] / 2 + 80, 15 + 250), 40, 500, "OUT")
    s.circle(*P(0, 15), 70, "OUT")
    s.circle(*P(0, 15), 57, "THIN")
    s.line(*P(-800, 15), *P(800, 15), "CEN")
    s.line(*P(0, -480), *P(0, 480), "CEN")
    s.text(*P(0, -330), "상류", 50, "center", "middle")
    s.text(*P(0, 330), "하류", 50, "center", "middle")

    s.hdim(ox - 650, ox + 650, oy - 90, oy - 560)
    s.hdim(ox - B / 2, ox + B / 2, oy + 400, oy + 540, "1,000")
    s.balloon(*P(-hw + 15, -20), *P(-760, -560), 10)
    s.balloon(*P(-FR_OUT + 30, 90), *P(-760, 560), 4)

    s.view_title(ox, oy - 700, "평 면 도")


BOM = [
    ("1", "스킨플레이트", "PL 9×1,100×1,100", "SS275", "1"),
    ("2", "수평 주형", "ㄷ-125×65×6 L=1,100", "SS275", "4"),
    ("3", "수직 보강재", "FB 75×9", "SS275", "9"),
    ("4", "가이드 프레임", "ㄷ-150×75×6.5 L=2,475", "SS275", "2"),
    ("5", "실(Sill) 빔", "ㄷ-150×75×6.5 L=1,150", "SS275", "1"),
    ("6", "상부 빔(권양대)", "H-150×150×7×10 L=1,300", "SS275", "1"),
    ("7", "랙식 개폐기(수동)", "핸들 Ø500, 2.0 ton", "조립품", "1"),
    ("8", "랙 바", "□50×50 L=1,800", "SM45C", "1"),
    ("9", "랙 커버 파이프", "Ø114.3×4.5 L=1,250", "STS304", "1"),
    ("10", "측부 수밀고무", "P형 Ø26", "CR", "2"),
    ("11", "하부 수밀고무", "평형 20×100", "CR", "1"),
    ("12", "앵커볼트", "M16×200", "SS275(용융아연)", "16"),
    ("13", "연결 러그·핀", "PL 16, 핀 Ø30", "SS275/STS304", "1조"),
]

NOTES = [
    "1. 본 도면은 랙형 일체식 문비(수동 랙식 개폐기 일체형 수문)의 일반 참고도이며,",
    "    제작 전 현장 여건·설계수압에 따라 구조 검토 후 치수를 확정할 것.",
    "2. 치수 단위: mm",
    "3. 설계 조건(가정): 순경간 1,000, 문비 1,100×1,100, 양정 1,000, 설계수심 1.5 m",
    "4. 강재는 KS D 3503 SS275, 용접은 연속 필릿 용접(각장 6mm 이상)으로 한다.",
    "5. 도장: 무기질 아연말 하도 + 에폭시 중·상도(총 건조도막 250㎛ 이상)",
    "6. 가이드 프레임·실 빔은 1차 콘크리트 블록아웃 후 수직·수평을 맞추고",
    "    무수축 몰탈(2차 콘크리트)로 충전한다.",
    "7. 수밀고무는 CR(클로로프렌) 재질로 하며, 볼트 체결 후 누수 시험 실시.",
]


def tables(s):
    # 재료표
    x0, y_top = 5000, 3950
    cols = [180, 620, 1100, 700, 300]
    row_h = 110
    titles = ("품번", "품 명", "규 격", "재 질", "수량")
    s.text(x0, y_top + 40, "재 료 표", 80, bold=True)
    rows = [titles] + BOM
    W = sum(cols)
    for i in range(len(rows) + 1):
        y = y_top - i * row_h
        s.line(x0, y, x0 + W, y, "OUT" if i in (0, 1, len(rows)) else "THIN")
    x = x0
    for c in [0] + cols:
        x += c
        s.line(x, y_top, x, y_top - len(rows) * row_h, "OUT" if c in (0, cols[-1]) else "THIN")
    for i, row in enumerate(rows):
        x = x0
        yc = y_top - (i + 0.5) * row_h
        for c, val in zip(cols, row):
            s.text(x + c / 2, yc, val, 45, "center", "middle", bold=(i == 0))
            x += c

    # 주기
    ny = y_top - len(rows) * row_h - 130
    s.text(x0, ny, "주  기", 70, bold=True)
    for i, n in enumerate(NOTES):
        s.text(x0, ny - 110 - i * 85, n, 45)

    # 표제란
    tx, ty, tw, th = 5000, 200, 3200, 700
    s.rect(tx, ty, tw, th, "FRM")
    for y in (ty + 350,):
        s.line(tx, y, tx + tw, y, "OUT")
    s.line(tx + 1700, ty, tx + 1700, ty + 350, "THIN")
    s.line(tx + 2450, ty, tx + 2450, ty + 350, "THIN")
    s.line(tx, ty + 175, tx + tw, ty + 175, "THIN")
    s.text(tx + 60, ty + 600, "도 면 명", 45)
    s.text(tx + tw / 2, ty + 470, "랙형 일체식 문비 일반도", 110, "center", "middle", bold=True)
    cells = [
        (tx, ty + 175, "공 사 명", ""), (tx + 1700, ty + 175, "축  척", "1:20 (A3)"),
        (tx + 2450, ty + 175, "도면번호", "G-001"),
        (tx, ty, "작 성 일", "2026. 10. 06"), (tx + 1700, ty, "단  위", "mm"),
        (tx + 2450, ty, "비  고", "참고도"),
    ]
    for cx, cy, k, v in cells:
        s.text(cx + 40, cy + 87, k, 45, "left", "middle")
        s.text(cx + 330, cy + 87, v, 50, "left", "middle")


def main():
    s = Sheet()
    s.rect(200, 200, SHEET_W - 400, SHEET_H - 400, "FRM")
    front_view(s, 1650, 1350)
    side_view(s, 4050, 1350)
    plan_view(s, 6550, 5050)
    tables(s)
    s.save()


if __name__ == "__main__":
    main()
