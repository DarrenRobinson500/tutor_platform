from .models import *
import yaml
from .rendering import *
from .validation import *
from rest_framework.response import Response

def generate_preview_from_content(content: str):
    # 1. Parse YAML
    print("Generate preview from content - 1")
    try:
        parsed = yaml.safe_load(content)
    except Exception as e:
        print("Generate preview from content - 1 (failed)")
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
    print("Generate preview from content - 2")
    errors = validate_template(parsed)
    if errors:
        return {
            "ok": False,
            "preview": parsed,
            "error": errors
        }

    # 3. Render preview
    print("Generate preview from content - 3")
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
                "errors": [str(e)]
            },
            "error": str(e)
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
    print("Generate values and question (content):", content)

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

        return {
            "ok": True,
            "preview": preview,
            "error": None
        }

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
                "errors": [str(e)]
            },
            "error": str(e)
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
