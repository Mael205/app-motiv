"""Les quêtes, côté base (SPEC §4.4).

Le modèle ``Quest`` existait depuis le premier jour et n'était rempli que par le
seed. Voici ce qui les pose, mesure leur avancement et paie les Éclats.

**L'avancement se recalcule, il ne s'incrémente pas.** C'est la règle du §10 :
les états dérivés ne sont pas stockés en double, ils se relisent depuis les
faits. Une quête dont la progression serait incrémentée à chaque session
divergerait au premier bug — et une quête fausse est pire qu'une quête absente,
parce qu'on la croit.

La ligne stockée ne porte donc que la **définition** du jour : ce qui a été
demandé, combien, et pour combien d'Éclats. Le reste se compte à la lecture.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, F, Sum, Value
from django.utils import timezone

from .models import Commitment, Profile, Project, Quest, RoadmapStep, Routine, RoutineCheck, Session, Track
from .rules import quests as regles
from .rules.calendar import evening_window, week_start


def panneau(user, *, today: date) -> dict:
    """Les quêtes du jour, posées si besoin, avec leur avancement réel."""
    _poser(user, today=today)

    from django.db.models import Q

    lignes = []
    du_jour_ou_de_la_semaine = Q(date=today) & ~Q(kind=Quest.HEBDO) | Q(
        kind=Quest.HEBDO, date=week_start(today)
    )
    for quete in Quest.objects.filter(user=user).filter(du_jour_ou_de_la_semaine):
        avance = _mesurer(user, quete, today=today)
        gagnee = avance >= quete.target

        if gagnee and not quete.done_at:
            _payer(user, quete)

        lignes.append(
            {
                "kind": quete.kind,
                "label": quete.label,
                "progress": min(avance, quete.target),
                "target": quete.target,
                "done": gagnee,
                "reward_shards": quete.reward_xp,   # champ réutilisé, voir _poser
            }
        )

    ordre = {Quest.PLANCHER: 0, Quest.BONUS: 1, Quest.HEBDO: 2}
    return {"quetes": sorted(lignes, key=lambda l: ordre.get(l["kind"], 9))}


@transaction.atomic
def _poser(user, *, today: date) -> None:
    """Écrit les quêtes manquantes. Idempotent : une par jour, une par semaine."""
    contexte = _contexte(user, today=today)

    if not Quest.objects.filter(user=user, date=today).exclude(kind=Quest.HEBDO).exists():
        for quete in regles.du_jour(contexte, jour=today):
            Quest.objects.create(
                user=user,
                kind=quete.kind,
                date=today,
                label=quete.label,
                target=quete.target,
                # Le champ s'appelle ``reward_xp`` depuis le premier modèle, mais
                # une quête ne paie **jamais** en XP (§4.4) : l'XP mesure le
                # travail réel. Ce sont des Éclats, comme pour les routines.
                reward_xp=quete.reward_shards,
            )

    semaine = week_start(today)
    if not Quest.objects.filter(user=user, kind=Quest.HEBDO, date=semaine).exists():
        hebdo = regles.de_la_semaine(contexte, jour=today)
        if hebdo:
            Quest.objects.create(
                user=user,
                kind=hebdo.kind,
                date=semaine,
                label=hebdo.label,
                target=hebdo.target,
                reward_xp=hebdo.reward_shards,
            )


def _contexte(user, *, today: date) -> regles.Contexte:
    from . import services

    profile: Profile = user.profile
    fenetre = evening_window(today, profile.windows_by_weekday(), profile.timezone_name)
    semaine = week_start(today)

    faites = {
        row["project"]: row["n"]
        for row in Session.objects.filter(
            user=user, status=Session.DONE, coach_day__gte=semaine, coach_day__lte=today
        )
        .values("project")
        .annotate(n=Count("id"))
    }

    retard, pire = "", 0
    actifs = list(Project.objects.filter(user=user, status=Project.ACTIVE, track__kind=Track.ATELIER))
    for projet in actifs:
        manque = projet.weekly_commitment - faites.get(projet.id, 0)
        if manque > pire:
            retard, pire = projet.name, manque

    # « Presque finie » : l'étape courante a déjà reçu du travail. Proposer de la
    # terminer a alors un sens ; le premier soir sur une étape neuve, non.
    presque = RoadmapStep.objects.filter(
        project__user=user,
        project__status=Project.ACTIVE,
        state=RoadmapStep.DOING,
        doing_since__isnull=False,
    ).exists()

    return regles.Contexte(
        plancher_minutes=services.floor_minutes(user, today=today),
        avant_vingt_heures=fenetre.start.hour < 20,
        etape_presque_finie=presque,
        projet_en_retard=retard,
        routines_du_jour=sum(
            1
            for r in Routine.objects.filter(user=user, active=True)
            if not r.weekdays or today.weekday() in r.weekdays
        ),
        corps_actif=Project.objects.filter(
            user=user, status=Project.ACTIVE, track__kind=Track.CORPS
        ).exists(),
        engagements_pris=sum(p.weekly_commitment for p in actifs),
        jours_valides_semaine=0,
    )


def _mesurer(user, quete: Quest, *, today: date) -> int:
    """Combien de fois la condition est remplie. Recalculé, jamais incrémenté."""
    semaine = week_start(today)

    if quete.kind == Quest.HEBDO:
        if "engagement" in quete.label.lower():
            return sum(
                min(c.done_sessions, c.planned_sessions)
                for c in Commitment.objects.filter(project__user=user, week_start=semaine)
            )
        return _jours_valides(user, semaine=semaine, today=today)

    if quete.kind == Quest.PLANCHER:
        return Session.objects.filter(
            user=user, coach_day=today, status=Session.DONE
        ).count()

    label = quete.label.lower()
    if "avant 20h" in label:
        zone = user.profile.timezone_name
        from zoneinfo import ZoneInfo

        return sum(
            1
            for s in Session.objects.filter(user=user, coach_day=today, status=Session.DONE)
            if s.started_at.astimezone(ZoneInfo(zone)).hour < 20
        )
    if "étape" in label:
        return RoadmapStep.objects.filter(
            project__user=user, state=RoadmapStep.DONE, done_at__date=today
        ).count()
    if "routines" in label:
        return RoutineCheck.objects.filter(routine__user=user, day=today).count()
    if "piste corps" in label:
        return Session.objects.filter(
            user=user, coach_day=today, status=Session.DONE, project__track__kind=Track.CORPS
        ).count()

    # Quête « une session sur <projet> » : le libellé porte le nom du projet.
    return Session.objects.filter(
        user=user,
        coach_day=today,
        status=Session.DONE,
        project__name=quete.label.replace("Une session sur ", ""),
    ).count()


def _jours_valides(user, *, semaine: date, today: date) -> int:
    from .services import DEGRADED_MINUTES

    par_jour = {
        row["coach_day"]: row["m"] or 0
        for row in Session.objects.filter(
            user=user, status=Session.DONE, coach_day__gte=semaine, coach_day__lte=today
        )
        .values("coach_day")
        .annotate(m=Sum("actual_minutes"))
    }
    return sum(1 for minutes in par_jour.values() if minutes >= DEGRADED_MINUTES)


@transaction.atomic
def _payer(user, quete: Quest) -> None:
    """Crédite les Éclats une fois, et jamais deux."""
    gagnee = Quest.objects.filter(pk=quete.pk, done_at__isnull=True).update(
        done_at=timezone.now(), progress=quete.target
    )
    if gagnee and quete.reward_xp:
        Profile.objects.filter(user=user).update(shards=F("shards") + quete.reward_xp)
