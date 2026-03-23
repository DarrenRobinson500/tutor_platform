import re
import math
from dataclasses import dataclass, field
from typing import Optional

DIAGRAM_TYPE = "AlgebraTable"

# Syntax:
#   AlgebraTable(x_min: 1, x_max: 7, expr: "x+2", blank: 4)
#   AlgebraTable(x_min: 1, x_max: 7, expr: "x+2", blanks: "3,4,5", highlight: 3)
#
# blank:     single x value to leave blank (legacy/simple mode)
# blanks:    comma-separated x values to leave blank (multi-step mode)
# highlight: which blank is currently highlighted yellow; others show as light grey


@dataclass
class AlgebraTableDiagram:
    x_min: int = 1
    x_max: int = 7
    expr: str = "x"
    blank: int = 0                         # legacy single-blank
    blanks: list = field(default_factory=list)  # multi-blank list
    highlight: int = 0                     # active (yellow) blank; 0 = auto
    step: int = 1                          # increment between x values
    label_1: str = ""                      # row 1 label (default: "x")
    label_2: str = ""                      # row 2 label (default: expr)


def parse(line: str) -> Optional[AlgebraTableDiagram]:
    def get_int(key, default):
        m = re.search(rf'\b{key}:\s*(-?\d+)', line)
        return int(m.group(1)) if m else default

    def get_str(key, default):
        m = re.search(rf'\b{key}:\s*"([^"]*)"', line)
        if m:
            return m.group(1)
        m = re.search(rf'\b{key}:\s*([^,)\s]+)', line)
        return m.group(1) if m else default

    x_min = get_int("x_min", 1)
    x_max = get_int("x_max", 7)
    blank = get_int("blank", 0)
    step  = get_int("step", 1)
    expr    = get_str("expr", "x")
    label_1 = get_str("label_1", "")
    label_2 = get_str("label_2", "")

    # Parse blanks: "3,4,5"
    blanks = []
    m = re.search(r'\bblanks:\s*"([^"]*)"', line)
    if m:
        blanks = [int(v.strip()) for v in m.group(1).split(',') if v.strip().lstrip('-').isdigit()]

    highlight = get_int("highlight", blanks[0] if blanks else 0)

    x_vals = list(range(x_min, x_max + 1, max(step, 1)))
    if len(x_vals) < 2 or len(x_vals) > 12:
        return None

    return AlgebraTableDiagram(
        x_min=x_min, x_max=x_max, expr=expr,
        blank=blank, blanks=blanks, highlight=highlight,
        step=step, label_1=label_1, label_2=label_2,
    )


def _eval_expr(expr_str: str, x_val: int):
    """Evaluate expr_str at x=x_val using sympy. Returns numeric value or None."""
    try:
        from sympy import Symbol
        from sympy.parsing.sympy_parser import (
            parse_expr, standard_transformations,
            implicit_multiplication_application,
        )
        x = Symbol("x")
        transformations = standard_transformations + (implicit_multiplication_application,)
        result = parse_expr(expr_str, local_dict={"x": x}, transformations=transformations)
        f = float(result.subs(x, x_val))
        return int(f) if f == int(f) else round(f, 4)
    except Exception:
        return None


def _fmt(val) -> str:
    if val is None:
        return "?"
    return str(val)


def viewbox(d: AlgebraTableDiagram) -> tuple:
    total_w = 56.0
    cell_h = 6.5
    total_h = cell_h * 2
    pad_x, pad_y = 2.0, 2.0
    vb_w = total_w + 2 * pad_x
    vb_h = total_h + 2 * pad_y
    return (-vb_w / 2, -vb_h / 2, vb_w, vb_h)


def render(d: AlgebraTableDiagram) -> str:
    x_vals = list(range(d.x_min, d.x_max + 1, max(d.step, 1)))
    n_data_cols = len(x_vals)
    n_cols = n_data_cols + 1      # label column + data columns

    total_w = 56.0
    cell_h  = 6.5
    total_h = cell_h * 2

    # Label column is 1.5× wider than each data column
    data_w  = total_w / (1.5 + n_data_cols)
    label_w = 1.5 * data_w

    x0 = -total_w / 2
    y0 = -total_h / 2

    def col_x(col):
        return x0 if col == 0 else x0 + label_w + (col - 1) * data_w

    def col_w(col):
        return label_w if col == 0 else data_w

    # 2.16 SVG units ≈ 18px (viewBox width 60 over 500px SVG) — matches question font
    TARGET_FS  = 2.16
    font_size  = min(data_w * 0.32, TARGET_FS)

    FILL_HEADER      = "#e8e8e8"
    FILL_HIGHLIGHT   = "#fff9c4"   # active blank — yellow
    FILL_BLANK_OTHER = "#f0f0f0"   # other blanks — light grey
    FILL_NORMAL      = "#ffffff"
    STROKE           = "#888888"
    SW               = 0.15

    # Build sets for fast lookup
    all_blanks = set(d.blanks) | ({d.blank} if d.blank else set())
    active = d.highlight if d.highlight else (d.blanks[0] if d.blanks else d.blank)

    out = []

    # Draw filled cells (no stroke — horizontal lines added separately)
    for row in range(2):
        for col in range(n_cols):
            cx = col_x(col)
            cw = col_w(col)
            cy = y0 + row * cell_h

            is_label_col = (col == 0)
            x_val = x_vals[col - 1] if col > 0 else None
            is_blank = row == 1 and col > 0 and x_val in all_blanks
            is_active = is_blank and x_val == active

            if is_label_col:
                fill = FILL_HEADER
            elif is_active:
                fill = FILL_HIGHLIGHT
            elif is_blank:
                fill = FILL_BLANK_OTHER
            else:
                fill = FILL_NORMAL

            out.append(
                f'<rect x="{cx:.3f}" y="{cy:.3f}" '
                f'width="{cw:.3f}" height="{cell_h:.3f}" '
                f'fill="{fill}" stroke="none"/>'
            )

            # Cell text
            tx = cx + cw * 0.08 if is_label_col else cx + cw / 2  # left-pad label col
            ty = cy + cell_h / 2

            if row == 0:
                text = (d.label_1 if d.label_1 else "x") if is_label_col else str(x_val)
                fs = font_size
            else:
                if is_label_col:
                    text = d.label_2 if d.label_2 else d.expr
                    fs = font_size
                elif is_blank:
                    text = ""
                    fs = font_size
                else:
                    text = _fmt(_eval_expr(d.expr, x_val))
                    fs = font_size

            if text:
                anchor = 'text-anchor="start"' if is_label_col else 'text-anchor="middle"'
                style  = 'font-weight="bold"'  if is_label_col else ''
                out.append(
                    f'<text x="{tx:.3f}" y="{ty:.3f}" '
                    f'font-size="{fs:.2f}" font-family="inherit" {anchor} {style}'
                    f'dominant-baseline="middle">'
                    f'{text}</text>'
                )

    # Horizontal lines only: top, middle, bottom
    for hy in [y0, y0 + cell_h, y0 + total_h]:
        out.append(
            f'<line x1="{x0:.3f}" y1="{hy:.3f}" x2="{x0 + total_w:.3f}" y2="{hy:.3f}" '
            f'stroke="{STROKE}" stroke-width="{SW}"/>'
        )

    return "\n".join(out)
