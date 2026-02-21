
import re
from dataclasses import dataclass
from typing import Optional, Tuple, List

DIAGRAM_TYPE = "GraphColumn"

@dataclass
class GraphColumnDiagram:
    type: str
    points: List[Tuple[str, float]]  # [(label, value), ...]
    pos: Tuple[float, float]          # (px, py) chart center, to match DotArray convention

# Example accepted:
# GraphColumn(points: [("Dogs", 5), ("Cats", 6)], pos: (0,0))

# Capture the points list and the pos tuple
GRAPH_COLUMN_REGEX = re.compile(
    r'GraphColumn\s*\(\s*'
    r'points:\s*\[(?P<cols>.+?)\]\s*,\s*'
    r'pos:\s*\(\s*(?P<x>-?\d+(?:\.\d*)?)\s*,\s*(?P<y>-?\d+(?:\.\d*)?)\s*\)\s*'
    r'\)\s*$'
)

# Capture pairs like ("Label", 12.3). Accept straight and curly quotes.
PAIR_REGEX = re.compile(
    r'\(\s*[\"“”](.*?)[\"“”]\s*,\s*(-?\d+(?:\.\d*)?)\s*\)'
)

def parse(line: str) -> Optional[GraphColumnDiagram]:
    match = GRAPH_COLUMN_REGEX.match(line)
    if not match:
        return None

    cols_raw = match.group("cols")
    px = float(match.group("x"))
    py = float(match.group("y"))

    pairs: List[Tuple[str, float]] = []
    for label, value in PAIR_REGEX.findall(cols_raw):
        pairs.append((label, float(value)))

    if not pairs:
        return None

    return GraphColumnDiagram(
        type=DIAGRAM_TYPE,
        points=pairs,
        pos=(px, py)
    )

def render(diagram: GraphColumnDiagram) -> str:
    """
    Returns ONLY SVG fragments (no <svg> wrapper) so the engine can wrap them.
    Layout is scaled to fit inside the engine's viewBox (-30..30 x -15..15).
    """
    cols = diagram.points
    px, py = diagram.pos

    # --- Layout constants (in engine user units) ---
    # Engine viewBox is 60w x 30h, so keep a comfortable margin.
    max_chart_height = 18.0  # total drawable height for points, centered on py
    bar_spacing = 4.0
    bar_width = 4.0

    n = len(cols)
    total_width = n * bar_width + (n - 1) * bar_spacing
    x0 = px - total_width / 2.0           # left edge so chart is centered on px
    y_base = py + max_chart_height / 2.0  # bottom baseline (y grows downward in SVG)

    max_val = max(v for _, v in cols) if cols else 0.0
    scale = (max_chart_height / max_val) if max_val != 0 else 0.0

    frags: List[str] = []

    # Optional baseline
    frags.append(
        f'<line x1="{x0 - 1}" y1="{y_base}" x2="{x0 + total_width + 1}" y2="{y_base}" '
        f'stroke="black" stroke-width="0.3" />'
    )

    for i, (label, value) in enumerate(cols):
        h = value * scale if scale else 0.0
        x = x0 + i * (bar_width + bar_spacing)
        y = y_base - h  # top-left y

        # Column
        frags.append(
            f'<rect x="{x}" y="{y}" width="{bar_width}" height="{h}" fill="#4e79a7" />'
        )

        # Category label (under baseline)
        frags.append(
            f'<text x="{x + bar_width/2}" y="{y_base + 2.2}" '
            f'font-size="2.2" text-anchor="middle" fill="#333">{label}</text>'
        )

        # Value label (above bar)
        frags.append(
            f'<text x="{x + bar_width/2}" y="{y - 0.8}" '
            f'font-size="2" text-anchor="middle" fill="#333">{value}</text>'
        )

    return "\n".join(frags)
