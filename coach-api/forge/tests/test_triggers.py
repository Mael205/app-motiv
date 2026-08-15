"""Tests des déclencheurs.

Un gardien qui n'arrive pas est un gardien qui n'existe pas : c'est le seul
mécanisme qui fait exister l'app quand on ne pense pas à elle.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import triggers
from forge.models import (
    DayWindow,
    NotificationLog,
    Profile,
    Project,
    RelaxWindow,
    RoadmapStep,
    Session,
    TimeSlot,
    Track,
)

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


def paris(h: int, m: int = 0, day: date = LUNDI) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, tzinfo=PARIS)


@pytest.fixture
def profile(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(
            profile=profile, weekday=weekday, start_time=time(18), end_time=time(23)
        )
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    project = Project.objects.create(user=user, track=atelier, name="Prototype UE5", slot=1)
    RoadmapStep.objects.create(
        project=project, order=0, label="Écrire le test de collision", state=RoadmapStep.DOING
    )
    return profile


@pytest.fixture
def project(profile):
    return Project.objects.get(user=profile.user)


class TestGardienDuSoir:
    def test_se_declenche_quatre_vingt_dix_minutes_avant_la_fin(self, profile):
        fired = triggers.check_guardian(profile, paris(21, 30))
        assert fired, "la fenêtre finit à 23h, le gardien tombe à 21h30"

    def test_ne_se_declenche_pas_trop_tot(self, profile):
        assert triggers.check_guardian(profile, paris(19, 0)) == []

    def test_propose_une_tache_precise_et_pas_une_morale(self, profile):
        triggers.check_guardian(profile, paris(21, 30))
        log = NotificationLog.objects.get(user=profile.user, kind=triggers.GUARDIAN)
        assert "Écrire le test de collision" in log.body
        assert "10 min" in log.body
        assert "devrais" not in log.body.lower()

    def test_annonce_les_boucliers_restants(self, profile):
        triggers.check_guardian(profile, paris(21, 30))
        log = NotificationLog.objects.get(user=profile.user, kind=triggers.GUARDIAN)
        assert "Boucliers : 2" in log.body

    def test_se_tait_si_la_journee_est_deja_validee(self, profile, project):
        Session.objects.create(
            user=profile.user,
            project=project,
            coach_day=LUNDI,
            started_at=paris(19, 0),
            ended_at=paris(19, 25),
            actual_minutes=25,
            status=Session.DONE,
        )
        assert triggers.check_guardian(profile, paris(21, 30)) == []

    def test_se_tait_si_une_session_tourne(self, profile, project):
        Session.objects.create(
            user=profile.user,
            project=project,
            coach_day=LUNDI,
            started_at=paris(21, 20),
            status=Session.RUNNING,
        )
        assert triggers.check_guardian(profile, paris(21, 30)) == []

    def test_ne_se_declenche_qu_une_fois_par_soir(self, profile):
        assert triggers.check_guardian(profile, paris(21, 30))
        assert triggers.check_guardian(profile, paris(21, 32)) == []
        assert NotificationLog.objects.filter(kind=triggers.GUARDIAN).count() == 1

    def test_suit_la_fenetre_du_jour(self, profile):
        """Fenêtre du samedi 10h-23h : le gardien reste calé sur sa fin."""
        samedi = date(2026, 3, 7)
        DayWindow.objects.filter(profile=profile, weekday=5).update(start_time=time(10))
        assert triggers.check_guardian(profile, paris(21, 30, samedi))


class TestRappelDeCreneau:
    def test_previent_dix_minutes_avant(self, profile, project):
        TimeSlot.objects.create(project=project, weekday=0, start_time=time(20, 30))
        fired = triggers.check_slot_reminder(profile, paris(20, 22))
        assert fired and fired[0]["project"] == "Prototype UE5"

    def test_ne_previent_pas_trop_tot(self, profile, project):
        TimeSlot.objects.create(project=project, weekday=0, start_time=time(20, 30))
        assert triggers.check_slot_reminder(profile, paris(19, 0)) == []

    def test_ignore_les_creneaux_des_autres_jours(self, profile, project):
        TimeSlot.objects.create(project=project, weekday=3, start_time=time(20, 30))
        assert triggers.check_slot_reminder(profile, paris(20, 22)) == []


class TestSasDeDetente:
    def test_annonce_la_fin_du_sas(self, profile):
        RelaxWindow.objects.create(
            user=profile.user, coach_day=LUNDI, started_at=paris(19, 0), ends_at=paris(19, 30)
        )
        assert triggers.check_relax_end(profile, paris(19, 31))

    def test_se_tait_si_la_journee_a_ete_validee_entre_temps(self, profile, project):
        RelaxWindow.objects.create(
            user=profile.user, coach_day=LUNDI, started_at=paris(19, 0), ends_at=paris(19, 30)
        )
        Session.objects.create(
            user=profile.user,
            project=project,
            coach_day=LUNDI,
            started_at=paris(18, 0),
            ended_at=paris(18, 25),
            actual_minutes=25,
            status=Session.DONE,
        )
        assert triggers.check_relax_end(profile, paris(19, 31)) == []


class TestPasseComplete:
    def test_run_all_reste_silencieux_hors_fenetre(self, profile):
        assert triggers.run_all(paris(15, 0)) == []

    def test_run_all_declenche_le_gardien(self, profile):
        fired = triggers.run_all(paris(21, 30))
        assert any(event["kind"] == triggers.GUARDIAN for event in fired)
