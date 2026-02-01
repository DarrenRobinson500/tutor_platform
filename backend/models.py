from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings as django_settings
from datetime import datetime, timedelta, time
# from django.utils.timezone import make_aware
from django.utils.timezone import make_aware


from django.utils import timezone
import pytz
tz = pytz.timezone("Australia/Sydney")

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

class TutorProfile(models.Model):
    # Branding
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutor")
    logo = models.ImageField(upload_to='branding/')
    color_scheme = models.CharField(max_length=20)
    welcome_message = models.TextField()

    # Bookings
    default_session_minutes = models.IntegerField(default=60)
    buffer_minutes = models.IntegerField(default=15)

    # QR codes
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"Profile {self.tutor} {self.id}"

    def appointment_status(self, date_obj, time_obj):
        dt = make_aware(datetime.combine(date_obj, time_obj))

        if TutorBlockedDay.objects.filter(tutor=self.tutor, date=date_obj).exists(): return "blocked"
        if Appointment.objects.filter(tutor=self.tutor, start_datetime__lte=dt, end_datetime__gt=dt).exists(): return "booked"

        weekday = date_obj.weekday()  # Monday=0 ... Sunday=6
        availability = TutorAvailability.objects.filter(tutor=self.tutor, weekday=weekday)
        if not availability.exists(): return "outside"
        for window in availability:
            if window.start_time <= time_obj < window.end_time:
                return "available"
        return "outside"

    def is_available(self, date, start, end):
        start_available = self.appointment_status(date, start) == "available"
        end_available = self.appointment_status(date, end) == "available"
        print("Is available (start, end):", start_available, self.appointment_status(date, start), end_available, self.appointment_status(date, end))
        return start_available and end_available


    def generate_weekly_slots(self, week_start):

        session_td = timedelta(minutes=self.default_session_minutes)

        week = []
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            week.append({"date": day_date, "bookable_slots": [], "segments": []})

        for day in week:
            d = day["date"]
            for minute in range(0, 24 * 60, 15):
                t = (datetime.min + timedelta(minutes=minute)).time()
                status = self.appointment_status(d, t)
                day["segments"].append({"time": t, "type": status})

                if status != "available": continue
                end_dt = datetime.combine(d, t) + session_td
                end_t = end_dt.time()
                end_status = self.appointment_status(d, end_t)
                if end_status == "available": day["bookable_slots"].append(t)

        return week

class Skill(models.Model):
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    code = models.CharField(max_length=100)
    description = models.TextField()
    grade_level = models.IntegerField()
    order_index = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.code}: {self.description[:40]}"

    def direct_templates(self):
        return Template.objects.filter(skill=self)

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

class Appointment(models.Model):
    tutor = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointment_tutor")
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student")
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    status = models.CharField(max_length=20)

    def __str__(self): return f"{self.start_datetime} {self.student} {self.tutor}"

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
    difficulty = models.CharField(max_length=50, blank=True)
    tags = models.JSONField(default=list, blank=True)

    curriculum = models.JSONField(default=list, blank=True)
    skill = models.ForeignKey(Skill, null=True, on_delete=models.SET_NULL)

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
        return f"{self.name} (v{self.version})"

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

    def __str__(self):
        return f"Instance {self.id} of {self.template.name}"

class Task(models.Model):
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)

class TaskItem(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, null=True, on_delete=models.CASCADE)

class QuestionAttempt(models.Model):
    question = models.ForeignKey(Question, null=True, on_delete=models.CASCADE)
    student = models.ForeignKey(django_settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    template = models.ForeignKey(Template, null=True, on_delete=models.CASCADE)

    skills = models.JSONField(null=True)
    selected_answer = models.TextField(null=True)
    correct = models.BooleanField(default=True)
    time_taken_ms = models.IntegerField(null=True, blank=True)

    attempted_at = models.DateTimeField(auto_now_add=True, null=True)



class SyllabusMapping(models.Model):
    template = models.ForeignKey(Template, on_delete=models.CASCADE)
    region = models.CharField(max_length=50)
    outcome_code = models.CharField(max_length=50)

