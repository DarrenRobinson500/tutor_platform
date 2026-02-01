from django.contrib import admin
from .models import *

admin.site.register([User, TutorAvailability])
admin.site.register(TutorProfile)
admin.site.register(TutorStudent)
admin.site.register(Appointment)

admin.site.register(Template)
admin.site.register(Skill)
