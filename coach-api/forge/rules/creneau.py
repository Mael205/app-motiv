"""Ce qu'on fait du temps qu'on a ce soir (SPEC §4.1, §4.5).

Jusqu'ici la durée et la tâche ne se parlaient pas. L'écran du soir proposait
toujours ``project.current_step`` — la première étape ouverte, quelle qu'elle
soit — et les trois boutons de durée ne faisaient que changer le chronomètre.
Choisir « Longue · 50 » sur une étape de trois sessions, c'était s'engager sur
soixante-quinze minutes en croyant en promettre cinquante ; et choisir
« Dégradé · 10 » n'allégeait rien du tout.

Le module remplit le créneau. Deux gestes, et deux seulement :

**On enchaîne.** Si l'étape suivante tient et qu'il reste du temps, on prend
celle d'après, et ainsi de suite. Une soirée de soixante-quinze minutes sur des
étapes de vingt-cinq en couvre trois, et le dire d'avance vaut mieux que de
laisser quelqu'un finir en vingt minutes et se demander ce qu'il fait là.

**On coupe.** Si l'étape ne tient pas dans ce qui reste, on n'en propose pas une
autre à la place : on en fait la part qui tient, et on le dit — « la moitié ».
Le temps passé est crédité sur l'étape, qui reprendra où elle s'est arrêtée.

**Ce que le module ne fait pas : enjamber.** L'ordre de la roadmap est la
roadmap. Sauter l'étape en cours parce qu'une plus loin serait plus courte
donnerait un soir un projet qui avance par les bouts faciles, et l'étape
difficile ne serait jamais commencée — c'est exactement la dérive que le §4.5
cherche à empêcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

# La session du §4.1. Toute estimation d'étape est un multiple de celle-ci.
MINUTES_PAR_SESSION = 25

# En dessous, on n'ouvre pas une portion de plus : cinq minutes sur une étape ne
# sont pas un début de travail, c'est une ligne en plus à l'écran.
PORTION_MINIMALE = 5


def minutes_de(sessions: int) -> int:
    """Ce qu'une estimation en sessions représente en minutes."""
    return max(1, sessions) * MINUTES_PAR_SESSION


def reste_de(etape) -> int:
    """Ce qu'il reste à faire sur une étape, en minutes.

    Zéro veut dire que le temps estimé est consommé sans que l'étape ait été
    close. Ce n'est pas une erreur — une estimation est une estimation — et le
    planificateur le traite pour ce que c'est : une étape à finir, qui prend le
    temps qu'il faut.
    """
    total = minutes_de(getattr(etape, "estimated_sessions", 1))
    faites = max(0, getattr(etape, "minutes_done", 0) or 0)
    return max(0, total - faites)


@dataclass(frozen=True)
class Portion:
    """Un morceau de soirée passé sur une étape."""

    etape: object
    #: Les minutes qu'on y consacre ce soir.
    minutes: int
    #: Ce qu'il restait à faire sur l'étape avant ce soir.
    reste_avant: int

    @property
    def entiere(self) -> bool:
        """L'étape est couverte en entier ce soir."""
        return self.minutes >= self.reste_avant

    @property
    def fraction(self) -> float:
        """La part de ce qui restait que cette portion couvre, de 0 à 1."""
        if self.reste_avant <= 0:
            return 1.0
        return min(1.0, self.minutes / self.reste_avant)

    @property
    def pourcentage(self) -> int:
        return round(self.fraction * 100)

    @property
    def a_clore(self) -> bool:
        """Le temps estimé est déjà consommé : il reste à la déclarer finie."""
        return self.reste_avant <= 0


@dataclass(frozen=True)
class Plan:
    """Ce que la soirée couvre, étape par étape, dans l'ordre de la roadmap."""

    minutes: int
    portions: list[Portion] = field(default_factory=list)

    @property
    def vide(self) -> bool:
        return not self.portions

    @property
    def premiere(self) -> Portion | None:
        return self.portions[0] if self.portions else None

    @property
    def couvert(self) -> int:
        """Les minutes réellement affectées à du travail."""
        return sum(p.minutes for p in self.portions)

    @property
    def coupe(self) -> bool:
        """La dernière étape du plan sera laissée en cours."""
        return bool(self.portions) and not self.portions[-1].entiere

    @property
    def enchaine(self) -> bool:
        return len(self.portions) > 1


def _ouvertes(etapes: Sequence) -> list:
    """Les étapes sur lesquelles on peut agir, l'étape en cours en tête.

    Le même ordre que ``Project.current_step`` : « en cours » d'abord, puis
    l'ordre de la roadmap. Deux tris différents pour la même question
    donneraient deux réponses différentes selon l'écran.
    """
    en_cours = [e for e in etapes if getattr(e, "state", "") == "doing"]
    a_faire = [e for e in etapes if getattr(e, "state", "") == "todo"]
    return en_cours + a_faire


def plan_pour(minutes: int, etapes: Sequence) -> Plan:
    """Remplit un créneau de ``minutes`` avec les étapes ouvertes, dans l'ordre.

    Rend un ``Plan`` vide s'il n'y a plus rien d'ouvert — l'écran dit alors
    d'écrire le prochain jalon, ce qui est le vrai geste manquant.
    """
    restant = max(0, minutes)
    portions: list[Portion] = []

    for etape in _ouvertes(etapes):
        if restant < PORTION_MINIMALE:
            break

        reste = reste_de(etape)

        # Étape dont le temps estimé est consommé : elle prend ce qui reste du
        # créneau. On ne devine pas ce qu'il lui faut encore — c'est le critère
        # de sortie qui tranche, pas le chronomètre.
        if reste <= 0:
            portions.append(Portion(etape=etape, minutes=restant, reste_avant=0))
            break

        part = min(reste, restant)
        portions.append(Portion(etape=etape, minutes=part, reste_avant=reste))
        restant -= part

    return Plan(minutes=max(0, minutes), portions=portions)


def crediter(portions: Sequence[Portion], minutes: int) -> list[tuple[object, int]]:
    """Répartit les minutes réellement travaillées sur les étapes prévues.

    Dans l'ordre, chacune jusqu'à son plafond, le reste débordant sur la
    suivante. C'est ce qui rend le remplissage partiel utilisable : sans cette
    répartition, une demi-étape faite un mardi serait à refaire en entier le
    jeudi, et personne n'accepterait deux fois de suite de n'en faire que la
    moitié.

    La séance plus courte que prévu ne crédite que ce qu'elle a duré ; la séance
    plus longue déborde sur les étapes suivantes du plan, jamais au-delà — on
    ne crédite pas un travail qui n'était pas au programme du soir.
    """
    restant = max(0, minutes)
    credits: list[tuple[object, int]] = []

    for portion in portions:
        if restant <= 0:
            break
        part = min(portion.minutes, restant)
        credits.append((portion.etape, part))
        restant -= part

    return credits
