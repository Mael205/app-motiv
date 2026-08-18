"""Le fantôme en direct (§12.7, ajout du 17 août 2026).

L'écart au fantôme existait déjà, mais seulement en fin de journée : il
arrivait quand la soirée était finie, c'est-à-dire quand plus rien ne pouvait
en être fait. Un bilan ne fait rien démarrer.

Ce qui se teste ici est la seule chose qui rend la version en direct honnête :
**la position du fantôme à 21h n'est pas la moitié de sa journée**. Elle est
tirée de la répartition horaire réelle du travail passé, et le repli linéaire
n'est utilisé que faute de données — jamais présenté comme une mesure.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import progression, services
from forge.models import DayWindow, Profile, Project, Season, Session, Track
from forge.rules import phantom as regles

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


class TestLaRepartitionHoraire:
    def test_sous_l_echantillon_minimal_elle_se_tait(self):
        """Trois soirées ne disent rien de l'heure à laquelle on travaille."""
        assert regles.hourly_shares({21: 60, 22: 30}) is None

    def test_elle_commence_a_la_bascule_du_coach(self):
        """2h du matin est la fin d'une journée, pas le début de la suivante."""
        parts = regles.hourly_shares({21: 600, 2: 600}, rollover_hour=4)
        # 21h est la 17ᵉ heure de la journée du coach, 2h la 22ᵉ.
        assert parts[17] == pytest.approx(0.0)
        assert parts[18] == pytest.approx(0.5)
        assert parts[-1] == pytest.approx(1.0)

    def test_elle_est_croissante(self):
        parts = regles.hourly_shares({h: 100 for h in range(24)})
        assert all(b >= a for a, b in zip(parts, parts[1:]))


class TestLaPartAUneHeure:
    def test_elle_s_interpole_dans_l_heure(self):
        parts = regles.hourly_shares({20: 600, 21: 600}, rollover_hour=4)
        assert regles.share_at(parts, hour=20, minute=30, rollover_hour=4) == pytest.approx(0.25)
        assert regles.share_at(parts, hour=21, minute=0, rollover_hour=4) == pytest.approx(0.5)

    def test_sans_repartition_le_repli_est_lineaire(self):
        assert regles.share_at(None, hour=16, minute=0, rollover_hour=4) == pytest.approx(0.5)


class TestLaPosition:
    def test_le_fantome_avance_dans_sa_journee(self):
        fantome = regles.Curve("Ragnarök", (100, 200, 300))
        milieu = regles.live(
            mine_now=150, mine_today=50, phantom=fantome, day_index=1, share=0.5, hour_label="21h00"
        )
        assert milieu.theirs == 150 and milieu.delta == 0
        # La même chose ramenée à aujourd'hui : la jauge du soir n'affiche que ça.
        assert milieu.theirs_today == 50 and milieu.delta_today == 0

    def test_le_premier_jour_part_de_zero(self):
        """Sans ce cas, le fantôme démarrerait la saison à son total du jour 1."""
        fantome = regles.Curve("Ragnarök", (100, 200))
        debut = regles.live(
            mine_now=0, mine_today=0, phantom=fantome, day_index=0, share=0.0, hour_label="18h00"
        )
        assert debut.theirs == 0

    def test_la_ligne_porte_l_heure_et_jamais_de_reproche(self):
        fantome = regles.Curve("Ragnarök", (100, 200, 300))
        derriere = regles.live(
            mine_now=50, mine_today=50, phantom=fantome, day_index=1, share=0.5, hour_label="21h40"
        )
        assert "21h40" in derriere.line and "est devant" in derriere.line
        for mot in ("retard", "relâché", "seulement", "devrais"):
            assert mot not in derriere.line.lower()

    def test_sans_fantome_il_ne_dit_rien(self):
        muet = regles.live(
            mine_now=50, mine_today=50, phantom=None, day_index=1, share=0.5, hour_label="21h40"
        )
        assert not muet.available and muet.line == ""


@pytest.mark.django_db
class TestSurLaJauge:
    def test_le_panneau_porte_le_direct(self, user):
        panneau = progression.phantom_panel(
            user, today=LUNDI, now=datetime(2026, 3, 2, 21, 30, tzinfo=PARIS)
        )
        assert "live" in panneau
        assert panneau["live"]["mine"] == panneau["mine"]

    def test_les_minutes_s_etalent_sur_les_heures_traversees(self, user):
        """Une session de 21h50 à 22h40 a travaillé dix minutes à 21h."""
        Session.objects.create(
            user=user,
            project=Project.objects.get(user=user),
            coach_day=LUNDI,
            started_at=datetime(2026, 3, 2, 21, 50, tzinfo=PARIS),
            actual_minutes=50,
            status=Session.DONE,
        )
        par_heure = progression._minutes_by_hour(user)
        assert par_heure == {21: 10, 22: 40}


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
    services.open_season(user, starts_on=LUNDI, stake=100)
    return user
