from .models import *


# ----------- STUDENTS ------------------

STUDENTS_CACHE = {}

def get_cached_students_for_tutor(tutor):
    tutor_id = tutor.id

    if tutor_id not in STUDENTS_CACHE:
        # Build fresh
        links = TutorStudent.objects.filter(tutor=tutor).select_related(
            "student__student_profile"
        )

        data = []
        for link in links:
            student_user = link.student
            profile = student_user.get_student_profile()

            data.append({
                "user_id": student_user.id,
                "profile_id": profile.id,
                "first_name": student_user.first_name,
                "last_name": student_user.last_name,
                "email": student_user.email,
                "year_level": profile.year_level,
                "area_of_study": profile.area_of_study,
            })

        STUDENTS_CACHE[tutor_id] = data

    return STUDENTS_CACHE[tutor_id]

def invalidate_students_cache_for_tutor(tutor_id):
    if tutor_id in STUDENTS_CACHE:
        del STUDENTS_CACHE[tutor_id]


# ------------WEEKLY SLOTS -------------

WEEKLY_SLOTS_CACHE = {}


def get_cached_weekly_slots(tutor, week_start, student):
    key = (tutor.id, week_start, student.id if student else None)

    if key not in WEEKLY_SLOTS_CACHE:
        WEEKLY_SLOTS_CACHE[key] = tutor.generate_weekly_slots(week_start, student)

    return WEEKLY_SLOTS_CACHE[key]

def invalidate_weekly_slots_cache_for_tutor(tutor_id):
    global WEEKLY_SLOTS_CACHE
    WEEKLY_SLOTS_CACHE = {
        key: value
        for key, value in WEEKLY_SLOTS_CACHE.items()
        if key[0] != tutor_id
    }


# ----------SKILLS ---------------


MATRIX_CACHE = None
GRADES = ["K", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]

def flatten_skills(skills, children_map, depth=0):
    flat = []
    for skill in skills:
        flat.append((skill, depth))
        children = children_map.get(skill.id, [])
        flat.extend(flatten_skills(children, children_map, depth + 1))
    return flat


def build_matrix():
    skills = list(
        Skill.objects.all()
        .select_related("parent")
        .order_by("id")
    )

    # Load template counts in one query
    template_counts = {
        (skill_id, grade): count
        for skill_id, grade, count in Template.objects
            .values_list("skill_id", "grade")
            .annotate(count=Count("id"))
    }

    # Build children map
    children_map = {}
    for skill in skills:
        parent_id = skill.parent_id
        children_map.setdefault(parent_id, []).append(skill)

    # Get top-level skills and flatten
    top_level = children_map.get(None, [])
    flat = flatten_skills(top_level, children_map)

    # Build rows
    rows = []
    for skill, depth in flat:
        # No DB hit — grades already loaded
        grade_list = [str(g) for g in skill.get_grade_list()]

        cells = {}
        for g in GRADES:
            g_str = str(g)
            colour = "covered" if g_str in grade_list else "empty"
            template_count = template_counts.get((skill.id, g_str), 0)

            cells[g_str] = {"colour": colour, "count": template_count}

        rows.append({
            "id": skill.id,
            "code": skill.code,
            "description": skill.description,
            "depth": depth,
            "children_count": len(children_map.get(skill.id, [])),
            "cells": cells,
        })

    return {
        "grades": GRADES,
        "skills": rows
    }


def update_matrix_cache_for_template_count(skill_id):
    global MATRIX_CACHE
    if MATRIX_CACHE is None:
        return  # nothing to update

    # Recompute template count for this skill only
    new_count = Template.objects.filter(skill_id=skill_id).count()

    # Update every grade cell for this skill
    for row in MATRIX_CACHE["skills"]:
        if row["id"] == skill_id:
            for g in GRADES:
                row["cells"][g]["count"] = new_count
            break


def get_matrix_cache():
    global MATRIX_CACHE
    if MATRIX_CACHE is None:
        MATRIX_CACHE = build_matrix()   # heavy work
    return MATRIX_CACHE


