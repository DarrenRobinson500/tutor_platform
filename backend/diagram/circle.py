import re
import math
from dataclasses import dataclass
from typing import Optional

DIAGRAM_TYPE = "Circle"

# Syntax: Circle(radius: 5, label_r: true, label_d: false)
#
# radius   — numeric value used in labels (the mathematical radius)
# label_r  — true (default) shows a radius line and its value
# label_d  — true shows a diameter line and its value (default false)
#
# When both are shown the diameter is drawn horizontally and the radius
# at 45° upward-right so they are visually distinct.


@dataclass
class CircleDiagram:
    radius: float = 1.0
    label_r: bool = True
    label_d: bool = False


def parse(line: str) -> Optional[CircleDiagram]:
    if not line.strip().startswith("Circle"):
        return None

    radius_match = re.search(r'\bradius:\s*([\d.]+)', line)
    if not radius_match:
        return None
    radius = float(radius_match.group(1))

    label_r_match = re.search(r'\blabel_r:\s*(true|false)', line)
    label_r = (label_r_match.group(1) != 'false') if label_r_match else True

    label_d_match = re.search(r'\blabel_d:\s*(true|false)', line)
    label_d = (label_d_match.group(1) != 'false') if label_d_match else False

    return CircleDiagram(radius=radius, label_r=label_r, label_d=label_d)


def _fmt(n: float) -> str:
    return str(int(n)) if n == int(n) else f"{n:.4g}"


def _label(x, y, text, font_size, anchor="middle"):
    return (
        f'<text x="{x:.3f}" y="{y:.3f}" font-size="{font_size}" '
        f'font-family="sans-serif" text-anchor="{anchor}" '
        f'dominant-baseline="middle" fill="#333">{text}</text>'
    )


def render(d: CircleDiagram) -> str:
    r_svg = 11.0   # SVG radius — fits within the default (-30,-15,60,30) viewBox
    sw = 0.25
    font_size = 2.2

    frags = []

    # Circle outline
    frags.append(
        f'<circle cx="0" cy="0" r="{r_svg}" '
        f'fill="none" stroke="black" stroke-width="{sw}"/>'
    )

    # Centre dot
    frags.append('<circle cx="0" cy="0" r="0.35" fill="black"/>')

    if d.label_r and d.label_d:
        # ── Both lines ──────────────────────────────────────────────────────
        # Diameter: horizontal across the full circle
        frags.append(
            f'<line x1="{-r_svg}" y1="0" x2="{r_svg}" y2="0" '
            f'stroke="black" stroke-width="{sw}"/>'
        )
        # Diameter label below the line, centred
        frags.append(_label(0, 1.8, _fmt(d.radius * 2), font_size))

        # Radius: 45° upward-right (y is negative = upward in SVG)
        rx = r_svg * math.cos(math.radians(45))
        ry = -r_svg * math.sin(math.radians(45))
        frags.append(
            f'<line x1="0" y1="0" x2="{rx:.3f}" y2="{ry:.3f}" '
            f'stroke="black" stroke-width="{sw}"/>'
        )
        # Radius label: perpendicular offset from mid-point of radius line
        # Perpendicular (clockwise 90° from line direction) shifts the label
        # to the upper-left of the line.
        mid_x, mid_y = rx / 2, ry / 2
        frags.append(_label(mid_x - 1.5, mid_y - 1.0, _fmt(d.radius), font_size))

    elif d.label_d:
        # ── Diameter only ────────────────────────────────────────────────────
        frags.append(
            f'<line x1="{-r_svg}" y1="0" x2="{r_svg}" y2="0" '
            f'stroke="black" stroke-width="{sw}"/>'
        )
        frags.append(_label(0, -1.8, _fmt(d.radius * 2), font_size))

    elif d.label_r:
        # ── Radius only ──────────────────────────────────────────────────────
        frags.append(
            f'<line x1="0" y1="0" x2="{r_svg}" y2="0" '
            f'stroke="black" stroke-width="{sw}"/>'
        )
        frags.append(_label(r_svg / 2, -1.8, _fmt(d.radius), font_size))

    return "\n".join(frags)
