from .cache import *

def get_combined_calendar(tutor, start_date_iso):
    start_date = date.fromisoformat(start_date_iso)
    today = date.today()

    weekly_bookings = get_weekly_bookings(tutor)     # { weekday: [ {start_time, ...}, ... ] }
    adhoc_bookings = get_adhoc_bookings(tutor, start_date_iso)  # { "YYYY-MM-DD": [ ... ] }

    result = {}

    for i in range(7):
        day = start_date + timedelta(days=i)
        day_str = day.isoformat()
        weekday = day.weekday()  # Monday=0

        # Determine day status
        if day < today:
            day_status = "past"
        elif day == today:
            day_status = "today"
        else:
            day_status = "future"

       # --- Weekly bookings (active + paused) ---
        weekly_for_day = []
        for b in weekly_bookings.get(weekday, []):
            wb_start_date = b.get("start_date")
            is_paused = False

            if wb_start_date:
                if day < wb_start_date:
                    is_paused = True

            weekly_for_day.append({
                **b,
                "booking_type": "weekly_paused" if is_paused else "weekly",
            })

        # --- Ad‑hoc bookings for this exact date ---
        adhoc_for_day = []
        for b in adhoc_bookings.get(day_str, []):
            adhoc_for_day.append({
                **b,
                "booking_type": "adhoc",    # for yellow colour
            })

        # --- Merge, with ad‑hoc overriding weekly ---
        # If an ad‑hoc booking exists at the same start_time, remove the weekly one.
        adhoc_times = {b.get("start_time") for b in adhoc_for_day}
        merged = [b for b in weekly_for_day if b.get("start_time") not in adhoc_times]
        merged.extend(adhoc_for_day)

        # --- Sort by start_time ---
        merged.sort(key=lambda b: b.get("start_time") or "")

        # Store result
        result[day_str] = {
            "day_status": day_status,
            "bookings": merged,
        }

    return result