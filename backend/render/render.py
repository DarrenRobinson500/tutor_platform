import yaml
import yaml as _yaml
import re
from .expr import *

EXPR_PATTERN = re.compile(r"{{(.*?)}}")


def _inject_format_pipe(text, format_type):
    """Rewrite {{ expr }} → {{ expr | format_type }} where no pipe already exists."""
    def repl(match):
        expr = match.group(1).strip()
        if "|" in expr:
            return match.group(0)
        return f"{{{{ {expr} | {format_type} }}}}"
    return EXPR_PATTERN.sub(repl, text)

class Render:
    def __init__(self, yaml_text):
        self.yaml_text = yaml_text
        self.template = yaml.safe_load(yaml_text)

        # Filled during rendering
        self.param_objects = {}
        self.substituted_yaml = None
        self.preview_yaml = None

    def render(self):
        self._load_parameters()
        self._substitute_expressions()
        return {
            "substituted_yaml": self.substituted_yaml,
            "preview": self.preview_yaml,
        }

    def _load_parameters(self):
        from .param import NameParameter, ExprParameter
        NameParameter._used_in_render = set()
        param_specs = self.template.get("parameters", {})
        for name, spec in param_specs.items():
            self.param_objects[name] = RandomParameter.from_yaml(name, spec)
        # Second pass: resolve derived (expr) parameters in definition order.
        # Each expr param must be defined after any params it references.
        for name, param in self.param_objects.items():
            if isinstance(param, ExprParameter):
                param.resolve(self.param_objects)

    def _substitute_expressions(self):
        # Deep copy the template for two different outputs
        substituted = yaml.safe_load(self.yaml_text)
        preview = yaml.safe_load(self.yaml_text)

        def walk(node, formatter):
            if isinstance(node, str):
                return self._process_string(node, formatter)
            if isinstance(node, list):
                return [walk(item, formatter) for item in node]
            if isinstance(node, dict):
                return {k: walk(v, formatter) for k, v in node.items()}
            return node

        self.substituted_yaml = walk(substituted, formatter="raw")
        self.preview_yaml = walk(preview, formatter="formatted")

    def _process_string(self, text, formatter):
        def repl(match):
            expr_text = match.group(1).strip()
            try:
                node = ExpressionNode(expr_text, self.param_objects)
            except Exception as e:
                raise ValueError(f"Error evaluating expression '{{{{ {expr_text} }}}}': {e}") from e
            value = node.evaluate()

            if formatter == "raw":
                return str(value)
            else:
                return node.format()

        return EXPR_PATTERN.sub(repl, text)


def _evaluate_rule(expr, params):
    from math import gcd
    from fractions import Fraction
    from ..maths.fractions import denominator, numerator
    # Allow {{ a }} style in addition to bare variable names
    expr = EXPR_PATTERN.sub(lambda m: m.group(1).strip(), expr)
    # Convert string fraction values (e.g. "3/5") to numeric so comparisons work
    numeric_params = {}
    for k, v in params.items():
        if isinstance(v, str):
            try:
                numeric_params[k] = Fraction(v)
            except (ValueError, ZeroDivisionError):
                numeric_params[k] = v
        else:
            numeric_params[k] = v
    from .expr import _LIST_CONTEXT
    ctx = {"__builtins__": {}, "gcd": gcd, "denominator": denominator, "numerator": numerator}
    ctx.update(_LIST_CONTEXT)
    # List parameters must be in globals (ctx), not locals, so that list
    # comprehensions inside the rule expression can access them (Python 3
    # comprehensions have their own scope and cannot see eval() locals).
    scalar_params = {}
    for k, v in numeric_params.items():
        if isinstance(v, list):
            ctx[k] = v
        else:
            scalar_params[k] = v
    return bool(eval(expr, ctx, scalar_params))


def render_template_preview(parsed):
    """
    Drop-in replacement for rendering.render_template_preview.
    Uses the Render class for parameter generation and expression substitution.
    Returns: {question, answers, solution, diagram_svg, diagram_code,
               substituted_yaml, params, errors}
    """
    yaml_text = _yaml.dump(parsed)

    validation = parsed.get("validation", {})
    rules = validation.get("rules", []) if isinstance(validation, dict) else []

    MAX_ATTEMPTS = 10
    last_error = None
    renderer = None
    collected_errors = []

    for attempt in range(MAX_ATTEMPTS):
        renderer = Render(yaml_text)
        renderer.render()

        params = {name: p.value for name, p in renderer.param_objects.items()}

        rule_failed = False
        for rule in rules:
            check = rule.get("check")
            message = rule.get("message", "Validation rule failed")
            try:
                if not _evaluate_rule(check, params):
                    rule_failed = True
                    last_error = message
                    break
            except Exception as e:
                rule_failed = True
                last_error = f"Rule error: {e}"
                collected_errors.append(last_error)
                break

        if not rule_failed:
            break
    else:
        raise ValueError(
            f"Parameter generation failed after {MAX_ATTEMPTS} attempts: {last_error}"
        )

    preview = renderer.preview_yaml or {}
    raw_sub = renderer.substituted_yaml or {}
    params = {name: p.value for name, p in renderer.param_objects.items()}

    # Extract question and solution from formatted preview
    question_block = preview.get("question", {})
    if isinstance(question_block, dict):
        question_text = question_block.get("text", "")
    else:
        question_text = str(question_block) if question_block else ""

    solution_block = preview.get("solution", {})
    if isinstance(solution_block, dict):
        solution_text = solution_block.get("text", "")
    else:
        solution_text = str(solution_block) if solution_block else ""

    # Extract answers: use formatted preview for text-format answers (so | fraction, | decimal etc.
    # are applied), and raw_sub for old type-key answers (int, dec_1, fraction key) which are
    # formatted manually below.
    raw_answers = raw_sub.get("answers", [])
    if not isinstance(raw_answers, list):
        collected_errors.append(f"Answers must be a list, got: {type(raw_answers).__name__}")
        raw_answers = []

    preview_answers = preview.get("answers", [])
    if not isinstance(preview_answers, list):
        preview_answers = []

    answers = []
    for i, ans in enumerate(raw_answers):
        if not isinstance(ans, dict):
            answers.append(ans)
            continue

        # Graph answer: answer contains a diagram spec dict or code string.
        if "diagram" in ans:
            diagram_spec = ans["diagram"]
            if isinstance(diagram_spec, dict):
                diagram_type = diagram_spec.get("type", "Cartesian")
                parts = []
                for k, v in diagram_spec.items():
                    if k == "type":
                        continue
                    parts.append(f'eq: "{v}"' if k == "eq" else f"{k}: {v}")
                code = f'{diagram_type}({", ".join(parts)})'
            else:
                code = str(diagram_spec)
            from ..diagram.engine import render_diagram_from_code
            svg = render_diagram_from_code(code)
            answers.append({"diagram_svg": svg, "correct": ans.get("correct", False)})
            continue

        # New format: answer has a text field.
        # If a `format` key is present, inject it as a pipe into each {{ }} expression
        # and re-process through the renderer so the correct formatter is applied.
        # Otherwise fall back to the already-walked preview value.
        if "text" in ans:
            format_type = ans.get("format")
            raw_text = str(ans.get("text", ""))
            if format_type:
                piped = _inject_format_pipe(raw_text, format_type)
                if "{{" in piped:
                    # Expressions still present — process through renderer with pipe injected
                    formatted_text = renderer._process_string(piped, "formatted")
                else:
                    # Already substituted by walk() — apply formatter directly to the value
                    from fractions import Fraction
                    from .format import FORMAT_REGISTRY
                    formatter_cls = FORMAT_REGISTRY.get(format_type)
                    if formatter_cls:
                        try:
                            val = Fraction(raw_text) if "/" in raw_text else float(raw_text)
                            formatted_text = formatter_cls().format(val)
                        except Exception:
                            formatted_text = raw_text
                    else:
                        formatted_text = raw_text
            else:
                preview_ans = preview_answers[i] if i < len(preview_answers) else {}
                formatted_text = str(preview_ans.get("text", raw_text)) if isinstance(preview_ans, dict) else raw_text
            answers.append({"text": formatted_text, "correct": ans.get("correct", False)})
            continue

        # Old format: answer value is stored under a type key; Render has already
        # substituted {{ }} expressions so the value is a number string like "12" or "3/7".
        if "logic" in ans:
            try:
                is_true = _evaluate_rule(ans["logic"], params)
            except Exception:
                is_true = False
            answers.append({"text": ans.get("text", ""), "correct": ans.get("correct", False) and is_true})
            continue

        if "input" in ans:
            text = str(ans["input"])
            answer_obj = {"text": text, "correct": ans.get("correct", False), "input_type": "text"}
            if ans.get("format_instruction"):
                answer_obj["format_instruction"] = str(ans["format_instruction"])
            if ans.get("answer_format"):
                answer_obj["answer_format"] = str(ans["answer_format"])
            if ans.get("tolerance") is not None:
                answer_obj["tolerance"] = float(ans["tolerance"])
            answers.append(answer_obj)
            continue

        if "int" in ans:
            try:
                text = str(evaluate_int_expression(str(ans["int"]), {}))
            except Exception:
                text = str(ans["int"])
            answers.append({"text": text, "correct": ans.get("correct", False)})
            continue

        if "dec_1" in ans:
            try:
                text = str(evaluate_dec_expression(str(ans["dec_1"]), {}, 1))
            except Exception:
                text = str(ans["dec_1"])
            answers.append({"text": text, "correct": ans.get("correct", False)})
            continue

        if "dec_2" in ans:
            try:
                text = str(evaluate_dec_expression(str(ans["dec_2"]), {}, 2))
            except Exception:
                text = str(ans["dec_2"])
            answers.append({"text": text, "correct": ans.get("correct", False)})
            continue

        if "fraction" in ans:
            try:
                val = evaluate_fraction_expression(str(ans["fraction"]), {})
                text = FractionFormat().format(val)
            except Exception:
                text = str(ans["fraction"])
            answers.append({"text": text, "correct": ans.get("correct", False)})
            continue

        answers.append(ans)

    seen = set()
    deduped_answers = []
    for ans in answers:
        if isinstance(ans, dict):
            # Diagram answers have no text — use a unique sentinel per index so
            # they are never collapsed by the deduplication logic.
            key = ans.get("text") if "text" in ans else id(ans)
        else:
            key = str(ans)
        if key not in seen:
            seen.add(key)
            deduped_answers.append(ans)

    # Diagram
    diagram_code = preview.get("diagram", "")
    svg = ""
    if isinstance(diagram_code, str) and diagram_code.strip() and diagram_code.strip().lower() != "none":
        try:
            from ..diagram.engine import render_diagram_from_code
            svg = render_diagram_from_code(diagram_code)
        except Exception as e:
            collected_errors.append(f"Diagram error: {e}")
            diagram_code = ""
    else:
        diagram_code = ""

    # Multi-step AlgebraTable: pre-render one SVG per blank with its highlight active
    multi_step = None
    if diagram_code and diagram_code.strip().startswith("AlgebraTable") and "blanks:" in diagram_code:
        try:
            import re as _mre
            from ..diagram import algebra_table as _at
            from ..diagram.engine import render_diagram_from_code as _rdc
            d = _at.parse(diagram_code)
            if d and d.blanks:
                # Get raw solution template (before param substitution) so we can
                # re-render it with blank_x = each step's x value.
                _raw = _yaml.safe_load(yaml_text)
                _sol_raw = _raw.get("solution", "")
                _sol_tmpl = (
                    _sol_raw.get("text", "") if isinstance(_sol_raw, dict)
                    else (str(_sol_raw) if _sol_raw else "")
                )

                steps = []
                for i, bx in enumerate(d.blanks):
                    # Only keep blanks from this step onward; earlier cells show their value
                    remaining = ",".join(str(b) for b in d.blanks[i:])
                    step_code = _mre.sub(r'\bblanks:\s*"[^"]*"', f'blanks: "{remaining}"', diagram_code)
                    if _mre.search(r'\bhighlight:\s*-?\d+', step_code):
                        step_code = _mre.sub(r'\bhighlight:\s*-?\d+', f'highlight: {bx}', step_code)
                    else:
                        step_code = step_code.rstrip(')') + f', highlight: {bx})'
                    step_svg = _rdc(step_code)

                    answer_val = _at._eval_expr(d.expr, bx)
                    if answer_val is None:
                        answer_str = ""
                    elif isinstance(answer_val, float) and answer_val == int(answer_val):
                        answer_str = str(int(answer_val))
                    else:
                        answer_str = str(answer_val)

                    # Render solution with blank_x substituted as a literal for this step.
                    # We inject the numeric value directly into {{ }} expressions so we
                    # don't need to mutate param objects.
                    step_solution = ""
                    if _sol_tmpl:
                        try:
                            def _inject_blank_x(tmpl, val):
                                return _mre.sub(
                                    r'\{\{(.*?)\}\}',
                                    lambda m: '{{' + _mre.sub(r'\bblank_x\b', str(val), m.group(1)) + '}}',
                                    tmpl,
                                )
                            step_solution = renderer._process_string(_inject_blank_x(_sol_tmpl, bx), "formatted")
                        except Exception as _e:
                            collected_errors.append(f"Multi-step solution error (blank_x={bx}): {_e}")
                            step_solution = ""

                    steps.append({"svg": step_svg, "answer": answer_str, "solution": step_solution})
                multi_step = {"steps": steps}
        except Exception:
            pass

    # Multi-part questions via question.parts (any diagram type)
    if not multi_step:
        preview_parts = []
        if isinstance(question_block, dict):
            preview_parts = question_block.get("parts", [])
            if not isinstance(preview_parts, list):
                preview_parts = []
        # Use raw_sub for answers (unformatted, for exact comparison)
        raw_q_block = raw_sub.get("question", {})
        raw_parts = raw_q_block.get("parts", []) if isinstance(raw_q_block, dict) else []

        if preview_parts:
            part_steps = []
            for i, part in enumerate(preview_parts):
                if not isinstance(part, dict):
                    continue
                raw_part = raw_parts[i] if i < len(raw_parts) and isinstance(raw_parts[i], dict) else {}

                # Compute raw answer: prefer value from raw substitution walk,
                # then fall back to re-evaluating the answer template directly from param objects.
                # Accept both "answer" (canonical) and "answers" (common typo).
                raw_ans = str(
                    raw_part.get("answer", raw_part.get("answers",
                    part.get("answer", part.get("answers", ""))))
                )
                if "{{" in raw_ans:
                    # Substitution didn't fully expand — re-process directly
                    try:
                        raw_ans = renderer._process_string(raw_ans, "raw")
                    except Exception:
                        pass
                # Normalise: convert "14.0" or sympy float strings → clean int/decimal
                try:
                    _f = float(raw_ans)
                    raw_ans = str(int(_f)) if _f == int(_f) else f"{_f:g}"
                except (ValueError, TypeError):
                    pass

                step = {
                    "svg": svg,
                    "question": str(part.get("text", "")),
                    "answer": raw_ans,
                    "solution": str(part.get("solution", "")),
                }
                tol = part.get("tolerance")
                if tol is not None:
                    try:
                        step["tolerance"] = float(tol)
                    except (TypeError, ValueError):
                        pass
                part_steps.append(step)
            if part_steps:
                multi_step = {"steps": part_steps}

    # Build debug substituted_yaml string
    debug = {
        "parameters": params,
        "question": question_text,
        "solution": solution_text,
        "answers": raw_answers,
        "diagram": preview.get("diagram", {}),
    }
    if multi_step:
        debug["multi_step_answers"] = [
            {"question": s.get("question", ""), "answer": s.get("answer", "")}
            for s in multi_step.get("steps", [])
        ]
    substituted_yaml = _yaml.dump(debug, sort_keys=False)

    return {
        "question": question_text,
        "answers": deduped_answers,
        "solution": solution_text,
        "diagram_svg": svg,
        "diagram_code": diagram_code,
        "substituted_yaml": substituted_yaml,
        "params": params,
        "errors": collected_errors,
        "multi_step": multi_step,
    }