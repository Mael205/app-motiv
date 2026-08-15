"""Endpoints DRF.

L'accueil est servi par un seul appel (`/api/home`) : le client n'a aucune
décision à recomposer, il affiche ce que le serveur a décidé (SPEC §11.1).
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import FridgeIdea, Project, RoadmapStep, Routine, Session
from .rules.calendar import coach_day, week_start


def _today(request) -> date:
    """La journée du coach de l'utilisateur — jamais ``date.today()`` (SPEC §1)."""
    profile = request.user.profile
    return coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "now": timezone.now().isoformat()})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def home(request):
    return Response(services.home_state(request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def projects(request):
    payload = []
    for project in (
        Project.objects.filter(user=request.user)
        .exclude(status=Project.ARCHIVED)
        .select_related("track")
        .prefetch_related("steps")
    ):
        step = project.current_step
        payload.append(
            {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "slot": project.slot,
                "color": project.color,
                "emblem": project.emblem,
                "track": project.track.kind,
                "completion": project.completion,
                "weekly_commitment": project.weekly_commitment,
                "is_coach_project": project.is_coach_project,
                "current_step": (
                    {"id": step.id, "label": step.label, "needs_split": step.needs_split} if step else None
                ),
                "steps": [
                    {
                        "id": s.id,
                        "label": s.label,
                        "state": s.state,
                        "estimated_sessions": s.estimated_sessions,
                        "needs_split": s.needs_split,
                    }
                    for s in project.steps.all()
                ],
            }
        )
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_session(request):
    project_id = request.data.get("project_id")
    minutes = int(request.data.get("minutes", 25))
    if minutes not in (10, 25, 50):
        return Response(
            {"detail": "Durées possibles : 10, 25 ou 50 minutes."}, status=status.HTTP_400_BAD_REQUEST
        )

    project = Project.objects.filter(user=request.user, id=project_id).first()
    if not project:
        return Response({"detail": "Projet introuvable."}, status=status.HTTP_404_NOT_FOUND)

    try:
        session = services.start_session(
            request.user,
            project,
            planned_minutes=minutes,
            energy_level=request.data.get("energy_level"),
            client_uuid=request.data.get("client_uuid") or None,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

    return Response(
        {
            "id": session.id,
            "project": session.project.name,
            "color": session.project.color,
            "started_at": session.started_at.isoformat(),
            "planned_minutes": session.planned_minutes,
            "mode": session.mode,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def end_session(request, session_id: int):
    session = Session.objects.filter(user=request.user, id=session_id, status=Session.RUNNING).first()
    if not session:
        return Response({"detail": "Aucune session en cours."}, status=status.HTTP_404_NOT_FOUND)

    next_action = (request.data.get("next_action") or "").strip()
    if not next_action:
        # L'amorce est obligatoire : on paie le démarrage à froid maintenant,
        # pendant que le contexte est chaud (SPEC §11.3).
        return Response(
            {"detail": "L'amorce est obligatoire : écris la première action de la prochaine session."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = services.end_session(
        session, note=request.data.get("note", ""), next_action=next_action
    )
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def abandon_session(request, session_id: int):
    session = Session.objects.filter(user=request.user, id=session_id, status=Session.RUNNING).first()
    if not session:
        return Response({"detail": "Aucune session en cours."}, status=status.HTTP_404_NOT_FOUND)
    session.status = Session.ABANDONED
    session.ended_at = timezone.now()
    session.save(update_fields=["status", "ended_at"])
    return Response({"status": "abandonnée"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def complete_step(request, step_id: int):
    step = RoadmapStep.objects.filter(project__user=request.user, id=step_id).first()
    if not step:
        return Response({"detail": "Étape introuvable."}, status=status.HTTP_404_NOT_FOUND)
    step.state = RoadmapStep.DONE
    step.done_at = timezone.now()
    step.save(update_fields=["state", "done_at"])

    profile = request.user.profile
    today = coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour)
    season = services.current_season(request.user, today=today)
    damage = 0
    if season and hasattr(season, "boss"):
        from .rules.seasons import damage_of

        damage = damage_of(steps_done=1)
        season.boss.damage_taken += damage
        season.boss.save(update_fields=["damage_taken"])

    return Response({"id": step.id, "state": step.state, "boss_damage": damage})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_project(request):
    """Ce que l'app comprend du markdown collé. N'écrit rien (SPEC §4.5)."""
    markdown = request.data.get("markdown", "")
    if not markdown.strip():
        return Response({"detail": "Colle d'abord le markdown du projet."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(services.preview_project(markdown))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_project(request):
    """Crée le projet et sa roadmap. Au frigo si les trois slots sont pris."""
    markdown = request.data.get("markdown", "")
    try:
        project = services.create_project_from_markdown(request.user, markdown)
    except ValueError as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "id": project.id,
            "name": project.name,
            "status": project.status,
            "slot": project.slot,
            "steps": project.steps.count(),
            "detail": (
                f"Projet créé sur le slot {project.slot}."
                if project.slot
                else "Les trois slots sont pris : le projet part au frigo. L'échange se fait le dimanche."
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def routines(request):
    """Le panneau de quêtes d'entretien du jour (SPEC §11.9)."""
    return Response(services.routine_panel(request.user, today=_today(request)))


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def routine_check(request, routine_id: int):
    """Coche ou décoche une routine pour la journée en cours.

    Le jour n'est jamais fourni par le client : une coche antidatée n'existe pas,
    au même titre qu'une session saisie après coup (SPEC §17).
    """
    routine = Routine.objects.filter(user=request.user, id=routine_id, active=True).first()
    if not routine:
        return Response({"detail": "Routine introuvable."}, status=status.HTTP_404_NOT_FOUND)

    today = _today(request)
    if request.method == "DELETE":
        result = services.uncheck_routine(routine, day=today)
    else:
        result = services.check_routine(routine, day=today)

    result["panel"] = services.routine_panel(request.user, today=today)
    return Response(result)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def fridge(request):
    if request.method == "POST":
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"detail": "Texte vide."}, status=status.HTTP_400_BAD_REQUEST)
        idea = FridgeIdea.objects.create(
            user=request.user, text=text, source=request.data.get("source", "app")
        )
        return Response({"id": idea.id, "text": idea.text}, status=status.HTTP_201_CREATED)

    return Response(
        [
            {"id": i.id, "text": i.text, "created_at": i.created_at.isoformat()}
            for i in FridgeIdea.objects.filter(user=request.user, promoted_at__isnull=True)
        ]
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_relax(request):
    """Le sas de détente : 30 minutes sans jugement, une fois par soir."""
    from django.conf import settings

    from .models import RelaxWindow

    profile = request.user.profile
    now = timezone.now()
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    state = services.home_state(request.user)
    if state["streak"]["sanction_level"] >= 1 and not state["validated_today"]:
        # Le privilège de scroller avant de bosser se perd quand la soirée
        # précédente est partie en scroll (SPEC §14, palier 1).
        return Response(
            {"detail": "Sas révoqué après un jour raté. Il revient dès que la journée est validée."},
            status=status.HTTP_403_FORBIDDEN,
        )

    minutes = settings.COACH["RELAX_MINUTES"]
    window, created = RelaxWindow.objects.get_or_create(
        user=request.user,
        coach_day=today,
        defaults={"started_at": now, "ends_at": now + timedelta(minutes=minutes)},
    )
    if not created:
        left = int((window.ends_at - now).total_seconds() // 60)
        return Response(
            {
                "detail": "Sas déjà utilisé ce soir."
                + (f" Il se termine dans {left} min." if left > 0 else "")
            },
            status=status.HTTP_409_CONFLICT,
        )

    return Response(
        {"started_at": window.started_at.isoformat(), "ends_at": window.ends_at.isoformat()},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def declare_day_off(request):
    """Un jour off déclaré au moins la veille est neutre (SPEC §11.5)."""
    from django.conf import settings

    from .models import DayOff

    profile = request.user.profile
    now = timezone.now()
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    try:
        target = date.fromisoformat(request.data.get("date", ""))
    except ValueError:
        return Response({"detail": "Date invalide."}, status=status.HTTP_400_BAD_REQUEST)

    if target <= today:
        return Response(
            {
                "detail": "Un jour off se déclare au moins la veille. "
                "Aujourd'hui, c'est un jour raté normal."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    week = week_start(target)
    taken = DayOff.objects.filter(
        user=request.user, date__gte=week, date__lt=week + timedelta(days=7)
    ).count()
    if taken >= settings.COACH["MAX_DAYS_OFF_PER_WEEK"]:
        return Response(
            {"detail": f"Déjà {taken} jours off cette semaine-là. Le plafond est atteint."},
            status=status.HTTP_409_CONFLICT,
        )

    day_off, created = DayOff.objects.get_or_create(user=request.user, date=target)
    return Response(
        {
            "date": day_off.date.isoformat(),
            "created": created,
            "detail": "Jour off enregistré. Il ne consomme pas de bouclier et ne casse pas le streak, "
            "mais il remet à zéro la progression vers le prochain bouclier.",
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_push(request):
    """Enregistre un abonnement Web Push pour cet appareil."""
    from .models import Device

    subscription = request.data.get("subscription")
    if not subscription:
        return Response({"detail": "Abonnement manquant."}, status=status.HTTP_400_BAD_REQUEST)

    device, _ = Device.objects.update_or_create(
        user=request.user,
        name=request.data.get("name", "Appareil"),
        defaults={
            "kind": request.data.get("kind", Device.PHONE),
            "push_subscription": subscription,
            "last_seen_at": timezone.now(),
        },
    )
    return Response({"id": device.id, "name": device.name})


@api_view(["GET"])
@permission_classes([AllowAny])
def push_key(request):
    """Clé publique VAPID, nécessaire au client pour s'abonner."""
    from django.conf import settings

    return Response({"public_key": settings.COACH["VAPID_PUBLIC_KEY"]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def journal(request):
    from .models import JournalEntry

    entries = (
        JournalEntry.objects.filter(session__user=request.user)
        .select_related("session", "session__project")
        .order_by("-created_at")[:100]
    )
    return Response(
        [
            {
                "id": e.id,
                "project": e.session.project.name,
                "color": e.session.project.color,
                "day": e.session.coach_day.isoformat(),
                "minutes": e.session.actual_minutes,
                "note": e.raw_note,
                "next_action": e.next_action,
            }
            for e in entries
        ]
    )
