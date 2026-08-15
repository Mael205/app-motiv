"""Tests des jetons de sonde (SPEC §8, §9).

Une sonde tourne dans une extension navigateur ou sur un téléphone : deux
endroits d'où un secret peut fuir. Le jeton est donc **limité à un seul
endpoint**. C'est ce que ces tests vérifient — pas seulement qu'il marche, mais
qu'il ne marche nulle part ailleurs.
"""

import json

import pytest
from django.test import Client

from forge.models import ProbeToken


@pytest.fixture
def user(django_user_model):
    from forge.models import Garde, Profile

    user = django_user_model.objects.create_user(username="arthur", password="coach")
    Profile.objects.create(user=user)
    Garde.objects.create(user=user, name="Réseaux sociaux", weekly_budget=2, auto_category="reseaux")
    return user


@pytest.fixture
def raw_token(user):
    _, raw = ProbeToken.issue(user, name="Chrome", kind="ext")
    return raw


def post_signals(client, raw, minutes=12):
    return client.post(
        "/api/signals",
        data=json.dumps({"source": "ext", "entries": [{"category": "reseaux", "minutes": minutes}]}),
        content_type="application/json",
        HTTP_X_PROBE_TOKEN=raw,
    )


@pytest.mark.django_db
class TestUsage:
    def test_un_jeton_valide_poste_des_signaux(self, raw_token):
        response = post_signals(Client(), raw_token)
        assert response.status_code == 201
        assert response.json()["stored"] == 1

    def test_le_secret_en_clair_n_est_pas_stocke(self, user, raw_token):
        token = ProbeToken.objects.get()
        assert raw_token not in token.token_hash
        assert len(token.token_hash) == 64

    def test_la_derniere_utilisation_est_horodatee(self, raw_token):
        post_signals(Client(), raw_token)
        assert ProbeToken.objects.get().last_used_at is not None


@pytest.mark.django_db
class TestPortee:
    """Le point entier de ce jeton : il ne déverrouille qu'un endpoint."""

    def test_il_ne_donne_acces_a_rien_d_autre(self, raw_token):
        client = Client()
        for url in ("/api/home", "/api/projects", "/api/journal", "/api/gardes"):
            response = client.get(url, HTTP_X_PROBE_TOKEN=raw_token)
            assert response.status_code in (401, 403), f"{url} accepte un jeton de sonde"

    def test_il_ne_permet_pas_de_declarer_une_garde_a_la_main(self, user, raw_token):
        from forge.models import Garde

        garde = Garde.objects.get(user=user)
        response = Client().post(
            f"/api/gardes/{garde.pk}/declare",
            data=json.dumps({"occurred": False}),
            content_type="application/json",
            HTTP_X_PROBE_TOKEN=raw_token,
        )
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestRefus:
    def test_jeton_inconnu(self):
        assert post_signals(Client(), "pas-un-jeton").status_code == 401

    def test_jeton_revoque(self, user, raw_token):
        from django.utils import timezone

        ProbeToken.objects.update(revoked_at=timezone.now())
        assert post_signals(Client(), raw_token).status_code == 401

    def test_sans_jeton_ni_session(self):
        response = Client().post(
            "/api/signals",
            data=json.dumps({"source": "ext", "entries": []}),
            content_type="application/json",
        )
        assert response.status_code in (401, 403)
