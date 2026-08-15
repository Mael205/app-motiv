"""Les gardes : ce qu'il s'agit de ne pas faire (SPEC §11.10).

Miroir du §11.9, et sujet où une mauvaise mécanique fait le plus de dégâts.

**Aucune garde ne vise zéro.** « Plus jamais » tient jusqu'à la première fois,
et transforme cette première fois en preuve d'échec total — le §0.3 appliqué au
pire endroit. Une garde porte donc un **budget hebdomadaire** : un nombre de
jours tolérés. Rester dessous **est** l'objectif atteint, pas un échec toléré.
C'est le geste du plafond d'XP du §4.4 : une limite tenable plutôt qu'un idéal
raté.

Deux compteurs, aucun qui ne redescende :

* le **cumul de jours tenus**, strictement monotone — un dépassement n'en
  retire aucun ;
* les **semaines tenues**, une semaine étant tenue quand le nombre de jours
  marqués reste sous le budget.

Le module ne produit aucun jugement : il compte des jours et rend des faits.
Les libellés qu'il fournit sont volontairement plats.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .calendar import week_start

MIN_BUDGET = 1          # un budget à zéro est refusé par construction (§11.10)
MAX_BUDGET = 7


@dataclass(frozen=True)
class Garde:
    """Une garde réduite à ce dont la règle a besoin."""

    key: str
    name: str
    weekly_budget: int

    def __post_init__(self) -> None:
        if self.weekly_budget < MIN_BUDGET:
            raise ValueError(
                "Une garde ne peut pas viser zéro : un objectif intenable transforme "
                "la première fois en abandon complet (SPEC §11.10)."
            )


@dataclass(frozen=True)
class GardeWeek:
    """L'état d'une garde sur une semaine."""

    garde_key: str
    week_start: date
    marked: int          # jours où c'est arrivé
    budget: int

    @property
    def held(self) -> bool:
        return self.marked <= self.budget

    @property
    def left(self) -> int:
        return max(0, self.budget - self.marked)

    @property
    def label(self) -> str:
        return f"{self.marked} / {self.budget}"


def week_state(garde: Garde, marked_days: Iterable[date], day: date) -> GardeWeek:
    """État de la garde sur la semaine contenant ``day``."""
    start = week_start(day)
    marked = sum(1 for d in marked_days if week_start(d) == start)
    return GardeWeek(
        garde_key=garde.key,
        week_start=start,
        marked=marked,
        budget=garde.weekly_budget,
    )


def held_days(declared_days: Iterable[date], marked_days: Iterable[date]) -> int:
    """Jours déclarés tenus. Le grand chiffre, et il ne redescend jamais.

    Une journée non déclarée ne compte nulle part : elle n'est ni tenue ni
    marquée. Le système ne devine pas.
    """
    marked = set(marked_days)
    return sum(1 for d in set(declared_days) if d not in marked)


def held_weeks(garde: Garde, declared_days: Iterable[date], marked_days: Iterable[date]) -> int:
    """Semaines passées sous le budget, parmi celles où quelque chose a été déclaré."""
    declared = {week_start(d) for d in declared_days}
    marked = list(marked_days)
    return sum(
        1
        for start in declared
        if sum(1 for d in marked if week_start(d) == start) <= garde.weekly_budget
    )


def message_for(week: GardeWeek, total_held_days: int) -> str:
    """Le retour affiché. Un fait, jamais un jugement (§11.10).

    Aucune mention de volonté, de rechute, de discipline ou de progrès perdu :
    le dépassement constate un dépassement et rappelle ce qui reste acquis.
    """
    if week.marked == 0:
        return f"{total_held_days} jours tenus au total."
    if week.held:
        return (
            f"{week.marked} sur un budget de {week.budget} cette semaine. "
            f"La semaine tient. {total_held_days} jours tenus au total."
        )
    return (
        f"{week.marked} jours cette semaine, budget {week.budget}. La semaine ne compte pas. "
        f"Les {total_held_days} jours tenus restent acquis."
    )
