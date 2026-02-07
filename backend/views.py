from django.contrib.auth.hashers import make_password
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout

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
        students = User.objects.filter(tutors__tutor=tutor)
        serializer = UserSerializer(students, many=True)
        return Response(serializer.data)

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
        date = request.data["date"]  # "2026-02-01"
        time = request.data["time"]  # "09:00"
        repeat = request.data.get("repeat_weekly", False)

        print("Check and book (user, tutor, studentid, date, time, repeat)",
              user, tutor, student_id, date, time, repeat)

        # Parse date + time
        date_dt = datetime.fromisoformat(date).date()
        start_t = datetime.strptime(time, "%H:%M").time()

        # Compute end time
        session_minutes = tutor.default_session_minutes
        end_t = (datetime.combine(date_dt, start_t) + timedelta(minutes=session_minutes)).time()

        print("Check and book (date_dt, start_t, end_t)", date_dt, start_t, end_t)

        # Weekly repetition
        weeks = 12 if repeat else 1
        created = 0

        for i in range(weeks):
            this_date = date_dt + timedelta(weeks=i)

            # Build naive datetimes
            naive_start = datetime.combine(this_date, start_t)
            naive_end = datetime.combine(this_date, end_t)

            # Localize to Sydney timezone
            start_dt = make_aware(naive_start)
            end_dt = make_aware(naive_end)

            # Availability check
            if tutor.is_available(this_date, start_t, end_t):
                Appointment.objects.create(
                    tutor=user,
                    student_id=student_id,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    status="booked",
                    created_by=student,
                )
                created += 1

        return Response({
            "status": "ok",
            "message": f"Appointment booked ({created} sessions)"
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

class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role="student").order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"])
    def home(self, request, pk=None):
        user = self.get_object()
        tutor = user.get_tutor()
        print("Student Home (user, tutor, tutor_id):", user, tutor, tutor.id if tutor else None)
        return Response({
            "id": user.id,
            "name": user.get_full_name() or user.username,
            "email": user.email,
            "tutor_id": tutor.id if tutor else None,
            "tutor_name": tutor.get_full_name() or tutor.username if tutor else None,
        })

    @action(detail=False, methods=["post"])
    def create_student(self, request):
        name = request.data.get("name")
        email = request.data.get("email")
        password = request.data.get("password") or User.objects.make_random_password()
        tutor_id = request.data.get("tutor_id")

        if not name or not email:
            return Response({"error": "Name and email are required"}, status=400)

        student = User.objects.create(
            username=email,
            email=email,
            first_name=name,
            role="student",
            password=make_password(password),
        )

        if tutor_id:
            TutorStudent.objects.create(
                tutor_id=tutor_id,
                student=student
            )

        return Response({
            "id": student.id,
            "name": student.first_name,
            "email": student.email,
            "password": password,  # shown once so admin can give it to the student
            "linked_to_tutor": tutor_id,

        })

class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.all().order_by("-created_at")
    serializer_class = NoteSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(author=user)

