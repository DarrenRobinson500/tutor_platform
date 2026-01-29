# # scripts/import_skills.py
# import json
# from app.models import Skill
#
# def import_skill_tree(node, parent=None):
#     skill = Skill.objects.create(
#         parent=parent,
#         code=node["code"],
#         description=node["description"],
#         grade_level=node.get("grade_level", 0),
#         order_index=node.get("order_index", 0),
#     )
#     print("Created:", node["description"])
#
#     for child in node.get("children", []):
#         import_skill_tree(child, parent=skill)
#
# def run():
#     print("Running")
#     with open("nsw_math_k10.json") as f:
#         data = json.load(f)
#
#     for top in data:
#         print("Top", top)
#         import_skill_tree(top)
#
import json
import os
from app.models import Skill

def import_skill_tree(node, parent=None):
    """Recursively create Skill objects from a nested JSON structure."""
    skill = Skill.objects.create(
        parent=parent,
        code=node["code"],
        description=node["description"],
        grade_level=node.get("grade_level", 0),
        order_index=node.get("order_index", 0),
    )

    for child in node.get("children", []):
        import_skill_tree(child, parent=skill)


def import_syllabus():
    """Load the NSW Mathematics K–10 syllabus into the database."""
    # Determine the path to the JSON file relative to the Django project
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "nsw_math_k10.json")

    # Load the JSON file
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Import each top-level skill
    for top in data:
        import_skill_tree(top)