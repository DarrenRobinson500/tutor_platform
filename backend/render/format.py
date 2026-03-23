import random

FORMAT_REGISTRY = {}

def register_format_type(cls):
    FORMAT_REGISTRY[cls.name] = cls
    return cls

class FormatType:
    name = None  # e.g. "fraction", "number", "percentage"

    def __init__(self, **options):
        self.options = options

    def format(self, value):
        raise NotImplementedError("FormatType subclasses must implement format()")

@register_format_type
class FractionFormat(FormatType):

    name = "fraction"
    default_format_type = "fraction"


    def format(self, value):
        # value may be "3/4", "-2/7", etc.
        if isinstance(value, str) and "/" in value:
            num, den = value.split("/")
            num, den = int(num), int(den)
        else:
            # Convert sympy types, floats, etc. to a Python Fraction
            from fractions import Fraction
            frac = Fraction(float(value)).limit_denominator(1000)
            num, den = frac.numerator, frac.denominator

        if num == 0 or den == 1:
            return str(num)

        return f"\\frac{{{num}}}{{{den}}}"

@register_format_type
class MixedNumberFormat(FormatType):
    name = "mixed_number"

    def format(self, value):
        if isinstance(value, str) and "/" in value:
            num, den = int(value.split("/")[0]), int(value.split("/")[1])
        else:
            from fractions import Fraction
            frac = Fraction(float(value)).limit_denominator(1000)
            num, den = frac.numerator, frac.denominator

        if num == 0:
            return "0"
        if den == 1:
            return str(num)

        sign_str = "-" if num < 0 else ""
        abs_num = abs(num)
        whole = abs_num // den
        remainder = abs_num % den

        if remainder == 0:
            return f"{sign_str}{whole}"
        if whole == 0:
            return f"{sign_str}\\frac{{{remainder}}}{{{den}}}"
        return f"{sign_str}{whole}\\frac{{{remainder}}}{{{den}}}"

@register_format_type
class DecimalFormat(FormatType):
    name = "decimal"

    def format(self, value):
        dp = int(self.options.get("decimal_places", 2))
        result = f"{float(value):.{dp}f}"
        # Strip trailing zeros (e.g. "3.40" → "3.4", "3.00" → "3")
        return result.rstrip("0").rstrip(".")

@register_format_type
class DollarFormat(FormatType):
    name = "dollar"

    def format(self, value):
        result = f"{float(value):,.2f}"
        # Strip ".00" for whole dollar amounts — $5 is cleaner than $5.00
        # Use \$ so KaTeX renders a literal dollar sign rather than entering math mode
        if result.endswith(".00"):
            return f"\\${result[:-3]}"
        return f"\\${result}"

@register_format_type
class PercentFormat(FormatType):
    name = "percent"

    def format(self, value):
        f = float(value) * 100
        if f == int(f):
            return f"{int(f)}%"
        return f"{f:g}%"

@register_format_type
class NumberFormat(FormatType):
    name = "number"
    default_format_type = "number"

    def format(self, value):
        sig_figs = int(self.options.get("sig_figs", 3))
        return f"{value:.{sig_figs}g}"

@register_format_type
class PercentageFormat(FormatType):
    name = "percentage"

    def format(self, value):
        sig_figs = int(self.options.get("sig_figs", 3))
        return f"{value * 100:.{sig_figs}g}%"

@register_format_type
class SurdFormat(FormatType):
    """Simplifies sqrt(n) into LaTeX surd form: e.g. sqrt(12) → 2\sqrt{3}, sqrt(16) → 4."""
    name = "surd"

    def format(self, value):
        from math import isqrt
        n = int(value ** 2)  # recover n from the sqrt result sympy gave us
        # Extract the largest perfect square factor
        a = 1
        for i in range(isqrt(n), 1, -1):
            if n % (i * i) == 0:
                a = i
                break
        b = n // (a * a)
        if b == 1:
            return str(a)
        if a == 1:
            return f"\\sqrt{{{b}}}"
        return f"{a}\\sqrt{{{b}}}"

@register_format_type
class IntegerFormat(FormatType):
    name = "integer"

    def format(self, value):
        return str(int(value))

@register_format_type
class BracketsFormat(FormatType):
    """Wraps the value in parentheses if negative, leaves positive values unchanged.
    e.g. -7 → (-7), 6 → 6"""
    name = "brackets"

    def format(self, value):
        n = int(value)
        if n < 0:
            return f"({n})"
        return str(n)

@register_format_type
class FactorFormat(FormatType):
    """Prime factorisation: factor(12) → '2 x 2 x 3', factor(100) → '2 x 2 x 5 x 5'."""
    name = "factor"

    def format(self, value):
        n = int(value)
        if n < 2:
            return str(n)
        factors = []
        d = 2
        while d * d <= n:
            while n % d == 0:
                factors.append(str(d))
                n //= d
            d += 1
        if n > 1:
            factors.append(str(n))
        return " x ".join(factors)