from django.contrib.auth.hashers import make_password
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
from datetime import datetime, timedelta, time as dtime


from .validation import *
from .rendering import *
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
import yaml
from .import_skills import *
from .ai import *
from .utilities import *
from .serializers import *
from .tutor_calendar import *

GRADES = ["K", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

MATRIX_CACHE = None

# views.py (or a separate utils/skills_matrix.py file)

# from .models import Skill

GRADES = ["K", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]

def flatten_skills(top_level_skills):
    flat = []

    def walk(skill, depth):
        flat.append((skill, depth))
        for child in skill.children.all().order_by("id"):
            walk(child, depth + 1)
    for root in top_level_skills:
        walk(root, 0)

    return flat



def build_matrix():
    top_level = Skill.objects.filter(parent=None).order_by("id")
    flat = flatten_skills(top_level)

    rows = []
    for skill, depth in flat:
        # print("Build matrix:", skill)
        grade_list = [str(g) for g in skill.get_grade_list()]
        cells = {}
        for g in GRADES:
            g_str = str(g)
            colour = "covered" if g_str in grade_list else "empty"
            count = 0
            # count = skill.template_count()
            cells[g_str] = {"colour": colour, "count": count}

        rows.append({
            "id": skill.id,
            "code": skill.code,
            "description": skill.description,
            "depth": depth,
            "cells": cells
        })

    return {
        "grades": GRADES,
        "skills": rows
    }


def get_matrix_cache():
    global MATRIX_CACHE
    if MATRIX_CACHE is None:
        MATRIX_CACHE = build_matrix()   # heavy work
    return MATRIX_CACHE

# get_matrix_cache()
# print("Matrix cache:")
# print(MATRIX_CACHE)


def flatten_skills(skills, depth=0):
    flat = []
    for skill in skills:
        flat.append((skill, depth))
        children = skill.children.all().order_by("id")
        flat.extend(flatten_skills(children, depth + 1))
    return flat

class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def me(self, request):
        user = request.user

        return Response({
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "first_name": user.first_name,
        })

class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"])
    def autosave(self, request):
        content = request.data.get("content", "")
        template_id = request.data.get("templateId") or request.data.get("id")
        # Normalize invalid IDs
        invalid_ids = [None, "", "undefined", "new"]
        if template_id in invalid_ids:
            template = Template.objects.create(
                content=content
            )
            return Response({"ok": True, "id": template.id})

        # If no template_id, do nothing and return success
        if not template_id:
            print("No success trying to create a tempate id, Template ID:", template_id)
            return Response({"ok": True})

        # If template_id exists, update the template
        try:
            template = Template.objects.get(pk=template_id)
            template.content = content
            template.save()
            # print(f"AUTOSAVED TEMPLATE {template_id}")
            return Response({"ok": True})
        except Template.DoesNotExist:
            template = Template.objects.create(content=content)
            return Response({"ok": True})

    @action(detail=False, methods=["post"])
    def preview(self, request):
        content = request.data.get("content", "")

        # Step 1: Try YAML
        try:
            parsed = yaml.safe_load(content)
        except Exception as e:
            return Response(
                {
                    "ok": False,
                    "preview": {
                        "question": "",
                        "answers": [],
                        "solution": "",
                        "diagram_svg": "",
                        "diagram_code": "",
                        "substituted_yaml": content,
                        "params": {},
                        "errors": [f"YAML error: {str(e)}"]
                    },
                    "error": f"YAML error: {str(e)}"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Deep validation (your rules)
        errors = validate_template(parsed)
        if errors:
            return Response(
                {"ok": False, "preview": parsed, "error": errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 3: Render preview (your logic)
        MAX_ATTEMPTS = 5
        last_error = None

        for attempt in range(MAX_ATTEMPTS):
            try:
                preview = render_template_preview(parsed)
                print("PREVIEW RETURNED FROM BACKEND:", preview)

                return Response({"ok": True, "preview": preview})
            except Exception as e:
                import traceback
                print("\n--- PREVIEW ERROR ATTEMPT", attempt, "---")
                traceback.print_exc()
                last_error = traceback.format_exc()

        # If all attempts failed, return the last error
        return Response(
            {
                "ok": False,
                "preview": {
                    "question": "",
                    "answers": [],
                    "solution": "",
                    "diagram_svg": "",
                    "diagram_code": "",
                    "substituted_yaml": original_yaml_text if 'original_yaml_text' in locals() else content,
                    "params": generated_params if 'generated_params' in locals() else {},
                    "errors": [f"Failed after {MAX_ATTEMPTS} attempts: {last_error}"]
                },
                "error": f"Failed after {MAX_ATTEMPTS} attempts: {last_error}"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=["post"])
    def generate(self, request):
        skill_id = request.data.get("skill_id")

        if not skill_id:
            return Response({"error": "skill_id missing"}, status=400)
        try:
            skill = Skill.objects.get(id=skill_id)
        except Skill.DoesNotExist:
            return Response({"error": "Skill not found"}, status=404)

        print("\nSkill:\n", skill.description)
        data = generate_template_content(skill.description)
        print("AI Output:\n", data)

        created_templates = []

        for item in data:
            template = Template.objects.create(
                skill=skill,
                subject=item["title"],
                content=format_for_editor(item),
            )
            created_templates.append(template)

        # Return ONLY the first created template
        first = created_templates[0]

        return Response({
            "id": first.id,
            "subject": first.subject,
            "content": first.content,
            "skill": first.skill.id,
        })

    @action(detail=True, methods=["post"])
    def diagram(self, request, pk=None):
        template = self.get_object()
        svg = request.data.get("svg")

        if not svg:
            return Response({"error": "SVG missing"}, status=400)

        diagram, _ = TemplateDiagram.objects.update_or_create(
            template=template,
            defaults={"svg_spec": svg}
        )

        return Response({"ok": True})


class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all().order_by("order_index")
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["retrieve", "children"]:
            return SkillDetailSerializer
        return SkillSerializer

    @action(detail=True, methods=["get"])
    def children(self, request, pk=None):
        parent = self.get_object()
        children = parent.children.order_by("order_index")
        serializer = SkillSerializer(children, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def direct_templates(self, request, pk=None):
        skill = self.get_object()
        templates = skill.direct_templates()
        serializer = TemplateSerializer(templates, many=True)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        parent_id = request.query_params.get("parent")
        if parent_id:
            skills = Skill.objects.filter(parent_id=parent_id).order_by("order_index")
        else:
            skills = Skill.objects.filter(parent__isnull=True).order_by("order_index")

        serializer = SkillSerializer(skills, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def parents(self, request, pk=None):
        skill = self.get_object()
        chain = []
        current = skill.parent

        while current:
            chain.append(current)
            current = current.parent

        # reverse so it goes root → child → current
        chain.reverse()

        serializer = SkillSerializer(chain, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def load_syllabus(self, request):
        # Safety: prevent accidental double-import
        from backend.models import Skill
        if Skill.objects.exists():
            return Response({"error": "Skills already exist. Clear them first."}, status=400)

        import_syllabus()
        return Response({"status": "Syllabus loaded successfully"})


    def destroy(self, request, *args, **kwargs):
        skill = self.get_object()

        if skill.children.exists():
            return Response(
                {"error": "Cannot delete a skill that has sub-skills."},
                status=400
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def diagram(self, request, pk=None):
        template = self.get_object()
        svg = request.data.get("svg")

        if not svg:
            return Response({"error": "SVG missing"}, status=400)

        diagram, _ = TemplateDiagram.objects.update_or_create(
            template=template,
            defaults={"svg_spec": svg}
        )

        return Response({"ok": True})

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def matrix(self, request):
        return Response(get_matrix_cache())


# -------------- TUTOR ---------------- #

class TutorViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(role="tutor").order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"])
    def home(self, request, pk=None):
        tutor = self.get_object()
        return Response({
            "id": tutor.id,
            "name": tutor.get_full_name() or tutor.username,
            "email": tutor.email,
        })

    @action(detail=True, methods=["get"])
    def templates(self, request, pk=None):
        tutor = self.get_object()
        templates = Template.objects.filter(created_by=tutor)
        serializer = TemplateSerializer(templates, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        tutor = self.get_object()

        # Get all students linked to this tutor
        links = TutorStudent.objects.filter(tutor=tutor).select_related("student__student_profile")
        student_users = [link.student for link in links]

        data = []
        for student_user in student_users:
            student_profile = student_user.get_student_profile()

            data.append({
                "id": student_user.id,
                "first_name": student_user.first_name,
                "last_name": student_user.last_name,
                "email": student_user.email,
                "year_level": student_profile.year_level,
                "area_of_study": student_profile.area_of_study,
            })

        return Response(data)

    @action(detail=False, methods=["post"])
    def create_tutor(self, request):
        name = request.data.get("name")
        email = request.data.get("email")
        password = request.data.get("password") or User.objects.make_random_password()

        if not name or not email:
            return Response({"error": "Name and email are required"}, status=400)

        new_tutor = User.objects.create(
            username=email,
            email=email,
            first_name=name,
            role="tutor",
            password=make_password(password),
        )

        TutorProfile.objects.create(tutor=new_tutor)

        return Response({
            "id": new_tutor.id,
            "name": new_tutor.first_name,
            "email": new_tutor.email,
            "password": password
        })

    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        tutor = self.get_object()

        availability = TutorAvailability.objects.filter(tutor=tutor)
        blocked = TutorBlockedDay.objects.filter(tutor=tutor)

        return Response({
            "availability": [
                {
                    "id": a.id,
                    "weekday": a.weekday,
                    "start_time": a.start_time,
                    "end_time": a.end_time,
                }
                for a in availability
            ],
            "blocked_days": [
                {
                    "id": b.id,
                    "date": b.date,
                }
                for b in blocked
            ]
        })

    @action(detail=True, methods=["post"])
    def add_availability(self, request, pk=None):
        tutor = self.get_object()
        js_weekday = int(request.data["weekday"])
        weekday = (js_weekday - 1) % 7
        start = request.data.get("start_time")
        end = request.data.get("end_time")

        a = TutorAvailability.objects.create(
            tutor=tutor,
            weekday=weekday,
            start_time=start,
            end_time=end,
        )

        return Response({"id": a.id})

    @action(detail=True, methods=["post"])
    def remove_availability(self, request, pk=None):
        TutorAvailability.objects.filter(id=request.data.get("id")).delete()
        return Response({"status": "ok"})

    @action(detail=True, methods=["post"])
    def block_day(self, request, pk=None):
        tutor = self.get_object()
        date = request.data.get("date")
        b = TutorBlockedDay.objects.create(tutor=tutor, date=date)
        return Response({"id": b.id})


    @action(detail=True, methods=["post"])
    def unblock_day(self, request, pk=None):
        TutorBlockedDay.objects.filter(id=request.data.get("id")).delete()
        return Response({"status": "ok"})

    @action(detail=True, methods=["get"])
    def weekly_slots(self, request, pk=None):
        user = self.get_object()
        tutor = user.get_tutor_profile()
        student_id = request.query_params.get("student")
        student = User.objects.filter(pk=student_id).first()
        # print("Weekly slots (student)", student_id, student)

        week_start_str = request.query_params.get("week_start")
        if not week_start_str:
            return Response({"error": "week_start is required (YYYY-MM-DD)"}, status=400)

        try:
            raw_date = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        week_start = get_sunday_start(raw_date)
        week_data = tutor.generate_weekly_slots(week_start, student)

        return Response({"week": week_data}, status=200)

    @action(detail=True, methods=["get"])
    def session_settings(self, request, pk=None):
        user = self.get_object()
        tutor = TutorProfile.objects.get(tutor=user)
        serializer = TutorSerializer(tutor)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="check_and_book")
    def check_and_book(self, request, pk=None):
        print("Check and book")
        user = self.get_object()
        tutor = user.get_tutor_profile()

        student_id = request.data["student_id"]
        student = User.objects.get(pk=student_id)
        date = request.data["date"]
        time = request.data["time"]
        repeat = request.data.get("repeat_weekly", False)

        # Parse date + time
        date_dt = datetime.fromisoformat(date).date()
        start_t = datetime.strptime(time, "%H:%M").time()

        # Compute end time
        session_minutes = tutor.default_session_minutes
        end_t = (datetime.combine(date_dt, start_t) +
                 timedelta(minutes=session_minutes)).time()

        weeks = 12 if repeat else 1

        created = 0
        results = []  # ← collect success/failure for each week

        for i in range(weeks):
            this_date = date_dt + timedelta(weeks=i)
            print("Check and Book:", this_date)
            # Check availability using your existing logic
            status = tutor.appointment_status(this_date, start_t)

            if status != "available":
                results.append({
                    "week": i + 1,
                    "date": str(this_date),
                    "time": start_t.strftime("%H:%M"),
                    "success": False,
                    "reason": status,
                })
                continue  # ← keep going to next week

            # Build aware datetimes
            naive_start = datetime.combine(this_date, start_t)
            naive_end = datetime.combine(this_date, end_t)
            start_dt = make_aware(naive_start)
            end_dt = make_aware(naive_end)

            try:
                Appointment.objects.create(
                    tutor=user,
                    student_id=student_id,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    status="booked",
                    created_by=student,
                )
                created += 1
                results.append({
                    "week": i + 1,
                    "date": str(this_date),
                    "time": start_t.strftime("%H:%M"),
                    "success": True,
                })
            except Exception as e:
                # Database or validation error
                results.append({
                    "week": i + 1,
                    "date": str(this_date),
                    "time": start_t.strftime("%H:%M"),
                    "success": False,
                    "reason": str(e),
                })

        return Response({
            "status": "ok" if created > 0 else "error",
            "created": created,
            "results": results,
        })

    @action(detail=True, methods=["post"], url_path="delete_booking")
    def delete_booking(self, request, pk=None):
        user = self.get_object()  # the tutor in tutor_view OR the tutor of the student

        booking_id = request.data.get("booking_id")
        if not booking_id:
            return Response({"error": "booking_id is required"}, status=400)
        try:
            appt = Appointment.objects.get(id=booking_id)
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found"}, status=404)

        appt.delete()
        return Response({"status": "ok", "message": "Booking deleted"})

# -------------- STUDENT ---------------- #

class StudentViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(role="student").select_related("student_profile")
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = super().get_object()
        profile = user.get_student_profile()
        return profile

    @action(detail=True, methods=["get"])
    def home(self, request, pk=None):
        student_profile = self.get_object()
        user = student_profile.user
        tutor_user = user.get_tutor()
        tutor_name = None
        tutor_id = None
        if tutor_user:
            tutor_name = tutor_user.get_full_name() or tutor_user.username
            tutor_id = tutor_user.id

        # Build the flattened response
        data = {
            "id": user.id,
            "name": user.get_full_name() or user.username,
            "email": user.email,
            "tutor_id": tutor_id,
            "tutor_name": tutor_name,
            "year_level": student_profile.year_level,
            "area_of_study": student_profile.area_of_study,
        }

        return Response(data)

    @action(detail=False, methods=["post"])
    def create_student(self, request):
        """
        Create a new student User + StudentProfile.
        """
        name = request.data.get("name")
        email = request.data.get("email")
        password = request.data.get("password") or User.objects.make_random_password()
        tutor_id = request.data.get("tutor_id")

        if not name or not email:
            return Response({"error": "Name and email are required"}, status=400)

        # Create the User
        student = User.objects.create(
            username=email,
            email=email,
            first_name=name,
            role="student",
            password=make_password(password),
        )

        # Create the StudentProfile
        StudentProfile.objects.create(user=student)

        # Link to tutor if provided
        if tutor_id:
            TutorStudent.objects.create(
                tutor_id=tutor_id,
                student=student
            )

        return Response({
            "id": student.id,
            "name": student.first_name,
            "email": student.email,
            "password": password,
            "linked_to_tutor": tutor_id,
        })

class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.all().order_by("-created_at")
    serializer_class = NoteSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(author=user)

