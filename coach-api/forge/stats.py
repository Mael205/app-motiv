"""Les statistiques longues (SPEC §16, jalon J6).

**Ce que ce module est, et ce qu'il n'est pas.** Il ne sert pas à décider —
l'accueil décide, avec une seule proposition (§11.1). Il ne sert pas non plus à
consoler un soir de streak cassé : c'est le rôle de ``trace.longue``, qui ne
rend que des compteurs incapables de baisser. Celui-ci rend des **séries**, donc
des courbes qui montent et qui descendent, et il faut le dire : on ne l'ouvre
pas un mauvais soir.

Il répond à une question que rien d'autre ne pouvait traiter : *à quoi
ressemblent mes trois derniers mois ?* Le bilan quotidien ne connaît qu'un jour,
la revue qu'une semaine, la saison que vingt-huit jours. Un rythme se voit sur
plus long — quel soir de la semaine tient réellement, quel projet a mangé le
trimestre, à quelle heure les séances démarrent pour de bon.

**Aucune ligne ne commente.** Le §17 interdit le jugement, et c'est ici qu'il
reviendrait le plus facilement : « ton lundi est ton pire jour » est un
reproche, alors que « lundi : 40 min sur douze semaines » est un fait. La
différence n'est pas de politesse — un fait se regarde, un reproche se ferme.
"""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Avg, Count, Max, Sum

from .models import Profile, RoadmapStep, Session
from .rules.calendar import week_start

# Douze semaines : un trimestre. Assez long pour qu'un rythme se distingue d'une
# bonne semaine, assez court pour que ce soit encore la même vie — au-delà, on
# regarde quelqu'un d'autre, et c'est déjà ce que fait le rappel des quatre
# semaines de la revue.
SEMAINES = 12

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def longues(user, *, today: date, semaines: int = SEMAINES) -> dict:
    """Les séries des dernières semaines. Des nombres, aucune phrase."""
    debut = week_start(today) - timedelta(weeks=semaines - 1)
    faites = Session.objects.filter(
        user=user, status=Session.DONE, coach_day__gte=debut, coach_day__lte=today
    )

    return {
        "depuis": debut.isoformat(),
        "semaines": _par_semaine(faites, debut=debut, semaines=semaines),
        "jours": _par_jour_de_semaine(faites),
        "projets": _par_projet(faites),
        "heures": _par_heure_de_demarrage(faites, user),
        "seances": _forme_des_seances(faites),
        "etapes": _etapes_par_semaine(user, debut=debut),
    }


def _par_semaine(faites, *, debut: date, semaines: int) -> list[dict]:
    """Minutes par semaine, **sans trou**.

    Les semaines vides sont construites explicitement : une série qui saute les
    semaines à zéro dessine une ligne continue là où il y a eu un arrêt, ce qui
    est exactement l'information qu'on vient chercher.
    """
    par_jour = {
        ligne["coach_day"]: (ligne["minutes"] or 0, ligne["n"])
        for ligne in faites.values("coach_day").annotate(minutes=Sum("actual_minutes"), n=Count("id"))
    }

    series: list[dict] = []
    for rang in range(semaines):
        lundi = debut + timedelta(weeks=rang)
        jours = [lundi + timedelta(days=i) for i in range(7)]
        minutes = sum(par_jour.get(j, (0, 0))[0] for j in jours)
        sessions = sum(par_jour.get(j, (0, 0))[1] for j in jours)
        series.append(
            {
                "debut": lundi.isoformat(),
                "minutes": minutes,
                "sessions": sessions,
                "jours_travailles": sum(1 for j in jours if par_jour.get(j, (0, 0))[0]),
            }
        )
    return series


def _par_jour_de_semaine(faites) -> list[dict]:
    """Le profil hebdomadaire : quel soir tient, lequel ne tient pas.

    C'est la série la plus utile du module, parce qu'elle porte sur une décision
    qu'on peut réellement prendre — déplacer un créneau. Les autres décrivent,
    celle-ci se répare.
    """
    totaux = {i: {"minutes": 0, "sessions": 0, "jours": set()} for i in range(7)}
    for session in faites.values("coach_day").annotate(minutes=Sum("actual_minutes"), n=Count("id")):
        jour = session["coach_day"]
        case = totaux[jour.weekday()]
        case["minutes"] += session["minutes"] or 0
        case["sessions"] += session["n"]
        case["jours"].add(jour)

    return [
        {
            "index": i,
            "label": JOURS[i],
            "minutes": totaux[i]["minutes"],
            "sessions": totaux[i]["sessions"],
            "jours_tenus": len(totaux[i]["jours"]),
        }
        for i in range(7)
    ]


def _par_projet(faites) -> list[dict]:
    lignes = faites.values("project__name", "project__color").annotate(
        minutes=Sum("actual_minutes"), sessions=Count("id")
    )
    return sorted(
        (
            {
                "nom": ligne["project__name"],
                "couleur": ligne["project__color"],
                "minutes": ligne["minutes"] or 0,
                "sessions": ligne["sessions"],
            }
            for ligne in lignes
        ),
        key=lambda ligne: -ligne["minutes"],
    )


def _par_heure_de_demarrage(faites, user) -> list[dict]:
    """À quelle heure les séances démarrent vraiment, par tranche horaire.

    Lu en heure locale et non en UTC : une séance de 21h à Paris est à 19h en
    UTC, et un histogramme d'heures de travail décalé de deux crans ne veut
    rien dire. C'est la même raison qu'au §1 pour la bascule de journée.
    """
    profile: Profile = user.profile
    zone = ZoneInfo(profile.timezone_name)

    tranches = {heure: 0 for heure in range(24)}
    for started_at, minutes in faites.values_list("started_at", "actual_minutes"):
        tranches[started_at.astimezone(zone).hour] += minutes or 0

    return [
        {"heure": heure, "minutes": minutes}
        for heure, minutes in sorted(tranches.items())
        if minutes
    ]


def _forme_des_seances(faites) -> dict:
    """La durée des séances : moyenne, plus longue, et la part des longues.

    La part des longues est la seule ligne du module qui ait un rapport direct
    avec une règle : depuis le 19 août, une séance longue rapporte davantage
    qu'une courte (prime de durée). Voir ce que ça donne en vrai est le genre de
    chose qu'on ne peut pas déduire d'un total de minutes.
    """
    agregat = faites.aggregate(
        moyenne=Avg("actual_minutes"), maximum=Max("actual_minutes"), total=Count("id")
    )
    total = agregat["total"] or 0
    longues_ = faites.filter(actual_minutes__gte=45).count()
    return {
        "moyenne": round(agregat["moyenne"] or 0),
        "plus_longue": agregat["maximum"] or 0,
        "total": total,
        "longues": longues_,
        "part_longues": round(longues_ / total, 3) if total else 0.0,
    }


def _etapes_par_semaine(user, *, debut: date) -> int:
    """Combien d'étapes de roadmap ont été finies sur la période.

    Le seul compteur d'**avancement** du module : tout le reste mesure du temps,
    et le temps ne dit pas si un projet avance. Deux trimestres au même volume
    dont l'un finit douze étapes et l'autre deux ne racontent pas la même chose.
    """
    return RoadmapStep.objects.filter(
        project__user=user, state=RoadmapStep.DONE, done_at__date__gte=debut
    ).count()
