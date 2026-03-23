import re
import math
from dataclasses import dataclass
from typing import Optional, List, Tuple

DIAGRAM_TYPE = "Polygon"

# Syntax: Polygon(sides: [5, 5, 5, 4, 3], pos: (x, y), scale: 1.5, labels: true, name: "")
#
# sides   — list of side lengths, one per side (3 or more)
# pos     — centre position in SVG units (default 0, 0)
# scale   — size multiplier; omit for auto-scaling to fit the canvas
# labels  — true (default) shows each side length; false hides them
# name    — optional text shown at the centre of the polygon
#
# The polygon is drawn using equal interior angles (regular-polygon angles) so
# it always looks like a recognisable n-gon.  Side lengths are labeled
# correctly but the shape is not an exact geometric representation of a polygon
# with those sides — it is intended for perimeter / area questions where you
# need to show side labels rather than precise angles.


@dataclass
class PolygonDiagram:
    sides: List[float]
    pos: Tuple[float, float] = (0.0, 0.0)
    scale: float = 0.0   # 0 = auto-scale
    labels: bool = True
    name: str = ""


def parse(line: str) -> Optional[PolygonDiagram]:
    if not line.strip().startswith("Polygon"):
        return None

    sides_match = re.search(r'sides:\s*\[([^\]]+)\]', line)
    if not sides_match:
        return None

    try:
        sides = [float(s.strip()) for s in sides_match.group(1).split(',') if s.strip()]
    except ValueError:
        return None

    if len(sides) < 3:
        return None

    pos_match = re.search(r'\bpos:\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)', line)
    pos = (float(pos_match.group(1)), float(pos_match.group(2))) if pos_match else (0.0, 0.0)

    scale_match = re.search(r'\bscale:\s*([\d.]+)', line)
    scale = float(scale_match.group(1)) if scale_match else 0.0

    labels_match = re.search(r'\blabels:\s*(true|false)', line)
    labels = (labels_match.group(1) != 'false') if labels_match else True

    name_match = re.search(r'\bname:\s*"([^"]*)"', line)
    name = name_match.group(1) if name_match else ""

    return PolygonDiagram(sides=sides, pos=pos, scale=scale, labels=labels, name=name)


def _build_vertices(sides: List[float], scale: float, pos: Tuple[float, float]) -> List[Tuple[float, float]]:
    """
    Place vertices using equal exterior angles (360/n per turn).
    The first side runs left-to-right at the bottom.  The polygon is then
    centred on pos.  The last vertex is forced back to the first so the
    shape is always closed regardless of side proportions.
    """
    n = len(sides)
    ext = 2 * math.pi / n   # exterior angle

    angle = 0.0              # start pointing right
    x, y = 0.0, 0.0
    verts: List[Tuple[float, float]] = [(x, y)]

    for i in range(n - 1):
        length = sides[i] * scale
        x += length * math.cos(angle)
        y += length * math.sin(angle)
        verts.append((x, y))
        angle -= ext            # turn counterclockwise in screen coords (y-down)

    # Centre on pos
    cx = sum(v[0] for v in verts) / n
    cy = sum(v[1] for v in verts) / n
    px, py = pos
    return [(v[0] + px - cx, v[1] + py - cy) for v in verts]


def _auto_scale(sides: List[float]) -> float:
    """Return a scale so the polygon spans about 22 SVG units on its longest axis."""
    n = len(sides)
    ext = 2 * math.pi / n
    angle = 0.0
    x, y = 0.0, 0.0
    xs, ys = [x], [y]
    for i in range(n - 1):
        x += sides[i] * math.cos(angle)
        y += sides[i] * math.sin(angle)
        xs.append(x)
        ys.append(y)
        angle -= ext
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return 20.0 / max(w, h, 1.0)


def _fmt(n: float) -> str:
    return str(int(n)) if n == int(n) else f"{n:.4g}"



def render(d: PolygonDiagram) -> str:
    scale = d.scale if d.scale > 0 else _auto_scale(d.sides)
    verts = _build_vertices(d.sides, scale, d.pos)
    n = len(verts)

    sw = 0.16
    font_size = 2.0

    cx = sum(v[0] for v in verts) / n
    cy = sum(v[1] for v in verts) / n

    frags: List[str] = []

    # Polygon outline
    pts = " ".join(f"{v[0]:.3f},{v[1]:.3f}" for v in verts)
    frags.append(
        f'<polygon points="{pts}" fill="none" stroke="black" stroke-width="{sw}"/>'
    )

    # Side labels
    if d.labels:
        for i in range(n):
            v1 = verts[i]
            v2 = verts[(i + 1) % n]
            mx = (v1[0] + v2[0]) / 2
            my = (v1[1] + v2[1]) / 2
            # Push label outward from centroid
            dx = mx - cx
            dy = my - cy
            dist = math.hypot(dx, dy) or 1.0
            offset = font_size * 1.3
            lx = mx + dx / dist * offset
            ly = my + dy / dist * offset
            frags.append(
                f'<text x="{lx:.3f}" y="{ly:.3f}" font-size="{font_size}" '
                f'font-family="sans-serif" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#333">{_fmt(d.sides[i])}</text>'
            )

    # Name in centre
    if d.name:
        frags.append(
            f'<text x="{cx:.3f}" y="{cy:.3f}" font-size="{font_size}" '
            f'font-family="sans-serif" text-anchor="middle" '
            f'dominant-baseline="middle" fill="#555">{d.name}</text>'
        )

    return "\n".join(frags)
