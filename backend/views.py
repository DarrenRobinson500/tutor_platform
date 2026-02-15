from django.contrib.auth.hashers import make_password
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
# from datetime import datetime, timedelta, time as dtime

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
from .cache import *
import time
from .template_utilities import *
from django.contrib.auth import get_user_model
User = get_user_model()

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

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def dev_login(self, request):
        username = request.data.get("username")

        dev_users = {
            "admin": "admin",
            "alex": "superalexrobinson@gmail.com",
            "blair": "Blair",
        }

        if username not in dev_users:
            return Response({"error": "Unknown dev user"}, status=400)

        try:
            user = User.objects.get(username=dev_users[username])
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        # Force login (no password)
        login(request, user)

        # Return the same structure as your normal login
        return Response({
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "role": user.role,
        })


class QuestionViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["post"])
    def record(self, request):
        student_id = request.data.get("student_id")
        template_id = request.data.get("template_id")

        if not student_id:
            return Response({"error": "student_id is required"}, 400)

        if not template_id:
            return generate_first_question(request)

        # Validate student
        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            return Response({"error": "Student not found"}, status=404)
        print("Found student")

        # Validate template
        try:
            template = Template.objects.get(id=template_id)
        except Template.DoesNotExist:
            return Response({"error": "Template not found"}, status=404)
        print("Found template")

        # Create the Question record
        q = Question.objects.create(
            template=template,
            student=student,
            params=request.data.get("params", {}),
            question_text=request.data.get("question_text", ""),
            correct_answer=request.data.get("correct_answer", ""),
            help_requested=request.data.get("help_requested", False),
            selected_answer=request.data.get("selected_answer"),
            correct=request.data.get("correct", False),
            time_taken_ms=request.data.get("time_taken_ms"),
        )

        # ---------------------------------------------------------
        # UPDATE STUDENT SKILL MASTERY
        # ---------------------------------------------------------
        skill = template.skill  # Template already has a skill FK

        matrix, _ = StudentSkillMatrix.objects.get_or_create(
            student=student,
            skill=skill,
            defaults={"mastery": 0.0}
        )
        # print("Mastery (pre):", matrix.mastery)

        # Update mastery
        if q.correct:
            matrix.mastery += 1
        else:
            matrix.mastery -= 5

        # Clamp mastery between 0 and 15
        matrix.mastery = max(0, min(15, matrix.mastery))
        matrix.save()
        # print("Mastery (post):", matrix.mastery)

        # ---------------------------------------------------------
        # DETERMINE NEXT DIFFICULTY
        # ---------------------------------------------------------
        if matrix.mastery <= 4:
            next_difficulty = "easy"
        elif matrix.mastery <= 9:
            next_difficulty = "medium"
        else:
            next_difficulty = "hard"

        # ---------------------------------------------------------
        # FETCH NEXT QUESTION DIRECTLY
        # ---------------------------------------------------------
        print(f"Looking for templates with:")
        print(f"  skill: {template.skill}")
        print(f"  grade: {template.grade}")
        print(f"  difficulty: {next_difficulty}")
        next_template = (
            Template.objects.filter(
                skill=template.skill,
                grade=template.grade,
                difficulty__iexact=next_difficulty
            )
            .order_by("?")
            .first()
        )
        print(f"Found next_template for specific difficulty: {next_template}")
        if next_template:
            preview = generate_values_and_question(next_template.id)
            if preview["ok"]:
                next_question = preview["preview"]
                next_question["template_id"] = next_template.id  # <-- FIX
                # print("Next question", next_question)
            else:
                next_question = None
        else:
            next_question = None

        if not next_template:
            print("No template found for specific difficulty, looking for any template...")
            next_template = Template.objects.filter(skill=template.skill, grade=template.grade).first()
            print(f"Fallback template: {next_template}")

        # Generate question from the template (either specific difficulty or fallback)
        next_question = None
        next_template_id = None
        if next_template:
            next_template_id = next_template.id
            print(f"Generating question for template: {next_template_id}")

            preview = generate_values_and_question(next_template.id)
            if preview["ok"]:
                next_question = preview["preview"]
                next_question["template_id"] = next_template.id
                print(f"Successfully generated question with template_id: {next_template.id}")
            else:
                print("Failed to generate question from template")
                next_question = None
                next_template_id = None
        else:
            print("No template found at all - this shouldn't happen in a normal system")

        # ---------------------------------------------------------
        # RETURN RESPONSE INCLUDING NEXT DIFFICULTY
        # ---------------------------------------------------------
        response_data = {
            "ok": True,
            "question_id": q.id,
            "mastery": matrix.mastery,
            "competence_label": mastery_label(matrix.mastery),
            "next_difficulty": next_difficulty,
            "next_question": next_question,
            "template_id": next_template.id if next_template else None,
        }
        print("Returning response:", response_data)  # Add this
        return Response(response_data, status=201)

class TemplateViewSet(viewsets.ModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    def preview(self, request):

        # 1. Content-based preview (TemplateEditorPage)
        content = request.data.get("content")
        if content:
            print("Preview - 1")
            result = generate_preview_from_content(content)
            return Response(
                {"ok": result["ok"], "preview": result["preview"], "error": result["error"]},
                status=200 if result["ok"] else 400
            )

        # 2. Skill + grade lookup (SkillsMatrix)
        skill_id = request.data.get("skill")
        grade = request.data.get("grade")
        difficulty = request.data.get("difficulty")
        if skill_id and grade:
            qs = Template.objects.filter(skill_id=skill_id, grade=grade)
            print("Query set:", skill_id, grade, qs)
            if difficulty: qs = qs.filter(difficulty=difficulty)
            qs = qs.order_by("id")
            first = qs.first()
            if not first:
                return Response({
                    "ok": False,
                    "error": "No templates exist for this skill and grade."
                }, status=404)

            result = generate_values_and_question(first.id)
            print("Preview - 2")
            print(qs)
            print(result)
            return Response({
                "ok": result["ok"],
                "template_id": first.id,
                "preview": result["preview"],
                "error": result["error"]
            }, status=200 if result["ok"] else 400)

        # 3. Template ID preview (Editor navigation)
        template_id = request.data.get("templateId") or request.data.get("id")
        if template_id:
            result = generate_values_and_question(template_id)
            print("Preview - 3")
            return Response(
                {"ok": result["ok"], "preview": result["preview"], "error": result["error"]},
                status=200 if result["ok"] else 400
            )

        # 4. Fallback
        print("Preview - 4")
        return Response(
            {"ok": False, "error": "No valid preview parameters provided"},
            status=400
        )

    @action(detail=False, methods=["post"])
    def generate(self, request):
        skill_id = request.data.get("skill_id")
        grade = request.data.get("grade")
        if not skill_id:
            return Response({"error": "skill_id missing"}, status=400)
        try:
            skill = Skill.objects.get(id=skill_id)
        except Skill.DoesNotExist:
            return Response({"error": "Skill not found"}, status=404)

        print(f"Skill: {skill.description}, Grade: {grade}")
        data = generate_template_content(skill.description, grade)
        print("AI Output:\n", data)

        created_templates = []

        for item in data:
            template = Template.objects.create(
                skill=skill,
                grade=grade,
                difficulty=item["difficulty"],
                subject=item["title"],
                content=format_for_editor(item),
            )
            created_templates.append(template)

        # Return ONLY the first created template
        first = created_templates[0]
        update_matrix_cache_for_template_count(skill_id)

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

    @action(detail=False, methods=["get"])
    def filtered(self, request):
        skill = request.query_params.get("skill")
        grade = request.query_params.get("grade")
        difficulty = request.query_params.get("difficulty")

        # print("FILTER RECEIVED GRADE:", repr(grade))

        qs = Template.objects.all()
        # print("pre", len(qs))
        if skill:
            qs = qs.filter(skill_id=skill)
        # print("skill", len(qs))
        if grade:
            qs = qs.filter(grade=grade)
        # print("grade", len(qs))
        if difficulty:
            qs = qs.filter(difficulty__iexact=difficulty.strip())
        # print("difficulty", len(qs))

        qs = qs.order_by("id")
        # print("post", len(qs))

        return Response([
            {
                "id": t.id,
                "name": t.name,
                "subject": t.subject,
                "skill": t.skill_id,
                "grade": t.grade,
                "difficulty": t.difficulty,
            }
            for t in qs
        ])

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



class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all().order_by("order_index")
    serializer_class = SkillSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def leaf(self, request):
        grade = request.query_params.get("grade")
        matrix = get_matrix_cache()  # uses cached tree
        rows = matrix["skills"]
        leaf_skills = []
        for row in rows:
            if row["children_count"] != 0:
                continue
            if grade:
                g = str(grade)
                if row["cells"][g]["colour"] != "covered":
                    continue

            leaf_skills.append({
                "id": row["id"],
                "description": row["description"],
            })

        return Response(leaf_skills)

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
        import_syllabus()
        global MATRIX_CACHE
        MATRIX_CACHE = None
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
        matrix = get_matrix_cache()  # fast, full matrix
        grade = request.query_params.get("grade")
        student_id = request.query_params.get("student_id")

        # ----------------------------------------
        # Build mastery map if student_id provided
        # ----------------------------------------
        mastery_map = {}

        if student_id:
            rows = StudentSkillMatrix.objects.filter(student_id=student_id)

            for row in rows:
                mastery_map[row.skill_id] = {
                    "mastery": row.mastery,
                    "competence_label": mastery_label(row.mastery)
                }

        # ----------------------------------------
        # Apply grade filtering if needed
        # ----------------------------------------
        if grade and grade != "All":
            filtered = filter_matrix_by_grade(matrix, grade)
            return Response({
                "grades": matrix["grades"],
                "skills": filtered,
                "mastery": mastery_map,
            })

        return Response({
            "grades": matrix["grades"],
            "skills": matrix["skills"],
            "mastery": mastery_map,
        })

# -------------- TUTOR ---------------- #

class TutorViewSet(viewsets.ModelViewSet):

    queryset = User.objects.filter(role="tutor").order_by("username")
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

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
        data = get_cached_students_for_tutor(tutor)
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
        invalidate_weekly_slots_cache_for_tutor(tutor.id)

        return Response({"id": a.id})

    @action(detail=True, methods=["post"])
    def remove_availability(self, request, pk=None):
        TutorAvailability.objects.filter(id=request.data.get("id")).delete()
        invalidate_weekly_slots_cache_for_tutor(tutor.id)

        return Response({"status": "ok"})

    @action(detail=True, methods=["post"])
    def block_day(self, request, pk=None):
        tutor = self.get_object()
        date = request.data.get("date")
        b = TutorBlockedDay.objects.create(tutor=tutor, date=date)
        invalidate_weekly_slots_cache_for_tutor(tutor.id)

        return Response({"id": b.id})


    @action(detail=True, methods=["post"])
    def unblock_day(self, request, pk=None):
        TutorBlockedDay.objects.filter(id=request.data.get("id")).delete()
        invalidate_weekly_slots_cache_for_tutor(tutor.id)

        return Response({"status": "ok"})

    @action(detail=True, methods=["get"])
    def weekly_slots(self, request, pk=None):
        start = time.perf_counter()

        user = self.get_object()
        tutor = user.get_tutor_profile()

        # Optional student
        student_id = request.query_params.get("student")
        student = User.objects.filter(pk=student_id).first() if student_id else None

        # Parse week_start
        week_start_str = request.query_params.get("week_start")
        if not week_start_str:
            return Response({"error": "week_start is required (YYYY-MM-DD)"}, status=400)

        try:
            raw_date = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        week_start = get_sunday_start(raw_date)

        # Use cached version
        week_data = get_cached_weekly_slots(tutor, week_start, student)

        print(f"Weekly slots build took {time.perf_counter() - start:.4f} seconds")

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
        invalidate_weekly_slots_cache_for_tutor(tutor.id)

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
    permission_classes = [AllowAny]

    def get_object(self):
        user = super().get_object()
        profile = user.get_student_profile()
        return profile

    @action(detail=True, methods=["get"])
    def home(self, request, pk=None):
        student_profile = self.get_object()
        user = student_profile.user

        tutor_user = user.get_tutor()
        tutor_name = tutor_user.get_full_name() or tutor_user.username if tutor_user else None
        tutor_id = tutor_user.id if tutor_user else None

        # Next booking
        next_booking = (Appointment.objects.filter(student=user, start_datetime__gte=timezone.now()).order_by("start_datetime").first())

        next_booking_data = None
        if next_booking:
            next_booking_data = {
                "id": next_booking.id,
                "start": next_booking.start_datetime,
                "end": next_booking.end_datetime,
            }

        data = {
            "id": user.id,
            "name": user.get_full_name() or user.username,
            "email": user.email,
            "tutor_id": tutor_id,
            "tutor_name": tutor_name,
            "year_level": student_profile.year_level,
            "area_of_study": student_profile.area_of_study,
            "next_booking": next_booking_data,
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
        invalidate_students_cache_for_tutor(tutor_id)

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

