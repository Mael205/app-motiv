"""Le bilan automatique quotidien (SPEC §13.1).

Généré chaque nuit après la bascule de 4h, lu le lendemain matin en dix
secondes. Sa contrainte principale n'est pas ce qu'il dit, c'est ce qu'il
**demande** : rien. Aucune interaction, aucun champ, aucun bouton. C'est le seul
écran du produit qu'on regarde sans avoir rien à y faire, et il perdrait tout
s'il réclamait quoi que ce soit.

Deuxième contrainte, qui décide de la forme : **une phrase de constat, jamais
plus**. « 3h05 disponibles, 50 min travaillées, 1h20 de scroll entre 19h et
20h30. » Le §17 interdit le jugement, et un bilan quotidien est l'endroit où il
reviendrait le plus facilement — trois lignes de commentaire sur une mauvaise
soirée, tous les matins, et l'app se ferme pour de bon.

Module pur : des minutes entrent, une barre et une phrase sortent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# L'ordre d'affichage de la répartition. Le travail d'abord, le reste ensuite :
# c'est ce que le §13.1 énumère, et l'ordre inverse ferait du bilan un compteur
# de fautes.
CATEGORIES = (
    ("travail_projet", "Travail projet"),
    ("travail_hors_projet", "Travail hors projet"),
    ("scroll_passif", "Scroll passif"),
    ("jeu", "Jeux"),
    ("autre", "Autre"),
)

# En dessous, une catégorie est du bruit de mesure et n'a pas à figurer dans une
# ligne qu'on lit en dix secondes.
MINUTES_VISIBLES = 5


@dataclass(frozen=True)
class BilanDuJour:
    disponibles: int
    travaillees: int
    creneau_prevu: bool
    creneau_tenu: bool
    repartition: list[tuple[str, int]] = field(default_factory=list)
    phrase: str = ""

    @property
    def part_travaillee(self) -> float:
        """Entre 0 et 1. La barre du §13.1, et rien d'autre."""
        if self.disponibles <= 0:
            return 0.0
        return min(1.0, self.travaillees / self.disponibles)


def composer(
    *,
    disponibles: int,
    travaillees: int,
    signaux: dict[str, int],
    creneau_prevu: bool = False,
    creneau_tenu: bool = False,
) -> BilanDuJour:
    """Le bilan d'une journée. ``signaux`` est en minutes par catégorie."""
    repartition = [
        (libelle, signaux.get(cle, 0))
        for cle, libelle in CATEGORIES
        if signaux.get(cle, 0) >= MINUTES_VISIBLES
    ]

    return BilanDuJour(
        disponibles=disponibles,
        travaillees=travaillees,
        creneau_prevu=creneau_prevu,
        creneau_tenu=creneau_tenu,
        repartition=repartition,
        phrase=_phrase(
            disponibles=disponibles,
            travaillees=travaillees,
            signaux=signaux,
            creneau_prevu=creneau_prevu,
            creneau_tenu=creneau_tenu,
        ),
    )


def _phrase(
    *,
    disponibles: int,
    travaillees: int,
    signaux: dict[str, int],
    creneau_prevu: bool,
    creneau_tenu: bool,
) -> str:
    """Une phrase, des chiffres, aucun adjectif.

    Ce qui est délibérément absent : « seulement », « déjà », « encore », et
    toute mention de ce qu'il aurait fallu faire. Le §13.1 demande un constat.
    Les chiffres se commentent tout seuls, et c'est précisément pour ça qu'ils
    valent mieux qu'un commentaire.
    """
    morceaux = [f"{_duree(disponibles)} disponibles", f"{_duree(travaillees)} travaillées"]

    scroll = signaux.get("scroll_passif", 0)
    if scroll >= MINUTES_VISIBLES:
        morceaux.append(f"{_duree(scroll)} de scroll")

    phrase = ", ".join(morceaux) + "."

    if creneau_prevu and not creneau_tenu:
        phrase += " Créneau prévu, pas tenu."
    elif creneau_prevu:
        phrase += " Créneau tenu."

    return phrase


def _duree(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    heures, reste = divmod(minutes, 60)
    return f"{heures}h{reste:02d}" if reste else f"{heures}h"
