"""Piste Entretien : les routines courtes, mesurées à la semaine (SPEC §11.9).

Une routine de trois minutes n'a aucune excuse quand elle est oubliée, et c'est
précisément ce qui rend un streak quotidien dangereux ici : la rupture y est
plus douloureuse que sur une session de travail ratée (SPEC §0.3). La piste
Entretien n'a donc **aucun streak**. Elle sépare deux réglages que le reste du
système confond volontiers :

* le **rythme** — les jours où la routine est proposée ;
* le **seuil** — le nombre de fois par semaine qui rend la semaine *tenue*.

Une routine proposée les sept jours avec un objectif à six est quotidienne à
l'affichage et indulgente au score. Le battement entre les deux joue le rôle
que le bouclier joue au §4.2.

Deux invariants que les tests verrouillent :

1. **Aucun compteur ne redescend.** Une semaine est tenue ou ne l'est pas ;
   une mauvaise semaine n'ajoute rien et ne retire rien.
2. **Aucune XP.** Une routine se paie en Éclats, et seulement dans la limite de
   son objectif hebdomadaire — au-delà la coche est gardée, la récompense
   s'éteint. Même geste que la dégressivité du §4.4 (SPEC §17).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, time

from .calendar import ROLLOVER_HOUR, week_start

SHARDS_PER_CHECK = 3
WEEK_HELD_BONUS = 10
DAYS_PER_WEEK = 7

# Le sens d'une fenêtre horaire. « Debout avant 7h30 » et « rien après 23h » se
# vérifient de la même façon, dans deux directions.
AVANT = "avant"
APRES = "apres"

REVEIL = "reveil"
APRES_DOUCHE = "apres_douche"
AVANT_COUCHER = "avant_coucher"
FIN_DE_SESSION = "fin_de_session"
LIBRE = "libre"

# Ordre d'affichage du panneau : l'ancre suit le déroulé de la journée, pas
# l'ordre alphabétique (SPEC §11.9 — ancrage sur un geste, pas sur une heure).
ANCHOR_ORDER = (REVEIL, APRES_DOUCHE, FIN_DE_SESSION, AVANT_COUCHER, LIBRE)

ANCHOR_LABELS = {
    REVEIL: "Au réveil",
    APRES_DOUCHE: "Après la douche",
    FIN_DE_SESSION: "En fin de session",
    AVANT_COUCHER: "Avant le coucher",
    LIBRE: "Dans la journée",
}


@dataclass(frozen=True)
class Routine:
    """Une routine réduite à ce dont la règle a besoin.

    ``weekdays`` vide signifie « proposée tous les jours ». Les jours suivent la
    convention de ``date.weekday()`` : 0 = lundi.
    """

    key: str
    name: str
    weekly_target: int
    weekdays: tuple[int, ...] = ()
    anchor: str = LIBRE
    # La fenêtre horaire, facultative. Elle transforme une routine en habitude
    # *horaire* : « se lever tôt » ne veut rien dire si la coche compte à 14h.
    # Le §11.9 ancre les routines sur un geste et non sur une heure, et ça reste
    # vrai — mais deux habitudes échappent à la règle par nature, parce que
    # l'heure **est** l'habitude : le lever et le coucher. Pour toutes les
    # autres, ``deadline`` reste vide et rien ne change.
    deadline: time | None = None
    direction: str = AVANT

    def is_due(self, day: date) -> bool:
        """La routine est-elle proposée ce jour-là ?"""
        return not self.weekdays or day.weekday() in self.weekdays

    @property
    def due_days_per_week(self) -> int:
        return DAYS_PER_WEEK if not self.weekdays else len(self.weekdays)

    @property
    def slack(self) -> int:
        """Oublis tolérés dans la semaine sans perdre le seuil.

        C'est le battement du §11.9. À zéro, la routine redevient une chaîne
        cassable — l'interface doit le signaler comme un réglage risqué.
        """
        return max(0, self.due_days_per_week - self.weekly_target)


def minutes_since_rollover(moment: time, rollover_hour: int = ROLLOVER_HOUR) -> int:
    """Minutes écoulées depuis la bascule de journée, pour une heure locale.

    C'est la seule façon correcte de comparer deux heures dans ce système. La
    journée du coach ne commence pas à minuit mais à 4h (§1), donc 00h20 est
    **tard** dans la journée d'hier, pas tôt dans celle d'aujourd'hui. Comparer
    les heures brutes ferait passer un coucher à 00h20 pour un coucher avant
    23h30, ce qui est exactement le mensonge que la mécanique doit empêcher.
    """
    return ((moment.hour - rollover_hour) * 60 + moment.minute) % (24 * 60)


def within_window(routine: Routine, moment: time, rollover_hour: int = ROLLOVER_HOUR) -> bool:
    """La coche tombe-t-elle dans la fenêtre de la routine ?

    Sans fenêtre déclarée, tout moment convient — c'est le cas de toutes les
    routines du §11.9, qui s'ancrent sur un geste et pas sur une horloge.
    """
    if routine.deadline is None:
        return True
    pose = minutes_since_rollover(moment, rollover_hour)
    limite = minutes_since_rollover(routine.deadline, rollover_hour)
    return pose <= limite if routine.direction == AVANT else pose >= limite


def window_label(routine: Routine) -> str:
    """« avant 7h30 », tel quel sous le nom de la routine. Vide s'il n'y en a pas."""
    if routine.deadline is None:
        return ""
    # « 7h30 » et non « 07h30 » : c'est comme ça qu'on écrit une heure en
    # français, et la ligne se lit sous un nom de routine, pas dans un journal.
    heure = f"{routine.deadline.hour}h{routine.deadline.minute:02d}".replace("h00", "h")
    return f"{'avant' if routine.direction == AVANT else 'après'} {heure}"


@dataclass(frozen=True)
class WeekState:
    """L'état d'une routine sur une semaine. Rien d'autre n'est affiché en grand."""

    routine_key: str
    week_start: date
    done: int
    target: int

    @property
    def held(self) -> bool:
        return self.done >= self.target

    @property
    def remaining(self) -> int:
        return max(0, self.target - self.done)

    @property
    def ratio(self) -> float:
        return round(min(1.0, self.done / max(1, self.target)), 4)

    @property
    def label(self) -> str:
        """« 4 / 6 cette semaine », tel quel sous la ligne du panneau."""
        return f"{self.done} / {self.target}"


@dataclass(frozen=True)
class PanelEntry:
    """Une ligne du panneau de quêtes du jour."""

    routine: Routine
    checked_today: bool
    week: WeekState

    @property
    def shards_if_checked(self) -> int:
        """Ce que rapporterait la coche maintenant. Zéro au-delà de l'objectif."""
        if self.checked_today:
            return 0
        return shards_for_check(self.routine, checks_before_in_week=self.week.done)


def weeks_of(checked_days: Iterable[date]) -> dict[date, int]:
    """Nombre de coches par semaine, indexé sur le lundi de chaque semaine."""
    counts: dict[date, int] = {}
    for day in checked_days:
        start = week_start(day)
        counts[start] = counts.get(start, 0) + 1
    return counts


def week_state(routine: Routine, checked_days: Iterable[date], day: date) -> WeekState:
    """État de la routine sur la semaine contenant ``day``."""
    start = week_start(day)
    done = sum(1 for d in checked_days if week_start(d) == start)
    return WeekState(
        routine_key=routine.key,
        week_start=start,
        done=done,
        target=routine.weekly_target,
    )


def shards_for_check(routine: Routine, *, checks_before_in_week: int) -> int:
    """Éclats d'une coche, en fonction de ce qui a déjà été fait cette semaine.

    Au-delà de l'objectif hebdomadaire la coche ne rapporte plus rien : le fait
    reste enregistré, la récompense s'éteint (SPEC §11.9).
    """
    if checks_before_in_week >= routine.weekly_target:
        return 0
    return SHARDS_PER_CHECK


def held_weeks(routine: Routine, checked_days: Iterable[date]) -> int:
    """Nombre de semaines où la routine a atteint son objectif. Ne redescend jamais."""
    return sum(1 for count in weeks_of(checked_days).values() if count >= routine.weekly_target)


def piste_week_held(
    routines: Iterable[Routine],
    checks_by_key: dict[str, Iterable[date]],
    day: date,
) -> bool:
    """La semaine de la piste est tenue si **chaque** routine active a tenu la sienne.

    Une piste sans routine active n'est pas « tenue » : elle est vide, ce qui
    n'est pas la même chose et ne doit rien créditer.
    """
    routines = list(routines)
    if not routines:
        return False
    return all(
        week_state(r, checks_by_key.get(r.key, ()), day).held for r in routines
    )


def piste_held_weeks(
    routines: Iterable[Routine],
    checks_by_key: dict[str, Iterable[date]],
) -> int:
    """Compteur cumulé de semaines tenues sur la piste — le seul grand chiffre.

    Strictement monotone : une mauvaise semaine n'ajoute rien et ne retire rien.
    """
    routines = list(routines)
    if not routines:
        return 0
    weeks: set[date] = set()
    for days in checks_by_key.values():
        weeks.update(week_start(d) for d in days)
    return sum(
        1
        for start in weeks
        if all(week_state(r, checks_by_key.get(r.key, ()), start).held for r in routines)
    )


def today_panel(
    routines: Iterable[Routine],
    checks_by_key: dict[str, Iterable[date]],
    day: date,
) -> list[PanelEntry]:
    """Les routines attendues aujourd'hui, dans l'ordre des ancres.

    Ne contient que ce qui est dû ce jour-là : le panneau ne montre jamais une
    ligne sur laquelle il n'y a rien à faire (SPEC §0.9).
    """
    entries = []
    for routine in routines:
        if not routine.is_due(day):
            continue
        days = list(checks_by_key.get(routine.key, ()))
        entries.append(
            PanelEntry(
                routine=routine,
                checked_today=day in days,
                week=week_state(routine, days, day),
            )
        )
    order = {anchor: i for i, anchor in enumerate(ANCHOR_ORDER)}
    entries.sort(key=lambda e: (order.get(e.routine.anchor, len(order)), e.routine.name))
    return entries
