"""Le bilan de saison comparé, et la passe de l'analyste (SPEC §13.4, §5.5).

L'analyste du §5.5 tourne « chaque nuit après la bascule de 4h, **et en fin de
saison** ». La passe de nuit existe déjà — bilan quotidien (§13.1) et détections
continues (§13.5). Celle-ci est l'autre : elle regarde quatre semaines d'un coup,
compare à toutes les saisons passées, et pose la question de fin de saison.

Rien n'est stocké : le bilan se recalcule depuis les faits, comme tout le reste
du système (§10). Une saison close ne bouge plus, donc le recalcul rend toujours
la même chose.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Sum

from .models import (
    Commitment,
    DayStatus,
    Project,
    RoadmapStep,
    Season,
    Session,
    Signal,
    Track,
    WeeklyReview,
)
from .rules import season_compare
from .rules.signals import SCROLL_PASSIF


def comparaison(user, season: Season) -> dict:
    """Le bloc §13.4 ajouté au bilan de fin de saison."""
    courante = _chiffres(user, season)
    passees = [
        _chiffres(user, s)
        for s in Season.objects.filter(user=user, index__lt=season.index).order_by("index")
    ]

    coupure = season_compare.rupture(_jours(user, season))
    revues = [
        r.report
        for r in WeeklyReview.objects.filter(
            user=user, week_start__gte=season.starts_on, week_start__lte=season.ends_on
        ).order_by("week_start")
    ]

    return {
        "saisons": [_ligne(c) for c in [*passees, courante]],
        "evolutions": [
            {
                "mesure": e.mesure,
                "valeur": e.valeur,
                "reference": e.reference,
                "sens": e.sens,
                "phrase": e.phrase,
            }
            for e in season_compare.comparer(courante, passees)
        ],
        "causes": season_compare.causes(revues),
        "question": season_compare.question(coupure),
        "rupture": (
            {"jour": coupure[0].isoformat(), "jours": coupure[1]} if coupure else None
        ),
        "part_du_coach": _part_du_coach(user, season),
        "premiere": not passees,
    }


def _ligne(chiffres: season_compare.Chiffres) -> dict:
    return {
        "index": chiffres.index,
        "nom": chiffres.nom,
        "heures": chiffres.heures,
        "sessions": chiffres.sessions,
        "regularite": chiffres.regularite,
        "etapes": chiffres.etapes,
        "engagements": f"{chiffres.engagements_tenus}/{chiffres.engagements_pris}",
        "fuite_minutes": chiffres.fuite_minutes,
    }


def _chiffres(user, season: Season) -> season_compare.Chiffres:
    sessions = Session.objects.filter(
        user=user,
        status=Session.DONE,
        coach_day__gte=season.starts_on,
        coach_day__lte=season.ends_on,
    ).aggregate(minutes=Sum("actual_minutes"), n=Count("id"))

    jours = (season.ends_on - season.starts_on).days + 1
    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)

    engagements = Commitment.objects.filter(
        project__user=user, week_start__gte=season.starts_on, week_start__lte=season.ends_on
    )

    return season_compare.Chiffres(
        index=season.index,
        nom=season.name,
        heures=round((sessions["minutes"] or 0) / 60, 1),
        sessions=sessions["n"] or 0,
        jours_tenus=DayStatus.objects.filter(
            user=user,
            track=atelier,
            state=DayStatus.VALIDEE,
            date__gte=season.starts_on,
            date__lte=season.ends_on,
        ).count(),
        jours=jours,
        etapes=RoadmapStep.objects.filter(
            project__user=user,
            state=RoadmapStep.DONE,
            done_at__date__gte=season.starts_on,
            done_at__date__lte=season.ends_on,
        ).count(),
        engagements_tenus=sum(1 for c in engagements if c.kept),
        engagements_pris=engagements.count(),
        fuite_minutes=Signal.objects.filter(
            user=user,
            category=SCROLL_PASSIF,
            day__gte=season.starts_on,
            day__lte=season.ends_on,
        ).aggregate(total=Sum("minutes"))["total"]
        or 0,
    )


def _jours(user, season: Season) -> list[tuple[date, bool]]:
    """Chaque jour de la saison, tenu ou non.

    Un jour **neutre** — jour off déclaré, bouclier — ne casse rien : il compte
    comme tenu. Le §4.2 en fait un état à part entière, et le §13.4 chercherait
    une rupture là où le système en a explicitement autorisé une.
    """
    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    etats = {
        s.date: s.state
        for s in DayStatus.objects.filter(
            user=user, track=atelier, date__gte=season.starts_on, date__lte=season.ends_on
        )
    }

    jours = []
    jour = season.starts_on
    while jour <= season.ends_on:
        etat = etats.get(jour)
        jours.append((jour, etat in (DayStatus.VALIDEE, DayStatus.NEUTRE)))
        jour += timedelta(days=1)
    return jours


def _part_du_coach(user, season: Season) -> float:
    """La part du mois passée à développer le coach lui-même (§11.6, §13.4).

    Affichée, jamais sanctionnée tant que le projet n'est pas fini — le §11.6 en
    fait une information, et le quota reste désactivé par défaut. C'est
    exactement le genre de chiffre qu'on ne veut pas découvrir par hasard trois
    saisons plus tard.
    """
    total = Session.objects.filter(
        user=user,
        status=Session.DONE,
        coach_day__gte=season.starts_on,
        coach_day__lte=season.ends_on,
    ).aggregate(m=Sum("actual_minutes"))["m"] or 0
    if not total:
        return 0.0

    coach = Session.objects.filter(
        user=user,
        status=Session.DONE,
        project__in=Project.objects.filter(user=user, is_coach_project=True),
        coach_day__gte=season.starts_on,
        coach_day__lte=season.ends_on,
    ).aggregate(m=Sum("actual_minutes"))["m"] or 0

    return round(coach / total, 3)
