"""Signaux des sondes : ce qu'une détection automatique peut et ne peut pas dire.

Les sondes du §8 (agent PC, ActivityWatch, git) et du §9 (extension, sonde
Android) remontent des observations. Ce module décide ce qu'on en fait, et
porte la règle la plus importante du dispositif (SPEC §11.10) :

> **Une détection marque. Une absence de détection ne certifie rien.**

L'asymétrie n'est pas une prudence, c'est ce qui rend le système utilisable.
Navigation privée, autre appareil, téléphone sans sonde : le silence d'une sonde
n'est jamais une preuve d'abstinence. Un système qui afficherait « journée
tenue, vérifiée » mentirait dans le sens rassurant — et un compteur qu'on sait
faux ne tient personne (§6).

Deuxième règle : **une catégorie et une durée, jamais du contenu.** Ce module ne
reçoit ni URL, ni titre, ni chemin de fichier. Ce qui lui arrive est déjà
catégorisé par la sonde ; il ne saurait pas quoi faire d'autre chose.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

AGENT, EXTENSION, MOBILE = "agent", "ext", "mobile"
SOURCES = (AGENT, EXTENSION, MOBILE)

# Catégories remontées par les sondes. Elles sont volontairement grossières :
# une catégorie fine demanderait de regarder le contenu.
TRAVAIL_PROJET = "travail_projet"
TRAVAIL_HORS_PROJET = "travail_hors_projet"
RESEAUX = "reseaux"
SCROLL_PASSIF = "scroll_passif"
ADULTE = "adulte"
JEU = "jeu"
SPORT = "sport"
AUTRE = "autre"

CATEGORIES = (
    TRAVAIL_PROJET,
    TRAVAIL_HORS_PROJET,
    RESEAUX,
    SCROLL_PASSIF,
    ADULTE,
    JEU,
    SPORT,
    AUTRE,
)

# En dessous de ce seuil, un passage n'est pas un usage : ouvrir un onglet par
# erreur ne doit pas marquer une journée.
MIN_MINUTES_TO_MARK = 3


@dataclass(frozen=True)
class Signal:
    """Une observation d'une sonde. Aucun contenu, par construction."""

    source: str
    category: str
    minutes: int
    day: date

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"Source inconnue : {self.source}")
        if self.category not in CATEGORIES:
            raise ValueError(f"Catégorie inconnue : {self.category}")
        if self.minutes < 0:
            raise ValueError("Une durée de signal ne peut pas être négative.")


@dataclass(frozen=True)
class Verdict:
    """Ce qu'on peut conclure d'un ensemble de signaux, pour une catégorie.

    ``marks`` est vrai quand une sonde a vu assez pour marquer la journée.
    Il n'existe **délibérément pas** de champ « clean » ou « vérifié tenu » :
    l'absence de signal n'est pas représentable comme une preuve.
    """

    category: str
    minutes: int
    marks: bool
    sources: tuple[str, ...]

    @property
    def label(self) -> str:
        if not self.marks:
            return "Rien vu par les sondes — ce n'est pas une preuve."
        origine = ", ".join(self.sources)
        return f"{self.minutes} min détectées ({origine})."


def minutes_by_category(signals: Iterable[Signal], day: date) -> dict[str, int]:
    """Total de minutes par catégorie pour une journée du coach."""
    totals: dict[str, int] = {}
    for signal in signals:
        if signal.day != day:
            continue
        totals[signal.category] = totals.get(signal.category, 0) + signal.minutes
    return totals


def verdict_for(signals: Iterable[Signal], category: str, day: date) -> Verdict:
    """Ce que les sondes permettent de dire d'une catégorie, ce jour-là.

    Le seul verdict positif possible est « marquée ». Il n'y a pas de verdict
    « tenue » : une sonde ne peut pas voir ce qui s'est passé ailleurs.
    """
    retenus = [s for s in signals if s.day == day and s.category == category]
    minutes = sum(s.minutes for s in retenus)
    return Verdict(
        category=category,
        minutes=minutes,
        marks=minutes >= MIN_MINUTES_TO_MARK,
        sources=tuple(sorted({s.source for s in retenus})),
    )


def certifies_held(*_args, **_kwargs) -> bool:
    """N'existe que pour être appelée et rendre ``False``.

    Elle documente une impossibilité de conception : aucun ensemble de signaux,
    aussi complet soit-il, ne permet de certifier qu'une journée a été tenue
    (SPEC §11.10). Le jour où quelqu'un cherchera cette fonction, il trouvera la
    réponse plutôt que d'en écrire une fausse.
    """
    return False
