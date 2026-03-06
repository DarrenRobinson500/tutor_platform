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

def format_mobile(mobile: str) -> str:
    if not mobile: return ""
    digits = "".join(filter(str.isdigit, mobile))
    if len(digits) == 10:
        return f"{digits[0:4]} {digits[4:7]} {digits[7:10]}"
    return mobile

def str_to_date(date_str):
    date_str = date_str.replace("Z", "+00:00")
    # print("Str to Date:", date_str)
    dt = datetime.fromisoformat(date_str)
    # print("Str to Date:", dt)
    if dt.tzinfo is None: dt = timezone.make_aware(dt, local_tz)
    # print("Str to Date (aware):", dt)
    dt = timezone.localtime(dt, local_tz)
    print("Str to Date (local):", dt)
    return dt

def get_times(start_time_str, duration):
    start_time_str = start_time_str.strip()
    if len(start_time_str) == 8 and start_time_str.count(":") == 2:
        start_time_str = start_time_str[:5]
    start_time = datetime.strptime(start_time_str, "%H:%M").time()

    # Compute end time
    end_dt = datetime.combine(date.today(), start_time) + timedelta(minutes=duration)
    end_time = end_dt.time()

    return start_time, end_time


def get_datetimes(start_datetime_str, duration):
    start_dt = str_to_date(start_datetime_str)
    end_dt = start_dt + timedelta(minutes=duration)
    print("Get datetimes:", start_dt, end_dt)
    return start_dt, end_dt

