"""Le rang : ce sur quoi on peut compter (SPEC §4.4, §12.3).

Jusqu'ici tout dérivait de l'XP — niveau, rang, privilèges. Or l'XP mesure le
**volume**, et le volume est précisément le mode de défaillance du §0.2 : le
sur-régime du jour 2 produit l'abandon du jour 6. Un système qui débloque des
droits sur l'XP finit donc par récompenser exactement ce qui fait décrocher.

Les deux axes sont donc séparés :

* **XP et niveaux** répondent à « combien j'ai fait ». Ils paient en loot
  cosmétique, en dégâts au boss, en Éclats, en score de saison. Ils ne
  débloquent **aucune règle** — ce qui est déjà l'esprit du §17 : le loot est
  de l'apparence, jamais du pouvoir.
* **Le rang** répond à « est-ce qu'on peut compter sur moi ». Il se calcule sur
  les semaines où les engagements ont été tenus, et lui seul ouvre des droits.

Le droit de tenir quatre projets s'obtient donc en démontrant qu'on en tient
trois — la seule preuve qui vaille, et qui ne s'achète pas en enchaînant les
sessions sur un seul projet.

**Le rang ne redescend jamais.** Il compte les semaines tenues *cumulées*, pas
l'état courant : le §17 interdit tout retrait rétroactif de niveau ou de rang.
Une mauvaise semaine n'en retire aucune, elle n'en ajoute pas.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

# Semaines d'engagements tenus nécessaires pour chaque rang.
#
# Les seuils sont volontairement atteignables : une saison fait quatre semaines,
# donc le 4ᵉ slot arrive vers une saison et demie. Des paliers hors de portée ne
# sont pas de l'exigence, ce sont des récompenses que personne ne voit.
RANK_LADDER = (
    ("F", 0),
    ("E", 1),
    ("D", 2),
    ("C", 4),
    ("B", 6),
    ("A", 9),
    ("S", 14),
    ("SS", 20),
)

RANK_ORDER = tuple(code for code, _ in RANK_LADDER)

BASE_SLOTS = 3
SLOT_AT_B = 4
SLOT_AT_A = 5

# Ce que chaque palier apporte. Les rangs intermédiaires donnent de la
# **souplesse**, jamais de la puissance : un bouclier de plus et un jour off de
# plus rendent le système plus tenable, ils ne rendent pas le travail plus
# rentable. C'est la différence entre aider quelqu'un à rester et le pousser à
# forcer.
EXTRA_SHIELD_FROM = "D"
EXTRA_DAY_OFF_FROM = "C"


@dataclass(frozen=True)
class Rewards:
    """Les droits ouverts par un rang. Cumulatifs, et jamais repris."""

    rank: str
    slots: int
    extra_shields: int
    extra_days_off: int


def _index(rank: str) -> int:
    return RANK_ORDER.index(rank) if rank in RANK_ORDER else 0


def rank_for(weeks_kept: int) -> str:
    """Le rang correspondant à un nombre de semaines tenues."""
    code = RANK_ORDER[0]
    for candidate, seuil in RANK_LADDER:
        if weeks_kept >= seuil:
            code = candidate
    return code


def rewards_for(rank: str) -> Rewards:
    """Les droits d'un rang, en cumulant ceux des paliers inférieurs."""
    niveau = _index(rank)
    slots = BASE_SLOTS
    if niveau >= _index("B"):
        slots = SLOT_AT_B
    if niveau >= _index("A"):
        slots = SLOT_AT_A
    return Rewards(
        rank=rank,
        slots=slots,
        extra_shields=1 if niveau >= _index(EXTRA_SHIELD_FROM) else 0,
        extra_days_off=1 if niveau >= _index(EXTRA_DAY_OFF_FROM) else 0,
    )


def weeks_kept(weeks: Iterable[tuple[date, bool]]) -> int:
    """Nombre de semaines où **tous** les engagements ont été tenus.

    ``weeks`` est une suite de ``(lundi de la semaine, engagement tenu)``, un
    élément par engagement. Une semaine ne compte que si aucun de ses
    engagements n'a été manqué : tenir deux projets sur trois n'est pas tenir sa
    semaine.

    Une semaine sans aucun engagement pris ne compte pas non plus — ne rien
    promettre n'est pas tenir sa parole.
    """
    par_semaine: dict[date, list[bool]] = {}
    for debut, tenu in weeks:
        par_semaine.setdefault(debut, []).append(tenu)
    return sum(1 for tenus in par_semaine.values() if tenus and all(tenus))


def next_rank(weeks_kept_count: int) -> tuple[str, int] | None:
    """Le prochain palier et ce qui en sépare. Un fait, pas une carotte."""
    for code, seuil in RANK_LADDER:
        if weeks_kept_count < seuil:
            return code, seuil - weeks_kept_count
    return None


def unlock_label(rank: str) -> str | None:
    """Ce que le prochain rang ouvrira, s'il ouvre quelque chose."""
    suivant = {
        "C": "un jour off de plus par saison",
        "D": "un bouclier de plus en réserve",
        "B": "un quatrième slot de projet",
        "A": "un cinquième slot de projet",
    }
    niveau = _index(rank)
    for code, texte in sorted(suivant.items(), key=lambda item: _index(item[0])):
        if _index(code) > niveau:
            return f"Rang {code} : {texte}."
    return None
