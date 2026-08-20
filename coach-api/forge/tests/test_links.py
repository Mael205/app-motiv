"""Tests du canal entrant (SPEC §11.7, §4.7, §5.3).

Un lien signé est le seul endroit du produit où quelque chose entre **sans
compte**. Ce qui se teste ici n'est donc pas qu'il marche — c'est ce qu'il
refuse :

* il ne fait que son geste, décidé à l'émission ;
* il ne montre rien de la base, même à celui qui l'a en main ;
* il se consomme une fois, et le second clic ne casse rien.

Le dernier point n'est pas une politesse : une messagerie qui pré-charge les
liens du message clique avant l'humain, et un lien qui répondrait « erreur » au
vrai clic ferait passer le §4.7 pour cassé.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import links
from forge.models import ActionLink, FridgeIdea, Profile


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    Profile.objects.create(user=user)
    return user


class TestEmission:
    def test_le_secret_n_est_rendu_qu_une_fois(self, user):
        lien, secret = links.emettre(user, kind=ActionLink.FRIGO)
        assert secret and secret not in str(lien.__dict__)
        assert lien.token_hash == ActionLink.hash_of(secret)

    def test_un_lien_de_frigo_dure_et_se_reutilise(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.FRIGO)
        assert lien.max_uses > 1, "c'est un raccourci qu'on épingle, pas un ticket"
        assert lien.expires_at > timezone.now() + timedelta(days=180)

    def test_un_lien_de_bilan_se_consomme_une_fois(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.VU, context={"titre": "Semaine 12"})
        assert lien.max_uses == 1

    def test_un_secret_inconnu_ne_resout_rien(self, user):
        assert links.resoudre("pas-un-vrai-jeton") is None
        assert links.resoudre("") is None


class TestCeQueLaPageMontre:
    def test_elle_ne_montre_que_ce_que_le_lien_porte(self, user):
        """Un lien qui fuit ne doit rien apprendre à personne."""
        FridgeIdea.objects.create(user=user, text="Une idée déjà au frigo")
        lien, _ = links.emettre(user, kind=ActionLink.FRIGO)

        vue = links.presenter(lien)
        assert "Une idée déjà au frigo" not in str(vue)
        assert set(vue) == {
            "kind", "titre", "question", "constat", "fait", "expire", "utilisable",
        }

    def test_le_titre_du_bilan_vient_du_contexte(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.VU, context={"titre": "Semaine du 10 août"})
        assert links.presenter(lien)["titre"] == "Semaine du 10 août"


class TestFrigo:
    def test_une_phrase_atterrit_au_frigo(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.FRIGO)
        resultat = links.consommer(lien, texte="Refaire l'écran de fin de partie")

        assert resultat["ok"]
        idee = FridgeIdea.objects.get(user=user)
        assert idee.text == "Refaire l'écran de fin de partie"
        assert idee.source == "lien"

    def test_le_vide_ne_cree_rien(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.FRIGO)
        assert not links.consommer(lien, texte="   ")["ok"]
        assert not FridgeIdea.objects.exists()

    def test_le_lien_reste_utilisable(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.FRIGO)
        links.consommer(lien, texte="Première idée")
        links.consommer(lien, texte="Deuxième idée")
        assert FridgeIdea.objects.count() == 2

    def test_un_texte_trop_long_est_coupe_pas_refuse(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.FRIGO)
        links.consommer(lien, texte="a" * (links.MAX_TEXTE + 500))
        assert len(FridgeIdea.objects.get(user=user).text) == links.MAX_TEXTE


class TestAccuseDeLecture:
    def test_un_clic_suffit(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.VU, context={"titre": "Semaine 12"})
        assert links.consommer(lien)["ok"]
        lien.refresh_from_db()
        assert lien.spent

    def test_le_second_clic_ne_casse_rien(self, user):
        """Une messagerie qui pré-charge le lien clique avant l'humain."""
        lien, _ = links.emettre(user, kind=ActionLink.VU)
        links.consommer(lien)
        second = links.consommer(lien)
        assert second["ok"] and "déjà" in second["message"].lower()

    def test_un_lien_expire_ne_marche_plus(self, user):
        lien, _ = links.emettre(user, kind=ActionLink.VU)
        ActionLink.objects.filter(pk=lien.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        lien.refresh_from_db()
        assert not links.consommer(lien)["ok"]


class TestReponse:
    def test_la_reponse_est_gardee(self, user):
        lien, _ = links.emettre(
            user, kind=ActionLink.REPONSE, context={"question": "Mardi, que s'est-il passé ?"}
        )
        links.consommer(lien, texte="Rentré tard, rien fait.")
        lien.refresh_from_db()
        assert lien.answer == "Rentré tard, rien fait."
        assert lien.spent


@pytest.mark.django_db
class TestParLeWeb:
    def test_la_page_s_ouvre_sans_compte(self, client, user):
        _, secret = links.emettre(user, kind=ActionLink.FRIGO)
        reponse = client.get(f"/l/{secret}")
        assert reponse.status_code == 200
        assert "frigo" in reponse.content.decode().lower()

    def test_la_page_ne_charge_aucun_script(self, user, client):
        """Elle doit s'ouvrir dans le navigateur intégré d'une messagerie."""
        _, secret = links.emettre(user, kind=ActionLink.VU)
        contenu = client.get(f"/l/{secret}").content.decode()
        assert "<script" not in contenu.lower()

    def test_un_lien_inconnu_rend_404_sans_rien_dire(self, client):
        reponse = client.get("/l/nimportequoi")
        assert reponse.status_code == 404

    def test_le_formulaire_remplit_le_frigo(self, client, user):
        _, secret = links.emettre(user, kind=ActionLink.FRIGO)
        reponse = client.post(f"/l/{secret}", {"texte": "Une idée en passant"})
        assert reponse.status_code == 200
        assert FridgeIdea.objects.filter(text="Une idée en passant").exists()

    def test_l_api_du_lien_ne_demande_aucune_authentification(self, client, user):
        _, secret = links.emettre(user, kind=ActionLink.VU, context={"titre": "Semaine 12"})
        assert client.get(f"/api/links/{secret}").status_code == 200
        assert client.post(f"/api/links/{secret}").status_code == 200

    def test_emettre_un_lien_demande_l_authentification(self, client, user):
        assert client.post("/api/links", {"kind": "frigo"}).status_code in (401, 403)


class TestQuestionDeRevue:
    """La revue du dimanche, répondue depuis la notification (§5.3, §11.7).

    Le type ``reponse`` et sa page existaient depuis le 17 août ; personne ne
    les émettait. Une revue qui n'existe que dans l'app est une revue qu'on
    ouvre le dimanche soir, c'est-à-dire jamais.
    """

    @pytest.fixture
    def revue(self, user):
        from forge.models import WeeklyReview

        return WeeklyReview.objects.create(
            user=user,
            week_start=timezone.now().date(),
            questions=[
                {"fait": "Mardi : créneau prévu, aucune session.", "question": "Que s'est-il passé ?", "reponse": ""},
                {"fait": "Deux soirs à 23h40.", "question": "Qu'est-ce qui retarde ?", "reponse": ""},
            ],
        )

    def test_le_lien_porte_la_question_et_son_fait(self, user, revue):
        from forge import review

        secret, question = review.lien_de_question(revue)
        vue = links.presenter(links.resoudre(secret))
        assert vue["question"] == question["question"]
        assert vue["constat"] == "Mardi : créneau prévu, aucune session."

    def test_la_reponse_atterrit_dans_la_revue(self, user, revue):
        from forge import review

        secret, _ = review.lien_de_question(revue)
        resultat = links.consommer(links.resoudre(secret), texte="J'étais au restaurant.")
        assert resultat["ok"]

        revue.refresh_from_db()
        assert revue.questions[0]["reponse"] == "J'étais au restaurant."
        assert revue.questions[1]["reponse"] == ""

    def test_la_question_suivante_est_celle_qui_reste(self, user, revue):
        from forge import review

        secret, _ = review.lien_de_question(revue)
        links.consommer(links.resoudre(secret), texte="Rentré tard.")
        revue.refresh_from_db()

        _, suivante = review.lien_de_question(revue)
        assert suivante["fait"] == "Deux soirs à 23h40."

    def test_une_revue_close_n_accepte_plus_rien(self, user, revue):
        from forge import review

        secret, _ = review.lien_de_question(revue)
        revue.closed_at = timezone.now()
        revue.save(update_fields=["closed_at"])

        # Le lien répond quand même : la réponse est gardée sur lui plutôt que
        # glissée dans un compte-rendu déjà écrit.
        resultat = links.consommer(links.resoudre(secret), texte="Trop tard.")
        assert resultat["ok"]
        revue.refresh_from_db()
        assert revue.questions[0]["reponse"] == ""

    def test_plus_de_lien_quand_tout_est_repondu(self, user, revue):
        from forge import review

        for question in revue.questions:
            question["reponse"] = "dit"
        revue.save(update_fields=["questions"])
        assert review.lien_de_question(revue) is None
