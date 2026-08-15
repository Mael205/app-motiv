"""Tests de la bascule de journée à 4h et de la fenêtre du soir."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from forge.rules.calendar import coach_day, day_bounds, evening_window, week_start

PARIS = ZoneInfo("Europe/Paris")


def paris(y, m, d, h, minute=0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=PARIS)


class TestBasculeDeJournee:
    def test_soiree_normale(self):
        assert coach_day(paris(2026, 3, 2, 21)) == date(2026, 3, 2)

    def test_apres_minuit_valide_la_veille(self):
        """Tant qu'il ne s'est pas couché, c'est le même soir (SPEC §1)."""
        assert coach_day(paris(2026, 3, 3, 0, 30)) == date(2026, 3, 2)
        assert coach_day(paris(2026, 3, 3, 3, 59)) == date(2026, 3, 2)

    def test_apres_quatre_heures_on_change_de_jour(self):
        assert coach_day(paris(2026, 3, 3, 4, 0)) == date(2026, 3, 3)

    def test_conversion_depuis_utc(self):
        moment = datetime(2026, 3, 2, 23, 30, tzinfo=ZoneInfo("UTC"))  # 00h30 à Paris
        assert coach_day(moment) == date(2026, 3, 2)

    def test_bornes_de_journee(self):
        debut, fin = day_bounds(date(2026, 3, 2))
        assert debut.astimezone(PARIS).hour == 4
        assert (fin - debut).days == 1


class TestFenetreDuSoir:
    semaine = {i: (time(18), time(23)) for i in range(5)}
    week_end = {5: (time(10), time(23)), 6: (time(10), time(23))}

    def test_fenetre_de_semaine(self):
        w = evening_window(date(2026, 3, 2), self.semaine)   # lundi
        assert w.total_minutes == 300

    def test_fenetre_de_week_end_parametrable(self):
        w = evening_window(date(2026, 3, 7), {**self.semaine, **self.week_end})  # samedi
        assert w.total_minutes == 780

    def test_valeur_par_defaut_si_le_jour_nest_pas_configure(self):
        w = evening_window(date(2026, 3, 7), self.semaine)
        assert w.total_minutes == 300

    def test_curseur_temps_reel(self):
        w = evening_window(date(2026, 3, 2), self.semaine)
        assert w.elapsed_minutes(paris(2026, 3, 2, 17)) == 0
        assert w.elapsed_minutes(paris(2026, 3, 2, 20, 30)) == 150
        assert w.ratio(paris(2026, 3, 2, 20, 30)) == 0.5
        assert w.elapsed_minutes(paris(2026, 3, 3, 2)) == 300, "jamais au-delà de la fin"


def test_debut_de_semaine_est_un_lundi():
    assert week_start(date(2026, 3, 7)) == date(2026, 3, 2)
    assert week_start(date(2026, 3, 2)) == date(2026, 3, 2)
