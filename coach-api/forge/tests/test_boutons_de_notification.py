"""Les boutons d'une notification, et le report (SPEC §11.7).

Le canal entrant était complet côté page — un lien signé, une page sans script,
trois gestes — et vide côté **notification** : le gardien arrivait avec son
texte et rien à faire dessus. Le soir où il tombe est précisément celui où l'on
n'ouvre pas l'app ; lui demander d'ouvrir l'app est donc lui demander la seule
chose qu'on ne fera pas.

Ce qui se teste ici n'est pas que les boutons existent, c'est ce qu'ils
garantissent :

* le service worker n'a **aucun jeton** — le droit d'agir voyage dans le lien,
  expire avec la soirée, et ne fait qu'une chose ;
* un lien émis pour une notification qui n'est jamais partie est **détruit** ;
* un report est tenu par le serveur, pas par le worker, et **ne part pas s'il
  arrive en retard**.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import links, triggers
from forge.models import (
    ActionLink,
    DayWindow,
    NotificationLog,
    Profile,
    Project,
    Rappel,
    RoadmapStep,
    Session,
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
    projet = Project.objects.create(user=user, track=atelier, name="Prototype UE5", slot=1)
    RoadmapStep.objects.create(
        project=projet, order=0, label="Écrire le test de collision", state=RoadmapStep.DOING
    )
    return profile


def boutons(profile) -> list[dict]:
    log = NotificationLog.objects.get(user=profile.user, kind=triggers.GUARDIAN)
    from forge.models import AgentEvent

    evenement = AgentEvent.objects.filter(user=profile.user, type="notification").first()
    assert evenement, "la notification doit être journalisée avec ses boutons"
    assert evenement.payload["notification"]["title"] == log.title
    return evenement.payload["notification"]["actions"]


class TestLesBoutonsDuGardien:
    def test_le_gardien_porte_ses_deux_gestes(self, profile):
        triggers.check_guardian(profile, paris(21, 30))
        actions = boutons(profile)
        assert [a["action"] for a in actions] == ["demarrer", "reporter"]

    def test_chaque_bouton_porte_une_adresse_a_appeler_et_rien_d_autre(self, profile):
        triggers.check_guardian(profile, paris(21, 30))
        for action in boutons(profile):
            assert action["post"].startswith("/api/links/")
            assert set(action) == {"action", "title", "post"}

    def test_les_liens_expirent_avec_la_soiree(self, profile):
        triggers.check_guardian(profile, paris(21, 30))
        for lien in ActionLink.objects.filter(user=profile.user):
            assert lien.expires_at < timezone.now() + timedelta(days=2)

    def test_un_gardien_deja_envoye_ne_laisse_pas_de_liens_orphelins(self, profile):
        triggers.check_guardian(profile, paris(21, 30))
        emis = ActionLink.objects.filter(user=profile.user).count()

        triggers.check_guardian(profile, paris(21, 33))       # même soir, rien ne part
        assert ActionLink.objects.filter(user=profile.user).count() == emis


class TestDemarrerDepuisLaNotification:
    def secret_de(self, profile, action: str) -> str:
        triggers.check_guardian(profile, paris(21, 30))
        adresse = next(a["post"] for a in boutons(profile) if a["action"] == action)
        return adresse.rsplit("/", 1)[-1]

    def test_le_bouton_demarre_la_seance_proposee(self, profile):
        secret = self.secret_de(profile, "demarrer")
        resultat = links.consommer(links.resoudre(secret))
        assert resultat["ok"]

        session = Session.objects.get(user=profile.user, status=Session.RUNNING)
        assert session.planned_minutes == 10
        assert session.project.name == "Prototype UE5"

    def test_deux_clics_ne_lancent_qu_une_seance(self, profile):
        secret = self.secret_de(profile, "demarrer")
        links.consommer(links.resoudre(secret))
        resultat = links.consommer(links.resoudre(secret))
        assert resultat["ok"], "le second passage dit « déjà », jamais « erreur »"
        assert Session.objects.filter(user=profile.user, status=Session.RUNNING).count() == 1

    def test_il_ne_lit_rien_de_la_base(self, profile):
        secret = self.secret_de(profile, "demarrer")
        vue = links.presenter(links.resoudre(secret))
        assert "Prototype UE5" not in str(vue)


class TestReport:
    def secret_de(self, profile) -> str:
        triggers.check_guardian(profile, paris(21, 30))
        adresse = next(a["post"] for a in boutons(profile) if a["action"] == "reporter")
        return adresse.rsplit("/", 1)[-1]

    def test_reporter_pose_un_rappel_un_quart_d_heure_plus_tard(self, profile):
        secret = self.secret_de(profile)
        avant = timezone.now()
        links.consommer(links.resoudre(secret))

        rappel = Rappel.objects.get(user=profile.user)
        assert rappel.due_at >= avant + timedelta(minutes=14)
        assert rappel.sent_at is None

    def test_le_rappel_part_a_l_heure(self, profile):
        links.consommer(links.resoudre(self.secret_de(profile)))
        rappel = Rappel.objects.get(user=profile.user)

        fired = triggers.check_rappels(profile, rappel.due_at)
        assert [f["kind"] for f in fired] == [triggers.RAPPEL]
        rappel.refresh_from_db()
        assert rappel.sent_at is not None

    def test_un_rappel_en_retard_ne_part_pas(self, profile):
        """Un gardien reporté d'un quart d'heure qui arrive une heure après
        réveille quelqu'un pour une soirée finie."""
        links.consommer(links.resoudre(self.secret_de(profile)))
        rappel = Rappel.objects.get(user=profile.user)

        assert triggers.check_rappels(profile, rappel.due_at + timedelta(hours=1)) == []
        rappel.refresh_from_db()
        assert rappel.sent_at is not None, "périmé : classé, pour ne pas ressortir plus tard"

    def test_un_rappel_devenu_sans_objet_se_tait(self, profile):
        """La journée a été validée pendant le report : plus rien à dire (§17)."""
        from forge.rules.calendar import coach_day

        links.consommer(links.resoudre(self.secret_de(profile)))
        rappel = Rappel.objects.get(user=profile.user)
        # La journée du coach de l'échéance, et non celle du gardien : le rappel
        # est posé maintenant, pas le lundi de la fixture.
        jour = coach_day(rappel.due_at, profile.timezone_name, profile.day_rollover_hour)

        Session.objects.create(
            user=profile.user,
            project=Project.objects.get(user=profile.user),
            coach_day=jour,
            started_at=rappel.due_at - timedelta(minutes=30),
            ended_at=rappel.due_at - timedelta(minutes=5),
            actual_minutes=25,
            status=Session.DONE,
        )
        assert triggers.check_rappels(profile, rappel.due_at) == []
