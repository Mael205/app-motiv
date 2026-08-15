"""Bascule de journée et fenêtre du soir.

La journée du coach ne commence pas à minuit mais à 4h du matin : une session
terminée à 00h30 valide la veille (SPEC §1). Toute la logique de date passe
par ici — aucun `date.today()` ne doit traîner ailleurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ROLLOVER_HOUR = 4


def coach_day(moment: datetime, tz: str = "Europe/Paris", rollover_hour: int = ROLLOVER_HOUR) -> date:
    """La journée du coach à laquelle appartient un instant donné."""
    local = moment.astimezone(ZoneInfo(tz))
    if local.hour < rollover_hour:
        local -= timedelta(days=1)
    return local.date()


def day_bounds(
    day: date, tz: str = "Europe/Paris", rollover_hour: int = ROLLOVER_HOUR
) -> tuple[datetime, datetime]:
    """Début et fin (exclusive) d'une journée du coach, en UTC."""
    zone = ZoneInfo(tz)
    start = datetime.combine(day, time(rollover_hour), tzinfo=zone)
    return start, start + timedelta(days=1)


@dataclass(frozen=True)
class EveningWindow:
    """La fenêtre du soir du jour, celle que la jauge représente."""

    day: date
    start: datetime
    end: datetime

    @property
    def total_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    def elapsed_minutes(self, now: datetime) -> int:
        if now <= self.start:
            return 0
        return min(self.total_minutes, int((now - self.start).total_seconds() // 60))

    def ratio(self, now: datetime) -> float:
        return round(self.elapsed_minutes(now) / max(1, self.total_minutes), 4)


def evening_window(
    day: date,
    windows_by_weekday: dict[int, tuple[time, time]],
    tz: str = "Europe/Paris",
) -> EveningWindow:
    """Fenêtre du soir pour une journée, paramétrable par jour de semaine.

    ``windows_by_weekday`` est indexé sur ``date.weekday()`` (0 = lundi).
    """
    zone = ZoneInfo(tz)
    start_t, end_t = windows_by_weekday.get(day.weekday(), (time(18), time(23)))
    start = datetime.combine(day, start_t, tzinfo=zone)
    end = datetime.combine(day, end_t, tzinfo=zone)
    if end <= start:                      # fenêtre qui déborde après minuit
        end += timedelta(days=1)
    return EveningWindow(day=day, start=start, end=end)


def week_start(day: date) -> date:
    """Lundi de la semaine d'une journée du coach."""
    return day - timedelta(days=day.weekday())
