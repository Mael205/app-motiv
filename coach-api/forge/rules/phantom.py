"""Le fantôme de saison (SPEC §12.7).

> Reprise directe du contre-la-montre de jeu de course, et c'est la mécanique de
> compétition qui lui correspond le mieux : **il performe contre un adversaire,
> pas contre une intention**.

C'est la phrase qui décide de tout ce module. Un objectif chiffré est une
intention ; on peut la renégocier à la baisse un mardi soir, et on le fait. Une
courbe déjà tracée par soi-même il y a trois mois ne se renégocie pas — elle est
là, elle avance d'un point par jour, et à J12 elle est devant ou derrière.

**Le fantôme ne juge jamais.** Il rend un écart, en heures, avec le nom de la
saison de référence. « −1h10, le fantôme est devant » est un fait ; « tu es en
retard » serait un reproche, et le §0.2 dit que le système n'est pas là pour
motiver.

Nommé ``phantom`` et non ``ghost`` pour une raison très concrète : ``ghost.py``
existe déjà et traite des **sessions fantômes** — une session lancée puis
oubliée. Deux mécaniques sans rapport, et deux modules qui ne doivent pas se
confondre au moment d'un import.
"""

from __future__ import annotations

from dataclasses import dataclass

# Les trois références possibles, choisies à l'ouverture (§12.7).
MEILLEURE, DERNIERE, MOYENNE = "meilleure", "derniere", "moyenne"
CHOIX = (MEILLEURE, DERNIERE, MOYENNE)

CHOIX_LABELS = {
    MEILLEURE: "Ta meilleure saison",
    DERNIERE: "Ta dernière saison",
    MOYENNE: "La moyenne de tes saisons",
}


@dataclass(frozen=True)
class Curve:
    """Une courbe cumulée, un point par jour de saison. Toujours croissante."""

    label: str
    points: tuple[int, ...]

    def at(self, day_index: int) -> int:
        """La valeur à un jour donné, bornée aux deux extrémités.

        Bornée et non nulle hors limites : une saison de référence plus courte
        que la saison en cours doit rester comparable après son dernier jour,
        sinon l'écart bondirait artificiellement le jour où le fantôme s'arrête.
        """
        if not self.points:
            return 0
        return self.points[max(0, min(day_index, len(self.points) - 1))]

    @property
    def total(self) -> int:
        return self.points[-1] if self.points else 0


@dataclass(frozen=True)
class Comparison:
    """L'écart au fantôme à un jour donné, prêt à afficher."""

    day_index: int
    mine: int
    theirs: int
    reference: str
    available: bool

    @property
    def delta(self) -> int:
        return self.mine - self.theirs

    @property
    def ahead(self) -> bool:
        return self.delta >= 0

    @property
    def line(self) -> str:
        """La ligne unique du §12.7. Factuelle, jamais un encouragement."""
        if not self.available:
            return "Première saison : pas encore de fantôme. C'est elle qui servira de référence."

        heures, minutes = divmod(abs(self.delta), 60)
        ecart = f"{heures}h{minutes:02d}" if heures else f"{minutes} min"
        jour = f"Jour {self.day_index + 1}"

        if self.delta == 0:
            return f"{jour} — à égalité avec {self.reference}."
        if self.ahead:
            return f"{jour} — tu es à +{ecart} sur {self.reference}."
        return f"{jour} — −{ecart}, {self.reference} est devant."


def cumulative(daily_minutes: list[int]) -> tuple[int, ...]:
    """Transforme des minutes quotidiennes en courbe cumulée."""
    total = 0
    points = []
    for minutes in daily_minutes:
        total += max(0, minutes)
        points.append(total)
    return tuple(points)


def average_curve(curves: list[Curve], *, label: str) -> Curve:
    """La moyenne jour par jour de plusieurs courbes.

    Moyenne des **cumuls** et non cumul des moyennes : les deux donnent le même
    total mais pas la même forme, et c'est la forme qui se compare jour après
    jour. La moyenne des cumuls conserve le rythme réel — un démarrage lent
    suivi d'une fin rapide reste visible.
    """
    if not curves:
        return Curve(label=label, points=())

    longueur = max(len(c.points) for c in curves)
    return Curve(
        label=label,
        points=tuple(
            round(sum(c.at(i) for c in curves) / len(curves)) for i in range(longueur)
        ),
    )


def pick(curves: list[Curve], choice: str) -> Curve | None:
    """La courbe de référence selon le choix fait à l'ouverture.

    ``curves`` est ordonné de la plus ancienne à la plus récente. Rend ``None``
    quand il n'y a aucune saison passée — le §12.7 prévoit ce cas et le
    remplace par la trajectoire du contrat, qui n'est pas un fantôme.
    """
    passees = [c for c in curves if c.points]
    if not passees:
        return None

    if choice == DERNIERE:
        return passees[-1]
    if choice == MOYENNE:
        return average_curve(passees, label=CHOIX_LABELS[MOYENNE])
    return max(passees, key=lambda c: c.total)


def compare(mine: Curve, phantom: Curve | None, *, day_index: int) -> Comparison:
    """L'écart à un jour donné. Sans fantôme, l'écart est nul et signalé."""
    if phantom is None:
        return Comparison(
            day_index=day_index,
            mine=mine.at(day_index),
            theirs=0,
            reference="",
            available=False,
        )

    return Comparison(
        day_index=day_index,
        mine=mine.at(day_index),
        theirs=phantom.at(day_index),
        reference=phantom.label,
        available=True,
    )


def series(mine: Curve, phantom: Curve | None, *, days: int) -> list[dict]:
    """Les deux courbes jour par jour, pour le tracé.

    La courbe personnelle s'arrête au jour courant ; celle du fantôme va
    jusqu'au bout. C'est ce qui rend le graphique lisible comme une course :
    on voit où l'adversaire sera, pas seulement où il est.
    """
    return [
        {
            "day": i + 1,
            "mine": mine.at(i) if i < len(mine.points) else None,
            "phantom": phantom.at(i) if phantom else None,
        }
        for i in range(days)
    ]
