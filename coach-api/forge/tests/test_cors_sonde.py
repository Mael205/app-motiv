"""Le préflight CORS d'une sonde navigateur (SPEC §9.1).

**Le défaut que ce fichier garde, et il a eu lieu.** L'extension envoie son
jeton dans l'en-tête ``X-Probe-Token``. La liste d'en-têtes autorisés par
défaut de django-cors-headers ne le contient pas — elle ne connaît que les
usuels. Le préflight répondait donc **200 en refusant l'en-tête**, et le
navigateur n'envoyait jamais la vraie requête.

Ce qui rend ce défaut méchant est la forme de son symptôme : aucune erreur,
aucun refus, aucun message. Le journal du serveur ne montrait que des
``OPTIONS`` qui réussissaient, l'extension affichait un état vide, et la seule
lecture possible était « il n'y a rien à envoyer » — qui est par ailleurs un cas
normal et fréquent, puisque tout ce qui tombe dans ``autre`` n'est pas envoyé.

Il ne touchait que les sondes vivant dans un navigateur. L'agent PC parle en
Python, donc sans CORS, et il fonctionnait : c'est ce qui l'a rendu invisible.
"""

import pytest


@pytest.mark.django_db
class TestPreflightDeLaSonde:
    ORIGINE = "moz-extension://11111111-2222-3333-4444-555555555555"

    def _preflight(self, client, methode="POST"):
        return client.options(
            "/api/signals",
            HTTP_ORIGIN=self.ORIGINE,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD=methode,
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="x-probe-token,content-type",
        )

    def test_le_preflight_autorise_l_en_tete_du_jeton(self, client):
        reponse = self._preflight(client)
        autorises = reponse.headers.get("access-control-allow-headers", "").lower()
        assert "x-probe-token" in autorises

    def test_les_en_tetes_usuels_restent_autorises(self, client):
        # La correction ajoute un en-tête, elle n'en remplace pas la liste :
        # écraser les défauts casserait l'app elle-même, qui envoie
        # `authorization` et `content-type`.
        autorises = self._preflight(client).headers.get("access-control-allow-headers", "").lower()
        assert "authorization" in autorises
        assert "content-type" in autorises

    def test_le_preflight_repond_a_une_origine_d_extension(self, client):
        # Une extension n'a pas d'origine http : la sienne est `moz-extension://`
        # sous Firefox et `chrome-extension://` sous Chrome. Une configuration
        # qui n'autoriserait que `localhost` les fermerait toutes les deux.
        reponse = self._preflight(client)
        assert reponse.status_code in (200, 204)
        assert reponse.headers.get("access-control-allow-origin")

    def test_l_endpoint_de_l_agent_est_couvert_aussi(self, client):
        # L'extension lit `/api/agent/state` pour savoir si elle doit masquer le
        # feed. C'est le même en-tête, donc le même piège.
        reponse = client.options(
            "/api/agent/state",
            HTTP_ORIGIN=self.ORIGINE,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="x-probe-token",
        )
        autorises = reponse.headers.get("access-control-allow-headers", "").lower()
        assert "x-probe-token" in autorises
