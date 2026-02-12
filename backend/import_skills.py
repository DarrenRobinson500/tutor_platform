import json
import os
from backend.models import Skill

def import_skill_tree(node, parent, existing_by_description):
    description = node["description"]

    years = node.get("years_practised", [])
    grades_str = ",".join(str(y) for y in years)
    # print(node["description"])

    skill = existing_by_description.get(description)

    if skill:
        print(f"{description} - Skipping")
    else:
        print(f"{description} - Importing")
        skill = Skill.objects.create(
            parent=parent,
            code=node["code"],
            description=description,
            grades=grades_str,
        )
        existing_by_description[description] = skill  # Add to lookup

    # Recurse into children
    for child in node.get("children", []):
        import_skill_tree(child, parent=skill, existing_by_description=existing_by_description)

def import_syllabus():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "nsw_math_k10_years.json")

    # Load the JSON file
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_skills = Skill.objects.all()
    existing_by_description = {s.description: s for s in existing_skills}

    # Import each top-level skill
    for top in data:
        import_skill_tree(top, parent=None, existing_by_description=existing_by_description)
