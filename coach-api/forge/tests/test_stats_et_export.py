"""Les deux confortables du jalon J6 : les séries longues et l'export.

Aucun des deux ne débloque quoi que ce soit — c'est la définition du J6 (§16).
Ce qui se teste ici est donc ce qu'ils **promettent** :

* une série sans trou, parce qu'une semaine vide sautée dessine une continuité
  là où il y a eu un arrêt, et c'est justement l'information qu'on vient
  chercher ;
* un export qui contient le travail et **aucun secret**, parce qu'un export se
  copie sur une clé et s'envoie par message.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import export, stats
from forge.models import (
    ActionLink,
    Device,
    JournalEntry,
    ProbeToken,
    Profile,
    Project,
    RoadmapStep,
    Session,
    Track,
)

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 8, 17)


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="stats", password="test")
    Profile.objects.create(user=user)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
    return user


def seance(user, *, jour: date, minutes: int, heure: int = 21) -> Session:
    debut = datetime.combine(jour, time(heure), tzinfo=PARIS)
    return Session.objects.create(
        user=user,
        project=Project.objects.get(user=user),
        coach_day=jour,
        started_at=debut,
        ended_at=debut + timedelta(minutes=minutes),
        planned_minutes=25,
        actual_minutes=minutes,
        status=Session.DONE,
    )


class TestSeriesLongues:
    def test_les_semaines_vides_restent_dans_la_serie(self, user):
        seance(user, jour=LUNDI - timedelta(weeks=3), minutes=50)
        seance(user, jour=LUNDI, minutes=25)

        series = stats.longues(user, today=LUNDI + timedelta(days=3), semaines=4)["semaines"]
        assert [s["minutes"] for s in series] == [50, 0, 0, 25]

    def test_le_profil_hebdomadaire_a_toujours_sept_jours(self, user):
        seance(user, jour=LUNDI, minutes=30)
        jours = stats.longues(user, today=LUNDI, semaines=2)["jours"]
        assert len(jours) == 7
        assert jours[0]["label"] == "lundi" and jours[0]["minutes"] == 30
        assert jours[6]["minutes"] == 0

    def test_l_heure_de_demarrage_est_locale(self, user):
        """21h à Paris est 19h en UTC : un histogramme en UTC décale tout."""
        seance(user, jour=LUNDI, minutes=25, heure=21)
        heures = stats.longues(user, today=LUNDI, semaines=1)["heures"]
        assert heures == [{"heure": 21, "minutes": 25}]

    def test_la_forme_des_seances_compte_les_longues(self, user):
        seance(user, jour=LUNDI, minutes=50)
        seance(user, jour=LUNDI + timedelta(days=1), minutes=20)
        forme = stats.longues(user, today=LUNDI + timedelta(days=2), semaines=1)["seances"]
        assert forme["plus_longue"] == 50
        assert forme["longues"] == 1
        assert forme["part_longues"] == 0.5

    def test_rien_ne_commente(self, user):
        """Le §17 interdit le jugement, et c'est ici qu'il reviendrait le plus vite."""
        seance(user, jour=LUNDI, minutes=25)
        texte = str(stats.longues(user, today=LUNDI, semaines=4))
        for mot in ("seulement", "faible", "mauvais", "bravo", "devrais"):
            assert mot not in texte.lower()


class TestExport:
    def test_il_porte_le_travail_ecrit_a_la_main(self, user):
        session = seance(user, jour=LUNDI, minutes=50)
        JournalEntry.objects.create(
            session=session, raw_note="Réécrit le parseur.", next_action="Brancher le test."
        )
        charge = export.tout(user)
        ligne = charge["sessions"][0]
        assert ligne["note"] == "Réécrit le parseur."
        assert ligne["amorce"] == "Brancher le test."
        assert ligne["minutes"] == 50

    def test_il_ne_porte_aucun_secret(self, user):
        """Un export s'envoie par message : ce qui y entre en sort un jour."""
        _, jeton = ProbeToken.issue(user, name="Firefox", kind="ext")
        _, secret = ActionLink.issue(user, kind=ActionLink.FRIGO)
        Device.objects.create(
            user=user, name="PC", push_subscription={"endpoint": "https://push.example/abc"}
        )
        user.profile.discord_webhook = "https://discord.example/hook"
        user.profile.save()

        texte = str(export.tout(user))
        assert jeton not in texte
        assert secret not in texte
        assert "push.example" not in texte
        assert "discord.example" not in texte

    def test_les_dates_absentes_restent_nulles(self, user):
        """`null` distingue « pas encore fait » de « fait à une date inconnue »."""
        seance(user, jour=LUNDI, minutes=25)
        etape = RoadmapStep.objects.create(
            project=Project.objects.get(user=user), order=1, label="Écran de liste"
        )
        assert etape.done_at is None
        assert export.tout(user)["projets"][0]["etapes"][0]["finie_le"] is None
