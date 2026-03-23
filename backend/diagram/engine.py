import re
from typing import List

from . import DIAGRAM_REGISTRY

def render_diagram_from_code(code: str) -> str:
    if not code:
        return ""
    if not isinstance(code, str):
        print(f"render_diagram_from_code: expected str, got {type(code).__name__}: {code!r}")
        return ""
    if not code.strip():
        return ""

    # print("Render diagram from code")
    lines = [l.strip() for l in re.split(r'[\n;]', code) if l.strip()]
    fragments = []

    DEFAULT_VIEWBOX = (-30, -15, 60, 30)

    print(f"render_diagram_from_code: registry={list(DIAGRAM_REGISTRY.keys())}")
    vb = DEFAULT_VIEWBOX
    for line in lines:
        print(f"render_diagram_from_code: line={line!r}")
        matched = False
        for diagram_type, module in DIAGRAM_REGISTRY.items():
            if line.startswith(diagram_type):
                matched = True
                try:
                    parsed = module.parse(line)
                    print(f"render_diagram_from_code: parsed={parsed}")
                    if parsed:
                        fragments.append(module.render(parsed))
                        if hasattr(module, "viewbox"):
                            vb = module.viewbox(parsed)
                    else:
                        print("Not parsed successfully")
                except Exception as e:
                    import traceback
                    print(f"render_diagram_from_code: ERROR in {diagram_type}: {e}")
                    traceback.print_exc()
                break
        if not matched:
            print(f"render_diagram_from_code: no match for {line!r}")

    vb_min_x, vb_min_y, vb_w, vb_h = vb
    svg_w = 500
    svg_h = round(svg_w * vb_h / vb_w)
    vb_str = f"{vb_min_x} {vb_min_y} {vb_w} {vb_h}"

    pre = f'<svg width="{svg_w}" height="{svg_h}" viewBox="{vb_str}" xmlns="http://www.w3.org/2000/svg">'
    body = "\n".join(fragments)
    post = '</svg>'

    return pre + str(body) + post