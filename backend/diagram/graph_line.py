
import re
from dataclasses import dataclass
from typing import Optional, Tuple, List

DIAGRAM_TYPE = "GraphLine"

@dataclass
class GraphLineDiagram:
    type: str
    points: List[Tuple[str, float]]  # [(label, value), ...] in x-order of appearance
    pos: Tuple[float, float]          # (px, py) chart center, consistent with other diagrams

# Example:
# GraphLine(points: [("Mon", 3), ("Tue", 5), ("Wed", 4)], pos: (0,0))

GRAPH_LINE_REGEX = re.compile(
    r'GraphLine\s*\(\s*'
    r'points:\s*\[(?P<pts>.+?)\]\s*,\s*'
    r'pos:\s*\(\s*(?P<x>-?\d+(?:\.\d*)?)\s*,\s*(?P<y>-?\d+(?:\.\d*)?)\s*\)\s*'
    r'\)\s*$'
)

# Accept pairs like ("Label", 12.3); allow straight or curly quotes
PAIR_REGEX = re.compile(
    r'\(\s*([\"“”])(.*?)\1\s*,\s*(-?\d+(?:\.\d*)?)\s*\)'
)

def parse(line: str) -> Optional[GraphLineDiagram]:
    m = GRAPH_LINE_REGEX.match(line)
    if not m:
        return None

    pts_raw = m.group("pts")
    px = float(m.group("x"))
    py = float(m.group("y"))

    points: List[Tuple[str, float]] = []
    for _, label, value in PAIR_REGEX.findall(pts_raw):
        points.append((label, float(value)))

    if not points:
        return None

    return GraphLineDiagram(
        type=DIAGRAM_TYPE,
        points=points,
        pos=(px, py)
    )

def render(diagram: GraphLineDiagram) -> str:
    """
    Returns ONLY SVG fragments so the engine can wrap them.
    The layout fits the engine's viewBox (-30..30 x -15..15).
    """
    pts = diagram.points
    px, py = diagram.pos

    # --- Layout constants (engine user units) ---
    max_chart_height = 18.0  # vertical drawing span
    max_chart_width  = 35.0  # horizontal span for the series (leave margins)
    marker_radius    = 0.9
    stroke_color     = "#e15759"
    grid_color       = "#ccc"

    n = len(pts)
    max_val = max((v for _, v in pts), default=0.0)
    # min_val = min((v for _, v in pts), default=0.0)
    min_val = 0

    # If all equal, avoid divide-by-zero and draw a flat line
    same = (max_val == min_val)
    vmin = min_val if not same else min_val - 1.0
    vmax = max_val if not same else max_val + 1.0

    # Center chart at (px, py)
    x0 = px - max_chart_width / 2.0
    # Use a baseline near bottom (similar to columns). y grows downward.
    y_top  = py - max_chart_height / 2.0
    y_base = py + max_chart_height / 2.0

    # Horizontal spacing across width
    dx = 0.0 if n <= 1 else (max_chart_width / (n - 1))

    def y_map(value: float) -> float:
        # Map [vmin..vmax] -> [y_top..y_base] (invert because SVG y increases downward)
        if vmax == vmin:
            return (y_top + y_base) / 2.0
        t = (value - vmin) / (vmax - vmin)
        return y_base - t * (y_base - y_top)

    # Gridline (optional): baseline
    frags: List[str] = [
        f'<line x1="{x0 - 1}" y1="{y_base}" x2="{x0 + max_chart_width + 1}" y2="{y_base}" '
        f'stroke="black" stroke-width="0.3" />'
    ]

    # Build polyline points
    poly_pts: List[str] = []
    for i, (_, v) in enumerate(pts):
        x = x0 + i * dx
        y = y_map(v)
        poly_pts.append(f"{x},{y}")

    if poly_pts:
        frags.append(
            f'<polyline fill="none" stroke="{stroke_color}" stroke-width="0.8" '
            f'points="{" ".join(poly_pts)}" />'
        )

    # Markers + labels
    for i, (label, v) in enumerate(pts):
        x = x0 + i * dx
        y = y_map(v)

        # Marker
        frags.append(
            f'<circle cx="{x}" cy="{y}" r="{marker_radius}" fill="{stroke_color}" />'
        )

        # Value label above marker
        frags.append(
            f'<text x="{x}" y="{y - 1.2}" font-size="2" text-anchor="middle" fill="#333">{v}</text>'
        )

        # Category label below baseline
        frags.append(
            f'<text x="{x}" y="{y_base + 2.2}" font-size="2.2" text-anchor="middle" fill="#333">{label}</text>'
        )

    return "\n".join(frags)
