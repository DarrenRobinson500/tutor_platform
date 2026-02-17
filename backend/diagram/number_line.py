import re
from dataclasses import dataclass
from typing import Optional, Tuple, List

DIAGRAM_TYPE = "NumberLine"

# NumberLine(min: 0, max: 10, arrows: [({{a}}, {{a + b}})], pos: (0, 0))

@dataclass
class NumberLineDiagram:
    type: str
    min_val: float
    max_val: float
    arrows: List[Tuple[float, float]]
    pos: Tuple[float, float]


NUMBERLINE_REGEX = re.compile(
    r"NumberLine\s*\(\s*min:\s*(?P<min>-?\d+)\s*,\s*max:\s*(?P<max>-?\d+)\s*,\s*arrows:\s*\[(?P<arrows>[^\]]*)\]\s*,\s*pos:\s*\(\s*(?P<x>-?\d+)\s*,\s*(?P<y>-?\d+)\s*\)\s*\)"
)

ARROW_REGEX = re.compile(r"\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)")


def parse(line: str) -> Optional[NumberLineDiagram]:
    print("NumberLine parse")
    match = NUMBERLINE_REGEX.match(line)
    if not match:
        print("NumberLine Regex failed")
        return None

    min_val = float(match.group("min"))
    max_val = float(match.group("max"))
    px = float(match.group("x"))
    py = float(match.group("y"))

    arrows_str = match.group("arrows").strip()
    arrows: List[Tuple[float, float]] = []

    if arrows_str:
        for m in ARROW_REGEX.finditer(arrows_str):
            start = float(m.group(1))
            end = float(m.group(2))
            arrows.append((start, end))

    return NumberLineDiagram(
        type="NumberLine",
        min_val=min_val,
        max_val=max_val,
        arrows=arrows,
        pos=(px, py),
    )


def render(nl: NumberLineDiagram) -> str:
    min_val = nl.min_val
    max_val = nl.max_val
    px, py = nl.pos

    # Visual scaling
    line_length = 50  # SVG units
    scale = line_length / (max_val - min_val)

    # Center the number line at pos
    x0 = px - line_length / 2
    y0 = py

    fragments = []

    # Arrowhead definition (only needs to be defined once)
    fragments.append(
        """
    <defs>
        <marker id="arrowhead" markerWidth="3" markerHeight="3" refX="2.5" refY="1.5"
                orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,3 L3,1.5 z" fill="blue" />
        </marker>

    </defs>
            """.strip()
        )

    # Base line
    fragments.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x0 + line_length}" y2="{y0}" stroke="black" stroke-width="0.5" />'
    )

    # Determine how many integers are on the line
    count = int(max_val) - int(min_val) + 1

    # Decide label step
    if count <= 11:
        step = 1
    elif count <= 21:
        step = 2
    else:
        step = 5

    # Tick marks + numbers for each integer
    for v in range(int(min_val), int(max_val) + 1):
        xv = x0 + (v - min_val) * scale

        # Tick
        fragments.append(
            f'<line x1="{xv}" y1="{y0}" x2="{xv}" y2="{y0 - 2}" stroke="black" stroke-width="0.25" />'
        )

        # Number label
        if (v - min_val) % step == 0:
            fragments.append(
                f'<text x="{xv}" y="{y0 + 6}" font-size="4" text-anchor="middle">{v}</text>'
            )

    # Arrows
    num_arrows = len(nl.arrows)

    for i, (start, end) in enumerate(nl.arrows):
        # Vertical offset: top arrow highest
        offset = 3 * (num_arrows - i)
        arrow_y = y0 - offset

        sx = x0 + (start - min_val) * scale
        ex = x0 + (end - min_val) * scale

        fragments.append(
            f'<line x1="{sx}" y1="{arrow_y}" x2="{ex}" y2="{arrow_y}" '
            f'stroke="blue" stroke-width="0.5" marker-end="url(#arrowhead)" />'
        )

    return "\n".join(fragments)