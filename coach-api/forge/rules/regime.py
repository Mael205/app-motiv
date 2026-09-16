"""Le régime de la saison — ce que la soirée autorise, et qui se resserre.

*(Tranché le 16 septembre 2026.)*

Trois heures décident de la soirée, et elles avancent d'une saison à l'autre :

- **le blocage** du §11.11, à 21h la première saison, jusqu'à **19h** ;
- **le sas** du §4.6, qui rouvre les réseaux vingt minutes pendant un blocage,
  jusqu'à dix ;
- **le couvre-feu**, nouveau : à 23h, tout se ferme **quoi qu'il arrive**, même
  la journée tenue, et YouTube y ferme en entier — à 23h on ne cherche plus une
  réponse technique. Jusqu'à 22h.

**Pourquoi un durcissement du tout.** Un cadre fixe cesse d'être un cadre : on
s'y installe, et la marge qu'il laissait devient la norme. Le durcissement est
lent à dessein — un quart d'heure par saison, soit par mois —, parce que c'est
l'écart qu'on ne remarque pas en le vivant et qu'on mesure en regardant derrière.

**Trois garde-fous, qui sont la moitié du module :**

1. **des planchers.** 19h, dix minutes, 22h, et on ne descend plus jamais. Sans
    eux, la pente finit à un système qui interdit tout, c'est-à-dire qu'on
    désinstalle ;
2. **rien ne change en cours de saison.** Le régime se lit à l'ouverture et
    tient vingt-huit jours. Une règle qui bouge un mardi soir n'est pas une
    règle, c'est une surprise ;
3. **aucune sanction ici.** Le §14 punit un décrochage ; ce module ne connaît
    que le numéro de la saison. Rater une saison ne durcit rien, la réussir non
    plus — sinon la réussite deviendrait une raison de craindre la suite.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import time

# Le point de départ, et le pas.
#
# Le pas de quinze minutes n'est pas un chiffre rond pris au hasard : il place
# le plancher de 19h à la neuvième saison, soit fin avril, et la première saison
# entièrement en régime dur en mai. C'est l'horizon qui a été choisi ; les deux
# autres pentes sont calées dessus pour arriver à peu près ensemble.
BLOCAGE_DEPART = time(21)
BLOCAGE_PAS_MINUTES = 15
BLOCAGE_PLANCHER = time(19)

SAS_DEPART_MINUTES = 20
SAS_PAS_MINUTES = 2
SAS_PLANCHER_MINUTES = 10

# Le week-end n'est pas un mardi *(16 septembre 2026)*. Vendredi et samedi soir,
# les deux heures reculent d'une heure — pas le sas, qui est déjà une soupape.
#
# Ce n'est pas une faveur : un couvre-feu à 22h un samedi est la règle qu'on
# enfreint, et une règle qu'on enfreint entraîne à enfreindre les autres. Mieux
# vaut une frontière qu'on tient six jours sur sept qu'une frontière de principe
# qui saute le week-end et emporte la semaine avec elle.
SOIRS_DE_WEEKEND = (4, 5)          # vendredi, samedi — 0 = lundi
DECALAGE_WEEKEND_MINUTES = 60

COUVRE_FEU_DEPART = time(23)
COUVRE_FEU_PAS_MINUTES = 10
COUVRE_FEU_PLANCHER = time(22)


def _decale(heure: time, minutes: int) -> time:
    """Recule une heure, en restant dans la journée. Minuit se dit ``00h00``."""
    total = (heure.hour * 60 + heure.minute + minutes) % (24 * 60)
    return time(total // 60, total % 60)


def _avance(depart: time, pas: int, plancher: time, saisons: int) -> time:
    minutes = depart.hour * 60 + depart.minute - pas * saisons
    minimum = plancher.hour * 60 + plancher.minute
    minutes = max(minimum, minutes)
    return time(minutes // 60, minutes % 60)


@dataclass(frozen=True)
class Regime:
    """Les trois heures de la soirée, pour une saison donnée."""

    index: int
    blocage: time
    sas_minutes: int
    couvre_feu: time

    @property
    def dur(self) -> bool:
        """Vrai quand les trois planchers sont atteints. Sert à le dire, une fois."""
        return (
            self.blocage == BLOCAGE_PLANCHER
            and self.sas_minutes == SAS_PLANCHER_MINUTES
            and self.couvre_feu == COUVRE_FEU_PLANCHER
        )

    def lignes(self) -> tuple[str, ...]:
        """Ce que la saison annonce à son ouverture. Des faits, pas une menace."""
        return (
            f"Blocage à {self.blocage:%Hh%M} si le projet du jour n'est pas fait.",
            f"Sas de détente : {self.sas_minutes} min, une fois par soir.",
            f"Couvre-feu à {self.couvre_feu:%Hh%M}, quoi qu'il arrive.",
        )


def pour_jour(index: int, weekday: int) -> Regime:
    """Le régime d'un soir précis. Vendredi et samedi reculent d'une heure.

    ``weekday`` est celui de la **journée du coach** : une soirée de vendredi
    qui déborde sur samedi 1h reste vendredi, et c'est ce qu'on veut — c'est la
    soirée qui est du week-end, pas l'horloge.
    """
    base = pour(index)
    if weekday not in SOIRS_DE_WEEKEND:
        return base
    return replace(
        base,
        blocage=_decale(base.blocage, DECALAGE_WEEKEND_MINUTES),
        couvre_feu=_decale(base.couvre_feu, DECALAGE_WEEKEND_MINUTES),
    )


def pour(index: int) -> Regime:
    """Le régime d'une saison. ``index`` est celui de la saison, 1 pour la première.

    Hors saison — avant la première, ou entre deux —, l'appelant passe 1 : le
    régime le plus doux. Une pause n'est pas le moment de serrer.
    """
    saisons = max(0, index - 1)
    return Regime(
        index=max(1, index),
        blocage=_avance(BLOCAGE_DEPART, BLOCAGE_PAS_MINUTES, BLOCAGE_PLANCHER, saisons),
        sas_minutes=max(
            SAS_PLANCHER_MINUTES, SAS_DEPART_MINUTES - SAS_PAS_MINUTES * saisons
        ),
        couvre_feu=_avance(
            COUVRE_FEU_DEPART, COUVRE_FEU_PAS_MINUTES, COUVRE_FEU_PLANCHER, saisons
        ),
    )
