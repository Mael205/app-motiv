"""La jauge de chaleur (SPEC §12.10).

> Une jauge de chaleur hebdomadaire qui monte à chaque jour travaillé et
> **redescend progressivement, jamais d'un coup**. Un jour raté la fait tiédir,
> pas s'éteindre — cohérent avec l'anti-fragilité du §4.2.

Cette asymétrie est toute la mécanique, et c'est elle qui la sépare du streak.
Le streak a le droit de casser : c'est ce qui lui donne son poids. Le momentum
n'a pas ce droit, parce qu'il joue le rôle inverse — il rend le lendemain d'un
mauvais jour **plus facile**, pas plus coûteux. Un jour manqué retire moins que
ce qu'un jour travaillé apporte, donc revenir rapporte toujours plus que ce que
l'absence a coûté.

**Rien n'est stocké.** La chaleur se recalcule depuis l'historique des jours à
chaque lecture. Un compteur persistant dériverait au premier bug, au premier
fuseau horaire, à la première correction manuelle — et une jauge fausse qui
multiplie l'XP est pire qu'une jauge absente.
"""

from __future__ import annotations

from dataclasses import dataclass

# Le multiplicateur va de 1,0 à 1,25 (§12.10 et le tableau du §4.4).
MULT_MIN = 1.0
MULT_MAX = 1.25

# L'asymétrie, chiffrée. Un jour travaillé chauffe de 0,22 ; un jour manqué ne
# refroidit que de 0,12. Il faut donc deux jours manqués pour effacer un jour
# fait, et cinq jours travaillés pour atteindre le maximum.
CHAUFFE = 0.22
REFROIDIT = 0.12

# Sur combien de jours on regarde. Sept jours glissants plutôt que la semaine
# calendaire : la chaleur ne doit pas retomber à zéro tous les lundis, ce qui
# ferait du dimanche soir le pire moment de la semaine pour travailler.
FENETRE = 7

PALIERS = (
    (0.00, "éteinte", "Rien depuis un moment."),
    (0.25, "tiède", "Ça repart."),
    (0.50, "chaude", "Le rythme est pris."),
    (0.75, "ardente", "Trois jours d'affilée se sentent."),
    (0.95, "incandescente", "Tu es à la chaleur maximale."),
)


@dataclass(frozen=True)
class Heat:
    """L'état de la jauge. ``level`` est la grandeur brute, 0 à 1."""

    level: float
    multiplier: float
    label: str
    detail: str
    days_worked: int
    cooling: bool          # le dernier jour connu était manqué

    @property
    def percent(self) -> int:
        return round(self.level * 100)


def _label_for(level: float) -> tuple[str, str]:
    retenu = PALIERS[0]
    for seuil, nom, detail in PALIERS:
        if level >= seuil:
            retenu = (seuil, nom, detail)
    return retenu[1], retenu[2]


def evaluate(days: list[bool]) -> Heat:
    """Calcule la chaleur depuis les jours récents, du plus ancien au plus récent.

    ``days`` porte ``True`` pour un jour travaillé. Seuls les ``FENETRE``
    derniers comptent — au-delà, un mois d'inactivité et une semaine
    d'inactivité doivent se ressembler, sinon la jauge devient une dette.
    """
    recents = days[-FENETRE:]

    niveau = 0.0
    for travaille in recents:
        niveau += CHAUFFE if travaille else -REFROIDIT
        # Le bornage à chaque pas, et non à la fin : sans lui, une longue série
        # constituerait une réserve invisible qui absorberait plusieurs jours
        # manqués sans que la jauge ne bouge, et la mécanique deviendrait
        # illisible.
        niveau = min(1.0, max(0.0, niveau))

    nom, detail = _label_for(niveau)

    return Heat(
        level=round(niveau, 3),
        multiplier=round(MULT_MIN + (MULT_MAX - MULT_MIN) * niveau, 3),
        label=nom,
        detail=detail,
        days_worked=sum(1 for j in recents if j),
        cooling=bool(recents) and not recents[-1],
    )


def multiplier(days: list[bool]) -> float:
    """Le multiplicateur seul, pour le calcul d'XP."""
    return evaluate(days).multiplier
