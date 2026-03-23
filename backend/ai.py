
import os
import time
import yaml
from .utilities import *
from openai import OpenAI

_DOC_PATH = os.path.join(os.path.dirname(__file__), "Editor Documentation.txt")
with open(_DOC_PATH, encoding="utf-8") as _f:
    _EDITOR_DOCS = _f.read()

PROMPT_INSTRUCTIONS = f"""
The following documentation describes the full template format. The docs use YAML syntax
(as written in the editor); when returning templates you must use JSON syntax instead —
but all rules for parameters, expressions, answers, diagrams, and validation apply equally.

{_EDITOR_DOCS}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JSON RETURN FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each template must be returned as an item in a JSON array.

{{
  "title": "...",
  "years": <integer 1–10>,
  "difficulty": "easy" | "medium" | "hard",
  "parameters": {{ "a": {{ "min": 2, "max": 9 }}, "b": {{ "min": 3, "max": 7 }} }},
  "question": {{ "text": "..." }},
  "answers": [ ... ],
  "solution": {{ "text": "..." }},
  "diagram": "none",
  "validation": {{ "rules": [] }}
}}

IMPORTANT: "parameters" must be a JSON object — do NOT embed YAML inside JSON:
  CORRECT: "parameters": {{ "a": {{ "min": 2, "max": 9 }} }}
  WRONG:   "parameters":\\n  a:\\n    min: 2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Every parameter used anywhere must be declared in the "parameters" block.
- Avoid min values of 0 or 1 for integer parameters — they produce trivial questions.
- Incorrect answers must use different mathematical expressions, not just a different format.
- percent parameters (type: percent) already render with a % sign (e.g. "35%"). Do NOT add a literal % after {{ rate }} in question text — write "{{ rate }} of" not "{{ rate }}% of".
- percent parameters store their value as the decimal proportion internally (35% is stored as 35/100). Do NOT divide by 100 in expressions — write {{ rate * amount }}, never {{ rate / 100 * amount }}.
- Return ONLY valid JSON. No markdown fences. No commentary.
"""


chat_key=os.environ["CHAT_KEY"]

client = OpenAI(api_key=chat_key)

def _extract_existing_questions(skill) -> list[str]:
    """Return question texts from all existing templates for this skill."""
    from .models import Template
    questions = []
    qs = Template.objects.filter(skill=skill).exclude(content__isnull=True).exclude(content="")
    for t in qs:
        try:
            parsed = yaml.safe_load(t.content)
            text = parsed.get("question", {}).get("text", "")
            if text:
                questions.append(text)
        except Exception:
            pass
    return questions


def generate_template_content(skill, grade) -> dict:
    existing_questions = _extract_existing_questions(skill)

    existing_section = ""
    if existing_questions:
        lines = [
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "EXISTING QUESTIONS — do not repeat these question types",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        for i, q in enumerate(existing_questions, 1):
            lines.append(f"{i}. {q}")
        existing_section = "\n".join(lines) + "\n"
        print(existing_section)

    prompt = (
        f"You are an expert NSW mathematics tutor. "
        f"Create a structured practice template for the skill: '{skill.description}' "
        f"and for the grade: '{grade}' which relates to '{maths_stage(grade)}'.\n"
    )
    prompt += PROMPT_INSTRUCTIONS
    prompt += (
        "\n- Provide exactly 5 easy templates, 5 medium templates, and 5 hard templates."
        "\n- The \"title\" must describe what the question actually asks, not the skill name."
        "\n  Good: \"Find the gradient from two points\", \"Identify the y-intercept from an equation\"."
        "\n  Bad:  \"Gradient Question 3\", \"Understanding gradient and intercepts - Easy - 1\"."
    )
    prompt += existing_section

    # print(prompt)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    raw = response.choices[0].message.content
    return extract_json(raw)


def update_template(existing_yaml: str, user_instruction: str) -> dict:
    """Update an existing template YAML based on a natural language instruction.
    Returns a single template dict."""
    prompt = (
        "You are an expert NSW mathematics tutor. "
        "Update the following template according to the instruction below.\n\n"
        f"INSTRUCTION: {user_instruction}\n\n"
        f"EXISTING TEMPLATE (YAML):\n{existing_yaml}\n\n"
    )
    prompt += PROMPT_INSTRUCTIONS
    prompt += (
        "\n- Return ONLY ONE template as a single JSON object (not an array)."
        "\n- Preserve all existing fields (title, years, difficulty, skill) unless the instruction requires changing them."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    raw = response.choices[0].message.content
    result = extract_json(raw)
    if isinstance(result, list):
        return result[0]
    return result

def generate_template_from_image(image_b64: str, mime_type: str, skills: list, grade: str, additional_prompt: str = "") -> dict:
    """Generate a single template from a question screenshot using GPT-4o vision.
    skills: leaf skills already filtered to the given grade.
    grade: NSW year level string (e.g. "7") provided by the user.
    """
    skill_lines = "\n".join(
        f"  {s['id']}: {s['description']} ({s['code']})"
        for s in skills
    )

    prompt = (
        "You are an expert NSW mathematics tutor. "
        "The image shows a maths question from a textbook or worksheet. "
        f"Generate ONE parameterised practice template based on this question for NSW Year {grade}.\n\n"
        "Select the single most appropriate skill from the list below and return "
        "its numeric ID in a top-level field called 'skill_id'.\n\n"
        "Infer the difficulty ('easy', 'medium', or 'hard') from the question's complexity.\n\n"
        f"AVAILABLE SKILLS (Year {grade}):\n{skill_lines}\n\n"
    )
    prompt += PROMPT_INSTRUCTIONS
    prompt += (
        "\n- Return ONLY ONE template as a single JSON object (not an array)."
        f"\n- Set the 'years' field to {grade}."
        "\n- Include the extra field 'skill_id' (integer matching one of the skill IDs above)."
        "\n- The \"title\" must describe what the question actually asks, not the skill name."
    )
    if additional_prompt and additional_prompt.strip():
        prompt += f"\n\nAdditional instructions from the user: {additional_prompt.strip()}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime_type};base64,{image_b64}",
                    "detail": "high",
                }},
            ],
        }],
        temperature=0.4,
    )
    raw = response.choices[0].message.content
    result = extract_json(raw)
    if isinstance(result, list):
        return result[0]
    return result

def generate_knowledge_from_image(image_b64: str, mime_type: str, additional_prompt: str = "") -> dict:
    """Generate a Knowledge item (title, text, diagram, text_2) from an image using GPT-4o vision."""
    prompt = (
        "You are an expert NSW mathematics tutor. "
        "The image shows a maths concept, formula, worked example, or explanation. "
        "Generate a structured knowledge item that explains the concept shown.\n\n"
        "Return a single JSON object with these fields:\n"
        "  title: short descriptive title (e.g. 'Circumference of a circle')\n"
        "  text: main explanation or formula in plain text. Use $...$ for inline LaTeX and $$...$$ for display LaTeX.\n"
        "  diagram: diagram code string using the diagram syntax from the documentation below, or 'none' if not applicable.\n"
        "  text_2: optional secondary text such as a worked example or additional notes. "
        "Use $...$ / $$...$$ for LaTeX. Leave empty string if not needed.\n\n"
        "Return ONLY valid JSON. No markdown fences. No commentary.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "DIAGRAM DOCUMENTATION\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    prompt += _EDITOR_DOCS
    if additional_prompt and additional_prompt.strip():
        prompt += f"\n\nAdditional instructions: {additional_prompt.strip()}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime_type};base64,{image_b64}",
                    "detail": "high",
                }},
            ],
        }],
        temperature=0.3,
    )
    raw = response.choices[0].message.content
    result = extract_json(raw)
    if isinstance(result, list):
        return result[0]
    return result
