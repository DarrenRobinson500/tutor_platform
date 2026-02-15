import re
import random
from math import gcd
import yaml as _yaml
from .diagram.engine import *


def to_int(x):
    if isinstance(x, int):
        return x
    if isinstance(x, str):
        cleaned = re.sub(r"[^0-9-]", "", x)
        if cleaned in ("", "-"):
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None


def simplify_fraction(num, den):
    print("Simplify (pre):", num, den)
    num = to_int(num)
    den = to_int(den)
    print("Simplify (post):", num, den)
    g = gcd(num, den)
    result = num // g, den // g
    print("Simplify (result):", result)
    return result

def evaluate_expression(expr: str):
    if not re.match(r'^[0-9+\-*/().\s]+$', expr):
        return expr  # fallback: return raw string
    try:
        return eval(expr, {"__builtins__": {}})
    except Exception:
        return expr

def substitute_params_and_expressions(text, params):
    pattern = r"\{\{\s*(.*?)\s*\}\}"

    def repl(match):
        expr = match.group(1).strip()

        # Case 1: simple param like "a"
        if expr in params:
            return str(params[expr])

        # Case 2: expression like "b * a"
        try:
            # Only allow names that exist in params
            allowed = {k: v for k, v in params.items()}
            value = eval(expr, {"__builtins__": {}}, allowed)
            return str(value)
        except Exception:
            # Fallback: leave it unchanged
            return f"{{{{ {expr} }}}}"

    return re.sub(pattern, repl, text)

def generate_param_values(params):
    """Generate numeric or fraction values for params based on YAML structure."""
    generated = {}

    for key, spec in params.items():

        # Case 1: literal values (int, float, str)
        if isinstance(spec, (int, float, str)):
            generated[key] = spec
            continue

        # Case 2: random range { min: X, max: Y }
        if isinstance(spec, dict) and "min" in spec and "max" in spec:
            generated[key] = random.randint(spec["min"], spec["max"])
            continue

        # Case 3: expression-based value { type: int, value: "{{ a * c }}" }
        if isinstance(spec, dict) and "value" in spec and spec.get("type") == "int":
            raw_expr = spec["value"]
            substituted = substitute_params_and_expressions(raw_expr, generated)
            try:
                generated[key] = evaluate_expression(substituted)
            except Exception:
                generated[key] = None
            continue

        # Case 4: FRACTION type { type: fraction, value: "num/den" }
        if isinstance(spec, dict) and spec.get("type") in ["fraction", "fraction_unsimplified"]:
            raw_expr = spec.get("value")

            # Substitute params into the fraction expression
            substituted = substitute_params_and_expressions(raw_expr, generated)

            # Expect something like "3/8" or "a/b"
            if "/" in substituted:
                num_str, den_str = substituted.split("/")
                num = evaluate_expression(num_str)
                den = evaluate_expression(den_str)

                # Simplify
                if spec.get("type") in ["fraction"]:

                    num, den = simplify_fraction(num, den)

                # Store as "num/den"
                generated[key] = f"{num}/{den}"

            else:
                generated[key] = None

        continue

        # Case 5: unsupported → None
        generated[key] = None

    # debug_print_params(generated)
    return generated

def evaluate_rule_expression(expr, params):
    # Evaluate rule like "b != 0" or "c != d"
    # Only allow access to params, nothing else
    safe_locals = dict(params)
    return bool(eval(expr, {"__builtins__": {}}, safe_locals))

def render_template_preview(parsed):
    print("Rendering template preview")
    """
    1. Generate parameters
    2. Substitute ALL {{ ... }} in the entire YAML
    3. Reload substituted YAML
    4. Render question, answers, solution, diagram, etc.
    """

    # 1. Generate parameters + enforce validation rules
    collected_errors = []
    params = parsed.get("parameters", {})
    validation = parsed.get("validation", {})
    rules = validation.get("rules", [])

    MAX_ATTEMPTS = 10
    last_error = None

    for attempt in range(MAX_ATTEMPTS):
        generated_params = generate_param_values(params)

        rule_failed = False
        for rule in rules:
            expr = rule.get("check")
            message = rule.get("message", "Validation rule failed")

            try:
                if not evaluate_rule_expression(expr, generated_params):
                    rule_failed = True
                    last_error = message
                    break
            except Exception as e:
                rule_failed = True
                last_error = f"Rule error: {str(e)}"
                collected_errors.append(f"{last_error}")
                break

        if not rule_failed:
            break
    else:
        collected_errors.append(f"Parameter generation failed after {MAX_ATTEMPTS} attempts: {last_error}")
        raise ValueError(
            f"Parameter generation failed after {MAX_ATTEMPTS} attempts: {last_error}"
        )


    # 2. Substitute parameters
    print("Substituting parameters")
    original_yaml_text = _yaml.dump(parsed)
    substituted_yaml_text = substitute_params_and_expressions(
        original_yaml_text, generated_params
    )
    result = {
        "substituted_yaml": substituted_yaml_text,
        "params": generated_params,
    }

    # 3. Reload substituted YAML
    substituted = _yaml.safe_load(substituted_yaml_text) or {}

    # 4. Extract substituted fields
    try:
        question_text = substituted.get("question", {}).get("text", "")
    except Exception as e:
        question_text = f"[ERROR extracting question: {e}]"
        collected_errors.append(question_text)

    solution_block = substituted.get("solution", {})
    if isinstance(solution_block, dict):
        solution_text = solution_block.get("text", "")
    else:
        solution_text = f"[ERROR: solution must be a mapping, got {type(solution_block).__name__}]"
        collected_errors.append(solution_text)

    raw_answers = substituted.get("answers")

    if isinstance(raw_answers, dict):
        raw_answers = raw_answers.get("text", [])

    if not isinstance(raw_answers, list):
        collected_errors.append(f"Answers must be a list, got: {type(raw_answers).__name__}")
        raw_answers = []

    answers = []

    for ans in raw_answers:
        if "int" in ans:
            value = evaluate_expression(ans["int"])
            answers.append({
                "text": str(value),
                "correct": ans.get("correct", False)
            })
            continue

        if "fraction" in ans or "fraction_unsimplified" in ans:
            key = "fraction" if "fraction" in ans else "fraction_unsimplified"
            expr = ans[key]

            num_str, den_str = expr.split("/")
            try:
                num = evaluate_expression(num_str)
                den = evaluate_expression(den_str)
                simplified = simplify_fraction(num, den)
                answers.append({
                    "text": f"{simplified[0]}/{simplified[1]}",
                    "correct": ans.get("correct", False)
                })
            except Exception as e:
                answers.append({
                    "text": f"[ERROR processing fractions: {e}]",
                    "correct": ans.get("correct", False)
                })
                collected_errors.append(f"[ERROR processing fractions: {e}]")

            if key == "fraction":
                num, den = simplify_fraction(num, den)

            answers.append({
                "text": f"{num}/{den}",
                "correct": ans.get("correct", False)
            })
            continue

        answers.append(ans)

    # Deduplicate answers
    seen = set()
    deduped_answers = []
    for ans in answers:
        text = ans.get("text")
        if text not in seen:
            seen.add(text)
            deduped_answers.append(ans)

    # Diagram SVG + code (already substituted)
    print("Rendering (substituted parameters for diagram):", substituted["diagram"])

    diagram_code = substituted.get("diagram", "")

    svg = ""
    if isinstance(diagram_code, str) and diagram_code.strip():
        svg = render_diagram_from_code(diagram_code)
    else:
        print("Failed to svg render:", diagram_code)

    substituted = build_debug_yaml(parsed, generated_params, substituted)
    substituted = substituted.replace("\\n", "\n")

    try:                    result['question'] = question_text
    except Exception as e:  result['question'] = f"[ERROR: {e}]"

    try:                    result['answers'] = deduped_answers
    except Exception as e:  result['answers'] = f"[ERROR: {e}]"

    try:                    result['params'] = generated_params
    except Exception as e:  result['params'] = f"[ERROR: {e}]"

    try:                    result['solution'] = solution_text
    except Exception as e:  result['solution'] = f"[ERROR: {e}]"

    try:                    result['diagram_svg'] = svg
    except Exception as e:  result['diagram_svg'] = f"[ERROR: {e}]"

    try:                    result['diagram_code'] = diagram_code
    except Exception as e:  result['diagram_code'] = f"[ERROR: {e}]"

    try:                    result['substituted_yaml'] = substituted
    except Exception as e:  result[''] = f"[ERROR: {e}]"

    result['errors'] = collected_errors

    return result

def debug_print_params(params: dict):
    print("Generated Parameters:")
    max_len = max(len(k) for k in params.keys()) if params else 0
    for key, value in params.items():
        print(f"  {key.ljust(max_len)} : {value}")

def build_debug_yaml(parsed, generated_params, substituted):
    debug = {}

    debug["parameters"] = generated_params
    debug["question"] = substituted.get("question", {}).get("text", "")
    debug["solution"] = substituted.get("solution", {}).get("text", "")
    debug["answers"] = substituted.get("answers", [])
    debug["diagram"] = substituted.get("diagram", {})

    return _yaml.dump(debug, sort_keys=False)