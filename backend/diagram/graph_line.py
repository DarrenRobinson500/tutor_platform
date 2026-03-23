
import re
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple, List

DIAGRAM_TYPE = "GraphLine"

# Syntax:
#   GraphLine(points: [("Jan", 12), ("Feb", 8), ...], y_label: "Rainfall (mm)")
#   pos: (x, y) is optional (default 0, 0)

@dataclass
class GraphLineDiagram:
    type: str
    points: List[Tuple[str, float]]
    pos: Tuple[float, float] = (0.0, 0.0)
    y_label: str = ""
    show_values: bool = True


# Accept pairs like ("Label", 12.3); allow straight or curly quotes
PAIR_REGEX = re.compile(
    r'\(\s*(["\u201c\u201d])(.*?)\1\s*,\s*(-?\d+(?:\.\d*)?)\s*\)'
)


def parse(line: str) -> Optional[GraphLineDiagram]:
    if not line.startswith("GraphLine"):
        return None

    pts_match = re.search(r'points:\s*\[(.+?)\]', line)
    if not pts_match:
        return None

    points: List[Tuple[str, float]] = []
    for _, label, value in PAIR_REGEX.findall(pts_match.group(1)):
        points.append((label, float(value)))

    if not points:
        return None

    pos_match = re.search(r'pos:\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)', line)
    pos = (float(pos_match.group(1)), float(pos_match.group(2))) if pos_match else (0.0, 0.0)

    y_label_match = re.search(r'y_label:\s*"([^"]*)"', line)
    y_label = y_label_match.group(1) if y_label_match else ""

    sv_match = re.search(r'\bshow_values:\s*(true|false)', line)
    show_values = (sv_match.group(1) != "false") if sv_match else True

    return GraphLineDiagram(type=DIAGRAM_TYPE, points=points, pos=pos, y_label=y_label, show_values=show_values)


def _nice_step(approx: float) -> float:
    if approx <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(approx))
    norm = approx / mag
    if norm < 1.5: return mag
    if norm < 3.5: return 2 * mag
    if norm < 7.5: return 5 * mag
    return 10 * mag


def _fmt(n: float) -> str:
    return str(int(n)) if n == int(n) else f"{n:.4g}"


# Chart dimensions (SVG units)
_CHART_W = 50.0
_CHART_H = 26.0
_PAD_LEFT   = 8.0   # y-axis tick labels
_PAD_RIGHT  = 4.5
_PAD_TOP    = 4.5   # y_label above arrowhead
_PAD_BOTTOM = 5.0   # x category labels


def viewbox(d: GraphLineDiagram) -> tuple:
    px, py = d.pos
    L = px - _CHART_W / 2
    R = px + _CHART_W / 2
    T = py - _CHART_H / 2
    B = py + _CHART_H / 2
    vb_min_x = L - _PAD_LEFT
    vb_min_y = T - _PAD_TOP
    vb_w = (R + _PAD_RIGHT) - vb_min_x
    vb_h = (B + _PAD_BOTTOM) - vb_min_y
    return (vb_min_x, vb_min_y, vb_w, vb_h)


def render(d: GraphLineDiagram) -> str:
    pts = d.points
    px, py = d.pos

    n = len(pts)
    max_val = max((v for _, v in pts), default=0.0)
    min_val = 0.0
    same = (max_val == min_val)
    vmin = min_val if not same else min_val - 1.0
    vmax = max_val if not same else max_val + 1.0

    L = px - _CHART_W / 2
    R = px + _CHART_W / 2
    T = py - _CHART_H / 2
    B = py + _CHART_H / 2

    # X positions: first point at L, last at R
    dx = 0.0 if n <= 1 else _CHART_W / (n - 1)

    def x_pos(i: int) -> float:
        return L + i * dx

    def y_pos(value: float) -> float:
        if vmax == vmin:
            return (T + B) / 2.0
        t = (value - vmin) / (vmax - vmin)
        return B - t * (B - T)

    sw       = 0.25
    tick_len = 0.8
    font_size = 1.8
    stroke_color = "#e15759"

    frags: List[str] = []

    # Background
    frags.append(
        f'<rect x="{L}" y="{T}" width="{_CHART_W}" height="{_CHART_H}" '
        f'fill="white" stroke="#aaa" stroke-width="{sw}"/>'
    )

    # Y-axis grid lines and ticks
    y_step = _nice_step((vmax - vmin) / 6)
    y_grid_start = math.ceil(vmin / y_step) * y_step

    y = y_grid_start
    while y <= vmax + y_step * 0.01:
        sy = y_pos(y)
        # Horizontal grid line
        frags.append(
            f'<line x1="{L}" y1="{sy:.3f}" x2="{R}" y2="{sy:.3f}" '
            f'stroke="#e0e0e0" stroke-width="{sw}"/>'
        )
        # Tick mark on y-axis
        frags.append(
            f'<line x1="{L - tick_len/2:.3f}" y1="{sy:.3f}" '
            f'x2="{L + tick_len/2:.3f}" y2="{sy:.3f}" '
            f'stroke="black" stroke-width="{sw}"/>'
        )
        # Tick label
        frags.append(
            f'<text x="{L - tick_len - 0.3:.3f}" y="{sy + font_size*0.35:.3f}" '
            f'text-anchor="end" font-size="{font_size}" '
            f'font-family="sans-serif" fill="#333">{_fmt(y)}</text>'
        )
        y += y_step

    # X-axis line (explicit, matches y-axis colour)
    frags.append(
        f'<line x1="{L}" y1="{B}" x2="{R}" y2="{B}" '
        f'stroke="black" stroke-width="{sw}"/>'
    )

    # Y-axis line with arrowhead
    aw, ah = 0.7, 1.2
    frags.append(
        f'<line x1="{L}" y1="{B}" x2="{L}" y2="{T}" '
        f'stroke="black" stroke-width="{sw}"/>'
    )
    frags.append(
        f'<polygon points="{L},{T} {L - aw/2:.3f},{T + ah} {L + aw/2:.3f},{T + ah}" '
        f'fill="black"/>'
    )

    # Y-axis label (same position as Cartesian: above arrowhead, shifted left)
    if d.y_label:
        frags.append(
            f'<text x="{L - 4.6:.3f}" y="{T - 1.8:.3f}" '
            f'text-anchor="start" font-size="{font_size}" '
            f'font-family="sans-serif" fill="#333">{d.y_label}</text>'
        )

    # Polyline
    poly_pts = [f"{x_pos(i):.3f},{y_pos(v):.3f}" for i, (_, v) in enumerate(pts)]
    if poly_pts:
        frags.append(
            f'<polyline fill="none" stroke="{stroke_color}" stroke-width="0.8" '
            f'points="{" ".join(poly_pts)}" />'
        )

    # Markers, value labels, and category labels
    for i, (label, v) in enumerate(pts):
        x = x_pos(i)
        y = y_pos(v)

        frags.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="0.9" fill="{stroke_color}" />'
        )
        if d.show_values:
            frags.append(
                f'<text x="{x:.3f}" y="{y - 1.2:.3f}" font-size="{font_size}" '
                f'text-anchor="middle" fill="#333">{_fmt(v)}</text>'
            )
        frags.append(
            f'<text x="{x:.3f}" y="{B + 3.0:.3f}" font-size="{font_size}" '
            f'text-anchor="middle" fill="#333">{label}</text>'
        )

    return "\n".join(frags)
