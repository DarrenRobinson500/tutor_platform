from collections import defaultdict
from django.core.cache import cache

from django.db import models

from django.contrib.auth.models import AbstractUser
from django.conf import settings as django_settings
from datetime import datetime, timedelta, time, date
# from django.utils.timezone import make_aware
from django.utils.timezone import make_aware, now as tz_now
from django.contrib.auth.models import UserManager

from django.db.models import Count
from .utilities import *


from django.utils import timezone
import pytz
tz = pytz.timezone("Australia/Sydney")
local_tz = timezone.get_default_timezone()
now = timezone.localtime(timezone.now(), local_tz)
today = now.date()

weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
days_needed_to_cancel = 1

# from django.db.models import Count
# from django_cte import With
# from django.db.models.expressions import RawSQL

class User(AbstractUser):
    ROLE_CHOICES = [
        ("student", "Student"),
        ("tutor", "Tutor"),
        ("parent", "Parent"),
        ("admin", "Admin"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    default_session_minutes = models.IntegerField(default=60)
    buffer_minutes = models.IntegerField(default=15)
    objects = UserManager()
    active = models.BooleanField(default=True)

    def get_student_profile(self):
        if self.role == "student":
            profile = StudentProfile.objects.filter(user=self).first()
        if not profile and self.role == "student":
            profile = StudentProfile.objects.create(user=self)
        return profile

    def get_tutor(self):
        if self.role == "tutor": return self
        if self.role == "student":
            link = TutorStudent.objects.filter(student=self).first()
            if link: return link.tutor
        if self.role == "parent":
            child_link = ParentChild.objects.filter(parent=self).first()
            if child_link: tutor_link = TutorStudent.objects.filter(student=child_link.child).first()
            if tutor_link: return TutorProfile.objects.filter(tutor=tutor_link.tutor).first()
        return None

    def get_tutor_profile(user):
        # Tutor: ensure a TutorProfile exists
        if user.role == "tutor":
            profile, _ = TutorProfile.objects.get_or_create(tutor=user)
            return profile

        # Student: follow TutorStudent → TutorProfile
        if user.role == "student":
            link = TutorStudent.objects.filter(student=user).first()
            if not link:
                return None
            profile, _ = TutorProfile.objects.get_or_create(tutor=link.tutor)
            return profile

        # Parent: follow ParentChild → TutorStudent → TutorProfile
        if user.role == "parent":
            child_link = ParentChild.objects.filter(parent=user).first()
            if not child_link:
                return None
            tutor_link = TutorStudent.objects.filter(student=child_link.child).first()
            if not tutor_link:
                return None
            profile, _ = TutorProfile.objects.get_or_create(tutor=tutor_link.tutor)
            return profile

        return None

    def to_dict(self):
        if self.role == "student":
            return self.get_student_profile().to_dict()
        if self.role == "tutor":
            return self.get_tutor_profile().to_dict()


    def next_booking(self):
        weekly = self.next_weekly_booking()
        adhoc = self.next_ad_hoc_booking()
        # print("Next booking", self, weekly, adhoc)

        if not weekly and not adhoc: return None
        if not adhoc: return weekly
        if not weekly: return adhoc

        return weekly if weekly["start_iso"] <= adhoc["start_iso"] else adhoc

    def next_ad_hoc_booking(self):
        # print("Next adhoc start")
        if self.role != "student": return None
        next_booking = (
            BookingAdhoc.objects
            .filter(student=self, start_datetime__gte=timezone.now())
            .order_by("start_datetime")
            .first()
        )
        # print("Next adhoc:", next_booking)

        if not next_booking: return None

        result = next_booking.to_dict()
        return result

    def next_weekly_booking(self):
        weekly_bookings = BookingWeekly.objects.filter(student=self)
        if not weekly_bookings.exists(): return None
        next_booking = sorted(weekly_bookings, key=lambda wb: wb.next_occurrence())[0]

        result = next_booking.to_dict()
        return result

    def booking_mode(self):
        weekly = self.next_weekly_booking()
        adhoc = self.next_ad_hoc_booking()
        mode = "weekly_booking"
        next_booking = weekly

        # print("Booking mode:", weekly, weekly.get("start_iso"))

        if not weekly and not adhoc:
            mode = "no_booking"
        elif weekly and adhoc:
            weekly_start = weekly["start_iso"]
            adhoc_start = adhoc["start_iso"]
            if adhoc_start < weekly_start:
                mode = "weekly_booking_but_adhoc_this_week"
                next_booking = adhoc
        elif weekly and weekly.get("start_date"):
            resume_date = weekly["start_date"]
            today = date.today()
            if resume_date > today:
                mode = "weekly_booking_but_paused"
        elif adhoc and not weekly:
            mode = "adhoc"
            next_booking = adhoc
        data = {
            "mode": mode,
            "next_booking": next_booking,
            "weekly": weekly,
            "adhoc": adhoc,
        }
        # print("Booking mode:", data)
        return data

    def booking_slots_weekly(self):
        if self.role != "tutor":
            return {i: [] for i in range(7)}

        availability = TutorAvailability.objects.filter(tutor=self)
        weekly_bookings = BookingWeekly.objects.filter(tutor=self)
        session_delta = timedelta(minutes=self.default_session_minutes)
        buffer_delta = timedelta(minutes=self.buffer_minutes)
        blocked = defaultdict(set)

        for wb in weekly_bookings:
            start_dt = datetime.combine(date.today(), wb.start_time) - buffer_delta
            end_dt = datetime.combine(date.today(), wb.end_time) + buffer_delta
            cur = start_dt
            while cur < end_dt:
                blocked[wb.weekday].add(cur.time())
                cur += timedelta(minutes=15)

        result = {i: [] for i in range(7)}

        for av in availability:
            weekday = av.weekday
            start = datetime.combine(date.today(), av.start_time)
            end = datetime.combine(date.today(), av.end_time)
            cur = start
            while cur + session_delta <= end:
                slot_time = cur.time()
                conflict = False
                check = cur
                while check < cur + session_delta:
                    if check.time() in blocked[weekday]:
                        conflict = True
                        break
                    check += timedelta(minutes=15)

                if not conflict:
                    result[weekday].append(slot_time.strftime("%H:%M"))

                cur += timedelta(minutes=15)

        return result

    def booking_slots_adhoc(self, weekly_slots, dates):
        # Get all adhoc bookings for the date range
        booking_map = self.booking_list_adhoc(dates)
        result = {}

        for day in dates:
            day_str = day.isoformat()
            weekday = day.weekday()

            # Weekly base slots for this weekday
            base_slots = weekly_slots.get(weekday, [])

            # Convert weekly slot times into datetime objects for this specific date
            slot_dts = []
            for time_str in base_slots:
                hour, minute = map(int, time_str.split(":"))
                slot_dts.append(
                    datetime.combine(day, time(hour, minute))
                )

            # Build a set of blocked increments from adhoc bookings
            blocked = set()

            for b in booking_map.get(day_str, []):
                # b["start_time"] and b["end_time"] are HH:MM strings
                start_h, start_m = map(int, b["start_time"].split(":"))
                end_h, end_m = map(int, b["end_time"].split(":"))

                cur = datetime.combine(day, time(start_h, start_m))
                end = datetime.combine(day, time(end_h, end_m))

                # Mark every 15‑minute increment as blocked
                while cur < end:
                    blocked.add(cur.time().strftime("%H:%M"))
                    cur += timedelta(minutes=15)

            # Filter out blocked slots
            final_slots = [
                dt.time().strftime("%H:%M")
                for dt in slot_dts
                if dt.time().strftime("%H:%M") not in blocked
            ]

            result[day_str] = final_slots

        return result

    def booking_list_weekly(self):
        if self.role != "tutor":
            return {i: [] for i in range(7)}

        qs = (BookingWeekly.objects.filter(tutor=self).select_related("student"))
        booking_map = defaultdict(list)

        for b in qs:
            data = b.to_dict()
            booking_map[data["weekday"]].append(data)

        return {i: booking_map[i] for i in range(7)}

    def booking_list_adhoc(self, dates):
        if not dates:
            return {}

        start_date = min(dates)
        end_date = max(dates)

        qs = (
            BookingAdhoc.objects
            .filter(
                tutor=self,
                start_datetime__date__range=(start_date, end_date),
            )
            .select_related("student")
        )

        booking_map = {}

        for b in qs:
            data = b.to_dict()
            booking_map.setdefault(data["day_str"], []).append(data)

        return booking_map

    def booking_create_weekly(self, weekday: int, start_time: time):
        if self.role != "student": raise ValueError("Only students can create weekly bookings.")
        tutor = self.get_tutor()
        if not tutor: raise ValueError("Student does not have an assigned tutor.")

        start_dt = datetime.combine(datetime.today(), start_time)
        end_dt = start_dt + timedelta(minutes=tutor.default_session_minutes)
        end_time = end_dt.time()

        exists = BookingWeekly.objects.filter(student=self,tutor=tutor,weekday=weekday,start_time=start_time).exists()
        if exists: raise ValueError("A weekly booking already exists for this time.")
        overlapping = BookingWeekly.objects.filter(student=self,tutor=tutor,weekday=weekday,start_time__lt=end_time,end_time__gt=start_time,).exists()
        if overlapping: raise ValueError("This weekly booking overlaps with an existing one.")

        wb = BookingWeekly.objects.create(student=self,tutor=tutor,weekday=weekday,start_time=start_time,end_time=end_time)
        return wb

    def booking_create_adhoc(self, start_dt):
        print("booking_create_adhoc")
        tutor = self.get_tutor()
        if not tutor: return None

        day = start_dt.date()
        dates = [day]

        weekly_slots = tutor.booking_slots_weekly()
        adhoc_slots = tutor.booking_slots_adhoc(weekly_slots, dates)

        day_str = day.isoformat()
        time_str = start_dt.time().strftime("%H:%M")

        if time_str not in adhoc_slots.get(day_str, []):
            print("Couldn't find time_str", time_str, adhoc_slots.get(day_str, []))
            return None

        booking = BookingAdhoc.objects.create(
            tutor=tutor,
            student=self,
            start_datetime=start_dt,
            end_datetime=start_dt + timedelta(minutes=60),
        )
        print("booking_create_adhoc - created")

        return booking

    def replace_this_weeks_adhoc(self, new_start_dt):
        existing = self.next_ad_hoc_booking()
        if existing:
            BookingAdhoc.objects.filter(id=existing["id"]).delete()
        return self.booking_create_adhoc(new_start_dt)

    def generate_weekly_slots(self, week_start, student=None, tutor_view=False):
        tutor_profile = self.get_tutor_profile()
        session_td = timedelta(minutes=self.default_session_minutes)
        week = []

        # Build the week skeletonx`
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            week.append({"date": day_date, "bookable_slots": [], "segments": []})

        # ── 1. Fetch all appointments for the week in one query
        week_start_dt = make_aware(datetime.combine(week_start, time.min))
        week_end_dt = make_aware(datetime.combine(week_start + timedelta(days=7), time.min))

        appointments = list(
            BookingAdhoc.objects.filter(
                tutor=self,
                start_datetime__lt=week_end_dt,
                end_datetime__gt=week_start_dt,
            ).select_related("student")
        )

        # Group appointments by date for fast lookup
        appointments_by_date = defaultdict(list)
        for appt in appointments:
            date_key = appt.start_datetime.date()
            appointments_by_date[date_key].append(appt)

        appt_start_times = defaultdict(set)

        for appt in appointments:
            date_key = appt.start_datetime.date()
            start_time = appt.start_datetime.time().replace(second=0, microsecond=0)
            appt_start_times[date_key].add(start_time)

        # ── 2. Fetch blocked days for the week
        blocked_days = set(
            TutorBlockedDay.objects.filter(
                tutor=self,
                date__gte=week_start,
                date__lt=week_start + timedelta(days=7),
            ).values_list("date", flat=True)
        )

        # ── 3. Fetch availability windows for the tutor
        availability_by_weekday = {}
        for av in TutorAvailability.objects.filter(tutor=self):
            availability_by_weekday.setdefault(av.weekday, []).append(av)

        # ── 4. Build segments and bookable slots in memory
        for day in week:
            d = day["date"]

            for minute in range(0, 24 * 60, 15):
                t = (datetime.min + timedelta(minutes=minute)).time()

                status, appt = tutor_profile.appointment_status_fast(
                    d, t, student,
                    blocked_days,
                    appointments_by_date,
                    availability_by_weekday,
                )

                if tutor_view and status in ("booked_self", "booked_other"):
                    status = "booked_other"

                segment = {"time": t, "type": status}

                if appt:
                    segment["bookingId"] = appt.id

                    # Only label the FIRST slot of the appointment
                    if t in appt_start_times[d]:

                        # Student view → only show THEIR name
                        if student is not None:
                            if appt.student_id == student.id:
                                segment["studentName"] = appt.student.first_name

                        # Tutor view → show ALL names
                        else:
                            segment["studentName"] = appt.student.first_name

                day["segments"].append(segment)

                # Only compute bookable_slots for available segments
                if status != "available":
                    continue

                end_dt = datetime.combine(d, t) + session_td
                end_t = end_dt.time()

                end_status, _ = tutor_profile.appointment_status_fast(
                    d,
                    end_t,
                    student,
                    blocked_days,
                    appointments_by_date,
                    availability_by_weekday,
                )

                if end_status == "available":
                    day["bookable_slots"].append(t)

        # print("Generate Slots (week):")
        # print_segments(week)

        return week


class BookingWeekly(models.Model):
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="appointment_tutor_weekly")
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="student_weekly")
    weekday = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField(blank=True, null=True)
    confirmed = models.BooleanField(default=False)

    def __str__(self):
        result = f"{self.tutor} and {self.student}: {weekday_names[self.weekday]}, {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        if not self.confirmed: result += " [unconfirmed]"
        return result

    def skip(self):
        self.start_date = now + timedelta(days=7)
        self.save(update_fields=["start_date"])

    def remove_skip(self):
        self.start_date = None
        print("Remove skip:", self, self.start_date)
        self.save(update_fields=["start_date"])

    def next_occurrence(self):
        sd = self.start_date
        if isinstance(sd, datetime):
            sd = sd.date()
        start_date = sd if sd and sd > today else today

        days_ahead = (self.weekday - start_date.weekday()) % 7
        # print("Next occurrence:", start_date, self.weekday, start_date.weekday(), days_ahead)
        next_booking_date = today + timedelta(days=days_ahead)
        while next_booking_date <= start_date:
            next_booking_date += timedelta(days=7)
        next_start_time = make_aware(datetime.combine(next_booking_date, self.start_time), local_tz)
        return next_start_time

    def student_can_edit(self):
        return self.next_occurrence() > now + timedelta(days=days_needed_to_cancel)

    def duration(self):
        return (self.end_time.hour * 60 + self.end_time.minute) - (self.start_time.hour * 60 + self.start_time.minute)

    def to_dict(self):
        start = self.next_occurrence()
        duration_minutes = self.duration()
        end = start + timedelta(minutes=duration_minutes)
        day_str = start.date().isoformat()

        return {
            "id": self.id,
            "student_id": self.student.id if self.student else None,
            "student_name": self.student.get_full_name() if self.student else None,
            "weekday": self.weekday,
            "start_time": start.time().isoformat(timespec="minutes"),
            "end_time": end.time().isoformat(timespec="minutes"),
            "day_str": day_str,
            "start_iso": start.isoformat(),
            "end_iso": end.isoformat(),
            "start_date": self.start_date,
            "confirmed": self.confirmed,
            "duration_minutes": duration_minutes,
            "booking_type": "weekly",
            "student_can_edit": self.student_can_edit(),
            "tutor_name": self.tutor.get_full_name() if self.tutor else None,
            "tutor_id": self.tutor.id if self.tutor else None,
        }

class BookingAdhoc(models.Model):
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointment_tutor")
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student")
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=20)
    created_by = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments_created")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.start_datetime} {self.student} {self.tutor}"

    def student_can_edit(self):
        return self.start_datetime > now + timedelta(days=days_needed_to_cancel)

    def duration(self):
        return (self.end_datetime.hour * 60 + self.end_datetime.minute) - (self.start_datetime.hour * 60 + self.start_datetime.minute)

    def to_dict(self):
        # Localise datetimes
        start = timezone.localtime(self.start_datetime)
        end = timezone.localtime(self.end_datetime)
        duration_minutes = self.duration()
        day_str = start.date().isoformat()

        return {
            "id": self.id,
            "student_id": self.student.id,
            "student_name": self.student.get_full_name(),
            "start_time": start.time().isoformat(timespec="minutes"),
            "end_time": end.time().isoformat(timespec="minutes"),
            "start_date": day_str,
            "day_str": day_str,
            "start_iso": start.isoformat(),
            "end_iso": end.isoformat(),
            "confirmed": self.confirmed,
            "duration_minutes": duration_minutes,
            "booking_type": "adhoc",
            "student_can_edit": self.student_can_edit(),
            "tutor_name": self.tutor.get_full_name() if self.tutor else None,
            "tutor_id": self.tutor.id if self.tutor else None,
        }

class ParentChild(models.Model):
    parent = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="children")
    child = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parents")

    class Meta:
        unique_together = ("parent", "child")

class TutorStudent(models.Model):
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="students")
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutors")

    class Meta:
        unique_together = ("tutor", "student")

    def __str__(self): return f"Tutor: {self.tutor} Student: {self.student}"

class StudentProfile(models.Model):
    user = models.OneToOneField(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    year_level = models.CharField(max_length=50, blank=True, null=True)
    area_of_study = models.TextField(blank=True, null=True)
    mobile = models.CharField(max_length = 20, null=True, blank=True, default='0493461541')
    address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self): return f"Profile {self.user} {self.id}"

    def next_booking(self):
        return self.user.next_booking()

    def to_dict(self):
        u = self.user
        tutor_user = u.get_tutor()
        tutor_profile = tutor_user.get_tutor_profile() if tutor_user else None
        booking_mode = u.booking_mode()
        # print("Booking mode:", booking_mode)

        return {
            # User + profile identifiers
            "user_id": u.id,
            "profile_id": self.id,

            # User identity
            "first_name": u.first_name,
            "last_name": u.last_name,
            "name": u.get_full_name() or u.username,
            "email": u.email,
            "active": u.active,

            # Student profile fields
            "year_level": self.year_level,
            "area_of_study": self.area_of_study,
            "mobile": self.mobile,
            "address": self.address,

            # Tutor details (flattened for convenience)
            "tutor_id": tutor_user.id if tutor_user else None,
            "tutor_name": tutor_user.get_full_name() if tutor_user else None,
            "tutor_mobile": tutor_profile.mobile if tutor_profile else None,
            "tutor_address": tutor_profile.address if tutor_profile else None,

            # Booking info (already unified via booking.to_dict())
            "booking_mode": booking_mode['mode'],
            "next_booking": booking_mode['next_booking'],
            "next_ad_hoc_booking": booking_mode['adhoc'],
            "next_weekly_booking": booking_mode['weekly'],
        }

class UserPreference(models.Model):
    user = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences")
    key = models.CharField(max_length=100)
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "key")

    def __str__(self):
        return f"{self.user} – {self.key} = {self.value}"


class TutorProfile(models.Model):
    # Branding
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutor")
    logo = models.ImageField(upload_to='branding/', null=True, blank=True)
    color_scheme = models.CharField(max_length=20, null=True, blank=True)
    welcome_message = models.TextField(null=True, blank=True)
    token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    mobile = models.CharField(max_length=20, blank=True, null=True, default='0493461541')
    address = models.CharField(max_length=255, blank=True, null=True)

    # Bookings
    default_session_minutes = models.IntegerField(default=60)
    buffer_minutes = models.IntegerField(default=15)

    def __str__(self): return f"{self.tutor}"

    def to_dict(self):
        u = self.tutor

        # If you want to show next bookings on TutorHomePage:
        # next_adhoc = u.next_ad_hoc_booking()
        # next_weekly = u.next_weekly_booking()

        return {
            # User identity
            "user_id": u.id,
            "profile_id": self.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "name": u.get_full_name() or u.username,
            "email": u.email,
            "active": u.active,

            # Tutor profile fields
            "mobile": format_mobile(self.mobile),
            "address": self.address,
            "default_session_minutes": self.default_session_minutes,
            "buffer_minutes": self.buffer_minutes,

            # Booking info (mirrors student structure)
            # "next_ad_hoc_booking": next_adhoc,
            # "next_weekly_booking": next_weekly,

            # Optional: combined next booking (same as student home)
            # "next_booking": next_adhoc or next_weekly,
        }


    def appointment_status(self, date_obj, time_obj, student=None):
        dt = make_aware(datetime.combine(date_obj, time_obj))

        if TutorBlockedDay.objects.filter(tutor=self.tutor, date=date_obj).exists(): return "blocked"
        appt = BookingAdhoc.objects.filter(tutor=self.tutor, start_datetime__lte=dt, end_datetime__gt=dt).first()
        if appt:
            print("BookingAdhoc status:", appt.student, student)
            if student and appt.student == student:
                return "booked_self"
            return "booked_other"

        weekday = date_obj.weekday()  # Monday=0 ... Sunday=6
        availability = TutorAvailability.objects.filter(tutor=self.tutor, weekday=weekday)
        if not availability.exists(): return "outside"
        for window in availability:
            if window.start_time <= time_obj < window.end_time:
                return "available"
        return "outside"

    def appointment_status_fast(
        self,
        date_obj,
        time_obj,
        student,
        blocked_days,
        appointments_by_date,
        availability_by_weekday,
    ):
        # 1. Blocked day
        if date_obj in blocked_days:
            return "blocked", None

        dt = make_aware(datetime.combine(date_obj, time_obj))

        # 2. BookingAdhoc check (using pre-fetched appointments for that date)
        for appt in appointments_by_date.get(date_obj, []):
            if appt.start_datetime <= dt < appt.end_datetime:
                if student and appt.student == student:
                    return "booked_self", appt
                return "booked_other", appt

        # 3. Availability windows
        weekday = date_obj.weekday()  # Monday=0 ... Sunday=6
        windows = availability_by_weekday.get(weekday, [])
        for window in windows:
            if window.start_time <= time_obj < window.end_time:
                return "available", None

        # 4. Outside availability
        return "outside", None




    def is_available(self, date, start, end):
        start_available = self.appointment_status(date, start) == "available"
        end_available = self.appointment_status(date, end) == "available"
        print("Is available (start, end):", start_available, self.appointment_status(date, start), end_available,
              self.appointment_status(date, end))
        return start_available and end_available


class Skill(models.Model):
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    code = models.CharField(max_length=100)
    description = models.TextField()
    grades = models.CharField(max_length=50, null=True, blank=True)
    order_index = models.IntegerField(default=0)
    detail = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.code}: {self.description[:40]}"

    def direct_templates(self):
        return Template.objects.filter(skill=self)

    def get_grade_list(self):
        raw = [g.strip() for g in self.grades.split(",") if g.strip()]
        parsed = []
        for g in raw:
            if g.upper() == "K":
                parsed.append("K")
            else:
                try:
                    parsed.append(int(g))
                except ValueError:
                    parsed.append(g)  # fallback for unexpected values
        return parsed

    def template_count(self):
        # 1. Collect all descendant skill IDs (including self)
        def collect_ids(skill):
            ids = [skill.id]
            for child in skill.children.all():
                ids.extend(collect_ids(child))
            return ids

        skill_ids = collect_ids(self)

        # 2. Count templates for all skills in the subtree
        total = Template.objects.filter(skill_id__in=skill_ids).count()

        # print("TEMPLATE COUNT:", self.id, total)
        return total

    def validated_count(self):
        return self.template_set.filter(validated=True).count()

    def unvalidated_count(self):
        return self.template_set.filter(validated=False).count()



class StudentSkillMatrix(models.Model):
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)

    mastery = models.FloatField(default=0.0)  # 0–1 or 0–100
    evidence_count = models.IntegerField(default=0)
    recent_correct_rate = models.FloatField(default=0.0)
    confidence = models.FloatField(default=0.0)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "skill")

class TutorAvailability(models.Model):
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    weekday = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    def __str__(self): return f"{self.weekday}, {self.start_time}= {self.end_time}"



class TutorBlockedDay(models.Model):
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()



class Notification(models.Model):
    recipient = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

class Template(models.Model):
    # --- Core content ---
    name = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True)

    # Raw YAML/JSON template content
    content = models.TextField(blank=True, null=True)

    # --- Metadata ---
    subject = models.CharField(max_length=200, blank=True, null=True)
    topic = models.CharField(max_length=100, blank=True)
    subtopic = models.CharField(max_length=100, blank=True)
    grade = models.CharField(max_length=2, null=True, blank=True)
    difficulty = models.CharField(max_length=50, blank=True)
    tags = models.JSONField(default=list, blank=True)

    curriculum = models.JSONField(default=list, blank=True)
    skill = models.ForeignKey(Skill, null=True, on_delete=models.SET_NULL)
    validated = models.BooleanField(default=False)

    # --- Workflow state ---
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("validated", "Validated"),
        ("published", "Published"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # --- Versioning ---
    version = models.IntegerField(default=1)

    # --- Ownership & audit ---
    created_by = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="templates_created")
    updated_by = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="templates_updated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Flags for quality control ---
    has_preview = models.BooleanField(default=False)  # set true once preview successfully generated
    last_validated_at = models.DateTimeField(null=True, blank=True)
    knowledge_items = models.ManyToManyField('Knowledge', blank=True, related_name='templates')

    def __str__(self):
        return f"{self.subject} (v{self.version})"

class Knowledge(models.Model):
    """
    A reusable piece of knowledge (formula, rule, definition) attached to one
    or more Skills.  Shown alongside the solution whenever a question from one
    of those skills is answered, so students always see the same canonical
    explanation for a concept.
    """
    title = models.CharField(max_length=200)
    text = models.TextField(blank=True)
    diagram = models.TextField(blank=True)
    text_2 = models.TextField(blank=True)
    skills = models.ManyToManyField(Skill, blank=True, related_name="knowledge_items")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "diagram": self.diagram,
            "skill_ids": list(self.skills.values_list("id", flat=True)),
        }


class TemplateDiagram(models.Model):
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    svg_spec = models.TextField()

class TemplateSkill(models.Model):
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("template", "skill")

class Question(models.Model):
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="question_instances")
    params = models.JSONField()
    question_text = models.TextField()
    correct_answer = models.TextField()
    help_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    selected_answer = models.TextField(null=True)
    correct = models.BooleanField(default=True)
    time_taken_ms = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Instance {self.id} of {self.template.name}"

class QuestionAttempt(models.Model):
    question = models.ForeignKey(Question, null=True, on_delete=models.CASCADE)
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    template = models.ForeignKey(Template, null=True, on_delete=models.CASCADE)

    skills = models.JSONField(null=True)
    selected_answer = models.TextField(null=True)
    correct = models.BooleanField(default=True)
    time_taken_ms = models.IntegerField(null=True, blank=True)

    attempted_at = models.DateTimeField(auto_now_add=True, null=True)

class Task(models.Model):
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)

class TaskItem(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, null=True, on_delete=models.CASCADE)

class SyllabusMapping(models.Model):
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    region = models.CharField(max_length=50)
    outcome_code = models.CharField(max_length=50)

class Note(models.Model):
    author = models.ForeignKey(django_settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="notes")
    template = models.ForeignKey(Template, null=True, blank=True, on_delete=models.SET_NULL, related_name="notes")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        if self.template:
            return f"Note by {self.author} on {self.template.name}"
        return f"Note by {self.author} (general)"

# Global

class GlobalSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=500)

    def __str__(self):
        return f"{self.key} = {self.value}"

    @staticmethod
    def get(key, default=None):
        try:
            return GlobalSetting.objects.get(key=key).value
        except GlobalSetting.DoesNotExist:
            return default

    @staticmethod
    def set(key, value):
        obj, _ = GlobalSetting.objects.update_or_create(
            key=key,
            defaults={"value": value},
        )
        return obj

def get_bool(key, default=False):
    cache_key = f"global_setting_{key}"
    val = cache.get(cache_key)
    if val is None:
        val = GlobalSetting.get(key, default)
        # print("Get bool (db):", val)
        global_settings_cache_min = get_int("global_settings_cache_min", 10)
        cache.set(cache_key, val, global_settings_cache_min * 60)
    return val.lower() in ("1", "true", "yes", "on")

def get_int(key, default=0):
    cache_key = f"global_setting_{key}"
    val = cache.get(cache_key)

    if val is None:
        val = GlobalSetting.get(key, default)
        cache.set(cache_key, val, 2 * 60)

    try:
        return int(val)
    except (TypeError, ValueError):
        return default

# Messaging

class SMSConversation(models.Model):
    tutor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sms_conversations_as_tutor")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sms_conversations_as_student")
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tutor} {self.student}"

class SMSMessage(models.Model):
    direction = models.CharField(max_length=10, choices=[("outbound", "Outbound"), ("inbound", "Inbound")])
    conversation = models.ForeignKey(SMSConversation, on_delete=models.CASCADE, related_name="messages")
    body = models.TextField()
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    provider_message_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default="queued")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.body} (Sent: {format_sms_datetime_django(self.sent_at)})"

    @property
    def tutor(self):
        return self.conversation.tutor

    @property
    def student(self):
        return self.conversation.student

    def to_dict(self):
        return {
            "id": self.id,
            "direction": self.direction,
            "tutor_id": self.tutor.id,
            "student_id": self.student.id,
            "student_name": f"{self.student.first_name} {self.student.last_name}",
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "status": self.status,
        }

class SMSSendJob(models.Model):
    conversation = models.ForeignKey(SMSConversation, blank=True, null=True, on_delete=models.CASCADE, related_name="jobs")
    body = models.TextField()
    scheduled_for = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled = models.BooleanField(default=False)

    last_error = models.TextField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)

    def __str__(self):
        result = f"{self.conversation}"
        if self.cancelled:
            result += " [Sent]"
        return result

    @property
    def time_until_sent(self):
        return self.scheduled_for - timezone.now()

    def to_dict(self):
        student = self.conversation.student
        tutor = self.conversation.tutor

        return {
            "id": self.id,
            "tutor_id": tutor.id,
            "student_id": student.id,
            "student_name": f"{student.first_name} {student.last_name}",
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "scheduled_for": self.scheduled_for.isoformat(),
            "time_until_sent_seconds": self.time_until_sent.total_seconds(),
            "cancelled": self.cancelled,
        }


def get_or_create_conversation(tutor, student):
    convo, created = SMSConversation.objects.get_or_create(
        tutor=tutor,
        student=student
    )
    return convo
