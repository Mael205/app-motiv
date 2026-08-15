"""Évaluation du streak, des boucliers et des sanctions.

C'est la mécanique la plus importante du produit (SPEC §4.2). Elle est écrite
comme une fonction pure prenant l'historique complet des journées et rendant
l'état : aucune logique de streak ne doit exister ailleurs.

Les règles, dans l'ordre où elles s'appliquent :

1. Une journée a trois états possibles : ``VALIDEE``, ``RATEE``, ``NEUTRE``.
2. Les journées neutres (jour off déclaré la veille, pause entre deux saisons)
   sont **retirées du calcul de continuité** : elles ne cassent rien, ne
   consomment pas de bouclier, mais remettent à zéro la progression vers le
   prochain bouclier.
3. Une journée ratée consomme un bouclier et le streak continue.
4. Sans bouclier disponible, une journée ratée met le streak à zéro.
5. Deux journées ratées consécutives cassent le streak **même avec des
   boucliers en stock** : c'est la règle « jamais deux fois d'affilée ».
6. Reprendre après trois journées ratées ou plus rend un bouclier : revenir
   doit rapporter plus que ne pas s'être arrêté n'aurait coûté (SPEC §14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

MAX_SHIELDS = 3
DAYS_PER_SHIELD = 5
COMEBACK_MISSED_THRESHOLD = 3   # nombre de jours ratés qui déclenche le retour
FLOOR_MINUTES = 25
DEBT_MINUTES = 10               # dette du palier 2 (SPEC §14)


class DayState(str, Enum):
    VALIDEE = "validee"
    RATEE = "ratee"
    NEUTRE = "neutre"


@dataclass(frozen=True)
class Day:
    """Une journée de l'historique, déjà résolue en amont."""

    date: date
    state: DayState


@dataclass(frozen=True)
class StreakEvent:
    """Ce qui s'est passé un jour donné, pour pouvoir l'afficher sans deviner."""

    date: date
    kind: str          # bouclier_consomme | streak_casse | bouclier_gagne | retour
    detail: str


@dataclass
class StreakState:
    current: int = 0
    best: int = 0
    shields: int = 2                    # stock de départ
    consecutive_for_shield: int = 0
    last_validated: date | None = None
    missed_run: int = 0                 # jours ratés consécutifs en cours
    broken_at: date | None = None
    events: list[StreakEvent] = field(default_factory=list)

    @property
    def sanction_level(self) -> int:
        """0 = rien, 1 = un jour raté, 2 = deux, 3 = décrochage installé."""
        return min(self.missed_run, 3)

    @property
    def required_minutes(self) -> int:
        """Minutes nécessaires pour valider la journée en cours.

        Le palier 2 ajoute une dette de 10 minutes, une seule journée, jamais
        cumulable (SPEC §14).
        """
        return FLOOR_MINUTES + DEBT_MINUTES if self.missed_run == 2 else FLOOR_MINUTES


def evaluate(days: list[Day], *, starting_shields: int = 2) -> StreakState:
    """Rejoue l'historique complet et rend l'état du streak.

    ``days`` doit être trié par date croissante et contenir **toutes** les
    journées de la période, y compris les ratées : c'est l'appelant qui décide
    ce qu'est une journée ratée, pas cette fonction.
    """
    state = StreakState(shields=starting_shields)
    previous_effective: DayState | None = None  # dernier jour non neutre

    for day in sorted(days, key=lambda d: d.date):
        if day.state is DayState.NEUTRE:
            # Coût nul, bénéfice nul : la continuité est préservée mais la
            # progression vers le prochain bouclier repart de zéro.
            state.consecutive_for_shield = 0
            continue

        if day.state is DayState.VALIDEE:
            if state.missed_run >= COMEBACK_MISSED_THRESHOLD:
                _grant_shield(state, day.date, reason="retour")
                state.events.append(
                    StreakEvent(day.date, "retour", f"Retour après {state.missed_run} jours.")
                )
            state.current += 1
            state.best = max(state.best, state.current)
            state.consecutive_for_shield += 1
            state.last_validated = day.date
            state.missed_run = 0

            if state.consecutive_for_shield >= DAYS_PER_SHIELD:
                state.consecutive_for_shield = 0
                _grant_shield(state, day.date, reason="serie")

        else:  # DayState.RATEE
            state.missed_run += 1
            state.consecutive_for_shield = 0

            if previous_effective is DayState.RATEE:
                # Règle « jamais deux fois » : les boucliers n'y peuvent rien.
                if state.current:
                    state.events.append(
                        StreakEvent(day.date, "streak_casse", "Deux jours d'affilée.")
                    )
                state.current = 0
                state.broken_at = day.date
            elif state.shields > 0:
                state.shields -= 1
                state.events.append(
                    StreakEvent(
                        day.date,
                        "bouclier_consomme",
                        f"Bouclier consommé. Il t'en reste {state.shields}.",
                    )
                )
            else:
                if state.current:
                    state.events.append(
                        StreakEvent(day.date, "streak_casse", "Plus aucun bouclier.")
                    )
                state.current = 0
                state.broken_at = day.date

        previous_effective = day.state

    return state


def _grant_shield(state: StreakState, on: date, *, reason: str) -> None:
    if state.shields >= MAX_SHIELDS:
        return
    state.shields += 1
    state.events.append(
        StreakEvent(on, "bouclier_gagne", f"Bouclier gagné ({reason}). Stock : {state.shields}.")
    )


def message_for(state: StreakState) -> str:
    """Le message affiché après un jour raté. Il ne culpabilise pas (SPEC §4.2)."""
    if state.missed_run == 0:
        return ""
    if state.missed_run == 1:
        return (
            f"Bouclier consommé. Il t'en reste {state.shields}. "
            "La règle : jamais deux fois d'affilée."
        )
    if state.missed_run == 2:
        return (
            f"Deux jours. Le streak est reparti de zéro. "
            f"Ce soir : {state.required_minutes} min pour repartir."
        )
    return "On reprend. Une tâche, dix minutes."
