from .format import *
from math import gcd
from fractions import Fraction as _Fraction

_NAMES = [
    "Emma", "Olivia", "Ava", "Isabella", "Sophia",
    "Liam", "Noah", "Oliver", "Elijah", "James",
]

class RandomParameter:
    def __init__(self, name, type_name, options):
        self.name = name
        self.type_name = type_name
        self.options = options or {}
        self.value = self.generate({})

    def __str__(self):
        return f"{self.name}: {self.value}"

    @classmethod
    def from_yaml(cls, name, spec):
        # spec may be literal, dict, or structured type
        if isinstance(spec, (int, float, str)):
            return LiteralParameter(name, spec)

        if "value" in spec:
            return LiteralParameter(name, spec["value"])

        param_type = spec.get("type")

        if param_type == "fraction":
            return FractionParameter(name, spec)
        if param_type == "decimal":
            return DecimalParameter(name, spec)
        if param_type == "dollar":
            return DollarParameter(name, spec)
        if param_type == "percent":
            return PercentParameter(name, spec)
        if param_type == "choice":
            return ChoiceParameter(name, spec)
        if param_type == "name":
            return NameParameter(name, spec)
        if param_type == "int":
            return IntParameter(name, spec)
        if param_type == "list":
            return ListParameter(name, spec)

        if "expr" in spec:
            return ExprParameter(name, spec)

        if "min" in spec and "max" in spec:
            return RangeParameter(name, spec)

        if "size" in spec:
            return RangeParameter(name, spec)

        raise ValueError(f"Unsupported parameter spec: {spec}")

    def generate(self, context):
        raise NotImplementedError

    def format(self, value):
        if not hasattr(self, "format_type") or self.format_type is None:
            return value

        formatter_cls = FORMAT_REGISTRY[self.format_type]
        formatter = formatter_cls(**self.options)
        return formatter.format(value)


class LiteralParameter(RandomParameter):
    def __init__(self, name, value):
        self._literal_value = value
        super().__init__(name, "literal", {})

    def generate(self, context):
        return self._literal_value

class RangeParameter(RandomParameter):
    SIZE_MAP = {
        "small":  (2, 5),
        "medium": (2, 10),
    }

    def __init__(self, name, options):
        super().__init__(name, "range", options)
        if options.get("brackets_when_negative"):
            self.default_format_type = "brackets"

    @staticmethod
    def _round_2_sig_figs(n):
        from math import log10, ceil
        if n == 0:
            return 0
        d = ceil(log10(abs(n) + 1e-9))
        factor = 10 ** (d - 2)
        return int(round(n / factor) * factor)

    def generate(self, context):
        size = self.options.get("size")
        if size == "large":
            value = self._round_2_sig_figs(random.randint(20, 1000))
        elif size in self.SIZE_MAP:
            lo, hi = self.SIZE_MAP[size]
            value = random.randint(lo, hi)
        else:
            lo = int(self.options["min"])
            hi = int(self.options["max"])
            step = int(self.options.get("step", 1))
            if step > 1:
                steps = list(range(lo, hi + 1, step))
                value = random.choice(steps)
            else:
                value = random.randint(lo, hi)

        sign = self.options.get("sign", "pos")
        if sign == "neg":
            value = -abs(value)
        elif sign == "pos_neg":
            if random.choice([True, False]):
                value = -abs(value)

        return value

class IntParameter(RandomParameter):
    """Generates a random integer using a named size preset or explicit min/max.

    YAML spec:
      n: { type: int, size: medium }      # small=(2,5), medium=(2,10), large=(2,20)
      n: { type: int, min: 3, max: 15 }   # explicit range
    """
    SIZE_MAP = {
        "small": (2, 5),
        "medium": (2, 10),
        "large": (2, 20),
    }

    def __init__(self, name, options):
        super().__init__(name, "int", options)

    def generate(self, context):
        size = self.options.get("size")
        if size in self.SIZE_MAP:
            lo, hi = self.SIZE_MAP[size]
        else:
            lo = int(self.options.get("min", 2))
            hi = int(self.options.get("max", 10))
        return random.randint(lo, hi)


class FractionParameter(RandomParameter):
    def __init__(self, name, options):
        super().__init__(name, "fraction", options)
        self.default_format_type = "mixed_number" if options.get("mixed") else "fraction"

    def generate(self, context):
        SIZE_MAP = {
            "v_small": (2, 5),
            "small": (2, 5),
            "medium": (2, 10),
            "large": (2, 20),
        }

        size = self.options.get("size", "medium")
        sign = self.options.get("sign", "pos")
        simplified = self.options.get("simplified", True)

        den_min, den_max = SIZE_MAP.get(size, (2, 10))
        den = random.randint(den_min, den_max)

        if size == "v_small":
            num = 1
        elif self.options.get("mixed"):
            # Generate a proper fractional part, then add a whole number
            num = random.randint(1, den - 1)
            min_whole = self.options.get("min_whole", 1)
            max_whole = self.options.get("max_whole", 5)
            whole = random.randint(min_whole, max_whole)
            num = whole * den + num  # store as improper fraction
        else:
            proper = self.options.get("proper", None)
            num = random.randint(1, den - 1)
            if proper == False:
                num = random.randint(den + 1, den_max)

        if simplified:
            g = gcd(num, den)
            num //= g
            den //= g

        if sign == "neg":
            num = -abs(num)
        elif sign == "pos_neg":
            if random.choice([True, False]):
                num = -abs(num)

        return f"{num}/{den}"


class DecimalParameter(RandomParameter):
    """Generates a decimal value with a fixed number of decimal places.

    YAML spec:
      a: { type: decimal, min: 1, max: 10, decimal_places: 1 }

    Stored as an exact fraction string (e.g. "17/5") so sympy arithmetic
    stays precise. Displayed via DecimalFormat (strips trailing zeros).
    Use {{ a | decimal(decimal_places=2) }} to override display precision.
    """
    default_format_type = "decimal"

    def __init__(self, name, options):
        super().__init__(name, "decimal", options)
        self.default_format_options = {"decimal_places": int(options.get("decimal_places", 1))}

    def generate(self, context):
        dp = int(self.options.get("decimal_places", 1))
        scale = 10 ** dp
        min_scaled = int(float(self.options["min"]) * scale)
        max_scaled = int(float(self.options["max"]) * scale)
        raw = random.randint(min_scaled, max_scaled)
        f = _Fraction(raw, scale)
        return f"{f.numerator}/{f.denominator}"


class DollarParameter(RandomParameter):
    """Generates a dollar-and-cents amount.

    YAML spec:
      price: { type: dollar, min: 5, max: 50 }

    min/max are in whole dollars. The generated value includes cents and is
    stored as an exact fraction (e.g. "$12.50" → "25/2"). Displayed via
    DollarFormat as "$12.50".
    """
    default_format_type = "dollar"

    def __init__(self, name, options):
        super().__init__(name, "dollar", options)

    def generate(self, context):
        size = self.options.get("size")

        if size == "small":
            # Whole dollars only, $3–$8
            dollars = random.randint(
                int(self.options.get("min", 3)),
                int(self.options.get("max", 8)),
            )
            return f"{dollars}/1"

        if size == "large":
            # 2 significant figures, multiples of $10 from $10–$1000
            step = int(self.options.get("step", 10))
            lo = int(self.options.get("min", 10)) // step
            hi = int(self.options.get("max", 1000)) // step
            dollars = random.randint(lo, hi) * step
            return f"{dollars}/1"

        # If step is specified, generate a whole-dollar multiple of step
        if "step" in self.options:
            step = int(self.options["step"])
            lo = int(self.options.get("min", 0)) // step
            hi = int(self.options.get("max", 100)) // step
            dollars = random.randint(lo, hi) * step
            return f"{dollars}/1"

        # Default / size == "medium": dollars with cents, $3–$10
        min_cents = int(float(self.options.get("min", 3)) * 100)
        max_cents = int(float(self.options.get("max", 10)) * 100)
        cents = random.randint(min_cents, max_cents)
        f = _Fraction(cents, 100)
        return f"{f.numerator}/{f.denominator}"


class PercentParameter(RandomParameter):
    """Generates a whole-number percentage value.

    YAML spec:
      rate: { type: percent, min: 10, max: 90 }

    Stored as a fraction string (e.g. "35/100"). Displayed via PercentFormat as "35%".
    In expressions, the raw value is the decimal proportion, so
    {{ a * b }} on two percent params gives the correct result directly.
    """
    default_format_type = "percent"
    COMMON_VALUES = [1, 5, 10, 12.5, 20, 25, 50]

    def __init__(self, name, options):
        super().__init__(name, "percent", options)

    def generate(self, context):
        if self.options.get("common"):
            pct = random.choice(self.COMMON_VALUES)
            f = _Fraction(str(pct)) / 100
            return f"{f.numerator}/{f.denominator}"
        n = random.randint(int(self.options["min"]), int(self.options["max"]))
        return f"{n}/100"


class ChoiceParameter(RandomParameter):
    """Picks one value at random from an explicit list.

    YAML spec:
      angle:
        type: choice
        values: [10, 30, 45, 60, 80, 90]

    The chosen value is stored as-is (int or float).
    """

    def __init__(self, name, options):
        super().__init__(name, "choice", options)

    def generate(self, context):
        values = self.options.get("values", [])
        if not values:
            raise ValueError(f"ChoiceParameter '{self.name}' has an empty values list")
        return random.choice(values)


class NameParameter(RandomParameter):
    """Picks a unique child's name per render from a built-in pool of 10 names.

    YAML spec:
      student: { type: name }

    Multiple name parameters within the same template each receive a different
    name. The pool is reset at the start of every render.
    """

    _used_in_render: set = set()

    def __init__(self, name, options):
        super().__init__(name, "name", options)

    def generate(self, context):
        available = [n for n in _NAMES if n not in NameParameter._used_in_render]
        if not available:
            available = list(_NAMES)  # fallback: all 10 used, start over
        chosen = random.choice(available)
        NameParameter._used_in_render.add(chosen)
        return chosen


class ListParameter(RandomParameter):
    """Generates a list of random integers.

    YAML spec:
      data:
        type: list
        count: 5      # number of values
        min: 1        # minimum value (inclusive)
        max: 10       # maximum value (inclusive)

    The value is a Python list, e.g. [3, 5, 7, 2, 8].
    Use {{ data | sorted }} to display sorted, or {{ mode(data) }} etc.
    """

    def __init__(self, name, options):
        super().__init__(name, "list", options)

    SIZE_MAP = {
        "small":  (2, 9),
        "medium": (2, 20),
        "large":  (2, 99),
    }

    def generate(self, context):
        count = int(self.options.get("count", 5))
        size = self.options.get("size")
        if size in self.SIZE_MAP:
            lo, hi = self.SIZE_MAP[size]
        else:
            lo = int(self.options.get("min", 1))
            hi = int(self.options.get("max", 10))
        values = [random.randint(lo, hi) for _ in range(count)]
        if self.options.get("order", False):
            values.sort()
        return values


class ExprParameter(RandomParameter):
    """A derived parameter whose value is computed from an expression over other parameters.

    YAML spec:
      total:
        expr: "2 * (a + b)"       # bare expression
      total:
        expr: "{{ 2 * (a + b) }}" # {{ }} wrapper also accepted

    The parameter must be defined AFTER any parameters it references so that
    their values are already available when it is resolved.
    """

    def __init__(self, name, options):
        # Bypass the normal super().__init__ which would call generate() immediately.
        self.name = name
        self.type_name = "expr"
        self.options = options or {}
        raw = str(options.get("expr", "0")).strip()
        # Strip optional {{ }} wrapper
        import re as _re
        m = _re.match(r'^\{\{\s*(.*?)\s*\}\}$', raw)
        self._expr = m.group(1).strip() if m else raw
        self.value = None   # filled by resolve()

    def generate(self, context):
        return None   # not used; see resolve()

    def resolve(self, param_objects):
        """Evaluate the expression using already-generated param values."""
        from .expr import ExpressionNode
        try:
            node = ExpressionNode(self._expr, param_objects)
            result = node.evaluate()
            # Convert sympy types to plain Python so the value is JSON-serialisable
            try:
                f = float(result)
                self.value = int(f) if f == int(f) else f
            except (TypeError, ValueError):
                self.value = result
        except Exception as e:
            raise ValueError(f"Derived parameter '{self.name}': {e}") from e
