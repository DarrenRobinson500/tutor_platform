from django.contrib.auth.hashers import make_password
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout
# from datetime import datetime, timedelta, time as dtime
from django.db.models import Case, When, Value, IntegerField


from .validation import *
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
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.tokens import RefreshToken
from .pre_view import *
from .message import *
from .booking import *

@method_decorator(csrf_exempt, name='dispatch')
class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"])
    def me(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"error": "Not authenticated"}, status=401)
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
            "alex": "Alex",
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

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[],)
    def register(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        role = request.data.get("role")

        if not email or not password or not role:
            return Response({"error": "Missing fields"}, status=400)

        if role not in ["tutor", "parent", "student"]:
            return Response({"error": "Invalid role"}, status=400)

        if User.objects.filter(username=email).exists():
            return Response({"error": "Email already registered"}, status=400)

        user = User.objects.create(
            username=email,
            email=email,
            password=make_password(password),
            role=role,
        )

        if user.role == "tutor":
            profile = TutorProfile.objects.create(tutor=user)

        login(request, user)

        return Response({
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "first_name": user.first_name,
        })

    @method_decorator(csrf_exempt, name='login')
    @action(detail=False, methods=["post"], permission_classes=[AllowAny], authentication_classes=[],)
    def login(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        user = authenticate(request, username=email, password=password)

        if user is None:
            print("Login: invalid credentials")
            return Response({"error": "Invalid credentials"}, status=400)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "first_name": user.first_name,
            }
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
                difficulty__iexact=next_difficulty,
                validated=True
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
            next_template = Template.objects.filter(skill=template.skill, grade=template.grade, validated=True).first()
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

    @action(detail=False, methods=["get"])
    def subjects(self, request):
        qs = Template.objects.all()
        skill = request.query_params.get("skill")
        grade = request.query_params.get("grade")
        difficulty = request.query_params.get("difficulty")
        validated = request.query_params.get("validated")
        if skill:
            qs = qs.filter(skill_id=skill)
        if grade:
            qs = qs.filter(grade=grade)
        if difficulty:
            qs = qs.filter(difficulty__iexact=difficulty.strip())
        if validated == "validated":
            qs = qs.filter(validated=True)
        elif validated == "unvalidated":
            qs = qs.filter(validated=False)
        subjects = qs.values_list("subject", flat=True).distinct()
        return Response([s for s in subjects if s])

    def perform_update(self, serializer):
        # Capture the old skill before saving in case it changes
        old_skill_id = serializer.instance.skill_id
        instance = serializer.save()
        new_skill_id = instance.skill_id
        if old_skill_id:
            update_matrix_cache_for_count(old_skill_id)
        if new_skill_id and new_skill_id != old_skill_id:
            update_matrix_cache_for_count(new_skill_id)

    def perform_destroy(self, instance):
        skill_id = instance.skill_id
        instance.delete()
        if skill_id:
            update_matrix_cache_for_count(skill_id)

    @action(detail=True, methods=['post'])
    def toggle_validated(self, request, pk=None):
        template = self.get_object()
        template.validated = not template.validated
        template.save()
        update_matrix_cache_for_count(template.skill_id)

        return Response({"validated": template.validated})

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        original = self.get_object()
        copy = Template.objects.create(
            skill=original.skill,
            grade=original.grade,
            name=original.name,
            subject=original.subject,
            difficulty=original.difficulty,
            content=original.content,
        )
        update_matrix_cache_for_count(copy.skill_id)
        return Response({"id": copy.id})

    @action(detail=False, methods=["post"])
    def preview(self, request):

        # 1. Content-based preview (TemplateEditorPage)
        content = request.data.get("content")
        if content:
            result = generate_preview_from_content(content)
            # Inject knowledge items when the template ID is also known
            template_id = request.data.get("templateId")
            if result["ok"] and template_id and result.get("preview") is not None:
                try:
                    tpl = Template.objects.get(pk=template_id)
                    from .diagram.engine import render_diagram_from_code
                    knowledge_items = []
                    for k in tpl.knowledge_items.all():
                        svg = ""
                        if k.diagram and k.diagram.strip() and k.diagram.strip().lower() != "none":
                            try:
                                svg = render_diagram_from_code(k.diagram)
                            except Exception:
                                pass
                        knowledge_items.append({
                            "id": k.id,
                            "title": k.title,
                            "text": k.text,
                            "text_2": k.text_2,
                            "diagram_svg": svg,
                        })
                    result["preview"]["knowledge_items"] = knowledge_items
                except Exception:
                    pass
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
            # print("Query set:", skill_id, grade, qs)
            if difficulty:
                qs = qs.filter(difficulty=difficulty)
            else:
                qs = qs.order_by(
                    Case(
                        When(difficulty="easy", then=0),
                        When(difficulty="medium", then=1),
                        When(difficulty="hard", then=2),
                        default=3,
                        output_field=IntegerField(),
                    ),
                    "id"
                )

            qs = qs.order_by("id")
            first = qs.first()
            if not first:
                return Response({
                    "ok": False,
                    "template_id": None,
                    "error": "No templates exist for this skill and grade."
                }, status=404)

            result = generate_values_and_question(first.id)
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
            return Response(
                {"ok": result["ok"], "preview": result["preview"], "error": result["error"]},
                status=200 if result["ok"] else 400
            )

        # 4. Fallback
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

        print(f"Generating Questions. Skill: {skill.description}, Grade: {grade}")
        try:
            data = generate_template_content(skill, grade)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"AI generation failed: {e}"}, status=500)

        print(f"AI returned {len(data) if isinstance(data, list) else type(data).__name__} items")

        if not isinstance(data, list):
            return Response({"error": f"AI returned unexpected type {type(data).__name__}, expected list"}, status=500)

        created_templates = []

        for i, item in enumerate(data):
            try:
                template = Template.objects.create(
                    skill=skill,
                    grade=grade,
                    name=item["title"],
                    difficulty=item["difficulty"],
                    subject=item["title"],
                    content=format_for_editor(item),
                )
                created_templates.append(template)
            except Exception as e:
                import traceback
                print(f"Failed to create template {i}: {e}")
                traceback.print_exc()
                # Continue so remaining templates are still saved

        if not created_templates:
            return Response({"error": "No templates could be created from AI output"}, status=500)

        # Return ONLY the first created template
        first = created_templates[0]
        update_matrix_cache_for_count(skill_id)

        return Response({
            "id": first.id,
            "subject": first.subject,
            "content": first.content,
            "skill": first.skill.id,
        })

    @action(detail=False, methods=["post"])
    def generate_from_image(self, request):
        image_b64 = request.data.get("image")
        mime_type = request.data.get("mime_type", "image/png")
        grade = request.data.get("grade", "")
        additional_prompt = request.data.get("additional_prompt", "")

        if not image_b64:
            return Response({"error": "image required"}, status=400)
        if not grade:
            return Response({"error": "grade required"}, status=400)

        # Build skill list filtered to the selected grade
        matrix = get_matrix_cache()
        grade_str = str(grade)
        skills_list = [
            {"id": row["id"], "code": row["code"], "description": row["description"]}
            for row in matrix["skills"]
            if row["children_count"] == 0
            and row["cells"].get(grade_str, {}).get("colour") == "covered"
        ]

        if not skills_list:
            return Response({"error": f"No skills found for Year {grade}"}, status=400)

        try:
            item = generate_template_from_image(image_b64, mime_type, skills_list, grade_str, additional_prompt)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"AI generation failed: {e}"}, status=500)

        skill_id = item.get("skill_id")
        skill = None
        if skill_id:
            try:
                skill = Skill.objects.get(id=int(skill_id))
            except Exception:
                pass

        template = Template.objects.create(
            skill=skill,
            grade=grade_str,
            name=item.get("title", ""),
            subject=item.get("title", ""),
            difficulty=item.get("difficulty", ""),
            content=format_for_editor(item),
        )

        if skill:
            update_matrix_cache_for_count(skill.id)

        return Response({
            "id": template.id,
            "subject": template.subject,
            "content": template.content,
            "skill": template.skill.id if template.skill else None,
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

    @action(detail=False, methods=["post"])
    def update_with_ai(self, request):
        existing_yaml = request.data.get("content", "")
        instruction = request.data.get("instruction", "")

        if not instruction.strip():
            return Response({"error": "instruction required"}, status=400)

        try:
            from .ai import update_template
            from .utilities import format_for_editor
            item = update_template(existing_yaml, instruction)
            content = format_for_editor(item)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"AI update failed: {e}"}, status=500)

        return Response({"content": content})

    @action(detail=False, methods=["get"])
    def filtered(self, request):
        skill = request.query_params.get("skill")
        grade = request.query_params.get("grade")
        difficulty = request.query_params.get("difficulty")
        validated = request.query_params.get("validated")

        qs = Template.objects.all()
        if skill: qs = qs.filter(skill_id=skill)
        if grade: qs = qs.filter(grade=grade)
        if difficulty: qs = qs.filter(difficulty__iexact=difficulty.strip())
        if validated == "validated": qs = qs.filter(validated=True)
        elif validated == "unvalidated": qs = qs.filter(validated=False)

        qs = qs.order_by("id")

        import yaml as _yaml
        def _question_text(t):
            try:
                parsed = _yaml.safe_load(t.content or "")
                return (parsed or {}).get("question", {}).get("text", "") or ""
            except Exception:
                return ""

        return Response([
            {
                "id": t.id,
                "name": t.name or t.subject or "",
                "subject": t.subject,
                "skill": t.skill_id,
                "grade": t.grade,
                "difficulty": t.difficulty,
                "validated": t.validated,
                "question_text": _question_text(t),
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
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"])
    def home(self, request, pk=None):
        tutor = self.get_object()
        profile = tutor.get_tutor_profile()
        return Response(profile.to_dict())

    @action(detail=True, methods=["get"])
    def students(self, request, pk=None):
        # print("Getting students:")
        tutor_user = self.get_object()
        data = get_cached_students_for_tutor(tutor_user)
        # print("Received students:", now)
        # print(data)
        return Response(data)

    @action(detail=True, methods=["get"], url_path="booking")
    def booking(self, request, pk=None):

        tutor = self.get_object()
        students = get_cached_students_for_tutor(tutor)

        today = date.today()
        weekday = today.weekday()
        last_monday = today - timedelta(days=weekday)
        next_monday = last_monday + timedelta(days=7)
        last_monday = last_monday.isoformat()
        next_monday = next_monday.isoformat()

        # Build two weeks using cached data
        week1 = get_combined_calendar(tutor, last_monday)
        week2 = get_combined_calendar(tutor, next_monday)
        # print("Week 1:", week1)

        return Response({
            "students": students,
            "week1": week1,
            "week2": week2,
        })

    @action(detail=True, methods=["post"])
    def edit(self, request, pk=None):
        print("Tutor edit")
        user = self.get_object()
        profile = user.get_tutor_profile()

        fields = request.data.get("fields", {})
        print("Tutor edit (fields)", fields)

        # Update User fields
        for key, value in fields.items():
            if hasattr(user, key):
                setattr(user, key, value)

        user.save()

        fields_to_update = ["mobile", "address", "default_session_minutes", "buffer_minutes"]
        changed = False
        for key, value in fields.items():
            if key in fields_to_update:
                print("Tutor edit:", key)
                setattr(profile, key, value)
                changed = True

        if changed:
            profile.save()

        return Response(profile.to_dict(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def sms(self, request, pk=None):
        tutor = self.get_object()
        conversations = SMSConversation.objects.filter(tutor=tutor).select_related("student").order_by("-last_message_at")

        data = []
        for convo in conversations:
            last_msg = convo.messages.order_by("-created_at").first()
            student = convo.student

            data.append({
                "conversation_id": convo.id,
                "student_id": student.id,
                "student_name": student.get_full_name() or student.username,
                "last_message": last_msg.body if last_msg else "",
                "last_message_at": last_msg.created_at if last_msg else convo.created_at,
            })

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="sms/conversation/(?P<conversation_id>[^/.]+)")
    def sms_conversation(self, request, pk=None, conversation_id=None):
        tutor = self.get_object()

        try:
            convo = SMSConversation.objects.get(id=conversation_id, tutor=tutor)
        except SMSConversation.DoesNotExist:
            return Response({"error": "Conversation not found"}, status=404)

        messages = convo.messages.order_by("created_at")

        return Response({
            "conversation_id": convo.id,
            "tutor_id": tutor.id,
            "student_id": convo.student.id,
            "student_name": convo.student.get_full_name(),
            "messages": [
                {
                    "id": m.id,
                    "direction": m.direction,
                    "body": m.body,
                    "created_at": m.created_at,
                    "sent_at": m.sent_at,
                    "delivered_at": m.delivered_at,
                    "status": m.status,
                    "phone_number": m.phone_number,
                }
                for m in messages
            ]
        })

    @action(detail=True, methods=["get"], url_path="sms/activity")
    def sms_activity(self, request, pk=None):
        tutor = self.get_object()

        today = timezone.localdate()
        start_of_day = timezone.make_aware(datetime.combine(today, time.min))

        jobs = (SMSSendJob.objects.filter(conversation__tutor_id=tutor.id, cancelled=False, retry_count__lt=3).order_by("-created_at"))
        messages = (SMSMessage.objects.filter(conversation__tutor_id=tutor.id, created_at__gte=start_of_day,).select_related("conversation", "conversation__student").order_by("-created_at"))
        active = get_bool("sms_send", default=False)
        # print("active's type:", type(active))


        return Response({
            "jobs": [job.to_dict() for job in jobs],
            "messages": [msg.to_dict() for msg in messages],
            "active": active
        })

    @action(detail=True, methods=["get"])
    def templates(self, request, pk=None):
        tutor = self.get_object()
        templates = Template.objects.filter(created_by=tutor)
        serializer = TemplateSerializer(templates, many=True)
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
        invalidate_availability_adhoc(tutor.id)
        Invalidate_availability_weekly(tutor.id)

        return Response({"id": a.id})

    @action(detail=True, methods=["post"])
    def remove_availability(self, request, pk=None):

        TutorAvailability.objects.filter(id=request.data.get("id")).delete()
        invalidate_availability_adhoc(request.data.get("id"))

        return Response({"status": "ok"})

    @action(detail=True, methods=["post"])
    def block_day(self, request, pk=None):
        tutor = self.get_object()
        date = request.data.get("date")
        b = TutorBlockedDay.objects.create(tutor=tutor, date=date)
        invalidate_availability_adhoc(tutor.id)

        return Response({"id": b.id})


    @action(detail=True, methods=["post"])
    def unblock_day(self, request, pk=None):
        TutorBlockedDay.objects.filter(id=request.data.get("id")).delete()
        invalidate_availability_adhoc(tutor.id)

        return Response({"status": "ok"})

    @action(detail=True, methods=["get"])
    def session_settings(self, request, pk=None):
        user = self.get_object()
        tutor = TutorProfile.objects.get(tutor=user)
        serializer = TutorSerializer(tutor)
        return Response(serializer.data)


    # --------------- UNIFIED FUNCTION ----------------------

    @action(detail=True, methods=["POST"], url_path="booking_action")
    def booking_action(self, request, pk=None):
        tutor = self.get_object()
        data = request.data
        print("Booking action (data):", data)
        user_role = request.user.role

        command = data.get("command") or data.get("action")
        booking_type = data.get("booking_type") or data.get("type")
        booking_id = request.data.get("id")

        if not command or not booking_type:
            return Response({"ok": False, "error": "Missing command or booking_type"}, status=400)
        model = BookingAdhoc if booking_type == "adhoc" else BookingWeekly

        # CREATE
        if command == "create":
            # print("→ start create")
            # Delay the weekly and create adhoc (for a one-off change to a weekly schedule)
            if data.get("pause_weekly"):
                student_id = request.data.get("student_id")
                student = User.objects.get(id=student_id)
                weekly = BookingWeekly.objects.filter(tutor=tutor, student=student).first()
                if weekly:
                    weekly.skip()
                    update_booking_caches(weekly, "skip")
            return create_booking(tutor, data, booking_type, user_role)

        # ADJUST EXISTING BOOKING
        try:
            booking = model.objects.get(id=booking_id)
        except model.DoesNotExist:
            print("Couldn't find booking. model, Booking id:", model, booking_id)
            return Response({"ok": False, "error": "Booking not found"}, status=404)

        if command == "confirm":return confirm_booking(booking, user_role)
        if command == "edit": return edit_booking(booking, data, booking_type, user_role)
        if command == "skip": return skip_booking(booking, user_role)
        if command == "remove_skip": return remove_skip_booking(booking, user_role)
        if command == "delete":return delete_booking(booking, booking_type, user_role)

        return Response({"ok": False, "error": "Unknown command"}, status=400)

# -------------- STUDENT ---------------- #

class StudentViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(role="student").select_related("student_profile")
    serializer_class = StudentSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        user = super().get_object()
        profile = user.get_student_profile()
        return profile

    def retrieve(self, request, *args, **kwargs):
        student_profile = self.get_object()
        return Response(student_profile.to_dict())

    @action(detail=True, methods=["post"])
    def edit(self, request, pk=None):
        student_profile = self.get_object()
        student = student_profile.user
        fields = request.data.get("fields", {})
        print("Student edit (fields)", fields)
        for key, value in fields.items():
            if hasattr(student, key):
                print("Saved (to user): ", key, value)
                setattr(student, key, value)

        student.save()

        profile_fields = ["year_level", "area_of_study", "mobile", "address"]
        changed = False

        for key, value in fields.items():
            if key in profile_fields:
                print("Student edit:", key)
                setattr(student_profile, key, value)
                changed = True
        if changed:
            student_profile.save()
        update_student_cache(student)
        return Response(student_profile.to_dict(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def home(self, request, pk=None):
        student_profile = self.get_object()
        result = student_profile.to_dict()
        print("Student home:", result)
        return Response(result)

    @action(detail=True, methods=["get"])
    def booking(self, request, pk=None):
        student_profile = self.get_object()
        student = student_profile.user

        tutor = student.get_tutor()
        if not tutor:
            return Response({"error": "Student has no tutor assigned"}, status=400)

        start_date = (date.today() + timedelta(days=1)).isoformat()

        weekly_slots = get_weekly_slots(tutor)
        weekly_bookings = get_weekly_bookings(tutor)
        weekly_bookings = mask_weekly_bookings(weekly_bookings, student.id)

        adhoc_slots = get_availability_adhoc(tutor, start_date)
        adhoc_bookings = get_adhoc_bookings(tutor, start_date)
        adhoc_bookings = mask_adhoc_bookings(adhoc_bookings, student.id)

        return Response({
            "weekly_slots": weekly_slots,
            "weekly_bookings": weekly_bookings,
            "adhoc_slots": adhoc_slots,
            "adhoc_bookings": adhoc_bookings,
        })

    @action(detail=False, methods=["post"])
    def create_student(self, request):
        name = request.data.get("name")
        email = request.data.get("email")
        password = request.data.get("password") or User.objects.make_random_password()
        tutor_id = request.data.get("tutor_id")
        print("Create student: Tutor id:", tutor_id)

        # Pre-creation checks
        if not name or not email: return Response({"error": "Name and email are required"}, status=400)
        user = User.objects.filter(email=email).first()
        if user: return Response({"error": "A user with this email already exists."}, status=400)

        # Create the user, student profile, link student to tutor and update cache
        user = User.objects.create(username=email, email=email, first_name=name, role="student", password=make_password(password),)
        StudentProfile.objects.get_or_create(user=user)
        if tutor_id: TutorStudent.objects.get_or_create(tutor_id=tutor_id, student=user)
        update_student_cache(user)

        return Response(user.to_dict())

class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.all().order_by("-created_at")
    serializer_class = NoteSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(author=user)

class BookingWeeklyViewSet(viewsets.ModelViewSet):
    queryset = BookingWeekly.objects.all()
    serializer_class = BookingWeeklySerializer

    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        booking = self.get_object()
        booking.skip()
        invalidate_weekly_slots(booking.tutor.id)
        return Response({
            "ok": True,
            "id": booking.id,
        })

    @action(detail=True, methods=["post"])
    def remove_skip(self, request, pk=None):
        booking = self.get_object()
        booking.remove_skip()
        invalidate_weekly_slots(booking.tutor.id)
        return Response({
            "ok": True,
            "id": booking.id,
        })


class BookingAdhocViewSet(viewsets.ModelViewSet):
    queryset = BookingAdhoc.objects.all()
    serializer_class = BookingAdhocSerializer

    def create(self, request, *args, **kwargs):
        print("BookingAdhoc api - create")
        student_id = request.data.get("student_id")
        start_str = request.data.get("start")
        if start_str.endswith("Z"): start_str = start_str.replace("Z", "+00:00")

        if not student_id or not start_str:
            print("Adhoc create", student_id, start_str)
            return Response({"error": "student_id and start are required"}, status=400)

        try:
            start_dt = datetime.fromisoformat(start_str)
            start_dt = timezone.localtime(start_dt, local_tz)

        except ValueError:
            print("Adhoc create - datestring:", start_str)
            return Response({"error": "Invalid datetime format"}, status=400)

        student = User.objects.get(id=student_id)

        try:
            booking = student.replace_this_weeks_adhoc(start_dt)

        except ValueError as e:
            print("Adhoc create - Booking error", str(e))
            return Response({"error": str(e)}, status=400)

        serializer = self.get_serializer(booking)
        return Response(serializer.data, status=201)

    def destroy(self, request, *args, **kwargs):
        booking = self.get_object()
        booking.delete()
        return Response(status=204)

    from rest_framework.decorators import action
    from rest_framework.response import Response
    from rest_framework import status

class BookingAdhocViewSet(viewsets.ModelViewSet):
    queryset = BookingAdhoc.objects.all()
    serializer_class = BookingAdhocSerializer

    @action(detail=False, methods=["post"], url_path="delete_override")
    def delete_override(self, request):
        print("Delete override")
        student_id = request.data.get("student_id")
        if not student_id:
            return Response({"error": "student_id required"}, status=400)

        student = User.objects.filter(id=student_id).first()
        if not student:
            return Response({"error": "Student not found"}, status=404)

        # Get the next ad-hoc booking (the override)
        override = student.next_ad_hoc_booking()
        if not override:
            return Response({"ok": True, "message": "No override to delete"})

        BookingAdhoc.objects.filter(id=override["id"]).delete()
        print("Deleted")

        # Invalidate caches
        tutor_id = student.get_tutor().id
        invalidate_availability_adhoc(tutor_id)
        invalidate_adhoc_bookings(tutor_id)

        return Response({"ok": True})

    @action(detail=False, methods=["post"], url_path="modify_one_week")
    def modify_one_week(self, request):
        print("Modify one week")
        student_id = request.data.get("student_id")
        start_str = request.data.get("start")

        if not student_id or not start_str:
            print("No student id or start str")
            return Response({"error": "student_id and start required"}, status=400)

        student = User.objects.filter(id=student_id).first()
        if not student:
            print("Student not found")
            return Response({"error": "Student not found"}, status=404)

        try:
            start_str = start_str.replace("Z", "+00:00")
            start_dt = datetime.fromisoformat(start_str)
            start_dt = timezone.localtime(start_dt, local_tz)

        except Exception:
            print("Invalid start datetime:", start_str)
            return Response({"error": "Invalid start datetime"}, status=400)

        # 1. Delete existing override (if any)
        override = student.next_ad_hoc_booking()
        if override:
            BookingAdhoc.objects.filter(id=override["id"]).delete()

        # 2. Create new override
        new_booking = student.booking_create_adhoc(start_dt)

        # 3. Pause weekly booking if needed
        weekly = student.next_weekly_booking()

        if weekly:
            weekly_id = weekly["id"]
            weekly = BookingWeekly.objects.get(id=weekly_id)
            weekly.skip()

        tutor_id = student.get_tutor().id
        invalidate_weekly_bookings(tutor_id)
        invalidate_adhoc_bookings(tutor_id)

        return Response({
            "ok": True,
        })

class SMSConversationViewSet(viewsets.ViewSet):

    def retrieve(self, request, pk=None):
        convo = SMSConversation.objects.get(pk=pk)
        messages = convo.messages.order_by("created_at")

        data = []
        for msg in messages:
            data.append({
                "id": msg.id,
                "direction": msg.direction,
                "body": msg.body,
                "created_at": msg.created_at,
                "sent_at": msg.sent_at,
                "delivered_at": msg.delivered_at,
                "status": msg.status,
                "phone_number": msg.phone_number,
            })

        return Response({
            "conversation_id": convo.id,
            "tutor_id": convo.tutor.id,
            "student_id": convo.student.id,
            "student_name": convo.student.get_full_name(),
            "messages": data,
        })

class PreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = UserPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPreference.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def set(self, request):
        key = request.data.get("key")
        value = request.data.get("value")

        if not key:
            return Response({"error": "Missing key"}, status=400)

        pref, _ = UserPreference.objects.update_or_create(
            user=request.user,
            key=key,
            defaults={"value": value}
        )

        return Response({"ok": True})

    @action(detail=False, methods=["get"])
    def flat(self, request):
        prefs = self.get_queryset()
        return Response({p.key: p.value for p in prefs})


class KnowledgeViewSet(viewsets.ModelViewSet):
    serializer_class = KnowledgeSerializer

    def get_queryset(self):
        qs = Knowledge.objects.prefetch_related("skills").order_by("title")
        skill_id = self.request.query_params.get("skill_id")
        if skill_id:
            qs = qs.filter(skills__id=skill_id)
        return qs

    @action(detail=False, methods=["post"])
    def preview(self, request):
        diagram_code = request.data.get("diagram", "")
        svg = ""
        error = None
        if diagram_code.strip() and diagram_code.strip().lower() != "none":
            try:
                from .diagram.engine import render_diagram_from_code
                svg = render_diagram_from_code(diagram_code)
            except Exception as e:
                error = str(e)
        return Response({"diagram_svg": svg, "error": error})

    @action(detail=False, methods=["post"])
    def generate_from_image(self, request):
        image_b64 = request.data.get("image")
        mime_type = request.data.get("mime_type", "image/png")
        additional_prompt = request.data.get("additional_prompt", "")

        if not image_b64:
            return Response({"error": "image required"}, status=400)

        try:
            from .ai import generate_knowledge_from_image
            item = generate_knowledge_from_image(image_b64, mime_type, additional_prompt)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": f"AI generation failed: {e}"}, status=500)

        return Response({
            "title": item.get("title", ""),
            "text": item.get("text", ""),
            "diagram": item.get("diagram", ""),
            "text_2": item.get("text_2", ""),
        })


@api_view(["GET"])
def editor_docs(request):
    import os
    doc_path = os.path.join(os.path.dirname(__file__), "Editor Documentation.txt")
    with open(doc_path, encoding="utf-8") as f:
        content = f.read()
    return Response({"content": content})
