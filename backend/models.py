from collections import defaultdict

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings as django_settings
from datetime import datetime, timedelta, time, date
# from django.utils.timezone import make_aware
from django.utils.timezone import make_aware, now as tz_now
from django.contrib.auth.models import UserManager

from django.db.models import Count


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

def print_segments(segments):
    for day in segments:
        for seg in day['segments']:
            # print(seg)
            if seg["type"] != "outside":
                print(f"{seg['time'].strftime('%H:%M')} — {seg['type']}")



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
        if user.role == "tutor": return TutorProfile.objects.filter(tutor=user).first()
        if user.role == "student":
            link = TutorStudent.objects.filter(student=user).first()
            if not link:
                return None
            return TutorProfile.objects.filter(tutor=link.tutor).first()
        if user.role == "parent":
            child_link = ParentChild.objects.filter(parent=user).first()
            if not child_link:
                return None
            tutor_link = TutorStudent.objects.filter(student=child_link.child).first()
            if not tutor_link:
                return None
            return TutorProfile.objects.filter(tutor=tutor_link.tutor).first()
        return None

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

        return {
            "id": next_booking.id,
            "start": next_booking.start_datetime.isoformat(),
            "end": next_booking.end_datetime.isoformat(),
            "confirmed": next_booking.confirmed,
            "student_can_edit": next_booking.student_can_edit(),
        }

    def next_weekly_booking(self):
        weekly_bookings = BookingWeekly.objects.filter(student=self)
        if not weekly_bookings.exists(): return None
        next_booking = sorted(weekly_bookings, key=lambda wb: wb.next_occurrence())[0]

        start_dt = next_booking.next_occurrence()
        session_minutes = int(
            (datetime.combine(date.today(), next_booking.end_time) -
             datetime.combine(date.today(), next_booking.start_time)).total_seconds() / 60
        )
        end_dt = start_dt + timedelta(minutes=session_minutes)

        return {
            "id": next_booking.id,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "confirmed": next_booking.confirmed,
            "start_date": next_booking.start_date.isoformat() if next_booking.start_date else None,
            "student_can_edit": next_booking.student_can_edit(),
        }

    def booking_mode(self):
        weekly = self.next_weekly_booking()
        adhoc = self.next_ad_hoc_booking()
        mode = "weekly_booking"
        next_booking = weekly

        if not weekly and not adhoc:
            mode = "no_booking"
        elif weekly and adhoc:
            weekly_start = weekly["start"]
            adhoc_start = adhoc["start"]
            if adhoc_start < weekly_start:
                mode = "weekly_booking_but_adhoc_this_week"
                next_booking = adhoc
        elif weekly and weekly.get("start_date"):
            resume_date = date.fromisoformat(weekly["start_date"])
            today = date.today()
            if resume_date > today:
                mode = "weekly_booking_but_paused"
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
        booking_map = self.booking_list_adhoc(dates)
        result = {}
        for day in dates:
            day_str = day.isoformat()
            weekday = day.weekday()  # 0 = Monday

            # Weekly slots for this weekday
            base_slots = weekly_slots.get(weekday, [])

            # Convert weekly slot times into datetime objects for this specific date
            slot_dts = []
            for time_str in base_slots:
                hour, minute = map(int, time_str.split(":"))
                slot_dts.append(
                    datetime.combine(day, datetime.min.time()).replace(
                        hour=hour, minute=minute
                    )
                )

            # Build blocked increments from ad-hoc bookings
            blocked = set()
            for b in booking_map.get(day_str, []):
                cur = datetime.fromisoformat(b["start"])
                end = datetime.fromisoformat(b["end"])
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

        bookings = BookingWeekly.objects.filter(tutor=self).select_related("student")

        booking_map = defaultdict(list)
        for b in bookings:
            booking_map[b.weekday].append({
                "id": b.id,
                "start_time": b.start_time.strftime("%H:%M"),
                "end_time": b.end_time.strftime("%H:%M"),
                "start_date": b.start_date,
                "student_id": b.student.id,
                "student_name": b.student.first_name,
                "confirmed": b.confirmed,
            })

        # Ensure all 7 days exist
        return {i: booking_map[i] for i in range(7)}

    def booking_list_adhoc(self, dates):
        if not dates:
            return {}

        start_date = min(dates)
        end_date = max(dates)

        qs = BookingAdhoc.objects.filter(
            tutor=self,
            start_datetime__date__range=(start_date, end_date),
        )

        booking_map = {}

        for b in qs:
            local_start = timezone.localtime(b.start_datetime)
            local_end = timezone.localtime(b.end_datetime)

            day_str = local_start.date().isoformat()
            start_time = local_start.strftime("%H:%M")

            booking_map.setdefault(day_str, []).append({
                "id": b.id,
                "start": local_start.isoformat(),
                "end": local_end.isoformat(),
                "student_id": b.student_id,
                "student_name": b.student.first_name,
                "confirmed": b.confirmed,
                "start_time": start_time,
            })

        # print("Adhoc bookings:", booking_map)
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
        self.save(update_fields=["start_date"])

    def next_occurrence(self):
        start_date = self.start_date if self.start_date and self.start_date > today else today
        days_ahead = (self.weekday - start_date.weekday()) % 7
        # print("Next occurrence:", start_date, self.weekday, start_date.weekday(), days_ahead)
        next_booking_date = today + timedelta(days=days_ahead)
        while next_booking_date <= start_date:
            next_booking_date += timedelta(days=7)
        next_start_time = make_aware(datetime.combine(next_booking_date, self.start_time), local_tz)
        return next_start_time

    def student_can_edit(self):
        return self.next_occurrence() > now + timedelta(days=days_needed_to_cancel)

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

    def __str__(self): return f"Student: {self.student} Tutor: {self.tutor.id} Student: {self.student.id}"

class StudentProfile(models.Model):
    user = models.OneToOneField(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    year_level = models.CharField(max_length=50, blank=True, null=True)
    area_of_study = models.TextField(blank=True, null=True)
    def __str__(self): return f"Profile {self.user} {self.id}"
    def next_booking(self):
        return self.user.next_booking()


class TutorProfile(models.Model):
    # Branding
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutor")
    logo = models.ImageField(upload_to='branding/', null=True, blank=True)
    color_scheme = models.CharField(max_length=20, null=True, blank=True)
    welcome_message = models.TextField(null=True, blank=True)
    token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    mobile = models.CharField(max_length = 20, null=True, blank=True)

    # Bookings
    default_session_minutes = models.IntegerField(default=60)
    buffer_minutes = models.IntegerField(default=15)


    def __str__(self): return f"{self.tutor}"

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

    def __str__(self):
        return f"{self.subject} (v{self.version})"

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