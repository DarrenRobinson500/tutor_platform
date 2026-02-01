from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r"templates", TemplateViewSet, basename="template")
router.register(r"skills", SkillViewSet, basename="skills")
router.register(r"tutors", TutorViewSet, basename="tutor")
router.register(r"students", StudentViewSet, basename="student")


urlpatterns = router.urls

