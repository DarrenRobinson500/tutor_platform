import sympy as sp
from .probability import *

ALLOWED_FUNCS = {
    "ways_sum": ways_sum,
    "nCr": nCr,
    "nPr": nPr,
    "hypergeom": hypergeom,
    "factorial": sp.factorial,
}

def evaluate_int_expression(expr: str, params: dict):
    for key, val in params.items():
        expr = expr.replace(f"{{{{ {key} }}}}", str(val))
        expr = expr.replace(f"{{{{{key}}}}}", str(val))

    try:
        sympy_expr = sp.sympify(expr, locals=ALLOWED_FUNCS)
        return sp.simplify(sympy_expr)
    except Exception:
        return expr

def simplify_fraction_expression(expr: str, params: dict) -> str:
    """
    Given a string like "num/den", evaluate both sides using the maths engine,
    simplify the resulting fraction, and return a clean 'a/b' string.
    """
    if "/" not in expr:
        # Not a fraction — evaluate normally
        value = evaluate_int_expression(expr, params)
        return str(value)

    num_str, den_str = expr.split("/", 1)

    # Evaluate numerator and denominator
    num_val = evaluate_int_expression(num_str.strip(), params)
    den_val = evaluate_int_expression(den_str.strip(), params)

    try:
        num_sym = sp.Rational(num_val)
        den_sym = sp.Rational(den_val)
        simplified = sp.simplify(num_sym / den_sym)

        # Ensure result is a rational number
        if isinstance(simplified, sp.Rational):
            return f"{simplified.p}/{simplified.q}"
        else:
            return str(simplified)

    except Exception:
        # Fallback: return unsimplified

        return f"{num_val}/{den_val}"


