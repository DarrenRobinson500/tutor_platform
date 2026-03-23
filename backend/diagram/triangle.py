import re
import math
from dataclasses import dataclass, field
from typing import List, Optional

DIAGRAM_TYPE = "Triangle"

# Syntax: Triangle(a: 5, b: 7, c: 6)
# c is optional — if omitted, a right angle at vertex C is assumed (c = √(a²+b²))
# Angle arcs:   arcs_A: 1, arcs_B: 2, arcs_C: 1      (1–3 arcs at a vertex)
# Angle labels: label_A: "30°", label_B: "x"          (uppercase = angle at vertex)
# Side labels:  label_a: "5", label_b: "10"            (lowercase = side opposite vertex)
# Tick marks:   ticks_a: 1, ticks_b: 2, ticks_c: 0
# Layout:       pos: (0, 0), scale: 1.5


@dataclass
class TriangleDiagram:
    a: float
    b: float
    c: float
    ticks_a: int = 0
    ticks_b: int = 0
    ticks_c: int = 0
    arcs_A: int = 0
    arcs_B: int = 0
    arcs_C: int = 0
    label_A: str = ""
    label_B: str = ""
    label_C: str = ""
    label_a: str = ""   # side label for side a (B–C)
    label_b: str = ""   # side label for side b (A–C)
    label_c: str = ""   # side label for side c (A–B)
    pos: List[float] = field(default_factory=lambda: [0.0, 0.0])
    scale: float = 1.0


def parse(line: str) -> Optional[TriangleDiagram]:
    def get_num(key):
        m = re.search(rf'\b{key}:\s*(-?[\d.]+)', line)
        return float(m.group(1)) if m else None

    def get_int(key):
        v = get_num(key)
        return int(v) if v is not None else None

    def get_str(key):
        m = re.search(rf'\b{key}:\s*"([^"]*)"', line)
        if m:
            return m.group(1)
        m = re.search(rf'\b{key}:\s*([^,)\s]+)', line)
        return m.group(1) if m else ""

    pos_match = re.search(r'\bpos:\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)', line)

    a = get_num("a")
    b = get_num("b")
    c = get_num("c")

    if None in (a, b):
        return None

    # If c is omitted, assume a right angle at vertex C (c is the hypotenuse)
    if c is None:
        c = math.sqrt(a * a + b * b)

    if a + b <= c or a + c <= b or b + c <= a:
        return None

    pos = [float(pos_match.group(1)), float(pos_match.group(2))] if pos_match else [0.0, 0.0]
    scale = get_num("scale") or 1.0

    return TriangleDiagram(
        a=a, b=b, c=c,
        ticks_a=get_int("ticks_a") or 0,
        ticks_b=get_int("ticks_b") or 0,
        ticks_c=get_int("ticks_c") or 0,
        arcs_A=get_int("arcs_A") or 0,
        arcs_B=get_int("arcs_B") or 0,
        arcs_C=get_int("arcs_C") or 0,
        label_A=get_str("label_A"),
        label_B=get_str("label_B"),
        label_C=get_str("label_C"),
        label_a=get_str("label_a"),
        label_b=get_str("label_b"),
        label_c=get_str("label_c"),
        pos=pos,
        scale=scale,
    )


def _tick_marks(x1, y1, x2, y2, count, sw):
    if count <= 0:
        return ""

    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    px = -dy / length
    py =  dx / length

    half = 0.8
    gap  = 0.44
    ux = dx / length
    uy = dy / length

    if count == 1:
        offsets = [0]
    elif count == 2:
        offsets = [-gap / 2, gap / 2]
    else:
        offsets = [-gap, 0, gap]

    parts = []
    for off in offsets:
        cx = mx + ux * off
        cy = my + uy * off
        parts.append(
            f'<line x1="{cx - px*half:.3f}" y1="{cy - py*half:.3f}" '
            f'x2="{cx + px*half:.3f}" y2="{cy + py*half:.3f}" '
            f'stroke="black" stroke-width="{sw}" stroke-linecap="round"/>'
        )
    return "\n".join(parts)


def _arc_indicators(cx, cy, angle_from, angle_to, count, sw):
    if count <= 0:
        return ""

    BASE_R = 3.52
    GAP_R  = 0.72

    a1 = angle_from
    a2 = angle_to
    while a2 < a1:
        a2 += 2 * math.pi
    sweep = a2 - a1
    large_arc = 1 if sweep > math.pi else 0

    parts = []
    for i in range(count):
        r = BASE_R + i * GAP_R
        sx1 = cx + r * math.cos(a1)
        sy1 = cy - r * math.sin(a1)
        sx2 = cx + r * math.cos(a2)
        sy2 = cy - r * math.sin(a2)
        parts.append(
            f'<path d="M{sx1:.3f},{sy1:.3f} A{r},{r} 0 {large_arc},0 {sx2:.3f},{sy2:.3f}" '
            f'fill="none" stroke="black" stroke-width="{sw * 0.7:.2f}"/>'
        )
    return "\n".join(parts)


def _angle_label(vx, vy, cent_svgx, cent_svgy, text, font_size):
    """Label placed 40 % of the way from vertex toward the SVG centroid."""
    if not text:
        return ""
    dx = cent_svgx - vx
    dy = cent_svgy - vy
    dist = math.hypot(dx, dy)
    if dist == 0:
        return ""
    ux, uy = dx / dist, dy / dist
    label_r = dist * 0.55
    lx = vx + ux * label_r
    ly = vy + uy * label_r
    return (
        f'<text x="{lx:.3f}" y="{ly:.3f}" '
        f'font-size="{font_size}" font-family="serif" '
        f'text-anchor="middle" dominant-baseline="middle">'
        f'{text}</text>'
    )


def _side_label(x1, y1, x2, y2, opp_x, opp_y, text, font_size):
    """Label placed at the midpoint of a side, offset outward (away from opposite vertex)."""
    if not text:
        return ""
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return ""
    # Perpendicular unit vectors (two options)
    px, py = -dy / length, dx / length
    # Pick the one pointing away from the opposite vertex
    to_opp_x = opp_x - mx
    to_opp_y = opp_y - my
    if px * to_opp_x + py * to_opp_y > 0:
        px, py = -px, -py  # flip to point away
    offset = font_size * 1.1
    lx = mx + px * offset
    ly = my + py * offset
    return (
        f'<text x="{lx:.3f}" y="{ly:.3f}" '
        f'font-size="{font_size}" font-family="serif" '
        f'text-anchor="middle" dominant-baseline="middle">'
        f'{text}</text>'
    )


def render(d: TriangleDiagram) -> str:
    a, b, c = d.a, d.b, d.c
    cx0, cy0 = d.pos
    scale = d.scale

    # Place B at origin, C along +x; compute A via law of cosines
    bx, by = 0.0, 0.0
    cx, cy = a, 0.0
    cos_b = (a*a + c*c - b*b) / (2*a*c)
    ax = c * cos_b
    ay = c * math.sqrt(max(0.0, 1 - cos_b*cos_b))

    # Centroid
    cent_x = (ax + bx + cx) / 3
    cent_y = (ay + by + cy) / 3

    def to_svg(x, y):
        return (
            cx0 + (x - cent_x) * scale,
            cy0 - (y - cent_y) * scale,
        )

    sax, say = to_svg(ax, ay)
    sbx, sby = to_svg(bx, by)
    scx, scy = to_svg(cx, cy)
    s_cent_x, s_cent_y = to_svg(cent_x, cent_y)

    sw = 0.4
    font_size = 2.2
    out = []

    # Sides
    out.append(f'<line x1="{sbx:.3f}" y1="{sby:.3f}" x2="{scx:.3f}" y2="{scy:.3f}" stroke="black" stroke-width="{sw}" stroke-linecap="round"/>')
    out.append(f'<line x1="{sax:.3f}" y1="{say:.3f}" x2="{scx:.3f}" y2="{scy:.3f}" stroke="black" stroke-width="{sw}" stroke-linecap="round"/>')
    out.append(f'<line x1="{sax:.3f}" y1="{say:.3f}" x2="{sbx:.3f}" y2="{sby:.3f}" stroke="black" stroke-width="{sw}" stroke-linecap="round"/>')

    # Tick marks: side a (B–C), side b (A–C), side c (A–B)
    out.append(_tick_marks(sbx, sby, scx, scy, d.ticks_a, sw * 0.8))
    out.append(_tick_marks(sax, say, scx, scy, d.ticks_b, sw * 0.8))
    out.append(_tick_marks(sax, say, sbx, sby, d.ticks_c, sw * 0.8))

    # Side length labels: opposite vertex used to determine outward direction
    out.append(_side_label(sbx, sby, scx, scy, sax, say, d.label_a, font_size))  # side a, opp A
    out.append(_side_label(sax, say, scx, scy, sbx, sby, d.label_b, font_size))  # side b, opp B
    out.append(_side_label(sax, say, sbx, sby, scx, scy, d.label_c, font_size))  # side c, opp C

    # Angle arcs and labels
    def math_angle(from_x, from_y, to_x, to_y):
        return math.atan2(-(to_y - from_y), to_x - from_x)

    def short_arc(p, q):
        sweep = (q - p) % (2 * math.pi)
        return (p, q) if sweep <= math.pi else (q, p)

    ang_atob = math_angle(sax, say, sbx, sby)
    ang_atoc = math_angle(sax, say, scx, scy)
    out.append(_arc_indicators(sax, say, *short_arc(ang_atob, ang_atoc), d.arcs_A, sw * 0.8))
    out.append(_angle_label(sax, say, s_cent_x, s_cent_y, d.label_A, font_size))

    ang_btoa = math_angle(sbx, sby, sax, say)
    ang_btoc = math_angle(sbx, sby, scx, scy)
    out.append(_arc_indicators(sbx, sby, *short_arc(ang_btoa, ang_btoc), d.arcs_B, sw * 0.8))
    out.append(_angle_label(sbx, sby, s_cent_x, s_cent_y, d.label_B, font_size))

    ang_ctoa = math_angle(scx, scy, sax, say)
    ang_ctob = math_angle(scx, scy, sbx, sby)
    out.append(_arc_indicators(scx, scy, *short_arc(ang_ctoa, ang_ctob), d.arcs_C, sw * 0.8))
    out.append(_angle_label(scx, scy, s_cent_x, s_cent_y, d.label_C, font_size))

    return "\n".join(p for p in out if p)
