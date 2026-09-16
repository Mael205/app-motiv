"""Le projet du jour, et le blocage de 21h (13 septembre 2026).

Ces tests gardent trois promesses plutôt qu'un barème, et ce sont elles qui se
perdraient au premier refactoring :

- travailler ailleurs ne libère pas la soirée ;
- un jour sans rendez-vous ne bloque rien ;
- rien ne se bloque avant 21h, quoi qu'il manque.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from forge import services
from forge.models import Profile, Project, Session, TimeSlot, Track
from forge.rules import jour as jour_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 9, 14)


def a(heure: int, minute: int = 0) -> datetime:
    return datetime.combine(LUNDI, time(heure, minute), tzinfo=PARIS)


@pytest.fixture
def user(db, django_user_model):
    user = django_user_model.objects.create_user(username="test", password="test")
    Profile.objects.create(user=user)
    Track.objects.create(user=user, kind=Track.ATELIER)
    return user


def projet(user, nom: str, *, slot: int, jour_semaine: int | None = 0) -> Project:
    p = Project.objects.create(
        user=user, track=Track.objects.get(user=user), name=nom, slot=slot
    )
    if jour_semaine is not None:
        TimeSlot.objects.create(project=p, weekday=jour_semaine, start_time=time(20, 30))
    return p


def poser(user, p: Project, minutes: int, *, jour: date = LUNDI) -> Session:
    debut = datetime.combine(jour, time(20, 30), tzinfo=PARIS)
    return Session.objects.create(
        user=user,
        project=p,
        planned_minutes=25,
        actual_minutes=minutes,
        status=Session.DONE,
        coach_day=jour,
        started_at=debut,
        ended_at=debut + timedelta(minutes=minutes),
    )


@pytest.mark.django_db
class TestCeQueLaJourneeDemande:
    def test_sans_creneau_la_journee_est_libre(self, user):
        projet(user, "Evolve", slot=1, jour_semaine=None)

        etat = services.projet_du_jour(user, today=LUNDI)

        assert etat.libre and etat.tenu
        assert "libre" in jour_rules.phrase(etat)

    def test_le_projet_prevu_demande_vingt_cinq_minutes(self, user):
        p = projet(user, "Evolve", slot=1)
        poser(user, p, 24)

        etat = services.projet_du_jour(user, today=LUNDI)

        assert not etat.tenu
        assert etat.restants[0].restantes == 1

    def test_vingt_cinq_minutes_tiennent_la_journee(self, user):
        p = projet(user, "Evolve", slot=1)
        poser(user, p, 25)

        assert services.projet_du_jour(user, today=LUNDI).tenu

    def test_travailler_ailleurs_ne_tient_pas_le_rendez_vous(self, user):
        """Le cœur de la règle : les minutes comptent, le rendez-vous reste dû."""
        prevu = projet(user, "Bot STS2", slot=1)
        autre = projet(user, "Proto UE5", slot=2, jour_semaine=None)
        poser(user, autre, 120)

        etat = services.projet_du_jour(user, today=LUNDI)

        assert not etat.tenu
        assert [x.name for x in etat.restants] == [prevu.name]

    def test_deux_creneaux_le_meme_jour_ne_doublent_pas_la_dette(self, user):
        p = projet(user, "Evolve", slot=1)
        TimeSlot.objects.create(project=p, weekday=0, start_time=time(9))
        poser(user, p, 25)

        etat = services.projet_du_jour(user, today=LUNDI)

        assert len(etat.attendus) == 1 and etat.tenu

    def test_deux_projets_prevus_veulent_chacun_leur_compte(self, user):
        un = projet(user, "Evolve", slot=1)
        projet(user, "Bot STS2", slot=2)
        poser(user, un, 30)

        etat = services.projet_du_jour(user, today=LUNDI)

        assert len(etat.attendus) == 2
        assert [x.name for x in etat.restants] == ["Bot STS2"]

    def test_un_projet_au_frigo_n_attend_rien(self, user):
        p = projet(user, "Evolve", slot=1)
        p.status = Project.FRIDGE
        p.save()

        assert services.projet_du_jour(user, today=LUNDI).libre

    def test_aucun_mot_de_jugement_dans_la_phrase(self, user):
        """§17 : la ligne du soir où l'on n'a rien fait est la plus surveillée."""
        projet(user, "Evolve", slot=1)

        texte = jour_rules.phrase(services.projet_du_jour(user, today=LUNDI)).lower()

        for mot in ("raté", "échec", "devrais", "encore", "toujours", "discipline", "effort"):
            assert mot not in texte


@pytest.mark.django_db
class TestBlocageDeVingtEtUneHeures:
    def etat(self, user, quand: datetime) -> dict:
        return services.agent_state(user, now=quand)["block_scroll"]

    def test_rien_n_est_bloque_avant_vingt_et_une_heures(self, user):
        projet(user, "Evolve", slot=1)

        assert self.etat(user, a(20, 59))["armed"] is False

    def test_a_vingt_et_une_heures_le_projet_non_fait_bloque(self, user):
        projet(user, "Evolve", slot=1)

        etat = self.etat(user, a(21, 1))
        assert etat["armed"] is True
        assert etat["armed_from"].startswith("2026-09-14T21:00")

    def test_le_projet_fait_ne_bloque_jamais(self, user):
        p = projet(user, "Evolve", slot=1)
        poser(user, p, 25)

        assert self.etat(user, a(22))["armed"] is False

    def test_un_jour_libre_ne_bloque_jamais(self, user):
        projet(user, "Evolve", slot=1, jour_semaine=None)

        assert self.etat(user, a(23))["armed"] is False

    def test_dix_minutes_ne_suffisent_plus_a_lever_le_blocage(self, user):
        """Le streak s'en contente (§4.2), le rendez-vous non."""
        p = projet(user, "Evolve", slot=1)
        poser(user, p, 10)

        assert self.etat(user, a(21, 30))["armed"] is True

    def test_travailler_sur_un_autre_projet_ne_leve_pas_le_blocage(self, user):
        projet(user, "Bot STS2", slot=1)
        autre = projet(user, "Proto UE5", slot=2, jour_semaine=None)
        poser(user, autre, 90)

        assert self.etat(user, a(21, 30))["armed"] is True

    def test_l_etat_ne_dit_pas_ce_qui_manque(self, user):
        """§8 : l'agent reçoit une heure et un booléen, jamais un historique."""
        projet(user, "Evolve", slot=1)

        assert set(self.etat(user, a(21, 30))) == {"armed", "armed_from"}
