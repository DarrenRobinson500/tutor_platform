import json
from .models import *
from datetime import datetime, timedelta

def format_for_editor(obj: dict) -> str:
    lines = []
    for key, value in obj.items():
        # Convert nested objects or lists to strings cleanly
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, indent=2)
        else:
            value_str = str(value)

        # Format with newline + tab indentation
        lines.append(f"{key}:\n    {value_str}")
    return "\n\n".join(lines)


def get_tutor_settings(user):
    try:
        return TutorProfile.objects.get(user=user)
    except TutorProfile.DoesNotExist:
        return None


def generate_week(tutor_user, tutor_profile, week_start):
    week = []
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        week.append({
            "date": day_date,
            "availability": [],
            "blocked": False,
            "bookings": [],
            "bookable_slots": [],
            "segments": []  # for the graphical view
        })
    return week

def get_sunday_start(date):
    weekday = date.weekday()  # Monday=0 ... Sunday=6
    days_since_sunday = (weekday + 1) % 7
    return date - timedelta(days=days_since_sunday)
