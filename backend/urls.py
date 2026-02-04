from rest_framework.routers import DefaultRouter
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import *

router = DefaultRouter()
router.register(r"templates", TemplateViewSet, basename="template")
router.register(r"skills", SkillViewSet, basename="skills")
router.register(r"tutors", TutorViewSet, basename="tutor")
router.register(r"students", StudentViewSet, basename="student")
router.register(r"notes", NoteViewSet, basename="note")
router.register(r"auth", AuthViewSet, basename="auth")

urlpatterns = [
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]

urlpatterns += router.urls
