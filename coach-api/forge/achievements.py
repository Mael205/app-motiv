"""Les faits qui décernent les hauts faits, lus en base (§12.3, §12.8).

``rules/achievements`` dit quel fait chaque haut fait regarde et à partir de
quel seuil il tombe. Ce module-ci produit les faits, et rien d'autre : aucune
condition n'est écrite ici, aucun cas particulier. C'est ce qui évite de
retomber dans la situation d'origine, où un haut fait pouvait être déclaré sans
qu'aucun code ne l'accorde jamais.

**Tous les faits se recalculent depuis l'historique.** Aucun compteur n'est
incrémenté et stocké. C'est la règle du §10 appliquée ici pour une raison
précise : un haut fait est définitif (§17 interdit de le reprendre), donc un
compteur qui dériverait le décernerait à tort — et il n'y aurait aucun moyen
propre de revenir en arrière.

Le coût est assumé : la relecture complète est lancée à la clôture d'une
session, à la fin d'une étape et à la clôture d'une saison, pas à chaque
affichage.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Max, Sum
from django.utils import timezone

from .models import (
    Achievement,
    DayOff,
    Hiatus,
    LootCard,
    Project,
    RoadmapStep,
    Season,
    Session,
    Signal,
    Track,
)
from .rules import achievements as regles
from .rules import signals as signal_rules
from .rules import streak as streak_rules
from .rules.calendar import week_start


def faits(user) -> dict[str, int]:
    """Tous les compteurs que le catalogue sait regarder."""
    faites = Session.objects.filter(user=user, status=Session.DONE)
    agregat = faites.aggregate(minutes=Sum("actual_minutes"), n=Count("id"))
    minutes = agregat["minutes"] or 0

    return {
        "sessions_terminees": agregat["n"] or 0,
        "heures_totales": minutes // 60,
        "jours_travailles": faites.values("coach_day").distinct().count(),
        "plus_longue_serie": _plus_longue_serie(user),
        "jours_sans_bouclier": _jours_sans_bouclier(user),
        "etapes_finies": RoadmapStep.objects.filter(
            project__user=user, state=RoadmapStep.DONE
        ).count(),
        "etapes_dans_une_saison": _etapes_dans_une_saison(user),
        "projets_termines": _projets_termines(user),
        "sessions_avant_20h": _sessions_avant_20h(user),
        # Relu depuis le détail gravé à la clôture, jamais recalculé : le
        # créneau a pu être déplacé depuis, et une séance tenue à l'heure dite
        # le reste même si l'heure dite a changé le mois suivant.
        "sessions_a_l_heure": faites.filter(xp_breakdown__punctual__gt=0).count(),
        "sessions_longues": faites.filter(actual_minutes__gte=50).count(),
        "semaines_sans_scroll": _semaines_sans_scroll(user),
        "branches_dans_une_semaine": _branches_dans_une_semaine(user),
        "saisons_closes": Season.objects.filter(user=user, status=Season.CLOSED).count(),
        "boss_abattus": _boss_abattus(user),
        "semaines_tenues": _semaines_tenues(user),
        "jours_off_declares": DayOff.objects.filter(user=user).count(),
        "retours_apres_arret": _retours_apres_arret(user),
        "retours_de_veille": _retours_de_veille(user),
        "cartes_possedees": LootCard.objects.filter(user=user).count(),
        "annees_accomplies": _annees_accomplies(user),
    }


def synchroniser(user) -> list[dict]:
    """Décerne ce qui est atteint et pas encore acquis. Rend les nouveaux.

    Idempotent : appelée deux fois de suite, la seconde ne rend rien. C'est ce
    qui permet de la brancher partout où un fait peut changer sans avoir à
    savoir si un autre appel l'a déjà faite.
    """
    acquis = set(Achievement.objects.filter(user=user).values_list("key", flat=True))
    nouveaux = []

    for haut_fait in regles.atteints(faits(user)):
        if haut_fait.key in acquis:
            continue
        _, cree = Achievement.objects.get_or_create(
            user=user,
            key=haut_fait.key,
            defaults={"label": haut_fait.label, "description": haut_fait.description},
        )
        if cree:
            nouveaux.append(
                {
                    "key": haut_fait.key,
                    "label": haut_fait.label,
                    "description": haut_fait.description,
                    "registre": haut_fait.registre,
                }
            )
    return nouveaux


def panneau(user) -> dict:
    """Ce que l'écran affiche : l'acquis, et les trois plus proches."""
    acquis = {
        a.key: a for a in Achievement.objects.filter(user=user).order_by("-unlocked_at")
    }
    mesures = faits(user)

    return {
        "obtenus": [
            {
                "key": cle,
                "label": acquis[cle].label,
                "description": acquis[cle].description,
                "registre": regles.PAR_CLE[cle].registre if cle in regles.PAR_CLE else "travail",
                "at": acquis[cle].unlocked_at.isoformat(),
            }
            for cle in acquis
        ],
        "total": len(regles.CATALOGUE),
        "prochains": regles.prochain(mesures, acquis=set(acquis), combien=3),
    }


# --------------------------------------------------------------------------
# Les faits qui demandent plus qu'un compte
# --------------------------------------------------------------------------

def _plus_longue_serie(user) -> int:
    """La plus longue suite de journées travaillées, jamais.

    Le fait brut, sans boucliers ni jours off : c'est un record, pas un état de
    streak. Même calcul que la trace longue, et pour la même raison — un
    compteur de record ne doit dépendre d'aucune règle qui pourrait changer.
    """
    jours = sorted(
        set(
            Session.objects.filter(user=user, status=Session.DONE).values_list(
                "coach_day", flat=True
            )
        )
    )
    if not jours:
        return 0

    meilleur = courant = 1
    for precedent, suivant in zip(jours, jours[1:]):
        courant = courant + 1 if (suivant - precedent).days == 1 else 1
        meilleur = max(meilleur, courant)
    return meilleur


def _jours_sans_bouclier(user) -> int:
    """Le plus long intervalle entre deux boucliers consommés.

    Compté depuis la première journée travaillée, pas depuis l'inscription :
    quelqu'un qui installe l'app et ne l'ouvre pas pendant un mois n'a pas tenu
    vingt-huit jours sans bouclier, il n'a rien tenu du tout.
    """
    from . import services

    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    debut = (
        Session.objects.filter(user=user, status=Session.DONE)
        .order_by("coach_day")
        .values_list("coach_day", flat=True)
        .first()
    )
    if debut is None:
        return 0

    aujourdhui = timezone.localdate()
    historique = services.resolve_days(user, atelier, until=aujourdhui)
    etat = streak_rules.evaluate(historique)

    consommations = sorted(
        e.date for e in etat.events if e.kind == "bouclier_consomme"
    )

    bornes = [debut, *consommations, aujourdhui]
    return max(
        ((suivant - precedent).days for precedent, suivant in zip(bornes, bornes[1:])),
        default=0,
    )


def _etapes_dans_une_saison(user) -> int:
    """Le maximum d'étapes terminées à l'intérieur d'une même saison."""
    maxi = 0
    for saison in Season.objects.filter(user=user):
        compte = RoadmapStep.objects.filter(
            project__user=user,
            state=RoadmapStep.DONE,
            done_at__date__gte=saison.starts_on,
            done_at__date__lte=saison.ends_on,
        ).count()
        maxi = max(maxi, compte)
    return maxi


def _projets_termines(user) -> int:
    """Les projets dont toutes les étapes sont faites, et qui en avaient.

    Un projet sans étape n'est pas terminé : il est vide. La nuance a son
    importance ici, où trois roadmaps vides donneraient « Maître d'œuvre ».
    """
    compte = 0
    for projet in Project.objects.filter(user=user).prefetch_related("steps"):
        etapes = list(projet.steps.all())
        if etapes and all(e.state == RoadmapStep.DONE for e in etapes):
            compte += 1
    return compte


def _sessions_avant_20h(user) -> int:
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(user.profile.timezone_name)
    return sum(
        1
        for debut in Session.objects.filter(user=user, status=Session.DONE).values_list(
            "started_at", flat=True
        )
        if debut.astimezone(zone).hour < 20
    )


def _semaines_sans_scroll(user) -> int:
    """Les semaines pleines sans une minute de scroll passif détecté.

    **Seules les semaines réellement observées comptent.** Une semaine sans
    aucun signal d'aucune sorte n'est pas une semaine sans scroll : c'est une
    semaine où la sonde ne tournait pas, et le §11.10 interdit de conclure du
    silence d'une sonde. Sans cette précaution, désinstaller l'agent
    décernerait « Ermite ».
    """
    signaux = Signal.objects.filter(user=user).values_list("day", "category", "minutes")
    par_semaine: dict[date, dict[str, int]] = {}
    for jour, categorie, minutes in signaux:
        semaine = par_semaine.setdefault(week_start(jour), {})
        semaine[categorie] = semaine.get(categorie, 0) + (minutes or 0)

    aujourdhui = timezone.localdate()
    return sum(
        1
        for debut, categories in par_semaine.items()
        if debut + timedelta(days=6) < aujourdhui        # semaine finie
        and sum(categories.values()) > 0                  # sonde active
        and categories.get(signal_rules.SCROLL_PASSIF, 0) == 0
    )


def _branches_dans_une_semaine(user) -> int:
    """Le maximum de branches distinctes nourries dans une même semaine."""
    par_semaine: dict[date, set[str]] = {}
    for jour, branche in (
        Session.objects.filter(user=user, status=Session.DONE)
        .exclude(project__branch="")
        .values_list("coach_day", "project__branch")
    ):
        par_semaine.setdefault(week_start(jour), set()).add(branche)
    return max((len(b) for b in par_semaine.values()), default=0)


def _boss_abattus(user) -> int:
    return sum(
        1
        for saison in Season.objects.filter(user=user).select_related("boss")
        if hasattr(saison, "boss") and saison.boss.is_dead
    )


def _semaines_tenues(user) -> int:
    from . import services

    return services.rank_state(user, today=timezone.localdate())["weeks_kept"]


def _retours_apres_arret(user) -> int:
    """Combien de fois le travail a repris après trois jours d'arrêt ou plus."""
    jours = sorted(
        set(
            Session.objects.filter(user=user, status=Session.DONE).values_list(
                "coach_day", flat=True
            )
        )
    )
    return sum(
        1
        for precedent, suivant in zip(jours, jours[1:])
        if (suivant - precedent).days > streak_rules.COMEBACK_MISSED_THRESHOLD
    )


def _retours_de_veille(user) -> int:
    """Sortir d'une veille et travailler le jour même.

    Le haut fait le plus discret du lot, et celui qui décrit le mieux ce que le
    produit essaie d'obtenir : la reprise n'est pas un jour comme un autre.
    """
    jours_travailles = set(
        Session.objects.filter(user=user, status=Session.DONE).values_list(
            "coach_day", flat=True
        )
    )
    compte = 0
    for veille in Hiatus.objects.filter(user=user):
        fin = veille.ends_on
        if veille.ended_early_at:
            fin = min(fin, veille.ended_early_at.date())
        if fin + timedelta(days=1) in jours_travailles:
            compte += 1
    return compte


def _annees_accomplies(user) -> int:
    """Les ascendances déjà prises. Zéro tant que la mécanique n'a pas servi."""
    from .models import Ascendance

    return Ascendance.objects.filter(user=user).count()
