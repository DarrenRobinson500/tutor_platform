from xml.etree.ElementTree import Element, SubElement, tostring

class SVGRenderingEngine:
    def __init__(self):
        self.warnings = []

    def render(self, diagram_spec: dict) -> dict:
        self.warnings = []

        width = diagram_spec.get("width", 400)
        height = diagram_spec.get("height", 300)

        svg = Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
        })

        # Optional: defs (markers, etc.)
        self._add_defs(svg)

        for element in diagram_spec.get("elements", []):
            self._render_element(svg, element)

        svg_str = tostring(svg, encoding="unicode")
        return {
            "svg": svg_str,
            "warnings": self.warnings,
        }

    def _render_element(self, parent, spec, transform=None):
        etype = spec.get("type")

        if etype == "line":
            self._render_line(parent, spec, transform)
        elif etype == "circle":
            self._render_circle(parent, spec, transform)
        elif etype == "rect":
            self._render_rect(parent, spec, transform)
        elif etype == "polygon":
            self._render_polygon(parent, spec, transform)
        elif etype == "polyline":
            self._render_polyline(parent, spec, transform)
        elif etype == "text":
            self._render_text(parent, spec, transform)
        elif etype == "arrow":
            self._render_arrow(parent, spec, transform)
        elif etype == "group":
            self._render_group(parent, spec, transform)
        else:
            self.warnings.append({"type": "unknown_element", "message": f"Unknown type '{etype}'"})

    def _apply_transform(self, attrs, transform):
        if not transform:
            return
        parts = []
        if "translate" in transform:
            x, y = transform["translate"]
            parts.append(f"translate({x},{y})")
        if "rotate" in transform:
            parts.append(f"rotate({transform['rotate']})")
        if parts:
            attrs["transform"] = " ".join(parts)

    def _apply_style(self, attrs, spec):
        for key in ["stroke", "stroke_width", "stroke_dasharray", "fill", "opacity", "font_size", "font_family", "text_anchor"]:
            if key in spec:
                svg_key = key.replace("_", "-")
                attrs[svg_key] = str(spec[key])

    def _render_line(self, parent, spec, transform):
        attrs = {
            "x1": str(spec["x1"]),
            "y1": str(spec["y1"]),
            "x2": str(spec["x2"]),
            "y2": str(spec["y2"]),
        }
        self._apply_style(attrs, spec)
        self._apply_transform(attrs, transform)
        SubElement(parent, "line", attrs)

    def _render_circle(self, parent, spec, transform):
        attrs = {
            "cx": str(spec["cx"]),
            "cy": str(spec["cy"]),
            "r": str(spec["r"]),
        }
        self._apply_style(attrs, spec)
        self._apply_transform(attrs, transform)
        SubElement(parent, "circle", attrs)

    def _render_rect(self, parent, spec, transform):
        attrs = {
            "x": str(spec["x"]),
            "y": str(spec["y"]),
            "width": str(spec["width"]),
            "height": str(spec["height"]),
        }
        self._apply_style(attrs, spec)
        self._apply_transform(attrs, transform)
        SubElement(parent, "rect", attrs)

    def _points_to_str(self, points):
        return " ".join(f"{x},{y}" for x, y in points)

    def _render_polygon(self, parent, spec, transform):
        attrs = {"points": self._points_to_str(spec["points"])}
        self._apply_style(attrs, spec)
        self._apply_transform(attrs, transform)
        SubElement(parent, "polygon", attrs)

    def _render_polyline(self, parent, spec, transform):
        attrs = {"points": self._points_to_str(spec["points"])}
        self._apply_style(attrs, spec)
        self._apply_transform(attrs, transform)
        SubElement(parent, "polyline", attrs)

    def _render_text(self, parent, spec, transform):
        attrs = {
            "x": str(spec["x"]),
            "y": str(spec["y"]),
        }
        if "anchor" in spec:
            attrs["text-anchor"] = spec["anchor"]
        self._apply_style(attrs, spec)
        self._apply_transform(attrs, transform)

        el = SubElement(parent, "text", attrs)
        el.text = str(spec.get("text", ""))

    def _render_arrow(self, parent, spec, transform):
        attrs = {
            "x1": str(spec["x1"]),
            "y1": str(spec["y1"]),
            "x2": str(spec["x2"]),
            "y2": str(spec["y2"]),
        }
        self._apply_style(attrs, spec)
        self._apply_transform(attrs, transform)
        attrs["marker-end"] = "url(#arrow)"
        SubElement(parent, "line", attrs)

    def _render_group(self, parent, spec, parent_transform):
        group_transform = parent_transform or {}
        # Merge transforms if needed
        if "translate" in spec or "rotate" in spec:
            group_transform = dict(group_transform) if group_transform else {}
            if "translate" in spec:
                group_transform["translate"] = spec["translate"]
            if "rotate" in spec:
                group_transform["rotate"] = spec["rotate"]

        for child in spec.get("elements", []):
            self._render_element(parent, child, group_transform)

    def _add_defs(self, svg_root):
        defs = SubElement(svg_root, "defs")
        marker = SubElement(defs, "marker", {
            "id": "arrow",
            "markerWidth": "10",
            "markerHeight": "10",
            "refX": "10",
            "refY": "3",
            "orient": "auto",
            "markerUnits": "strokeWidth",
        })
        SubElement(marker, "path", {
            "d": "M0,0 L10,3 L0,6 z",
            "fill": "#000"
        })

    def _check_bounds(self, x, y, width, height):
        if x < 0 or y < 0 or x > width or y > height:
            self.warnings.append({
                "type": "off_canvas",
                "message": f"Element at ({x}, {y}) is outside canvas"
            })