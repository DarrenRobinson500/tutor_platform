import re
import math
from dataclasses import dataclass, field
from typing import List, Optional

DIAGRAM_TYPE = "Angle"

# Syntax: Angle(deg: 65)
# Optional: pos: (0, 0), size: 12


@dataclass
class AngleDiagram:
    deg: float
    pos: List[float] = field(default_factory=lambda: [0.0, 0.0])
    size: float = 12.0
    display_label: bool = True


def parse(line: str) -> Optional[AngleDiagram]:
    deg_match   = re.search(r'\bdeg:\s*([\d.]+)', line)
    pos_match   = re.search(r'\bpos:\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)', line)
    size_match  = re.search(r'\bsize:\s*([\d.]+)', line)
    label_match = re.search(r'\bdisplay_label:\s*(true|false)', line)

    if not deg_match:
        return None

    deg = float(deg_match.group(1))
    if deg <= 0 or deg >= 360:
        return None

    pos           = [float(pos_match.group(1)), float(pos_match.group(2))] if pos_match else [0.0, 0.0]
    size          = float(size_match.group(1)) if size_match else 12.0
    display_label = (label_match.group(1) == "true") if label_match else True

    return AngleDiagram(deg=deg, pos=pos, size=size, display_label=display_label)


def render(d: AngleDiagram) -> str:
    cx, cy  = d.pos
    deg     = d.deg
    rad     = math.radians(deg)
    arc_r   = d.size * 0.3
    label_r = arc_r + 2.8
    sw      = 0.5

    # Ray 1: horizontal right
    r1x = cx + d.size

    # Ray 2: deg° counterclockwise (SVG y is flipped, so negate sin)
    r2x = cx + d.size * math.cos(rad)
    r2y = cy - d.size * math.sin(rad)

    # Arc end point along Ray 2 at arc_r distance
    ax_end    = cx + arc_r * math.cos(rad)
    ay_end    = cy - arc_r * math.sin(rad)
    large_arc = 1 if deg > 180 else 0

    # Label at the angle bisector
    bis_rad = math.radians(deg / 2)
    lx = cx + label_r * math.cos(bis_rad)
    ly = cy - label_r * math.sin(bis_rad)

    parts = [
        f'<line x1="{cx}" y1="{cy}" x2="{r1x:.2f}" y2="{cy:.2f}" stroke="black" stroke-width="{sw}" stroke-linecap="round"/>',
        f'<line x1="{cx}" y1="{cy}" x2="{r2x:.2f}" y2="{r2y:.2f}" stroke="black" stroke-width="{sw}" stroke-linecap="round"/>',
        f'<path d="M{cx + arc_r:.2f},{cy:.2f} A{arc_r:.2f},{arc_r:.2f} 0 {large_arc},0 {ax_end:.2f},{ay_end:.2f}" fill="none" stroke="black" stroke-width="{sw * 0.65:.2f}"/>',
    ]

    if d.display_label:
        label = str(int(deg)) if deg == int(deg) else str(deg)
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" text-anchor="middle" dominant-baseline="middle" font-size="2.8" font-family="sans-serif" fill="black">{label}°</text>'
        )

    return "\n".join(parts)
