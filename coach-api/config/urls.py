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
    path("api/projects/preview", api.preview_project),
    path("api/projects/import", api.import_project),
    path("api/signals", api.signals),
    path("api/projects/<int:project_id>/repos", api.project_repos),
    path("api/sessions/<int:session_id>/evidence", api.session_evidence),
    path("api/gardes", api.gardes),
    path("api/gardes/<int:garde_id>/declare", api.declare_garde),
    path("api/routines", api.routines),
    path("api/routines/<int:routine_id>/check", api.routine_check),
    path("api/fridge", api.fridge),
    path("api/journal", api.journal),
    path("api/relax/start", api.start_relax),
    path("api/days-off", api.declare_day_off),
    path("api/push/subscribe", api.register_push),
    path("api/push/key", api.push_key),
]
