from typing import List

from . import DIAGRAM_REGISTRY

def render_diagram_from_code(code: str) -> str:
    # print("Render diagram from code")
    lines = [l.strip() for l in code.split("\n") if l.strip()]
    fragments = []

    for line in lines:
        print("Render engine (line):", line)
        for diagram_type, module in DIAGRAM_REGISTRY.items():
            if line.startswith(diagram_type):
                parsed = module.parse(line)
                print("Render engine (parsed):", parsed)
                if parsed:
                    fragments.append(module.render(parsed))
                else:
                    print("Not parsed successfully")
                break

    pre = '<svg width="400" height="240" viewBox="-25 -15 50 30" xmlns="http://www.w3.org/2000/svg">'
    body =  {" ".join(fragments)}
    post = '</svg>'

    print("SVG Engine:", body)

    return pre + str(body) + post