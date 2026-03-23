from .models import *
import yaml
import traceback as _traceback
from .render import render_template_preview
from .validation import *
from rest_framework.response import Response

import re as _re

def _fix_unquoted_diagram(content: str) -> str:
    """
    Quote an unquoted diagram string so YAML doesn't misparse the key: value
    pairs inside diagram command strings like Triangle(...) or Cartesian(...).

    Handles both forms:
        diagram: Triangle(a: 5, b: 5, c: 6)
        diagram:
          Triangle(a: 5, b: 5, c: 6)
    """
    def _quote(value: str) -> str:
        """Return single-quoted version of value, or the original if already safe."""
        value = value.strip()
        if value.startswith(("'", '"', '{', '|', '>')):
            return value
        if _re.match(r'[A-Z][A-Za-z]+\s*\(', value):
            return "'" + value.replace("'", "''") + "'"
        return value

    # Case 1: value on the same line — "diagram: Triangle(...)"
    def _fix_same_line(m):
        raw = m.group(2)
        quoted = _quote(raw)
        return m.group(1) + quoted if quoted != raw.strip() else m.group(0)

    content = _re.sub(
        r'^(\s*diagram:\s+)([^\n\'"\[{|>][^\n]+)$',
        _fix_same_line,
        content,
        flags=_re.MULTILINE,
    )

    # Case 2: value on the next indented line — "diagram:\n  Triangle(...)"
    def _fix_next_line(m):
        prefix = m.group(1)   # "diagram:\n"
        indent = m.group(2)   # leading whitespace of value line
        raw = m.group(3)
        quoted = _quote(raw)
        return (prefix + indent + quoted) if quoted != raw.strip() else m.group(0)

    content = _re.sub(
        r'^(\s*diagram:\s*\n)(\s+)([^\n\'"\[{|>][^\n]+)$',
        _fix_next_line,
        content,
        flags=_re.MULTILINE,
    )

    return content


_PARAM_PROPERTY_KEYS = {
    'min', 'max', 'type', 'size', 'proper', 'simplified', 'sign',
    'mixed', 'min_whole', 'max_whole', 'decimal_places', 'value',
    'min_numerator', 'max_numerator', 'min_denominator', 'max_denominator',
    'values', 'step',
}

_TOP_LEVEL_KEYS = {
    'title', 'years', 'difficulty', 'parameters', 'question',
    'answers', 'solution', 'diagram', 'validation', 'introduction', 'worked_example',
}


def _fix_parameters_indentation(content: str) -> str:
    """
    Detect and repair incorrectly indented parameters blocks.

    The AI sometimes emits:
        parameters:
            a:          ← 4 spaces
          min: 2        ← 2 spaces (should be 6, or at least deeper than 'a:')
          max: 5
        b:              ← 0 spaces (should be 2)
          min: 1

    Strategy:
      1. Quick-parse the YAML. If every parameter already has a non-null dict
         value, indentation is fine — return unchanged.
      2. Otherwise, scan the raw text from 'parameters:' forward, collecting
         parameter names (any key NOT in _PARAM_PROPERTY_KEYS and NOT a known
         top-level key) and their properties, then re-emit the block at the
         canonical 2-space / 4-space indentation.
    """
    try:
        parsed = yaml.safe_load(content) or {}
    except Exception:
        parsed = {}

    params = parsed.get('parameters', {})
    # If already a valid dict of dicts, nothing to fix
    if isinstance(params, dict) and params and all(
        isinstance(v, dict) and v for v in params.values()
    ):
        return content

    lines = content.split('\n')

    # Find the 'parameters:' line
    param_idx = next(
        (i for i, l in enumerate(lines) if _re.match(r'^parameters\s*:', l)),
        None,
    )
    if param_idx is None:
        return content

    # Scan forward, collecting (name, {prop: raw_value}) entries
    entries = []
    current_name = None
    current_props = {}

    for line in lines[param_idx + 1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        m = _re.match(r'^([a-zA-Z_]\w*)\s*:\s*(.*)', stripped)
        if not m:
            continue

        key, raw_val = m.group(1), m.group(2).strip()

        # Stop when we reach the next known top-level section
        if key in _TOP_LEVEL_KEYS:
            break

        if key in _PARAM_PROPERTY_KEYS:
            if current_name is not None:
                current_props[key] = raw_val
        else:
            # New parameter name
            if current_name is not None:
                entries.append((current_name, current_props))
            current_name = key
            current_props = {}

    if current_name is not None:
        entries.append((current_name, current_props))

    if not entries:
        return content

    # Find where the old block ends in the line list
    block_end = param_idx + 1
    for i in range(param_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith('#'):
            block_end = i + 1
            continue
        m = _re.match(r'^([a-zA-Z_]\w*)\s*:', lines[i])
        if m and m.group(1) in _TOP_LEVEL_KEYS:
            break
        block_end = i + 1

    # Re-emit with canonical indentation (2 spaces / 4 spaces)
    new_block = []
    for name, props in entries:
        new_block.append(f'  {name}:')
        for prop_key, prop_val in props.items():
            new_block.append(f'    {prop_key}: {prop_val}' if prop_val else f'    {prop_key}:')

    new_lines = lines[:param_idx + 1] + new_block + lines[block_end:]
    return '\n'.join(new_lines)


def generate_preview_from_content(content: str):
    # 1. Parse YAML
    # print("Generate preview from content - 1")
    content = _fix_unquoted_diagram(content)
    content = _fix_parameters_indentation(content)
    try:
        parsed = yaml.safe_load(content)
    except Exception as e:
        # print("Generate preview from content - 1 (failed)")
        return {
            "ok": False,
            "preview": {
                "question": "",
                "answers": [],
                "solution": "",
                "diagram_svg": "",
                "diagram_code": "",
                "substituted_yaml": content,
                "params": {},
                "errors": [f"YAML error: {str(e)}"]
            },
            "error": f"YAML error: {str(e)}"
        }

    # 2. Validate
    # print("Generate preview from content - 2")
    errors = validate_template(parsed)
    if errors:
        return {
            "ok": False,
            "preview": parsed,
            "error": errors
        }

    # 3. Render preview
    # print("Generate preview from content - 3")
    try:
        preview = render_template_preview(parsed)
        if "substituted_yaml" not in preview:
            preview["substituted_yaml"] = yaml.safe_dump(preview.get("full_yaml", parsed))
        #
        # preview["substituted_yaml"] = yaml.safe_dump(parsed)
        return {
            "ok": True,
            "preview": preview,
            "error": None
        }
    except Exception as e:
        tb = _traceback.format_exc()
        msg = f"{type(e).__name__}: {e}\n\n{tb}"
        return {
            "ok": False,
            "preview": {
                "question": "",
                "answers": [],
                "solution": "",
                "diagram_svg": "",
                "diagram_code": "",
                "substituted_yaml": content,
                "params": {},
                "errors": [msg]
            },
            "error": msg
        }


def generate_values_and_question(template_id: int):
    # 1. Load template
    template_obj = Template.objects.select_related("skill").get(pk=template_id)
    print("Template object", template_obj)
    try:
        template_obj = Template.objects.select_related("skill").get(pk=template_id)
    except Template.DoesNotExist:
        print("Template doesn't exist")
        return {
            "ok": False,
            "preview": None,
            "error": f"Template {template_id} not found"
        }

    content = template_obj.content
    # print("Generate values and question (content):", content)

    # 2. Parse YAML
    try:
        parsed = yaml.safe_load(content)
    except Exception as e:
        return {
            "ok": False,
            "preview": {
                "question": "",
                "answers": [],
                "solution": "",
                "diagram_svg": "",
                "diagram_code": "",
                "substituted_yaml": content,
                "params": {},
                "errors": [f"YAML error: {str(e)}"]
            },
            "error": f"YAML error: {str(e)}"
        }

    # 3. Validate
    errors = validate_template(parsed)
    if errors:
        return {
            "ok": False,
            "preview": parsed,
            "error": errors
        }

    # 4. Render preview
    try:
        preview = render_template_preview(parsed)

        # Always include substituted YAML
        if "substituted_yaml" not in preview:
            preview["substituted_yaml"] = yaml.safe_dump(preview.get("full_yaml", parsed))

        # preview["substituted_yaml"] = yaml.safe_dump(parsed)

        # Inject metadata
        preview["skill"] = template_obj.skill.description if template_obj.skill else None
        preview["grade"] = template_obj.grade
        preview["difficulty"] = template_obj.difficulty

        # Inject linked knowledge items (rendered)
        knowledge_items = []
        for k in template_obj.knowledge_items.all():
            svg = ""
            if k.diagram and k.diagram.strip() and k.diagram.strip().lower() != "none":
                try:
                    from .diagram.engine import render_diagram_from_code
                    svg = render_diagram_from_code(k.diagram)
                except Exception:
                    pass
            knowledge_items.append({
                "id": k.id,
                "title": k.title,
                "text": k.text,
                "text_2": k.text_2,
                "diagram_svg": svg,
            })
        preview["knowledge_items"] = knowledge_items

        return {
            "ok": True,
            "preview": preview,
            "error": None
        }

    except Exception as e:
        tb = _traceback.format_exc()
        msg = f"{type(e).__name__}: {e}\n\n{tb}"
        return {
            "ok": False,
            "preview": {
                "question": "",
                "answers": [],
                "solution": "",
                "diagram_svg": "",
                "diagram_code": "",
                "substituted_yaml": content,
                "params": {},
                "errors": [msg]
            },
            "error": msg
        }


def generate_preview_from_template_id(template_id: int):
    # 1. Load template
    try:
        template_obj = Template.objects.select_related("skill").get(pk=template_id)
    except Template.DoesNotExist:
        return {
            "ok": False,
            "preview": None,
            "error": f"Template {template_id} not found"
        }

    content = template_obj.content

    # 2. Parse YAML
    try:
        parsed = yaml.safe_load(content)
    except Exception as e:
        return {
            "ok": False,
            "preview": {
                "question": "",
                "answers": [],
                "solution": "",
                "diagram_svg": "",
                "diagram_code": "",
                "substituted_yaml": content,
                "params": {},
                "errors": [f"YAML error: {str(e)}"]
            },
            "error": f"YAML error: {str(e)}"
        }

    # 3. Validate
    errors = validate_template(parsed)
    if errors:
        return {
            "ok": False,
            "preview": parsed,
            "error": errors
        }

    # 4. Render preview (retry loop)
    MAX_ATTEMPTS = 5
    last_error = None

    for attempt in range(MAX_ATTEMPTS):
        try:
            preview = render_template_preview(parsed)

            # Inject metadata
            preview["skill"] = template_obj.skill.description if template_obj.skill else None
            preview["grade"] = template_obj.grade
            preview["difficulty"] = template_obj.difficulty

            return {
                "ok": True,
                "preview": preview,
                "error": None
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            last_error = traceback.format_exc()

    # 5. All attempts failed
    return {
        "ok": False,
        "preview": {
            "question": "",
            "answers": [],
            "solution": "",
            "diagram_svg": "",
            "diagram_code": "",
            "substituted_yaml": content,
            "params": {},
            "errors": [f"Failed after {MAX_ATTEMPTS} attempts: {last_error}"]
        },
        "error": f"Failed after {MAX_ATTEMPTS} attempts: {last_error}"
    }

def generate_first_question(request):
    print("Generating first question")
    student_id = request.data.get("student_id")
    skill_id = request.data.get("skill_id")

    # ---------------------------------------------------------
    # VALIDATE STUDENT
    # ---------------------------------------------------------
    try:
        user = User.objects.get(pk=student_id)
        student = user.get_student_profile()
    except User.DoesNotExist:
        return Response({"error": "Student not found"}, status=404)

    # ---------------------------------------------------------
    # VALIDATE SKILL
    # ---------------------------------------------------------
    try:
        skill = Skill.objects.get(pk=skill_id)
    except Skill.DoesNotExist:
        return Response({"error": "Skill not found"}, status=404)

    # ---------------------------------------------------------
    # GET OR CREATE STUDENT SKILL MATRIX
    # ---------------------------------------------------------
    matrix, _ = StudentSkillMatrix.objects.get_or_create(
        student=user,
        skill=skill,
        defaults={"mastery": 0}
    )

    # ---------------------------------------------------------
    # DETERMINE DIFFICULTY FROM MASTERY
    # ---------------------------------------------------------
    if matrix.mastery <= 4:
        difficulty = "easy"
    elif matrix.mastery <= 9:
        difficulty = "medium"
    else:
        difficulty = "hard"

    # ---------------------------------------------------------
    # SELECT A TEMPLATE OF THAT DIFFICULTY
    # ---------------------------------------------------------
    template = (
        Template.objects.filter(
            skill=skill,
            grade=student.year_level,
            difficulty__iexact=difficulty
        )
        .order_by("?")
        .first()
    )

    if not template:
        return Response(
            {"error": f"No templates available for difficulty '{difficulty}'"},
            status=404
        )

    # ---------------------------------------------------------
    # GENERATE PREVIEW FOR THE FIRST QUESTION
    # ---------------------------------------------------------
    preview = generate_preview_from_template_id(template.id)

    if not preview["ok"]:
        return Response(
            {"error": preview["error"], "template_id": template.id},
            status=500
        )

    next_question = preview["preview"]
    next_question["template_id"] = template.id  # <-- CRITICAL FIX

    # ---------------------------------------------------------
    # RETURN FIRST QUESTION
    # ---------------------------------------------------------
    return Response(
        {
            "ok": True,
            "template_id": template.id,
            "mastery": matrix.mastery,
            "competence_label": mastery_label(matrix.mastery),
            "next_difficulty": difficulty,
            "next_question": next_question,
        }
    )

def sanitize(obj):
    if obj is ...:
        return None
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj

def mastery_label(mastery: int) -> str:
    if mastery <= 4:
        return "Developing"
    if mastery <= 9:
        return "Emerging"
    if mastery <= 14:
        return "Competent"
    return "Mastered"
