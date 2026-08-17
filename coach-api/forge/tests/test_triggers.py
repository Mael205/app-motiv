"""Tests des déclencheurs.

Un gardien qui n'arrive pas est un gardien qui n'existe pas : c'est le seul
mécanisme qui fait exister l'app quand on ne pense pas à elle.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import triggers
from forge.llm import set_provider
from forge.llm.fake import ScriptedProvider, UnavailableProvider
from forge.models import (
    DayWindow,
    JournalEntry,
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


class TestGardienDecoupeParLeModele:
    """§5.4 : l'étape vaut une à trois séances, la notification en promet dix minutes.

    Le modèle est là pour couper. Il n'est là que pour ça, et il ne peut rien
    casser : chaque échec ci-dessous doit rendre le gardien du repli, à
    l'identique.
    """

    def test_le_modele_decoupe_l_etape(self, profile):
        set_provider(ScriptedProvider([{"tache": "Écrire le cas du mur dans test_collision.py"}]))
        triggers.check_guardian(profile, paris(21, 30))
        log = NotificationLog.objects.get(user=profile.user, kind=triggers.GUARDIAN)
        assert "10 min : Écrire le cas du mur dans test_collision.py" in log.body
        assert "Boucliers : 2" in log.body, "le système garde la main sur ce qu'il ajoute"

    def test_le_modele_recoit_l_etape_et_le_temps_restant(self, profile):
        fournisseur = ScriptedProvider([{"tache": "Écrire le cas du mur dans test_collision.py"}])
        set_provider(fournisseur)
        triggers.check_guardian(profile, paris(21, 30))
        prompt = fournisseur.calls[0]["prompt"]
        assert "Écrire le test de collision" in prompt
        assert "90 minutes" in prompt

    def test_sans_modele_le_gardien_part_quand_meme(self, profile):
        set_provider(UnavailableProvider())
        assert triggers.check_guardian(profile, paris(21, 30))
        log = NotificationLog.objects.get(user=profile.user, kind=triggers.GUARDIAN)
        assert "Écrire le test de collision" in log.body

    def test_une_reponse_floue_retombe_sur_le_repli(self, profile):
        """La porte refuse, et le soir continue comme si rien n'avait été tenté."""
        set_provider(ScriptedProvider([{"tache": "Avancer sur le prototype"}]))
        assert triggers.check_guardian(profile, paris(21, 30))
        log = NotificationLog.objects.get(user=profile.user, kind=triggers.GUARDIAN)
        assert "Écrire le test de collision" in log.body
        assert "Avancer" not in log.body

    def test_un_modele_qui_moralise_est_ecarte(self, profile):
        set_provider(ScriptedProvider([{"tache": "Allez, écris le test de collision maintenant"}]))
        triggers.check_guardian(profile, paris(21, 30))
        log = NotificationLog.objects.get(user=profile.user, kind=triggers.GUARDIAN)
        assert "Allez" not in log.body

    def test_l_amorce_prime_sur_l_etape_dans_le_repli(self, profile, project):
        """Le §11.3 : l'amorce a été payée pendant que le contexte était chaud."""
        session = Session.objects.create(
            user=profile.user,
            project=project,
            coach_day=LUNDI - timedelta(days=1),
            started_at=paris(19, 0),
            ended_at=paris(19, 25),
            actual_minutes=25,
            status=Session.DONE,
        )
        JournalEntry.objects.create(
            session=session, next_action="Brancher le raycast sur le mur de gauche"
        )
        set_provider(UnavailableProvider())
        triggers.check_guardian(profile, paris(21, 30))
        log = NotificationLog.objects.get(user=profile.user, kind=triggers.GUARDIAN)
        assert "Brancher le raycast" in log.body

    def test_les_blocages_du_dernier_debrief_sont_donnes_au_modele(self, profile, project):
        """§5.2 : buter deux fois sur la même chose à 21h30 fait refermer l'app."""
        session = Session.objects.create(
            user=profile.user,
            project=project,
            coach_day=LUNDI - timedelta(days=1),
            started_at=paris(19, 0),
            ended_at=paris(19, 25),
            actual_minutes=25,
            status=Session.DONE,
        )
        JournalEntry.objects.create(
            session=session,
            next_action="Brancher le raycast sur le mur de gauche",
            blockers=["le collider du mur est en trigger"],
        )
        fournisseur = ScriptedProvider([{"tache": "Basculer le collider du mur hors trigger"}])
        set_provider(fournisseur)
        triggers.check_guardian(profile, paris(21, 30))
        assert "collider du mur est en trigger" in fournisseur.calls[0]["prompt"]


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
