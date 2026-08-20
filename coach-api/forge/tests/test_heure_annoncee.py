"""L'heure que l'app annonce, et ce qu'elle pèse (SPEC §11.2, 20 août 2026).

Depuis que le minuteur ne plafonne plus les minutes, **n'importe quelle heure
vaut une journée validée** — ce qui est voulu. Le prix à payer était que l'heure
annoncée ne pesait plus rien : la tenir ne rapportait pas, la manquer ne coûtait
rien le soir même, et le seul forfait horaire du barème payait « avant 20h »,
c'est-à-dire l'horloge et non la parole donnée. Une app qui dit « 20h30 » et qui
paie « avant 20h » se contredit à voix haute.

Deux mécaniques répondent, et ce qui se teste ici est surtout ce qu'elles
**refusent** : aucune ne retire quoi que ce soit à qui travaille hors créneau.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import services, triggers
from forge.models import (
    DayWindow,
    NotificationLog,
    Profile,
    Project,
    RoadmapStep,
    Session,
    TimeSlot,
    Track,
)
from forge.rules import xp as xp_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


def paris(h: int, m: int = 0, day: date = LUNDI) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, tzinfo=PARIS)


@pytest.fixture
def profile(db):
    User = get_user_model()
    user = User.objects.create_user(username="heure", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(
            profile=profile, weekday=weekday, start_time=time(18), end_time=time(23)
        )
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    projet = Project.objects.create(user=user, track=atelier, name="Bot STS2", slot=1)
    RoadmapStep.objects.create(
        project=projet, order=0, label="Écrire le test de collision", state=RoadmapStep.DOING
    )
    TimeSlot.objects.create(project=projet, weekday=0, start_time=time(20, 30), duration_minutes=25)
    return profile


@pytest.fixture
def projet(profile):
    return Project.objects.get(user=profile.user)


def seance(profile, projet, *, debut: datetime) -> Session:
    return Session.objects.create(
        user=profile.user,
        project=projet,
        coach_day=LUNDI,
        started_at=debut,
        planned_minutes=25,
        status=Session.RUNNING,
    )


class TestPrimeDePonctualite:
    def test_le_creneau_tenu_est_prime(self, profile, projet):
        session = seance(profile, projet, debut=paris(20, 40))
        assert services.ecart_au_creneau(session) == 10

        resultat = services.end_session(
            session, now=paris(21, 10), next_action="suite demain"
        )
        assert resultat["breakdown"]["punctual"] == xp_rules.PONCTUALITE_BONUS

    def test_une_heure_plus_tard_ne_retire_rien(self, profile, projet):
        """Le §17 interdit le malus : on ne gagne pas, on ne perd pas."""
        session = seance(profile, projet, debut=paris(22, 0))
        resultat = services.end_session(session, now=paris(22, 30), next_action="x")
        assert resultat["breakdown"]["punctual"] == 0
        assert resultat["xp"] > 0

    def test_sans_creneau_declare_il_n_y_a_rien_a_tenir(self, profile, projet):
        TimeSlot.objects.all().delete()
        session = seance(profile, projet, debut=paris(20, 30))
        assert services.ecart_au_creneau(session) is None
        assert services.end_session(session, now=paris(21, 0), next_action="x")["xp"] > 0

    def test_un_creneau_tardif_vaut_autant_qu_un_creneau_tot(self, profile, projet):
        """Le point de la règle : c'est le rendez-vous qui paie, pas l'horloge."""
        TimeSlot.objects.all().update(start_time=time(22, 0))
        session = seance(profile, projet, debut=paris(22, 5))
        tardif = services.end_session(session, now=paris(22, 35), next_action="x")

        TimeSlot.objects.all().update(start_time=time(18, 0))
        matinal = seance(profile, projet, debut=paris(18, 5))
        matinal.rank_in_day = 1
        matinal.save(update_fields=["rank_in_day"])
        tot = services.end_session(matinal, now=paris(18, 35), next_action="x")

        assert tardif["breakdown"]["punctual"] == tot["breakdown"]["punctual"]

    def test_une_seance_apres_minuit_n_est_pas_ponctuelle(self, profile, projet):
        """00h20 appartient à la journée d'hier : son créneau est à quatre heures."""
        session = seance(profile, projet, debut=paris(0, 20, LUNDI + timedelta(days=1)))
        assert services.ecart_au_creneau(session) > xp_rules.TOLERANCE_MINUTES


class TestGardienDeCreneau:
    def test_il_constate_le_creneau_passe(self, profile):
        fired = triggers.check_slot_guardian(profile, paris(20, 50))
        assert [f["kind"] for f in fired] == [triggers.GUARDIAN_SLOT]

        log = NotificationLog.objects.get(user=profile.user, kind__startswith="gardien_creneau")
        assert "20h30" in log.body

    def test_il_ne_dit_rien_avant_l_heure(self, profile):
        assert triggers.check_slot_guardian(profile, paris(20, 35)) == []

    def test_il_se_tait_si_le_projet_a_deja_eu_sa_seance(self, profile, projet):
        Session.objects.create(
            user=profile.user,
            project=projet,
            coach_day=LUNDI,
            started_at=paris(14, 0),
            ended_at=paris(14, 30),
            actual_minutes=30,
            status=Session.DONE,
        )
        assert triggers.check_slot_guardian(profile, paris(20, 50)) == []

    def test_il_se_tait_pendant_une_seance(self, profile, projet):
        seance(profile, projet, debut=paris(20, 40))
        assert triggers.check_slot_guardian(profile, paris(20, 50)) == []

    def test_il_ne_parle_ni_de_streak_ni_de_bouclier(self, profile):
        """Il constate une heure ; l'enjeu de la journée appartient au gardien du soir."""
        triggers.check_slot_guardian(profile, paris(20, 50))
        log = NotificationLog.objects.get(user=profile.user, kind__startswith="gardien_creneau")
        assert "bouclier" not in log.body.lower()
        assert "streak" not in log.body.lower()

    def test_il_porte_les_deux_boutons(self, profile):
        triggers.check_slot_guardian(profile, paris(20, 50))
        from forge.models import AgentEvent

        evenement = AgentEvent.objects.filter(user=profile.user, type="notification").first()
        actions = evenement.payload["notification"]["actions"]
        assert [a["action"] for a in actions] == ["demarrer", "reporter"]

    def test_il_ne_part_qu_une_fois_par_creneau_et_par_jour(self, profile):
        triggers.check_slot_guardian(profile, paris(20, 50))
        assert triggers.check_slot_guardian(profile, paris(20, 53)) == []


class TestDureeProposee:
    """Le bouton du soir annonce le plancher, jamais la durée du créneau.

    Un créneau de cinquante minutes affichait « Démarrer · 50 min » sur le gros
    bouton, ce qui est le contraire de ce que le §4.1 cherche : le plancher est
    ridicule à dessein pour survivre aux mauvais soirs. Depuis que le
    dépassement compte et que « +15 min » existe, une séance monte — elle ne se
    décide pas à froid pour une heure entière.
    """

    def test_le_creneau_n_impose_pas_sa_duree(self, profile):
        from forge.models import TimeSlot

        TimeSlot.objects.all().update(duration_minutes=50)
        proposition = services.propose(profile.user, today=LUNDI)
        assert proposition["minutes"] == 25
        assert proposition["creneau"]["minutes"] == 50, "l'intention reste dite"

    def test_le_creneau_reste_annonce_par_le_rappel(self, profile):
        """La durée déclarée n'a pas disparu : elle est une intention, pas un bouton."""
        from forge.models import NotificationLog, TimeSlot

        TimeSlot.objects.all().update(duration_minutes=50)
        triggers.check_slot_reminder(profile, paris(20, 25))
        log = NotificationLog.objects.get(user=profile.user, kind__startswith="creneau")
        assert "50 minutes" in log.body
