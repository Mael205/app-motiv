from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from forge import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", api.health),
    path("api/auth/token", TokenObtainPairView.as_view()),
    path("api/auth/refresh", TokenRefreshView.as_view()),
    path("api/home", api.home),
    path("api/projects", api.projects),
    path("api/sessions/start", api.start_session),
    path("api/sessions/<int:session_id>/end", api.end_session),
    path("api/sessions/<int:session_id>/abandon", api.abandon_session),
    path("api/steps/<int:step_id>/complete", api.complete_step),
    path("api/fridge", api.fridge),
    path("api/journal", api.journal),
]
