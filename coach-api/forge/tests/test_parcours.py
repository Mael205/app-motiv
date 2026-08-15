"""Test d'intégration du parcours réel : la soirée normale du SPEC §15.

Il ouvre l'accueil, démarre la session proposée, la termine, et vérifie que
l'XP, les dégâts au boss et le streak ont bougé comme prévu.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import services
from forge.models import Profile, Project, Season, Session, Track
from forge.rules.calendar import coach_day


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    today = coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour)
    Project.objects.create(user=user, track=atelier, name="Prototype UE5", slot=1)
    services.open_season(user, starts_on=today, stake=100)
    return user


@pytest.fixture
def project(user):
    return Project.objects.get(user=user, name="Prototype UE5")


class TestAccueil:
    def test_l_accueil_propose_une_seule_chose(self, user):
        state = services.home_state(user)
        assert state["proposal"] is not None
        assert state["proposal"]["project"]["name"] == "Prototype UE5"
        assert state["proposal"]["minutes"] in (10, 25, 50)

    def test_l_accueil_expose_la_saison_et_le_boss(self, user):
        state = services.home_state(user)
        assert state["season"]["name"]
        assert state["boss"]["ratio"] == 1.0, "le boss est intact avant la première session"

    def test_journee_non_validee_au_depart(self, user):
        state = services.home_state(user)
        assert state["validated_today"] is False
        assert state["required_minutes"] == 25

    def test_le_coach_nest_jamais_ce_que_lapp_propose(self, user):
        """SPEC §11.6 : accessible en un tap, jamais promu par le système."""
        atelier = Track.objects.get(user=user, kind=Track.ATELIER)
        Project.objects.create(
            user=user, track=atelier, name="Développement du coach", is_coach_project=True
        )
        proposal = services.home_state(user)["proposal"]
        assert proposal["project"]["name"] == "Prototype UE5"

    def test_aucune_proposition_si_seul_le_coach_est_actif(self, user, project):
        atelier = Track.objects.get(user=user, kind=Track.ATELIER)
        project.delete()
        Project.objects.create(
            user=user, track=atelier, name="Développement du coach", is_coach_project=True
        )
        assert services.home_state(user)["proposal"] is None


class TestParcoursDeSession:
    def test_soiree_normale_de_bout_en_bout(self, user, project):
        session = services.start_session(user, project, planned_minutes=25)
        assert session.status == Session.RUNNING
        assert session.rank_in_day == 1

        state = services.home_state(user)
        assert state["running_session"]["id"] == session.id

        result = services.end_session(
            session,
            now=session.started_at + timedelta(minutes=25),
            note="Détection de collision branchée.",
            next_action="Écrire le test de capture du survivant.",
        )

        assert result["minutes"] == 25
        assert result["xp"] > 0
        assert result["boss_damage"] == 25

        state = services.home_state(user)
        assert state["validated_today"] is True
        assert state["boss"]["current_hp"] == state["boss"]["max_hp"] - 25
        assert state["progression"]["total_xp"] == result["xp"]

    def test_l_amorce_est_conservee_et_reproposee(self, user, project):
        session = services.start_session(user, project, planned_minutes=25)
        services.end_session(
            session,
            now=session.started_at + timedelta(minutes=25),
            next_action="Écrire le test de capture.",
        )
        state = services.home_state(user)
        assert state["proposal"]["amorce"] == "Écrire le test de capture."

    def test_deux_sessions_simultanees_refusees(self, user, project):
        services.start_session(user, project, planned_minutes=25)
        with pytest.raises(ValueError):
            services.start_session(user, project, planned_minutes=25)

    def test_le_mode_degrade_valide_la_journee(self, user, project):
        session = services.start_session(user, project, planned_minutes=10)
        assert session.mode == Session.DEGRADED
        services.end_session(
            session, now=session.started_at + timedelta(minutes=10), next_action="Suite demain."
        )
        assert services.home_state(user)["validated_today"] is True

    def test_les_minutes_ne_depassent_jamais_le_prevu(self, user, project):
        """Impossible de déclarer après coup une session de 3h (SPEC §6)."""
        session = services.start_session(user, project, planned_minutes=25)
        services.end_session(session, now=session.started_at + timedelta(hours=3), next_action="x")
        session.refresh_from_db()
        assert session.actual_minutes == 25

    def test_une_session_sous_le_plancher_ne_rapporte_rien(self, user, project):
        """Démarrer puis arrêter aussitôt ne doit donner aucune XP (SPEC §17)."""
        session = services.start_session(user, project, planned_minutes=25)
        result = services.end_session(
            session, now=session.started_at + timedelta(minutes=2), next_action="x"
        )
        assert result["aborted"] is True
        assert result["xp"] == 0
        assert result["boss_damage"] == 0

        session.refresh_from_db()
        assert session.status == Session.ABANDONED
        state = services.home_state(user)
        assert state["validated_today"] is False
        assert state["progression"]["total_xp"] == 0

    def test_le_plafond_de_regime_s_applique_sur_la_journee(self, user, project):
        """La 5ᵉ session du jour ne rapporte plus d'XP mais reste enregistrée."""
        xps = []
        for _ in range(5):
            session = services.start_session(user, project, planned_minutes=25)
            result = services.end_session(
                session, now=session.started_at + timedelta(minutes=25), next_action="suite"
            )
            xps.append(result["xp"])

        assert xps[0] > 0 and xps[1] > 0 and xps[2] > 0
        assert xps[3] < xps[2], "la 4ᵉ est réduite"
        assert xps[4] == 0, "la 5ᵉ ne rapporte plus rien"
        assert Session.objects.filter(user=user, status=Session.DONE).count() == 5
        assert services.home_state(user)["minutes_today"] == 125, "les heures comptent quand même"


class TestSaison:
    def test_ouverture_de_saison_cree_un_boss(self, user):
        season = Season.objects.get(user=user, status=Season.RUNNING)
        assert season.boss.max_hp > 0
        assert season.name and season.accent.startswith("#")

    def test_deux_saisons_ne_portent_pas_le_meme_nom(self, user):
        first = Season.objects.get(user=user)
        first.status = Season.CLOSED
        first.save()
        second = services.open_season(user, starts_on=first.ends_on + timedelta(days=3))
        assert second.name != first.name
        assert second.index == first.index + 1
