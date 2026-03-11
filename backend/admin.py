from django.contrib import admin
from .models import *

admin.site.register([User, ])
admin.site.register([BookingWeekly])
admin.site.register([TutorAvailability, TutorProfile, TutorStudent, StudentProfile])
admin.site.register([Skill, Template, Note])
admin.site.register([SMSConversation, SMSMessage, SMSSendJob])

@admin.register(GlobalSetting)
class GlobalSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value")
    search_fields = ("key",)

@admin.register(BookingAdhoc)
class BookingAdhocAdmin(admin.ModelAdmin):
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
