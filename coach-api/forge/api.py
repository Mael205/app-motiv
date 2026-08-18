"""Endpoints DRF.

L'accueil est servi par un seul appel (`/api/home`) : le client n'a aucune
décision à recomposer, il affiche ce que le serveur a décidé (SPEC §11.1).
"""

from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings

from . import (
    coaching,
    daily,
    detections,
    leak,
    links,
    progression,
    quests,
    review,
    season_flow,
    services,
    trace,
    weekly,
)
from .models import (
    ActionLink,
    FridgeIdea,
    Garde,
    Project,
    ProjectInterview,
    ProjectRepo,
    RoadmapStep,
    Routine,
    Session,
    WeeklyReport,
)
from .probeauth import ProbeTokenAuthentication
from .rules import hiatus as hiatus_rules
from .rules import signals as signal_rules
from .rules import slots as slot_rules
from .rules import timezones as timezone_rules
from .rules import verification as verification_rules
from .rules.calendar import coach_day, week_start


# Les endpoints de sonde acceptent le jeton restreint **en plus** de
# l'authentification normale : l'agent poste sans session, l'utilisateur garde
# l'accès depuis l'app.
PROBE_AUTH = [ProbeTokenAuthentication, *api_settings.DEFAULT_AUTHENTICATION_CLASSES]


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
    today = _today(request)
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
                "domain": project.domain,
                "domain_label": slot_rules.DOMAIN_LABELS.get(project.domain, project.domain),
                "verification": project.verification,
                "verification_label": verification_rules.LABELS.get(
                    project.verification, project.verification
                ),
                "repos": project.repos.count(),
                "completion": project.completion,
                "weekly_commitment": project.weekly_commitment,
                "is_coach_project": project.is_coach_project,
                "hold": services.hold_payload(request.user, project, today=today),
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
    # 30 et 35 entrent avec le plancher progressif du §4.1 : ce sont les durées
    # que le serveur propose lui-même aux rangs B et A, et les refuser ici
    # rendrait sa propre proposition impossible à démarrer.
    minutes = int(request.data.get("minutes", 25))
    if minutes not in (10, 25, 30, 35, 50):
        return Response(
            {"detail": "Durées possibles : 10, 25, 30, 35 ou 50 minutes."},
            status=status.HTTP_400_BAD_REQUEST,
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
    return Response(services.complete_step(request.user, step, today=_today(request)))


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
    before = services.taken_slots(request.user)
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
            "domain": project.domain,
            "steps": project.steps.count(),
            "detail": (
                f"Projet créé sur le slot {project.slot}."
                if project.slot
                else slot_rules.refused_reason(before, project.domain) or "Projet envoyé au frigo."
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@authentication_classes(PROBE_AUTH)
@permission_classes([IsAuthenticated])
def signals(request):
    """Point d'entrée des sondes : agent PC, extension, sonde Android.

    Le corps ne transporte que des catégories, des durées et, quand la sonde
    sait la donner, la fenêtre horaire observée. Il n'existe aucun champ pour
    une URL ou un titre — c'est la garantie, pas une convention (SPEC §11.10).

    La fenêtre est facultative : une recette mobile qui dit seulement « cette
    application a été ouverte » reste utile pour marquer une journée, même si
    elle ne permet pas d'attribuer du temps à une session.
    """
    source = request.data.get("source", "")
    if source not in signal_rules.SOURCES:
        return Response(
            {"detail": f"Source inconnue. Attendues : {', '.join(signal_rules.SOURCES)}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    entries = request.data.get("entries") or []
    try:
        result = services.ingest_signals(
            request.user, source=source, entries=entries, day=_today(request)
        )
    except ValueError as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def project_repos(request, project_id: int):
    """Déclare les dépôts git d'un projet — la preuve de travail du §8.3."""
    project = Project.objects.filter(user=request.user, id=project_id).first()
    if not project:
        return Response({"detail": "Projet introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "POST":
        path = (request.data.get("path") or "").strip()
        if not path:
            return Response({"detail": "Chemin du dépôt manquant."}, status=status.HTTP_400_BAD_REQUEST)
        repo, _ = ProjectRepo.objects.get_or_create(
            project=project, path=path, defaults={"remote": request.data.get("remote", "")}
        )
        return Response({"id": repo.id, "path": repo.path}, status=status.HTTP_201_CREATED)

    return Response(
        [{"id": r.id, "path": r.path, "remote": r.remote} for r in project.repos.all()]
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def session_evidence(request, session_id: int):
    """Ce que les dépôts montrent pendant la session. N'invalide rien (SPEC §6)."""
    session = Session.objects.filter(user=request.user, id=session_id).first()
    if not session:
        return Response({"detail": "Session introuvable."}, status=status.HTTP_404_NOT_FOUND)
    return Response(services.session_evidence(session))


@api_view(["GET"])
@authentication_classes(PROBE_AUTH)
@permission_classes([IsAuthenticated])
def agent_state(request):
    """Le strict nécessaire à l'agent local (SPEC §8).

    Lisible avec un jeton de sonde, donc volontairement pauvre : ni historique,
    ni gardes, ni journal. Le serveur donne le **nom** du projet en cours ;
    l'agent retrouve quoi lancer dans sa propre liste blanche. Le serveur ne
    transmet jamais de commande — même une réponse de modèle compromise ne peut
    faire exécuter que ce que l'utilisateur a lui-même autorisé.
    """
    return Response(services.agent_state(request.user))


@api_view(["POST"])
@authentication_classes(PROBE_AUTH)
@permission_classes([IsAuthenticated])
def agent_ghost(request):
    """L'agent signale une session sans activité ; le serveur décide (SPEC §8.7).

    L'agent rapporte ce qu'il a mesuré, jamais ce qu'il conclut : c'est le
    serveur qui vérifie le dépassement et l'inactivité. Un agent bavard ou
    compromis ne peut donc pas fermer une session en cours.
    """
    session = Session.objects.filter(
        user=request.user, id=request.data.get("session_id"), status=Session.RUNNING
    ).first()
    if not session:
        return Response({"closed": False, "reason": "aucune session en cours avec cet identifiant"})

    brut = request.data.get("last_active_at")
    last_active = parse_datetime(brut) if brut else None
    return Response(services.close_ghost_session(session, last_active_at=last_active))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gardes(request):
    """L'état des gardes du jour (SPEC §11.10)."""
    return Response(services.gardes_panel(request.user, today=_today(request)))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def declare_garde(request, garde_id: int):
    """Déclare la journée en cours pour une garde : tenue, ou marquée.

    Comme pour une session, la journée n'est jamais fournie par le client : on
    déclare aujourd'hui, pas hier (SPEC §17).
    """
    garde = Garde.objects.filter(user=request.user, id=garde_id, active=True).first()
    if not garde:
        return Response({"detail": "Garde introuvable."}, status=status.HTTP_404_NOT_FOUND)

    occurred = bool(request.data.get("occurred", False))
    return Response(services.declare_garde(garde, day=_today(request), occurred=occurred))


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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def weekly_review(request):
    """La revue du dimanche (SPEC §5.3, §13.3).

    ``GET`` ouvre la revue de la semaine si elle n'existe pas — les questions
    sont calculées à ce moment-là, à partir des constats du §13.5. ``POST`` la
    clôt et écrit le compte-rendu, avec ou sans réponses.
    """
    if request.method == "POST":
        revue = review.clore(review.ouvrir(request.user))
    else:
        revue = review.ouvrir(request.user)

    return Response(_revue_payload(revue))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def weekly_review_answer(request):
    """Une réponse, deux phrases suffisent (SPEC §13.3)."""
    try:
        revue = review.repondre(
            review.ouvrir(request.user),
            index=int(request.data.get("index", -1)),
            texte=request.data.get("texte", ""),
        )
    except (ValueError, TypeError) as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_revue_payload(revue))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def weekly_review_contract(request):
    """Applique le contrat proposé. Jamais automatique (SPEC §17)."""
    revue = review.ouvrir(request.user)
    return Response({"changes": review.appliquer_contrat(revue), "revue": _revue_payload(revue)})


def _revue_payload(revue) -> dict:
    return {
        "week_start": revue.week_start.isoformat(),
        # Le seul bloc de la revue qui ne compte rien : une note d'il y a un
        # mois, telle qu'elle a été écrite (§13.3 étendu).
        "il_y_a_quatre_semaines": review.il_y_a_quatre_semaines(
            revue.user, semaine=revue.week_start
        ),
        "questions": revue.questions,
        "answered": revue.answered,
        "report": revue.report,
        "contract": revue.contract,
        "contract_applied": revue.contract_applied_at is not None,
        "closed": revue.closed_at is not None,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def daily_report(request):
    """Le bilan de la journée écoulée (SPEC §13.1).

    Recalculé à la lecture : une sonde qui remonte ses minutes en retard doit
    pouvoir corriger le tableau du matin plutôt que le laisser faux.
    """
    jour, bilan = daily.hier(request.user)
    return Response(
        {
            "jour": jour.isoformat(),
            "disponibles": bilan.disponibles,
            "travaillees": bilan.travaillees,
            "part": round(bilan.part_travaillee, 3),
            "creneau_prevu": bilan.creneau_prevu,
            "creneau_tenu": bilan.creneau_tenu,
            "repartition": [
                {"label": label, "minutes": minutes} for label, minutes in bilan.repartition
            ],
            "phrase": bilan.phrase,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def project_commitment(request, project_id: int):
    """Change l'engagement hebdomadaire d'un projet (SPEC §4.3, §5.3).

    Baisser est possible n'importe quel jour : subir une semaine qu'on sait
    intenable la fait rater, et rater un engagement coûte le rang. Monter attend
    le dimanche — une hausse prise un soir d'élan est le sur-régime du §0.2.
    """
    projet = Project.objects.filter(user=request.user, id=project_id).first()
    if not projet:
        return Response({"detail": "Projet introuvable."}, status=status.HTTP_404_NOT_FOUND)

    try:
        vise = int(request.data.get("weekly_commitment"))
    except (TypeError, ValueError):
        return Response({"detail": "Nombre de sessions attendu."}, status=status.HTTP_400_BAD_REQUEST)

    ok, motif = slot_rules.peut_changer_engagement(
        actuel=projet.weekly_commitment, vise=vise, weekday=_today(request).weekday()
    )
    if not ok:
        return Response({"detail": motif}, status=status.HTTP_409_CONFLICT)

    projet.weekly_commitment = vise
    projet.save(update_fields=["weekly_commitment"])
    return Response({"id": projet.id, "weekly_commitment": projet.weekly_commitment})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def project_hold(request, project_id: int):
    """Le projet en attente déclarée : bloqué par un tiers ou du matériel.

    ``POST`` la déclare, ``DELETE`` en sort immédiatement. L'attente fait taire
    la détection « projet mort » et lève l'engagement de la semaine, mais **ne
    libère pas le slot** — c'est ce qui la distingue du frigo.
    """
    projet = Project.objects.filter(user=request.user, id=project_id).first()
    if not projet:
        return Response({"detail": "Projet introuvable."}, status=status.HTTP_404_NOT_FOUND)

    today = _today(request)

    if request.method == "DELETE":
        sorti = services.end_hold(request.user, projet, today=today)
        return Response({"id": projet.id, "hold": None, "ended": sorti})

    try:
        debut = date.fromisoformat(request.data.get("starts_on") or today.isoformat())
        fin = date.fromisoformat(request.data["ends_on"])
    except (KeyError, TypeError, ValueError):
        return Response(
            {"detail": "Donne une date de fin (AAAA-MM-JJ)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        services.declare_hold(
            request.user,
            projet,
            starts_on=debut,
            ends_on=fin,
            reason=request.data.get("reason", ""),
            today=today,
        )
    except ValueError as error:
        return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)

    return Response(
        {"id": projet.id, "hold": services.hold_payload(request.user, projet, today=today)},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def quests_panel(request):
    """Les quêtes du jour et de la semaine (SPEC §4.4).

    Elles paient en Éclats, jamais en XP : l'XP mesure le travail réel, et une
    quête qui en donnerait ferait payer deux fois la même session.
    """
    return Response(quests.panneau(request.user, today=_today(request)))


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def veille(request):
    """Le mode veille : une pause déclarée qui n'est pas un abandon.

    ``POST`` la déclare, ``DELETE`` en sort tout de suite. Sortir est immédiat —
    une pause dont on ne peut pas sortir est une raison de plus de ne pas la
    prendre.
    """
    today = _today(request)

    if request.method == "POST":
        try:
            en_cours = services.declarer_veille(
                request.user,
                debut=date.fromisoformat(request.data["debut"]),
                fin=date.fromisoformat(request.data["fin"]),
                today=today,
                raison=request.data.get("raison", ""),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_veille_payload(en_cours, today), status=status.HTTP_201_CREATED)

    if request.method == "DELETE":
        services.terminer_veille(request.user, today=today)
        return Response({"active": False, "message": ""})

    services.synchroniser_veille(request.user, today=today)
    return Response(_veille_payload(services.veille_en_cours(request.user, today=today), today))


def _veille_payload(veille_en_cours, today: date) -> dict:
    if veille_en_cours is None:
        return {
            "active": False,
            "message": "",
            "min_jours": hiatus_rules.DUREE_MINIMALE,
            "max_jours": hiatus_rules.DUREE_MAXIMALE,
        }
    return {
        "active": True,
        "debut": veille_en_cours.starts_on.isoformat(),
        "fin": veille_en_cours.ends_on.isoformat(),
        "jours": veille_en_cours.days,
        "raison": veille_en_cours.reason,
        "message": hiatus_rules.message(veille_en_cours.starts_on, veille_en_cours.ends_on),
        "min_jours": hiatus_rules.DUREE_MINIMALE,
        "max_jours": hiatus_rules.DUREE_MAXIMALE,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trace_longue(request):
    """Les compteurs qui ne redescendent jamais.

    À consulter le soir où le streak vient de casser — c'est-à-dire le seul
    soir où tous les autres chiffres de l'app disent zéro.

    **Volontairement hors de la vitrine fermée du §14.** La vitrine ferme les
    *récompenses* : le loot, les reliques, l'équipement. On ne consulte pas ses
    trophées un soir où l'on n'a rien fait, et c'est juste. La trace n'est pas
    une récompense, c'est le relevé du travail déjà accompli — le fermer
    reviendrait à sanctionner quelqu'un en lui retirant des faits, ce que le
    §17 n'autorise nulle part.
    """
    return Response(trace.longue(request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leak_report(request):
    """Le rapport de fuite de temps (SPEC §13.2).

    Strictement local : ces chiffres ne partent jamais dans le bilan de l'ami,
    ni dans un export, ni dans une notification lisible sur écran verrouillé.
    """
    return Response(leak.rapport(request.user, today=_today(request)))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def detections_view(request):
    """Les constats du §13.5, déjà faits, dans l'ordre où ils comptent.

    Ils ne décident rien : chacun porte une proposition, et la proposition
    attend un geste. Le §17 interdit qu'un système retire un projet ou baisse un
    engagement de lui-même.
    """
    return Response(
        [
            {
                "kind": d.kind,
                "constat": d.constat,
                "proposition": d.proposition,
                "donnees": d.donnees,
            }
            for d in detections.toutes(request.user, today=_today(request))
        ]
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def weekly_reports(request):
    """Ce qui est parti à l'ami, et ce qu'il en a fait (SPEC §4.7).

    L'utilisateur doit pouvoir relire **mot pour mot** ce qui a été envoyé en
    son nom. Un bilan recalculé à l'affichage ne dirait pas ce que l'ami a lu,
    et c'est justement la question au bout de trois semaines sans lecture.
    """
    profile = request.user.profile
    rapports = WeeklyReport.objects.filter(user=request.user)[:12]
    demande = profile.buddy_disable_requested_at

    return Response(
        {
            "actif": weekly.destinataire_actif(profile),
            "destinataire_configure": bool(profile.buddy_channel),
            "desactivation_demandee_le": demande.isoformat() if demande else None,
            "desactivation_effective_le": (
                (demande + weekly.DELAI_DESARMEMENT).isoformat() if demande else None
            ),
            "non_lus": weekly.non_lus(request.user),
            "seuil_non_lus": weekly.SEUIL_NON_LUS,
            # Le constat des trois semaines sans lecture était déjà là ; ce qui
            # manquait était la suite. Un constat sans suite s'ignore (§4.7).
            "remplacement": weekly.proposition_de_remplacement(request.user),
            "rapports": [
                {
                    "week_start": r.week_start.isoformat(),
                    "body": r.body,
                    "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                    "read_at": r.read_at.isoformat() if r.read_at else None,
                }
                for r in rapports
            ],
        }
    )


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def weekly_disable(request):
    """Demande — ou annule — l'arrêt du bilan (SPEC §4.7).

    ``POST`` enregistre la demande, qui ne prend effet que 24 heures plus tard.
    ``DELETE`` l'annule, et prend effet tout de suite : seul l'arrêt coûte du
    temps. C'est le seul mécanisme volontairement difficile à désarmer du
    produit, et le délai est tout ce qui le rend difficile.
    """
    profile = request.user.profile

    if request.method == "DELETE":
        weekly.annuler_desactivation(profile)
        return Response({"actif": weekly.destinataire_actif(profile), "effective_le": None})

    effective = weekly.demander_desactivation(profile)
    return Response(
        {
            "actif": weekly.destinataire_actif(profile),
            "effective_le": effective.isoformat(),
            "detail": "Le bilan continue de partir jusque-là. Annulable à tout moment.",
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def weekly_buddy(request):
    """Change le destinataire du bilan. Immédiat (SPEC §4.7 étendu).

    Remplacer n'est pas arrêter : le bilan continue de partir, à quelqu'un
    d'autre. Faire payer les vingt-quatre heures du désarmement au geste qui
    sauve le mécanisme reviendrait à le décourager — et un contrôleur qui ne
    regarde plus est pire que pas de contrôleur, puisqu'on se croit surveillé.
    """
    try:
        canal = weekly.remplacer_destinataire(
            request.user.profile, request.data.get("channel", "")
        )
    except ValueError as error:
        return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)

    return Response(
        {
            "channel": canal,
            "actif": weekly.destinataire_actif(request.user.profile),
            "detail": "Le précédent destinataire a été prévenu.",
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def timezone_check(request):
    """Détecte un écart de fuseau, et ne bascule que sur demande.

    ``GET ?tz=Europe/Lisbon`` constate. ``POST {"tz": …}`` applique. Voyager
    casse la fenêtre du soir et la bascule de 4h **en silence** : on lit des
    chiffres faux en les croyant justes. Mais une escale de trois heures n'est
    pas un déménagement, et le §11.1 n'autorise le système à décider que de ce
    qu'on fait maintenant — pas du fuseau.
    """
    profile = request.user.profile
    detecte = (request.query_params.get("tz") or request.data.get("tz") or "").strip()
    proposition = timezone_rules.proposer(
        profile.timezone_name, detecte, at=timezone.now()
    )

    if request.method == "POST":
        if not proposition.valide:
            return Response(
                {"detail": proposition.line or "Rien à basculer."},
                status=status.HTTP_409_CONFLICT,
            )
        profile.timezone_name = proposition.detecte
        profile.save(update_fields=["timezone_name"])
        return Response({"timezone": profile.timezone_name, "switched": True})

    return Response(
        {
            "timezone": profile.timezone_name,
            "detected": proposition.detecte,
            "offset_minutes": proposition.ecart_minutes,
            "proposed": proposition.valide,
            "line": proposition.line,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def issue_link(request):
    """Émet un lien signé et rend son adresse (SPEC §11.7).

    Le secret n'existe qu'ici : ensuite, seule son empreinte est stockée. Un
    lien de frigo se met en raccourci sur l'écran d'accueil du téléphone, et
    devient la capture d'idée en une phrase que le §11.7 attendait du bot.
    """
    kind = request.data.get("kind", "")
    if kind not in dict(ActionLink.KINDS):
        return Response({"detail": "Type de lien inconnu."}, status=status.HTTP_400_BAD_REQUEST)

    lien, secret = links.emettre(request.user, kind=kind, context=request.data.get("context") or {})
    return Response(
        {
            "id": lien.id,
            "kind": lien.kind,
            "url": request.build_absolute_uri(f"/l/{secret}"),
            "expires_at": lien.expires_at.isoformat() if lien.expires_at else None,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def action_link(request, token: str):
    """La seule porte d'entrée sans compte du produit (SPEC §11.7, §4.7).

    Sans authentification, volontairement : l'ami du §4.7 n'a aucune raison de
    créer un compte pour cliquer « vu » une fois par semaine. Le lien **est**
    le secret, il ne donne accès qu'à son propre geste, et il ne lit rien.
    """
    lien = links.resoudre(token)
    if lien is None:
        return Response({"detail": "Lien inconnu."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(links.presenter(lien))

    resultat = links.consommer(lien, texte=request.data.get("texte", ""))
    code = status.HTTP_200_OK if resultat["ok"] else status.HTTP_400_BAD_REQUEST
    return Response(resultat, status=code)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_relax(request):
    """Le sas de détente : 30 minutes sans jugement, une fois par soir."""
    from django.conf import settings

    from .models import RelaxWindow

    profile = request.user.profile
    now = timezone.now()
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    if services.sanctions_for(request.user, today=today).relax_revoked:
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


# --------------------------------------------------------------------------
# L'assistant (SPEC §5.1, §5.2)
# --------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def briefing(request):
    """Ce qu'on fait maintenant, décidé par le modèle quand il est là.

    Ne rend jamais d'erreur pour une raison d'IA : une panne de modèle produit
    la proposition déterministe et un ``ai_note`` qui dit pourquoi. Un 503 ici
    fermerait l'app un soir où elle sert.
    """
    result = coaching.briefing(request.user)
    if result is None:
        return Response(
            {"detail": "Aucun projet actif à proposer."}, status=status.HTTP_404_NOT_FOUND
        )
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def debrief(request, session_id: int):
    """Structure des notes brutes en suggestion d'amorce. **N'écrit rien.**

    La clôture reste `/end`, et l'amorce reste saisie par l'utilisateur : ce
    qui sort d'ici est un brouillon à valider, pas une décision (SPEC §11.3).
    """
    session = Session.objects.filter(user=request.user, id=session_id).first()
    if not session:
        return Response({"detail": "Session inconnue."}, status=status.HTTP_404_NOT_FOUND)

    return Response(coaching.debrief(session, note=request.data.get("note", "")))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def interview_start(request):
    """Ouvre un entretien de projet et pose la première question (§4.5)."""
    try:
        return Response(coaching.interview_start(request.user), status=status.HTTP_201_CREATED)
    except coaching.InterviewUnavailable as error:
        # 503 et non 500 : ce n'est pas un bug, c'est un service absent, et le
        # client doit pouvoir proposer le collage de markdown à la place.
        return Response(
            {"detail": str(error), "fallback": "markdown"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def interview(request, interview_id: int):
    """GET relit l'entretien, POST y répond et rend le tour suivant."""
    entretien = ProjectInterview.objects.filter(user=request.user, id=interview_id).first()
    if not entretien:
        return Response({"detail": "Entretien inconnu."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(coaching._payload(entretien))

    try:
        return Response(coaching.interview_reply(entretien, answer=request.data.get("answer", "")))
    except ValueError as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
    except coaching.InterviewUnavailable as error:
        return Response(
            {"detail": str(error), "fallback": "markdown"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def interview_import(request, interview_id: int):
    """Crée le projet depuis la roadmap proposée, après confirmation à l'écran."""
    entretien = ProjectInterview.objects.filter(user=request.user, id=interview_id).first()
    if not entretien:
        return Response({"detail": "Entretien inconnu."}, status=status.HTTP_404_NOT_FOUND)

    try:
        projet = coaching.interview_import(entretien)
    except ValueError as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {"id": projet.id, "name": projet.name, "slot": projet.slot, "status": projet.status},
        status=status.HTTP_201_CREATED,
    )


# --------------------------------------------------------------------------
# Le jeu : arbre, loot, reliques, chaleur (SPEC §12)
# --------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def progression_panel(request):
    """Tout l'écran « Personnage » en un appel.

    Un seul aller-retour parce que ces quatre panneaux s'affichent ensemble et
    qu'aucun n'a de sens seul : la chaleur explique l'XP, l'arbre explique où
    sont passées les heures, les reliques expliquent les bonus.
    """
    user = request.user
    today = _today(request)

    # Vitrine fermée (§14, palier 1). Le refus est explicite et daté de la
    # prochaine session : un écran vide se lit comme une panne, et une sanction
    # qu'on prend pour un bug ne sanctionne rien.
    if services.sanctions_for(user, today=today).showcase_locked:
        return Response(
            {
                "showcase_locked": True,
                "detail": "Vitrine fermée jusqu'à la prochaine session. "
                "Dix minutes suffisent à la rouvrir.",
            },
            status=status.HTTP_423_LOCKED,
        )

    # La clôture de semaine est idempotente : l'appeler à l'ouverture garantit
    # que les cartes tombent même si le déclencheur nocturne n'a pas tourné.
    ferme = progression.close_week(user, week=week_start(today) - timedelta(days=7))

    return Response(
        {
            "showcase_locked": False,
            "skills": progression.skill_tree(user),
            "momentum": progression.heat(user, today=today),
            "relics": progression.relic_panel(user),
            "collection": progression.collection(user),
            "pending_cards": ferme["drawn"],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def equip_card(request, key: str):
    try:
        return Response({"equipped": progression.equip_card(request.user, key)})
    except ValueError as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def toggle_relic(request, key: str):
    try:
        return Response(progression.toggle_relic(request.user, key))
    except ValueError as error:
        # Le motif du plafond est écrit pour être affiché tel quel : un refus
        # muet dans une interface de jeu se lit comme un bug (§12.8).
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)


# --------------------------------------------------------------------------
# Le cycle de saison (SPEC §12.2, §7.4)
# --------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def season_state(request):
    """Où en est la saison : à clore, à ouvrir, ou en cours.

    Un seul appel parce que le client n'a pas à recomposer cette décision. Une
    saison finie pendant qu'on ne regardait pas doit se conclure au moment où
    l'on revient, pas rester en suspens.
    """
    today = _today(request)
    a_clore = season_flow.pending_close(request.user, today=today)
    courante = services.current_season(request.user, today=today)

    return Response(
        {
            "pending_close": bool(a_clore),
            "running": bool(courante and not a_clore),
            # Proposée, jamais appliquée : la clôture anticipée du §14 demande
            # un geste, sinon c'est l'app qui déclare l'abandon.
            "exit_offer": season_flow.exit_offer(request.user, today=today),
            "offer": None if courante and not a_clore else season_flow.next_offer(request.user, today=today),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def close_season(request):
    """Clôt la saison finie et rend son bilan. Idempotent.

    ``early`` clôt une saison **en cours** au titre du §14 : au-delà de cinq
    jours d'arrêt, repartir à neuf vaut mieux que traîner vingt jours de retard
    impossible à rattraper. Le drapeau est explicite parce que ce chemin perd
    la mise, et qu'on ne l'emprunte jamais par inadvertance.
    """
    today = _today(request)
    saison = season_flow.pending_close(request.user, today=today)

    if saison is None and request.data.get("early"):
        if season_flow.exit_offer(request.user, today=today) is None:
            return Response(
                {"detail": "La clôture anticipée n'est pas ouverte."},
                status=status.HTTP_403_FORBIDDEN,
            )
        saison = services.current_season(request.user, today=today)

    if saison is None:
        return Response(
            {"detail": "Aucune saison à clore."}, status=status.HTTP_400_BAD_REQUEST
        )

    bilan = season_flow.close_season(request.user, saison, today=today)
    bilan["offer"] = season_flow.next_offer(request.user, today=today)
    return Response(bilan)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def open_season(request):
    """Ouvre la saison suivante avec le modificateur et le fantôme choisis."""
    if services.current_season(request.user, today=_today(request)):
        return Response(
            {"detail": "Une saison est déjà en cours."}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        saison = season_flow.open_next(
            request.user,
            today=_today(request),
            modifier_key=request.data.get("modifier", ""),
            phantom_choice=request.data.get("phantom", "meilleure"),
            stake=max(0, int(request.data.get("stake", 0) or 0)),
            # Le contrat est facultatif : refuser d'ouvrir tant que personne
            # n'a signé transformerait le rituel en formulaire, et un
            # formulaire se remplit sans le lire.
            contract_sessions_per_week=max(0, int(request.data.get("contract", 0) or 0)),
        )
    except (ValueError, TypeError) as error:
        return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "index": saison.index,
            "name": saison.name,
            "accent": saison.accent,
            "baseline": saison.baseline,
            "modifier": progression.season_modifier(saison),
            "boss": services.boss_payload(saison),
            "stake": saison.stake_shards,
            "contract": {
                "sessions_per_week": saison.contract_sessions_per_week,
                "projects": saison.contract_projects,
                "signed": saison.signed,
            },
            "ends_on": saison.ends_on.isoformat(),
        },
        status=status.HTTP_201_CREATED,
    )
