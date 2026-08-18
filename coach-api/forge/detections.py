"""Ce que les sept détections du §13.5 lisent en base.

La logique est dans ``rules/derives`` — pure, testable sur des historiques
fabriqués. Ce module ne fait que sortir les chiffres et les lui donner.

**Aucune écriture, aucune décision.** Ces constats ne ferment pas un projet, ne
baissent pas un engagement et ne déclarent pas une soirée off : ils proposent,
et la proposition attend un geste. Le §17 interdit qu'un système retire quoi que
ce soit tout seul, et le §11.1 ne l'autorise à décider que de ce qu'on fait
maintenant — pas de ce à quoi on renonce.
"""

from __future__ import annotations

from datetime import date, timedelta

from zoneinfo import ZoneInfo

from django.db.models import Count, Max, Sum
from django.utils import timezone

from . import services
from .models import Commitment, Project, RoadmapStep, Session, Signal
from .rules import derives
from .rules.calendar import week_start
from .rules.signals import AGENT, EXTENSION, MOBILE, SCROLL_PASSIF

# Fenêtre de comparaison pour la migration du scroll : deux semaines pleines.
FENETRE_MIGRATION = 7


def toutes(user, *, today: date | None = None) -> list[derives.Derive]:
    """Les constats du jour, du plus urgent au moins urgent.

    L'ordre n'est pas cosmétique : c'est celui dans lequel ils seront lus, et le
    §0.9 veut qu'on n'ait pas à arbitrer. Le sur-régime passe devant tout parce
    qu'il annonce un arrêt à venir ; les propositions de ménage passent en
    dernier parce qu'elles peuvent attendre dimanche.
    """
    today = today or timezone.now().date()
    trouvees = [
        _sur_regime(user, today=today),
        _fin_de_soiree(user, today=today),
        _migration_scroll(user, today=today),
        *_engagements(user, today=today),
        *_etapes_figees(user, today=today),
        _concentration(user, today=today),
        *_projets_morts(user, today=today),
    ]
    return [d for d in trouvees if d is not None]


def _projets_morts(user, *, today: date) -> list[derives.Derive | None]:
    dernieres = {
        row["project"]: row["last"]
        for row in Session.objects.filter(user=user, status=Session.DONE)
        .values("project")
        .annotate(last=Max("coach_day"))
    }
    # Un projet en attente déclarée ne peut pas être mort : quelqu'un d'autre le
    # tient. La détection se tait pendant, et les jours d'attente sortent du
    # décompte après — sans quoi un projet bloqué quatorze jours serait déclaré
    # mort le lendemain de son déblocage, c'est-à-dire au seul moment où il
    # redevient vivant.
    en_attente = services.projects_on_hold(user, day=today)

    sortie = []
    for projet in Project.objects.filter(user=user, status=Project.ACTIVE):
        if projet.id in en_attente:
            continue
        derniere = dernieres.get(projet.id)
        debut = derniere or projet.created_at.date()
        jours = (today - debut).days
        jours -= services.hold_days_between(user, projet.id, since=debut, until=today)
        sortie.append(derives.projet_mort(projet.name, max(0, jours)))
    return sortie


def _etapes_figees(user, *, today: date) -> list[derives.Derive | None]:
    maintenant = timezone.now()
    etapes = RoadmapStep.objects.filter(
        project__user=user,
        project__status=Project.ACTIVE,
        state=RoadmapStep.DOING,
        doing_since__isnull=False,
    ).select_related("project")

    return [
        derives.etape_figee(e.project.name, e.label, (maintenant - e.doing_since).days)
        for e in etapes
    ]


def _engagements(user, *, today: date) -> list[derives.Derive | None]:
    semaine = week_start(today)
    en_attente = services.projects_on_hold(user, day=today)
    sortie = []
    for projet in Project.objects.filter(user=user, status=Project.ACTIVE).exclude(
        id__in=en_attente
    ):
        historique = [
            (c.done_sessions, c.planned_sessions)
            for c in Commitment.objects.filter(project=projet, week_start__lt=semaine)[
                : derives.SEMAINES_ENGAGEMENT
            ]
        ]
        sortie.append(derives.engagement_irrealiste(projet.name, historique))
    return sortie


def _concentration(user, *, today: date) -> derives.Derive | None:
    semaine = week_start(today)
    minutes = {
        row["project__name"]: row["minutes"] or 0
        for row in Session.objects.filter(
            user=user, status=Session.DONE, coach_day__gte=semaine, coach_day__lte=today
        )
        .values("project__name")
        .annotate(minutes=Sum("actual_minutes"))
    }
    return derives.concentration(minutes)


def _fin_de_soiree(user, *, today: date) -> derives.Derive | None:
    debut = today - timedelta(days=derives.JOURS_FIN_DE_SOIREE * 2)
    zone = ZoneInfo(user.profile.timezone_name)

    # Une seule session par jour : la première. Les suivantes décrivent l'élan
    # de la soirée, pas l'heure à laquelle on s'y met, et c'est celle-là qui
    # glisse quand le décrochage commence.
    premieres: dict[date, int] = {}
    for session in Session.objects.filter(
        user=user, status=Session.DONE, coach_day__gte=debut, coach_day__lte=today
    ).order_by("started_at"):
        if session.coach_day in premieres:
            continue
        local = session.started_at.astimezone(zone)
        premieres[session.coach_day] = local.hour * 60 + local.minute

    return derives.fin_de_soiree(sorted(premieres.items()))


def _migration_scroll(user, *, today: date) -> derives.Derive | None:
    fin_avant = today - timedelta(days=FENETRE_MIGRATION)
    debut_avant = fin_avant - timedelta(days=FENETRE_MIGRATION - 1)

    def minutes(sources: tuple[str, ...], debut: date, fin: date) -> int:
        return (
            Signal.objects.filter(
                user=user,
                source__in=sources,
                category=SCROLL_PASSIF,
                day__gte=debut,
                day__lte=fin,
            ).aggregate(total=Sum("minutes"))["total"]
            or 0
        )

    debut_apres = fin_avant + timedelta(days=1)
    # Le PC, c'est l'agent **et** l'extension : la même fuite vue par deux
    # sondes. Ne compter que l'une des deux ferait apparaître une migration à
    # chaque fois qu'un navigateur change.
    pc = (AGENT, EXTENSION)

    return derives.migration_scroll(
        mobile_avant=minutes((MOBILE,), debut_avant, fin_avant),
        mobile_apres=minutes((MOBILE,), debut_apres, today),
        pc_avant=minutes(pc, debut_avant, fin_avant),
        pc_apres=minutes(pc, debut_apres, today),
    )


def _sur_regime(user, *, today: date) -> derives.Derive | None:
    debut = today - timedelta(days=derives.JOURS_SUR_REGIME - 1)
    par_jour = {
        row["coach_day"]: row["n"]
        for row in Session.objects.filter(
            user=user, status=Session.DONE, coach_day__gte=debut, coach_day__lte=today
        )
        .values("coach_day")
        .annotate(n=Count("id"))
    }
    jours = [
        par_jour.get(debut + timedelta(days=i), 0) for i in range(derives.JOURS_SUR_REGIME)
    ]
    return derives.sur_regime(jours)
