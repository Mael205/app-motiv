"""Attribution des slots actifs (SPEC §4.3).

Deux limites dures, pas une :

1. **Trois projets actifs au maximum.** Le cœur du dispositif anti-dispersion.
2. **Deux slots au maximum par domaine.** Trois projets de code dans les trois
   slots, c'est une seule vie déguisée en trois : les mêmes outils, la même
   posture, la même fatigue. La diversité n'est pas un confort, c'est ce qui
   permet à une soirée sans énergie de coder d'exister quand même.

La règle se vérifie au moment où un projet prend un slot. Elle ne déloge jamais
un projet déjà installé — une limite qui expulse rétroactivement serait une
sanction, et le §17 les interdit.
"""

from __future__ import annotations

from collections.abc import Iterable

from . import ranks

BASE_SLOTS = 3
ABSOLUTE_MAX_SLOTS = 5
MAX_PER_DOMAIN = 2

# La piste Corps a ses propres slots, et ils ne bougent jamais : quatre activités
# physiques en parallèle sont de la dispersion au même titre que quatre projets
# (SPEC §11.4).
CORPS_SLOTS = 2

# Rétro-compatibilité : la limite de base, pour les appels sans rang.
MAX_ACTIVE = BASE_SLOTS

CODE = "code"
CORPS = "corps"
CREATIF = "creatif"
SAVOIR = "savoir"
PRATIQUE = "pratique"

DOMAINS = (CODE, CORPS, CREATIF, SAVOIR, PRATIQUE)

DOMAIN_LABELS = {
    CODE: "Code",
    CORPS: "Corps",
    CREATIF: "Créatif",
    SAVOIR: "Savoir",
    PRATIQUE: "Pratique",
}


def unlocked_slots(rank: str) -> int:
    """Combien de slots d'atelier sont ouverts à ce rang.

    Le rang **est** la régularité depuis la refonte du §4.4 : il se calcule sur
    les semaines d'engagements tenus, pas sur l'XP. Une seule condition suffit
    donc ici, là où il en fallait deux quand le rang mesurait le volume.
    """
    return min(ranks.rewards_for(rank).slots, ABSOLUTE_MAX_SLOTS)


def slots_for_track(kind: str, rank: str) -> int:
    """Les slots d'une piste. Seul l'Atelier grandit avec le rang (SPEC §11.4)."""
    if kind == "corps":
        return CORPS_SLOTS
    return unlocked_slots(rank)


def assign_slot(
    taken: Iterable[tuple[int, str]], domain: str, *, total_slots: int = BASE_SLOTS
) -> int | None:
    """Le slot qu'un projet de ce domaine peut prendre, ou rien.

    ``taken`` est la liste des ``(slot, domaine)`` déjà actifs. Rendre ``None``
    n'est pas une erreur : l'appelant envoie le projet au frigo.
    """
    taken = list(taken)
    used = {slot for slot, _ in taken}
    if len(used) >= total_slots:
        return None
    if sum(1 for _, d in taken if d == domain) >= MAX_PER_DOMAIN:
        return None
    return next((slot for slot in range(1, total_slots + 1) if slot not in used), None)


SUNDAY = 6


def can_replace(*, weekday: int, project_finished: bool, has_sessions: bool) -> tuple[bool, str]:
    """Peut-on sortir un projet de son slot aujourd'hui ?

    Le dimanche protège contre l'abandon d'un projet pour un autre plus
    excitant. Il ne protège pas contre la réussite : un projet dont la roadmap
    est finie libère son slot le jour même.

    La session enregistrée n'est pas un soupçon, c'est une garde-fou : sans
    elle, une roadmap d'une seule étape cochée servirait à contourner le
    dimanche. Le système ne sanctionne pas la triche, il la rend inutile.
    """
    if weekday == SUNDAY:
        return True, "Dimanche : l'échange est ouvert."
    if project_finished and has_sessions:
        return True, "Roadmap terminée : le slot se libère sans attendre dimanche."
    if project_finished:
        return False, (
            "Roadmap marquée finie, mais aucune session enregistrée sur ce projet. "
            "L'échange attend dimanche."
        )
    return False, "L'échange de slot se fait le dimanche."


def must_fill_vacancy(*, weekday: int, vacant: int) -> bool:
    """Un slot laissé vacant doit être repris le dimanche.

    Sans cette règle, une limite de 3 se transformerait en limite de 2 par
    simple inertie.
    """
    return weekday == SUNDAY and vacant > 0


def refused_reason(
    taken: Iterable[tuple[int, str]], domain: str, *, total_slots: int = BASE_SLOTS
) -> str | None:
    """Pourquoi le projet n'a pas trouvé de slot. Factuel, sans reproche."""
    taken = list(taken)
    if len({slot for slot, _ in taken}) >= total_slots:
        return (
            f"Les {total_slots} slots sont pris. Le projet part au frigo, "
            "l'échange se fait le dimanche."
        )
    same = sum(1 for _, d in taken if d == domain)
    if same >= MAX_PER_DOMAIN:
        label = DOMAIN_LABELS.get(domain, domain)
        return (
            f"Deux slots sont déjà en « {label} », et c'est le maximum. "
            "Le projet part au frigo : le troisième slot est réservé à un autre domaine."
        )
    return None


def saturated_domains(taken: Iterable[tuple[int, str]]) -> list[str]:
    """Domaines qui ont atteint leur plafond. Sert à expliquer avant de refuser."""
    counts: dict[str, int] = {}
    for _, domain in taken:
        counts[domain] = counts.get(domain, 0) + 1
    return sorted(d for d, n in counts.items() if n >= MAX_PER_DOMAIN)


def breaches_diversity(taken: Iterable[tuple[int, str]]) -> str | None:
    """Un domaine occupe-t-il déjà plus que son plafond ?

    Ne se produit que sur des données antérieures à la règle : elle s'affiche
    comme un constat, elle ne déloge personne.
    """
    counts: dict[str, int] = {}
    for _, domain in taken:
        counts[domain] = counts.get(domain, 0) + 1
    over = [d for d, n in counts.items() if n > MAX_PER_DOMAIN]
    return over[0] if over else None


# --------------------------------------------------------------------------
# L'engagement hebdomadaire : baisser quand on veut, monter le dimanche
# --------------------------------------------------------------------------

# Le §4.3 réserve l'échange de slot au dimanche, pour protéger de l'abandon
# impulsif d'un projet pour un autre plus excitant. L'engagement n'est pas dans
# ce cas : le baisser en milieu de semaine n'est pas un abandon, c'est un
# ajustement honnête. Le refuser force à subir une semaine qu'on sait déjà
# intenable — donc à la rater, donc à perdre le rang pour rien.
#
# Le monter, en revanche, reste au dimanche. Une hausse prise un soir d'élan est
# exactement le sur-régime du §0.2, et c'est elle qu'il faut faire dormir une
# nuit.
DIMANCHE = 6
ENGAGEMENT_MAX = 14


def peut_changer_engagement(*, actuel: int, vise: int, weekday: int) -> tuple[bool, str]:
    """Rend ``(autorise, motif)``. Le motif est affiche tel quel."""
    if vise < 1:
        return False, "Un engagement à zéro n'est pas un engagement. Le minimum est 1."
    if vise > ENGAGEMENT_MAX:
        return False, f"Le maximum est {ENGAGEMENT_MAX} sessions par semaine."
    if vise <= actuel:
        return True, ""
    if weekday == DIMANCHE:
        return True, ""
    return (
        False,
        "Monter un engagement attend le dimanche. Le baisser, non — ça se fait quand tu veux.",
    )
