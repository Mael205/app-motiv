from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from forge import api, views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Le canal entrant (SPEC §11.7). Court à dessein : il se colle dans un
    # message, se met en raccourci sur un écran d'accueil, et se tape à la main
    # si la messagerie l'a mutilé.
    path("l/<str:token>", views.action_link_page),
    path("api/links", api.issue_link),
    path("api/weekly", api.weekly_reports),
    path("api/weekly/disable", api.weekly_disable),
    path("api/links/<str:token>", api.action_link),
    path("api/health", api.health),
    path("api/auth/token", TokenObtainPairView.as_view()),
    path("api/auth/refresh", TokenRefreshView.as_view()),
    path("api/home", api.home),
    path("api/projects", api.projects),
    path("api/briefing", api.briefing),
    path("api/progression", api.progression_panel),
    path("api/season", api.season_state),
    path("api/season/close", api.close_season),
    path("api/season/open", api.open_season),
    path("api/loot/<str:key>/equip", api.equip_card),
    path("api/relics/<str:key>/toggle", api.toggle_relic),
    path("api/sessions/<int:session_id>/debrief", api.debrief),
    path("api/sessions/start", api.start_session),
    path("api/sessions/<int:session_id>/end", api.end_session),
    path("api/sessions/<int:session_id>/abandon", api.abandon_session),
    path("api/steps/<int:step_id>/complete", api.complete_step),
    path("api/projects/preview", api.preview_project),
    path("api/interviews", api.interview_start),
    path("api/interviews/<int:interview_id>", api.interview),
    path("api/interviews/<int:interview_id>/import", api.interview_import),
    path("api/projects/import", api.import_project),
    path("api/signals", api.signals),
    path("api/agent/state", api.agent_state),
    path("api/agent/ghost", api.agent_ghost),
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
