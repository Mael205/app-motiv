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
from datetime import date, datetime

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
    """Une observation d'une sonde. Aucun contenu, par construction.

    ``started_at`` et ``ended_at`` sont facultatifs, et cette facultativité est
    une décision, pas un oubli. Une sonde qui mesure une fenêtre — l'agent, une
    extension — les fournit. Une recette d'automatisation mobile qui dit
    seulement « l'application a été ouverte » ne le peut pas. Le second cas reste
    utile pour **marquer** une journée ; il est en revanche inutilisable pour
    attribuer du temps à une session, et le code doit refuser de faire semblant.
    """

    source: str
    category: str
    minutes: int
    day: date
    started_at: datetime | None = None
    ended_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"Source inconnue : {self.source}")
        if self.category not in CATEGORIES:
            raise ValueError(f"Catégorie inconnue : {self.category}")
        if self.minutes < 0:
            raise ValueError("Une durée de signal ne peut pas être négative.")
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("Une fenêtre de signal ne peut pas se terminer avant de commencer.")

    @property
    def has_window(self) -> bool:
        """Le signal peut-il être situé dans le temps ?"""
        return self.started_at is not None and self.ended_at is not None


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


@dataclass(frozen=True)
class Coverage:
    """Ce que les sondes ont vu **pendant** une session (SPEC §6).

    C'est la « qualité de session » : le temps où l'application déclarée du
    projet était devant, rapporté à la durée de la session.

    Elle **n'invalide jamais** une session. Le §6 est explicite : la preuve
    d'activité s'affiche, elle ne juge pas. Être devant un éditeur n'est pas
    travailler, et l'inverse est vrai aussi — on peut réfléchir au tableau.
    """

    category: str
    session_minutes: int
    covered_minutes: int
    ignored_signals: int

    @property
    def ratio(self) -> float:
        """Plafonné à 1 : deux sondes qui voient la même heure ne font pas deux heures."""
        if self.session_minutes <= 0:
            return 0.0
        return round(min(1.0, self.covered_minutes / self.session_minutes), 3)

    @property
    def percent(self) -> int:
        return int(round(self.ratio * 100))

    @property
    def label(self) -> str:
        if self.session_minutes <= 0:
            return "Session sans durée."
        if self.covered_minutes == 0 and self.ignored_signals:
            return (
                f"{self.ignored_signals} signal(s) sans fenêtre horaire : "
                "impossible de les rattacher à cette session."
            )
        return f"{self.percent} % de la session avec l'application déclarée devant."


def overlap_minutes(signal: Signal, start: datetime, end: datetime) -> int:
    """Minutes du signal qui tombent dans la fenêtre ``[start, end]``.

    Un signal sans fenêtre rend zéro. On ne répartit pas un total journalier au
    prorata : ce serait inventer une mesure que la sonde n'a pas faite.
    """
    if not signal.has_window:
        return 0
    debut = max(signal.started_at, start)
    fin = min(signal.ended_at, end)
    if fin <= debut:
        return 0

    fenetre = (fin - debut).total_seconds() / 60
    duree_signal = (signal.ended_at - signal.started_at).total_seconds() / 60
    if duree_signal <= 0:
        return 0

    # Le signal annonce N minutes d'usage sur une fenêtre plus large : on
    # attribue la part de cette fenêtre qui recouvre la session.
    return int(round(signal.minutes * (fenetre / duree_signal)))


def session_coverage(
    signals: Iterable[Signal], *, category: str, start: datetime, end: datetime
) -> Coverage:
    """Couverture d'une session par une catégorie de signaux."""
    retenus = [s for s in signals if s.category == category]
    covered = sum(overlap_minutes(s, start, end) for s in retenus)
    ignored = sum(1 for s in retenus if not s.has_window)
    session_minutes = int(round((end - start).total_seconds() / 60))
    return Coverage(
        category=category,
        session_minutes=session_minutes,
        covered_minutes=covered,
        ignored_signals=ignored,
    )


def certifies_held(*_args, **_kwargs) -> bool:
    """N'existe que pour être appelée et rendre ``False``.

    Elle documente une impossibilité de conception : aucun ensemble de signaux,
    aussi complet soit-il, ne permet de certifier qu'une journée a été tenue
    (SPEC §11.10). Le jour où quelqu'un cherchera cette fonction, il trouvera la
    réponse plutôt que d'en écrire une fausse.
    """
    return False
