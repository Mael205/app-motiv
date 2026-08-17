"""Tests du mode veille (pause déclarée longue).

Le manque qu'elle comble est le plus dangereux du système : les jours off sont
plafonnés à deux par semaine, et rien ne couvrait des vacances, une grippe ou
une semaine de partiels. Un système sans pause n'en offre qu'une, la
désinstallation.

Ce qui se teste ici est donc : que rien ne casse pendant, que rien ne se
construise non plus, que la saison soit rendue intacte, et qu'on en sorte sans
rien demander à personne.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import services, triggers
from forge.models import DayWindow, Hiatus, Profile, Project, Season, Session, Track
from forge.rules import hiatus as regles
from forge.rules import streak as streak_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


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


def session(user, jour: date):
    Session.objects.create(
        user=user,
        project=Project.objects.get(user=user),
        coach_day=jour,
        started_at=datetime(jour.year, jour.month, jour.day, 19, tzinfo=PARIS),
        actual_minutes=25,
        status=Session.DONE,
    )


class TestLesRegles:
    def test_trois_jours_minimum(self):
        verdict = regles.verifier(debut=LUNDI, fin=LUNDI + timedelta(days=1), aujourdhui=LUNDI)
        assert not verdict.ok and "jour off" in verdict.raison

    def test_jamais_retroactive(self):
        """Comme le jour off du §11.5 : sinon c'est l'excuse écrite le lendemain."""
        verdict = regles.verifier(
            debut=LUNDI - timedelta(days=2), fin=LUNDI + timedelta(days=5), aujourdhui=LUNDI
        )
        assert not verdict.ok and "après coup" in verdict.raison

    def test_quatre_semaines_maximum(self):
        verdict = regles.verifier(debut=LUNDI, fin=LUNDI + timedelta(days=40), aujourdhui=LUNDI)
        assert not verdict.ok and "ferme la saison" in verdict.raison

    def test_une_semaine_passe(self):
        assert regles.verifier(debut=LUNDI, fin=LUNDI + timedelta(days=6), aujourdhui=LUNDI).ok

    def test_le_message_ne_fait_pas_de_decompte_anxiogene(self):
        texte = regles.message(LUNDI, LUNDI + timedelta(days=6)).lower()
        for mot in ("perdu", "reste", "attention", "streak"):
            assert mot not in texte


@pytest.mark.django_db
class TestCeQuiSePasse:
    def test_les_jours_de_veille_sont_neutres(self, user):
        session(user, LUNDI)
        services.declarer_veille(
            user, debut=LUNDI + timedelta(days=1), fin=LUNDI + timedelta(days=7), today=LUNDI
        )

        atelier = Track.objects.get(user=user)
        jours = services.resolve_days(user, atelier, until=LUNDI + timedelta(days=7))
        etats = {j.date: j.state for j in jours}

        assert etats[LUNDI + timedelta(days=3)] == streak_rules.DayState.NEUTRE
        assert etats[LUNDI + timedelta(days=7)] == streak_rules.DayState.NEUTRE

    def test_le_streak_survit_a_une_semaine_d_absence(self, user):
        for jour in range(3):
            session(user, LUNDI + timedelta(days=jour))
        services.declarer_veille(
            user,
            debut=LUNDI + timedelta(days=3),
            fin=LUNDI + timedelta(days=9),
            today=LUNDI + timedelta(days=2),
        )

        atelier = Track.objects.get(user=user)
        etat = services.streak_state(user, atelier, today=LUNDI + timedelta(days=10))
        assert etat.current == 3, "trois jours travaillés, et rien de cassé depuis"

    def test_aucun_declencheur_ne_part(self, user):
        services.declarer_veille(
            user, debut=LUNDI, fin=LUNDI + timedelta(days=6), today=LUNDI
        )
        # 21h30 un jour de veille : le gardien se tairait de toute façon si la
        # journée était validée, ici il doit se taire parce qu'on est absent.
        assert triggers.run_all(datetime(2026, 3, 2, 21, 30, tzinfo=PARIS)) == []

    def test_la_saison_est_gelee_puis_rendue_intacte(self, user):
        saison = Season.objects.get(user=user)
        fin_prevue = saison.ends_on

        services.declarer_veille(
            user, debut=LUNDI, fin=LUNDI + timedelta(days=6), today=LUNDI
        )
        saison.refresh_from_db()
        assert saison.status == Season.PAUSED

        services.synchroniser_veille(user, today=LUNDI + timedelta(days=7))
        saison.refresh_from_db()
        assert saison.status == Season.RUNNING
        assert saison.ends_on == fin_prevue + timedelta(days=7), "sept jours gelés, sept rendus"

    def test_la_reprise_ne_rallonge_pas_deux_fois(self, user):
        """Deux lectures de l'accueil ne doivent pas rendre les jours en double."""
        services.declarer_veille(
            user, debut=LUNDI, fin=LUNDI + timedelta(days=6), today=LUNDI
        )
        services.synchroniser_veille(user, today=LUNDI + timedelta(days=7))
        fin = Season.objects.get(user=user).ends_on

        services.synchroniser_veille(user, today=LUNDI + timedelta(days=8))
        assert Season.objects.get(user=user).ends_on == fin

    def test_on_en_sort_quand_on_veut(self, user):
        services.declarer_veille(
            user, debut=LUNDI, fin=LUNDI + timedelta(days=20), today=LUNDI
        )
        services.terminer_veille(
            user, today=LUNDI + timedelta(days=3), now=datetime(2026, 3, 5, 12, tzinfo=PARIS)
        )

        assert services.veille_en_cours(user, today=LUNDI + timedelta(days=4)) is None
        saison = Season.objects.get(user=user)
        assert saison.status == Season.RUNNING

    def test_les_jours_d_apres_une_sortie_redeviennent_normaux(self, user):
        session(user, LUNDI)
        services.declarer_veille(
            user, debut=LUNDI + timedelta(days=1), fin=LUNDI + timedelta(days=20), today=LUNDI
        )
        services.terminer_veille(
            user, today=LUNDI + timedelta(days=3), now=datetime(2026, 3, 5, 12, tzinfo=PARIS)
        )

        atelier = Track.objects.get(user=user)
        etats = {
            j.date: j.state
            for j in services.resolve_days(user, atelier, until=LUNDI + timedelta(days=6))
        }
        assert etats[LUNDI + timedelta(days=2)] == streak_rules.DayState.NEUTRE
        assert etats[LUNDI + timedelta(days=6)] == streak_rules.DayState.RATEE

    def test_deux_veilles_en_meme_temps_sont_refusees(self, user):
        services.declarer_veille(
            user, debut=LUNDI, fin=LUNDI + timedelta(days=6), today=LUNDI
        )
        with pytest.raises(ValueError, match="déjà en cours"):
            services.declarer_veille(
                user, debut=LUNDI + timedelta(days=2), fin=LUNDI + timedelta(days=8), today=LUNDI
            )

    def test_par_l_api(self, client, user):
        """Déclarée pour dans deux jours : l'API refuse tout ce qui est passé."""
        from django.utils import timezone

        client.force_login(user)
        debut = timezone.now().date() + timedelta(days=2)
        reponse = client.post(
            "/api/veille",
            {"debut": debut.isoformat(), "fin": (debut + timedelta(days=6)).isoformat()},
            content_type="application/json",
        )
        assert reponse.status_code == 201, reponse.content
        assert Hiatus.objects.filter(user=user).exists()
        assert client.get("/api/veille").json()["active"] is False, "elle commence dans deux jours"

    def test_l_api_refuse_une_veille_retroactive(self, client, user):
        from django.utils import timezone

        client.force_login(user)
        debut = timezone.now().date() - timedelta(days=3)
        reponse = client.post(
            "/api/veille",
            {"debut": debut.isoformat(), "fin": (debut + timedelta(days=6)).isoformat()},
            content_type="application/json",
        )
        assert reponse.status_code == 400 and "après coup" in reponse.json()["detail"]
