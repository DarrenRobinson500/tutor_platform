import re
from .param import *
from .engine import *


# ── List helper functions ────────────────────────────────────────────────────
# Exported so render.py can include them in validation rule contexts.

def list_mode(lst):
    """Return the most frequent value; first encountered on a tie."""
    counts = {}
    for v in lst:
        counts[v] = counts.get(v, 0) + 1
    return max(counts, key=counts.get)

def list_median(lst):
    """Return the median; returns a float for even-length lists."""
    s = sorted(lst)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2

def list_mean(lst):
    from fractions import Fraction
    return Fraction(sum(lst), len(lst))

def list_range(lst):
    return max(lst) - min(lst)

_LIST_CONTEXT = {
    "mode":     list_mode,
    "median":   list_median,
    "mean":     list_mean,
    "range_of": list_range,
    "sorted":   sorted,
    "sum":      sum,
    "min":      min,
    "max":      max,
    "len":      len,
}

class ExpressionNode:
    def __init__(self, raw_expr, params=None):
        self.original_expr = raw_expr.strip()
        self.params = params or {}  # dict of RandomParameter objects

        self.raw_expr = None
        self.format_type = None
        self.format_options = {}

        self._parse()
        self.evaluate()
        self.output = self.format()

    def __str__(self):
        return f"{self.original_expr} -> {self.output}"

    def _parse(self):
        expr = self.original_expr

        if "|" in expr:
            expr_part, format_part = map(str.strip, expr.split("|", 1))
        else:
            expr_part = expr
            format_part = None

        self.raw_expr = expr_part
        self.format_type, self.format_options = self._parse_format(format_part)

    @staticmethod
    def _parse_format(format_part):
        if not format_part:
            return None, {}

        if "(" not in format_part:
            return format_part, {}

        name, args = format_part.split("(", 1)
        name = name.strip()
        args = args.rstrip(")")

        options = {}
        for item in args.split(","):
            key, val = map(str.strip, item.split("="))
            options[key] = val

        return name, options

    def evaluate(self):
        # 1. Generate values from parameter objects
        value_map = {}
        for name, param in self.params.items():
            value_map[name] = param.value

        # 2. If any referenced variable is a list, use Python eval with list functions
        list_vars = {k for k, v in value_map.items() if isinstance(v, list)}
        if list_vars and any(re.search(rf'\b{re.escape(k)}\b', self.raw_expr) for k in list_vars):
            ctx = dict(_LIST_CONTEXT)
            ctx["__builtins__"] = {}
            ctx.update(value_map)
            self.evaluated_value = eval(self.raw_expr, ctx)
            return self.evaluated_value

        # 3. Substitute into expression
        # Wrap fraction values in parentheses so that e.g. a / b with a=23/4, b=11/5
        # becomes (23/4) / (11/5) rather than 23/4 / 11/5 (which parses incorrectly).
        substituted = self.raw_expr
        for key, val in value_map.items():
            val_str = str(val)
            if "/" in val_str:
                val_str = f"({val_str})"
            substituted = re.sub(rf'\b{re.escape(key)}\b', val_str, substituted)

        # 4. Evaluate using maths engine
        self.evaluated_value = evaluate_number_expression(substituted, value_map)
        return self.evaluated_value

    def format(self):
        # 0. List values — format as comma-separated; | sorted sorts first
        if isinstance(self.evaluated_value, list):
            vals = sorted(self.evaluated_value) if self.format_type == "sorted" else self.evaluated_value
            return ", ".join(str(int(v) if isinstance(v, float) and v == int(v) else v) for v in vals)

        # 1. Explicit format type always wins
        if self.format_type is not None:
            formatter_cls = FORMAT_REGISTRY[self.format_type]
            formatter = formatter_cls(**self.format_options)
            return formatter.format(self.evaluated_value)

        expr = self.raw_expr.strip()

        # 2. Single variable → use its default format
        if expr in self.params:
            param = self.params[expr]
            if hasattr(param, "default_format_type") and param.default_format_type:
                formatter_cls = FORMAT_REGISTRY[param.default_format_type]
                fmt_opts = getattr(param, "default_format_options", {})
                formatter = formatter_cls(**fmt_opts)
                return formatter.format(self.evaluated_value)

        # 3. Multi-variable: check if all variables share the same default format
        vars_in_expr = [name for name in self.params if name in expr]

        if vars_in_expr:
            default_types = {
                self.params[name].default_format_type
                for name in vars_in_expr
                if hasattr(self.params[name], "default_format_type")
            }

            # If all default types are the same and not None
            if len(default_types) == 1:
                fmt = default_types.pop()
                if fmt:
                    formatter_cls = FORMAT_REGISTRY[fmt]
                    formatter = formatter_cls()
                    return formatter.format(self.evaluated_value)

        # 4. Fallback: plain string — convert sympy/float to a clean representation
        try:
            f = float(self.evaluated_value)
            if f == int(f):
                return str(int(f))
            return f"{f:g}"
        except (TypeError, ValueError):
            return str(self.evaluated_value)
