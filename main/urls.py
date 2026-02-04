from django.urls import path, include
from django.contrib import admin
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("backend.urls")),
    path('', RedirectView.as_view(url='/index.html', permanent=False)),

]
