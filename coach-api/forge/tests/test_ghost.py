"""Tests de la session fantôme (SPEC §8.7).

Le cas réel : une session lancée, le téléphone sonne, la soirée part ailleurs,
et le minuteur tourne encore à minuit.

La faute à éviter absolument est **la fermeture d'une session qui travaillait
encore**. Elle est invisible — personne ne remarque une session close à 22h10
au lieu de 22h40 — et elle porte sur ce que le système existe pour compter.
D'où deux verrous : une marge de dépassement, et le refus de conclure quand la
sonde n'a rien mesuré.
"""

from datetime import datetime, timedelta, timezone

import pytest

from forge.rules.ghost import GRACE_MINUTES, evaluate

DEBUT = datetime(2026, 3, 2, 20, 30, tzinfo=timezone.utc)


def verdict(*, planned=25, apres_minutes=60, inactif_depuis=None, sans_mesure=False):
    now = DEBUT + timedelta(minutes=apres_minutes)
    last = None if sans_mesure else now - timedelta(minutes=inactif_depuis if inactif_depuis is not None else 30)
    return evaluate(started_at=DEBUT, planned_minutes=planned, now=now, last_active_at=last)


class TestPasUnFantome:
    def test_une_session_dans_les_temps(self):
        v = verdict(apres_minutes=20, inactif_depuis=1)
        assert not v.is_ghost and "n'a pas encore dépassé" in v.reason

    def test_un_depassement_dans_la_marge_est_normal(self):
        """Finir sa phrase, relire son test : ce n'est pas de l'inactivité."""
        v = verdict(planned=25, apres_minutes=25 + GRACE_MINUTES - 1, inactif_depuis=1)
        assert not v.is_ghost

    def test_une_session_qui_travaille_encore_n_est_pas_fermee(self):
        v = verdict(apres_minutes=90, inactif_depuis=2)
        assert not v.is_ghost and "tourne encore" in v.reason

    def test_sans_mesure_on_ne_conclut_pas(self):
        """La même asymétrie qu'au §11.10 : une sonde muette ne prouve rien."""
        v = verdict(apres_minutes=180, sans_mesure=True)
        assert not v.is_ghost
        assert "absence de données" in v.reason

    def test_une_mesure_anterieure_au_demarrage_est_inutilisable(self):
        now = DEBUT + timedelta(hours=3)
        v = evaluate(
            started_at=DEBUT,
            planned_minutes=25,
            now=now,
            last_active_at=DEBUT - timedelta(minutes=10),
        )
        assert not v.is_ghost and "précède le démarrage" in v.reason


class TestFantome:
    def test_depassement_et_inactivite_prolongee(self):
        v = verdict(planned=25, apres_minutes=180, inactif_depuis=120)
        assert v.is_ghost

    def test_la_cloture_se_fait_au_dernier_instant_prouve(self):
        """Le temps entre la dernière activité et maintenant n'a pas été travaillé."""
        now = DEBUT + timedelta(minutes=180)
        dernier = DEBUT + timedelta(minutes=22)
        v = evaluate(started_at=DEBUT, planned_minutes=25, now=now, last_active_at=dernier)
        assert v.is_ghost
        assert v.close_at == dernier
        assert v.active_minutes == 22

    def test_le_motif_est_chiffre(self):
        v = verdict(planned=25, apres_minutes=180, inactif_depuis=120)
        assert "min" in v.reason and "aucune activité" in v.reason


@pytest.mark.django_db
class TestClotureEnBase:
    @pytest.fixture
    def session(self, django_user_model):
        from django.utils import timezone as dj

        from forge import services
        from forge.models import Profile, Project, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        track = Track.objects.create(user=user, kind=Track.ATELIER)
        projet = Project.objects.create(user=user, track=track, name="P", slot=1)
        s = services.start_session(user, projet, planned_minutes=25)
        s.started_at = dj.now() - timedelta(hours=3)
        s.save(update_fields=["started_at"])
        return s

    def test_une_session_fantome_est_close_aux_minutes_reelles(self, session):
        from forge import services
        from forge.models import Session

        dernier = session.started_at + timedelta(minutes=22)
        resultat = services.close_ghost_session(session, last_active_at=dernier)

        session.refresh_from_db()
        assert resultat["closed"]
        assert session.status == Session.DONE
        assert session.actual_minutes == 22, "ni 25 planifiées, ni 180 écoulées"

    def test_sans_mesure_la_session_reste_ouverte(self, session):
        from forge import services
        from forge.models import Session

        resultat = services.close_ghost_session(session, last_active_at=None)
        session.refresh_from_db()
        assert not resultat["closed"]
        assert session.status == Session.RUNNING

    def test_l_agent_ne_decide_pas_a_la_place_du_serveur(self, django_user_model):
        """Un agent compromis ne doit pas pouvoir fermer une session en cours."""
        from django.utils import timezone as dj

        from forge import services
        from forge.models import Profile, Project, Session, Track

        user = django_user_model.objects.create_user(username="autre", password="coach")
        Profile.objects.create(user=user)
        track = Track.objects.create(user=user, kind=Track.ATELIER)
        projet = Project.objects.create(user=user, track=track, name="Q", slot=1)
        fraiche = services.start_session(user, projet, planned_minutes=50)

        # L'agent prétend qu'il n'y a plus d'activité : le serveur refuse quand
        # même, la session vient de démarrer.
        resultat = services.close_ghost_session(
            fraiche, last_active_at=dj.now() - timedelta(hours=2)
        )
        fraiche.refresh_from_db()
        assert not resultat["closed"]
        assert fraiche.status == Session.RUNNING


@pytest.mark.django_db
class TestEtatDeLAgent:
    def test_l_etat_ne_contient_ni_garde_ni_journal(self, django_user_model):
        """Le jeton de sonde peut fuir : il ne doit rien donner de plus."""
        from forge import services
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)

        etat = services.agent_state(user)
        assert set(etat) == {"now", "day", "running_session", "notifications"}

    def test_l_etat_donne_le_nom_du_projet_jamais_une_commande(self, django_user_model):
        """Le serveur ne transmet aucune commande — c'est la règle du §8."""
        from forge import services
        from forge.models import Profile, Project, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        track = Track.objects.create(user=user, kind=Track.ATELIER)
        projet = Project.objects.create(user=user, track=track, name="Bestiaire", slot=1)
        services.start_session(user, projet, planned_minutes=25)

        courante = services.agent_state(user)["running_session"]
        assert courante["project"] == "Bestiaire"
        interdits = {"command", "commands", "executable", "exe", "path", "cmd"}
        assert not (set(courante) & interdits)
