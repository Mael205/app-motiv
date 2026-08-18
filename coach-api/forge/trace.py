"""La trace longue : les compteurs qui ne redescendent jamais.

Un écran à consulter le soir où le streak vient de casser, et qui n'existe que
pour ce soir-là.

Tout le reste du produit mesure du **présent** : le streak en cours, la semaine
en cours, la vie du boss, l'écart au fantôme aujourd'hui. C'est ce qu'il faut
pour décider quoi faire ce soir (§11.1), et c'est aussi ce qui rend un jour
raté brutal — au matin du jour 1, tous les chiffres de l'app disent zéro, et
aucun ne dit qu'on a travaillé cent quarante heures.

Ce module ne rend que des compteurs **monotones**. Aucun ne peut baisser, quoi
qu'il arrive : pas de série en cours, pas de moyenne, pas de pourcentage
hebdomadaire, pas de « il te reste ». Un seul compteur qui redescendrait
suffirait à annuler l'écran entier, puisque c'est un écran qu'on ouvre en ayant
déjà perdu quelque chose.

Le meilleur streak y figure ; le streak courant, non. Le premier est un record,
il ne se reprend pas ; le second est exactement ce dont on vient à peine de
sortir.

**Aucune phrase de consolation.** Le §17 interdit au système d'encourager comme
il lui interdit de reprocher : « tu as déjà fait tellement » serait un
commentaire, donc un jugement, donc un mensonge le jour où il tombe à côté. Il
n'y a que des nombres et leur date.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Count, Max, Sum

from .models import (
    Achievement,
    LootCard,
    OwnedRelic,
    RoadmapStep,
    Season,
    Session,
)
from .rules import skills as skill_rules
from .rules import xp as xp_rules


def longue(user) -> dict:
    """Tout ce qui ne redescend jamais, avec la date du premier jour."""
    faites = Session.objects.filter(user=user, status=Session.DONE)
    agregat = faites.aggregate(
        minutes=Sum("actual_minutes"),
        xp=Sum("xp_awarded"),
        sessions=Count("id"),
        premiere=Max("coach_day"),
    )
    minutes = agregat["minutes"] or 0
    total_xp = agregat["xp"] or 0

    jours = faites.values("coach_day").distinct().count()
    debut = faites.order_by("coach_day").values_list("coach_day", flat=True).first()

    etapes = RoadmapStep.objects.filter(
        project__user=user, state=RoadmapStep.DONE
    ).count()
    saisons = Season.objects.filter(user=user, status=Season.CLOSED)
    boss_abattus = sum(
        1 for s in saisons if hasattr(s, "boss") and s.boss.is_dead
    )

    return {
        "since": debut.isoformat() if debut else None,
        "days_since": (date.today() - debut).days if debut else 0,
        "compteurs": [
            _ligne("Heures travaillées", round(minutes / 60, 1), "h"),
            _ligne("Sessions terminées", agregat["sessions"] or 0),
            _ligne("Jours travaillés", jours),
            _ligne("Étapes de roadmap finies", etapes),
            _ligne("Meilleure série", _meilleur_streak(user), " jours"),
            _ligne("Niveau atteint", xp_rules.level_for(total_xp)),
            _ligne("XP cumulée", total_xp),
            _ligne("Saisons closes", saisons.count()),
            _ligne("Boss abattus", boss_abattus),
            _ligne("Titres décernés", saisons.exclude(title_awarded="").count()),
            _ligne("Hauts faits", Achievement.objects.filter(user=user).count()),
            _ligne("Cartes trouvées", LootCard.objects.filter(user=user).count()),
            _ligne("Reliques", OwnedRelic.objects.filter(user=user).count()),
        ],
        "branches": _branches(user),
        "titres": list(
            saisons.exclude(title_awarded="")
            .order_by("index")
            .values_list("title_awarded", flat=True)
        ),
    }


def _ligne(label: str, valeur, unite: str = "") -> dict:
    return {"label": label, "value": valeur, "unit": unite}


def _meilleur_streak(user) -> int:
    """La plus longue série de jours travaillés, jamais.

    Recalculée depuis les journées réellement travaillées plutôt que lue sur un
    champ : le meilleur streak stocké descend du calcul de streak courant, qui
    connaît les boucliers, les jours off et les jours neutres. Ici on ne veut
    que le fait brut — des jours d'affilée où quelque chose a été fait.
    """
    jours = sorted(
        set(
            Session.objects.filter(user=user, status=Session.DONE)
            .values_list("coach_day", flat=True)
        )
    )
    if not jours:
        return 0

    meilleur = courant = 1
    for precedent, suivant in zip(jours, jours[1:]):
        courant = courant + 1 if (suivant - precedent).days == 1 else 1
        meilleur = max(meilleur, courant)
    return meilleur


def _branches(user) -> list[dict]:
    """Les heures par branche. Elles ne baissent pas non plus : les heures ont
    été faites, et un projet archivé continue de compter (§12.9)."""
    lignes = (
        Session.objects.filter(user=user, status=Session.DONE)
        .exclude(project__branch="")
        .values("project__branch")
        .annotate(total=Sum("actual_minutes"))
    )
    etats = skill_rules.tree({l["project__branch"]: l["total"] or 0 for l in lignes})
    return [
        {"key": b.key, "label": b.label, "color": b.color, "hours": b.hours, "title": b.title}
        for b in etats
        if b.minutes
    ]
