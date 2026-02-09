from django.contrib import admin
from .models import *

admin.site.register([User, ])
admin.site.register([TutorAvailability, TutorProfile, TutorStudent, StudentProfile])
admin.site.register([Skill, Template, Note])

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "tutor",
        "student",
        "start_datetime",
        "end_datetime",
        "status",
        "created_at",
        "created_by",
    )

    readonly_fields = ("created_at", "created_by")
