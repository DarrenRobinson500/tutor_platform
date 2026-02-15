import re
from dataclasses import dataclass
from typing import Optional, Tuple

DIAGRAM_TYPE = "Rect"

@dataclass
class RectDiagram:
    type: str
    x: float
    y: float
    pos: Tuple[float, float]


RECT_REGEX = re.compile(
    r"Rect\s*\(\s*x:\s*([^,]+)\s*,\s*y:\s*([^,]+)\s*,\s*pos:\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)\s*\)"
)

def parse(line: str) -> Optional[RectDiagram]:
    print("Rect parse")
    match = RECT_REGEX.match(line)
    if not match:
        print("Rect Regex failed")
        return None

    x = float(match.group(1).strip())
    y = float(match.group(2).strip())
    px = float(match.group(3))
    py = float(match.group(4))

    return RectDiagram(type="Rect", x=x, y=y, pos=(px, py))


def render(rect: RectDiagram) -> str:
    print("Rect render")
    x, y = rect.x, rect.y
    px, py = rect.pos

    # Convert centre → top-left corner
    x0 = px - x / 2
    y0 = py - y / 2

    result =  f"""
    <rect
        x="{x0}"
        y="{y0}"
        width="{x}"
        height="{y}"
        fill="none"
        stroke="black"
        stroke-width="0.5"
    />
    """

    print("Rect (output):", result)

    return result