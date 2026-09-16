"""La semaine se règle le dimanche, et se lit tous les jours (§11.2, 13/09/2026).

Ce que ces tests gardent : la grille reste **lisible** en semaine — la cacher
reviendrait à cacher le contrat qu'on est en train de tenir — et elle ne
s'**écrit** que le dimanche.
"""

from datetime import date, time

import pytest
from rest_framework.test import APIClient

from forge import api
from forge.models import Profile, Project, TimeSlot, Track

DIMANCHE = date(2026, 9, 20)
MARDI = date(2026, 9, 15)


@pytest.fixture
def jour(monkeypatch):
    """Le jour que l'API croit être. Une semaine ne s'attend pas pour la tester."""

    def poser(valeur: date):
        monkeypatch.setattr(api, "_today", lambda request: valeur)

    return poser


@pytest.fixture
def client(db, django_user_model):
    user = django_user_model.objects.create_user(username="test", password="test")
    Profile.objects.create(user=user)
    track = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=track, name="Evolve", slot=1)
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def projet(client) -> Project:
    return Project.objects.get(name="Evolve")


@pytest.mark.django_db
class TestLecture:
    def test_la_grille_se_lit_en_semaine(self, client, jour):
        TimeSlot.objects.create(project=projet(client), weekday=1, start_time=time(20, 30))

        jour(MARDI)
        reponse = client.get("/api/creneaux")

        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["ouvert"] is False
        assert corps["jours_avant_ouverture"] == 5
        assert corps["projets"][0]["creneaux"][0]["heure"] == "20:30"
        assert corps["requis_minutes"] == 25 and corps["heure_de_blocage"] == "21h00"

    def test_le_dimanche_elle_est_ouverte(self, client, jour):
        jour(DIMANCHE)
        corps = client.get("/api/creneaux").json()

        assert corps["ouvert"] is True and corps["jours_avant_ouverture"] == 0


@pytest.mark.django_db
class TestEcriture:
    def poser(self, client, **extra):
        return client.post(
            "/api/creneaux",
            {"project_id": projet(client).id, "weekday": 1, "heure": "20:30", **extra},
            format="json",
        )

    def test_le_dimanche_on_pose_un_creneau(self, client, jour):
        jour(DIMANCHE)
        reponse = self.poser(client)

        assert reponse.status_code == 201
        assert TimeSlot.objects.count() == 1
        assert reponse.json()["minutes"] == 25

    def test_en_semaine_c_est_refuse_sans_reproche(self, client, jour):
        jour(MARDI)
        reponse = self.poser(client)

        assert reponse.status_code == 409
        assert "dimanche" in reponse.json()["detail"]
        assert TimeSlot.objects.count() == 0

    def test_deux_projets_ne_partagent_pas_la_meme_heure(self, client, jour):
        jour(DIMANCHE)
        self.poser(client)
        autre = Project.objects.create(
            user=projet(client).user, track=Track.objects.first(), name="Bot", slot=2
        )

        reponse = client.post(
            "/api/creneaux",
            {"project_id": autre.id, "weekday": 1, "heure": "20:30"},
            format="json",
        )

        assert reponse.status_code == 409
        assert "occupe déjà" in reponse.json()["detail"]

    def test_une_heure_illisible_est_refusee(self, client, jour):
        jour(DIMANCHE)
        reponse = client.post(
            "/api/creneaux",
            {"project_id": projet(client).id, "weekday": 1, "heure": "vingt heures"},
            format="json",
        )

        assert reponse.status_code == 400

    def test_le_dimanche_on_retire_un_creneau(self, client, jour):
        jour(DIMANCHE)
        creneau = TimeSlot.objects.create(
            project=projet(client), weekday=1, start_time=time(20, 30)
        )

        reponse = client.delete(f"/api/creneaux/{creneau.id}")

        assert reponse.status_code == 200 and TimeSlot.objects.count() == 0

    def test_en_semaine_on_ne_retire_rien(self, client, jour):
        jour(MARDI)
        creneau = TimeSlot.objects.create(
            project=projet(client), weekday=1, start_time=time(20, 30)
        )

        reponse = client.delete(f"/api/creneaux/{creneau.id}")

        assert reponse.status_code == 409 and TimeSlot.objects.count() == 1
