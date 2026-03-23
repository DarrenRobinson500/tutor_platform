import re
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

DIAGRAM_TYPE = "Rect"

# Syntax: Rect(x: 5, y: 3, pos: (0, 0), scale: 1, labels: true)
# labels: true (default) shows dimension labels; labels: false hides them


@dataclass
class RectDiagram:
    x: float
    y: float
    pos: Tuple[float, float] = (0.0, 0.0)
    scale: float = 1.0
    labels: bool = True
    name: str = ""


def parse(line: str) -> Optional[RectDiagram]:
    def get_num(key):
        m = re.search(rf'\b{key}:\s*(-?[\d.]+)', line)
        return float(m.group(1)) if m else None

    pos_match = re.search(r'\bpos:\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)', line)
    labels_match = re.search(r'\blabels:\s*(true|false)', line)
    name_match = re.search(r'\bname:\s*"([^"]*)"', line)

    x = get_num("x")
    y = get_num("y")

    if x is None or y is None:
        return None

    pos = (float(pos_match.group(1)), float(pos_match.group(2))) if pos_match else (0.0, 0.0)
    scale = get_num("scale") or 1.0
    labels = (labels_match.group(1) != "false") if labels_match else True
    name = name_match.group(1) if name_match else ""

    result = RectDiagram(x=x, y=y, pos=pos, scale=scale, labels=labels, name=name)
    print(f"Rect parse: x={x}, y={y}, pos={pos}, scale={scale}, labels={labels}, name={name!r}")
    return result


def render(d: RectDiagram) -> str:
    cx, cy = d.pos
    w = d.x * d.scale
    h = d.y * d.scale

    # SVG: y increases downward, so top-left corner:
    x0 = cx - w / 2
    y0 = cy - h / 2

    sw = 0.4
    font_size = 2.0
    out = []

    out.append(
        f'<rect x="{x0:.3f}" y="{y0:.3f}" width="{w:.3f}" height="{h:.3f}" '
        f'fill="none" stroke="black" stroke-width="{sw}"/>'
    )

    if d.name:
        out.append(
            f'<text x="{cx:.3f}" y="{cy + font_size * 0.35:.3f}" text-anchor="middle" '
            f'font-size="{font_size}" font-family="sans-serif" fill="#333">{d.name}</text>'
        )

    if d.labels:
        # Width label: centred below the bottom edge
        lx = cx
        ly = y0 + h + font_size * 1.4
        out.append(
            f'<text x="{lx:.3f}" y="{ly:.3f}" text-anchor="middle" '
            f'font-size="{font_size}" font-family="sans-serif" fill="#333">{_fmt(d.x)}</text>'
        )

        # Height label: centred to the left of the left edge, no rotation
        hx = x0 - font_size * 0.9
        hy = cy + font_size * 0.35
        out.append(
            f'<text x="{hx:.3f}" y="{hy:.3f}" text-anchor="middle" '
            f'font-size="{font_size}" font-family="sans-serif" fill="#333">{_fmt(d.y)}</text>'
        )

    return "\n".join(out)


def _fmt(n: float) -> str:
    """Format a number: strip unnecessary trailing zeros."""
    return str(int(n)) if n == int(n) else f"{n:g}"
