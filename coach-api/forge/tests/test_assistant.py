"""L'assistant qui agit sur l'app (§5 étendu).

C'est le seul endroit du produit où une décision de modèle devient une écriture
en base. Tout ce fichier existe pour vérifier les murs qui rendent ça
acceptable, et ils sont trois :

1. **le catalogue est fermé** — l'assistant ne peut proposer que des verbes
   déclarés, et aucun de ces verbes ne fabrique du travail ;
2. **rien ne s'écrit sans un geste** — le tour de conversation ne modifie rien,
   quoi que le modèle réponde ;
3. **l'aperçu qu'on a lu est celui qui s'applique** — sinon l'action est
   périmée, pas appliquée à l'aveugle.

Le quatrième point n'est pas un mur mais compte autant : une action refusée est
**conservée avec son motif**. Lire « baisser l'engagement à zéro — refusé :
zéro n'est pas un engagement » apprend la règle ; un silence n'apprend rien.
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from forge import assistant
from forge.llm import Task, set_provider
from forge.llm.base import QualityGateFailed
from forge.llm.fake import ScriptedProvider, UnavailableProvider
from forge.llm.gate import check_assistant
from forge.models import (
    DayWindow,
    Profile,
    Project,
    ProposedAction,
    RoadmapStep,
    Routine,
    Track,
)
from forge.rules import actions as catalogue

LUNDI = date(2026, 3, 2)          # un lundi
DIMANCHE = date(2026, 3, 8)


# --------------------------------------------------------------------------
# Le catalogue
# --------------------------------------------------------------------------

class TestLeCatalogue:
    def test_aucun_verbe_ne_fabrique_du_travail(self):
        """Le mur le plus important. Un assistant conversationnel est exactement
        le chemin par lequel « valide ma journée » rentrerait : il suffirait de
        demander gentiment."""
        for action in catalogue.CATALOGUE:
            for interdit in catalogue.TOUCHE_LA_MESURE:
                assert interdit not in action.cle, (
                    f"« {action.cle} » touche à la mesure du travail (§17)"
                )

    def test_chaque_verbe_a_une_execution(self):
        from forge import actions as executeurs

        assert set(catalogue.CLES) == set(executeurs.RESOLVEURS)

    def test_une_cle_inconnue_est_refusee(self):
        verdict = catalogue.verifier_forme("session.creer", {})
        assert not verdict.ok and "sais faire" in verdict.raison

    def test_un_parametre_manquant_est_refuse(self):
        verdict = catalogue.verifier_forme("projet.renommer", {"projet": "Bestiaire"})
        assert not verdict.ok and "nom" in verdict.raison

    def test_un_parametre_invente_est_refuse(self):
        """Un paramètre inconnu signale que le modèle a compris autre chose ;
        l'ignorer ferait une action à moitié juste, le pire des cas."""
        verdict = catalogue.verifier_forme(
            "projet.renommer", {"projet": "B", "nom": "C", "supprimer": True}
        )
        assert not verdict.ok and "inconnus" in verdict.raison

    def test_les_types_sont_convertis(self):
        verdict = catalogue.verifier_forme(
            "projet.engagement", {"projet": "Bestiaire", "sessions": "3"}
        )
        assert verdict.ok and verdict.params["sessions"] == 3


# --------------------------------------------------------------------------
# La porte
# --------------------------------------------------------------------------

class TestLaPorte:
    def test_le_faux_accompli_est_refuse(self):
        """Quelqu'un qui lit « c'est fait » ne clique pas sur Appliquer : la
        modification n'a jamais lieu et l'app paraît cassée."""
        with pytest.raises(QualityGateFailed, match="propose"):
            check_assistant(
                {"reponse": "C'est fait, j'ai renommé le projet.", "actions": []},
                cles_connues=catalogue.CLES,
            )

    def test_la_felicitation_est_refusee(self):
        with pytest.raises(QualityGateFailed, match="félicitation"):
            check_assistant(
                {"reponse": "Excellent, je te propose ceci.", "actions": []},
                cles_connues=catalogue.CLES,
            )

    def test_une_action_hors_catalogue_est_refusee(self):
        """Ne devrait jamais arriver — l'énumération du schéma l'empêche. C'est
        la ligne qui tient le mur si un backend n'applique pas le schéma."""
        with pytest.raises(QualityGateFailed, match="hors catalogue"):
            check_assistant(
                {"reponse": "Voilà.", "actions": [{"action": "xp.donner", "params": {}}]},
                cles_connues=catalogue.CLES,
            )

    def test_une_proposition_normale_passe(self):
        propre = check_assistant(
            {
                "reponse": "Je te propose de renommer le projet.",
                "actions": [{"action": "projet.renommer", "params": {"projet": "A", "nom": "B"}}],
            },
            cles_connues=catalogue.CLES,
        )
        assert propre["actions"][0]["action"] == "projet.renommer"


# --------------------------------------------------------------------------
# Le tour de conversation
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestLeTour:
    def test_parler_n_ecrit_rien(self, user):
        """Le mur numéro deux : le tour propose, il n'applique pas."""
        _repondre(
            "Voilà ce que ça donnerait.",
            [{"action": "projet.renommer", "params": {"projet": "Bestiaire", "nom": "Bestiaire v2"}}],
        )
        fil = assistant.parler(user, "renomme Bestiaire en Bestiaire v2", today=LUNDI)

        assert Project.objects.get(user=user).name == "Bestiaire"
        action = fil["turns"][-1]["actions"][0]
        assert action["state"] == ProposedAction.EN_ATTENTE
        assert action["before"] == "Bestiaire" and action["after"] == "Bestiaire v2"

    def test_la_demande_survit_a_un_modele_absent(self, user):
        """Si le modèle tombe, ce qu'on vient de taper n'est pas perdu."""
        set_provider(UnavailableProvider())
        with pytest.raises(assistant.AssistantIndisponible):
            assistant.parler(user, "fusionne mes routines", today=LUNDI)

        fil = assistant.payload_fil(user)
        assert fil["turns"][-1]["text"] == "fusionne mes routines"
        assert fil["turns"][-1]["role"] == "user"

    def test_une_action_impossible_est_conservee_avec_son_motif(self, user):
        """Un silence n'apprend pas la règle ; une carte refusée, si."""
        _repondre(
            "Je te propose de descendre à zéro.",
            [{"action": "projet.engagement", "params": {"projet": "Bestiaire", "sessions": 0}}],
        )
        fil = assistant.parler(user, "mets Bestiaire à zéro session", today=LUNDI)

        action = fil["turns"][-1]["actions"][0]
        assert action["state"] == ProposedAction.ECARTEE
        assert action["detail"]

    def test_le_fil_garde_ses_derniers_tours_pas_ses_premiers(self, user):
        """Une conversation longue garde sa fin : c'est la seule partie encore
        pertinente, et l'état joint à chaque tour est de toute façon frais."""
        for i in range(assistant.MEMOIRE + 4):
            _repondre(f"réponse {i}", [])
            assistant.parler(user, f"demande {i}", today=LUNDI)

        fournisseur = _repondre("dernière", [])
        assistant.parler(user, "la toute dernière", today=LUNDI)

        prompt = fournisseur.calls[-1]["prompt"]
        assert "demande 0" not in prompt
        assert f"demande {assistant.MEMOIRE + 3}" in prompt
        assert "la toute dernière" in prompt

    def test_l_etat_envoye_ne_contient_ni_journal_ni_notes(self, user):
        """Tout ce qui entre dans le prompt part chez un fournisseur, et
        l'assistant n'a rien à faire des notes de session."""
        etat = assistant.etat_pour_le_modele(user, today=LUNDI)
        assert "Bestiaire" in etat
        for absent in ("note", "journal", "streak", "bouclier"):
            assert absent not in etat.lower()

    def test_un_projet_invente_est_refuse_avec_les_vrais_noms(self, user):
        _repondre(
            "Voilà.",
            [{"action": "projet.renommer", "params": {"projet": "Zelda", "nom": "X"}}],
        )
        fil = assistant.parler(user, "renomme Zelda", today=LUNDI)
        detail = fil["turns"][-1]["actions"][0]["detail"]
        assert "Zelda" in detail and "Bestiaire" in detail

    def test_le_nom_est_insensible_a_la_casse_mais_jamais_approximatif(self, user):
        _repondre("Voilà.", [{"action": "projet.renommer", "params": {"projet": "bestiaire", "nom": "X"}}])
        assert assistant.parler(user, "x", today=LUNDI)["turns"][-1]["actions"][0]["state"] == "attente"

        _repondre("Voilà.", [{"action": "projet.renommer", "params": {"projet": "le bestiaire", "nom": "X"}}])
        assert assistant.parler(user, "y", today=LUNDI)["turns"][-1]["actions"][0]["state"] == "ecartee"


# --------------------------------------------------------------------------
# Appliquer
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestAppliquer:
    def test_un_geste_ecrit_enfin(self, user):
        action = _proposer(
            user, "projet.renommer", {"projet": "Bestiaire", "nom": "Bestiaire v2"}
        )
        assistant.appliquer(action, user=user, today=LUNDI)

        assert Project.objects.get(user=user).name == "Bestiaire v2"
        action.refresh_from_db()
        assert action.state == ProposedAction.APPLIQUEE

    def test_on_n_applique_pas_deux_fois(self, user):
        """Deux onglets, deux clics : une fusion appliquée deux fois archiverait
        une routine de plus."""
        action = _proposer(user, "projet.renommer", {"projet": "Bestiaire", "nom": "B2"})
        assistant.appliquer(action, user=user, today=LUNDI)
        with pytest.raises(ValueError, match="déjà"):
            assistant.appliquer(action, user=user, today=LUNDI)

    def test_un_etat_qui_a_bouge_perime_la_proposition(self, user):
        """L'aperçu qu'on a lu ne décrit plus ce qui se passerait."""
        action = _proposer(user, "projet.renommer", {"projet": "Bestiaire", "nom": "B2"})

        projet = Project.objects.get(user=user)
        RoadmapStep.objects.create(project=projet, label="Une étape ajoutée entre-temps")

        assistant.appliquer(action, user=user, today=LUNDI)
        action.refresh_from_db()
        assert action.state == ProposedAction.PERIMEE
        assert Project.objects.get(user=user).name == "Bestiaire"

    def test_ecarter_n_ecrit_rien(self, user):
        action = _proposer(user, "projet.renommer", {"projet": "Bestiaire", "nom": "B2"})
        assistant.ecarter(action)
        assert Project.objects.get(user=user).name == "Bestiaire"

    def test_fermer_le_fil_perime_ce_qui_restait(self, user):
        """Une proposition sans sa conversation est un bouton sans contexte."""
        action = _proposer(user, "projet.renommer", {"projet": "Bestiaire", "nom": "B2"})
        assistant.fermer(user)
        action.refresh_from_db()
        assert action.state == ProposedAction.PERIMEE


# --------------------------------------------------------------------------
# Les actions elles-mêmes
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestLesActions:
    def test_fusionner_deux_routines(self, user):
        """L'exemple qui a motivé tout ça."""
        piste = Track.objects.create(user=user, kind=Track.ENTRETIEN)
        Routine.objects.create(
            user=user, track=piste, name="Vaisselle", anchor="reveil",
            weekdays=[0, 1, 2], weekly_target=3,
        )
        Routine.objects.create(
            user=user, track=piste, name="Rangement", anchor="libre",
            weekdays=[3, 4], weekly_target=2,
        )

        action = _proposer(
            user, "routine.fusionner",
            {"routines": ["Vaisselle", "Rangement"], "nom": "Tenir l'appart", "ancrage": "reveil"},
        )
        assert "archivée" in action.warning
        assistant.appliquer(action, user=user, today=LUNDI)

        actives = list(Routine.objects.filter(user=user, active=True))
        assert len(actives) == 1
        assert actives[0].name == "Tenir l'appart"
        # Les jours sont l'union : une fusion ne supprime pas de jours en douce.
        assert actives[0].weekdays == [0, 1, 2, 3, 4]

    def test_decouper_une_etape(self, user):
        projet = Project.objects.get(user=user)
        RoadmapStep.objects.create(project=projet, label="Faire le raycast", order=0, estimated_sessions=3)
        RoadmapStep.objects.create(project=projet, label="Suite", order=1)

        action = _proposer(
            user, "etape.decouper",
            {"projet": "Bestiaire", "etape": "Faire le raycast",
             "morceaux": ["Écrire le test de collision", "Brancher le raycast"]},
        )
        assistant.appliquer(action, user=user, today=LUNDI)

        libelles = [e.label for e in projet.steps.order_by("order")]
        assert libelles == ["Écrire le test de collision", "Brancher le raycast", "Suite"]

    def test_une_etape_deja_travaillee_ne_s_efface_pas(self, user):
        from django.utils import timezone as dj

        projet = Project.objects.get(user=user)
        RoadmapStep.objects.create(
            project=projet, label="Commencée", order=0, doing_since=dj.now()
        )
        action = _proposer(user, "etape.supprimer", {"projet": "Bestiaire", "etape": "Commencée"})
        assert action.state == ProposedAction.ECARTEE
        assert "ne mène nulle part" in action.detail

    def test_monter_un_engagement_attend_dimanche(self, user):
        """L'action passe par la règle du §4.3, elle ne la recopie pas."""
        lundi = _proposer(user, "projet.engagement", {"projet": "Bestiaire", "sessions": 5})
        assert lundi.state == ProposedAction.ECARTEE

        dimanche = _proposer(
            user, "projet.engagement", {"projet": "Bestiaire", "sessions": 5}, today=DIMANCHE
        )
        assert dimanche.state == ProposedAction.EN_ATTENTE

    def test_baisser_un_engagement_marche_en_semaine(self, user):
        action = _proposer(user, "projet.engagement", {"projet": "Bestiaire", "sessions": 1})
        assert action.state == ProposedAction.EN_ATTENTE

    def test_un_jour_off_retroactif_est_refuse(self, user):
        action = _proposer(user, "jour_off.declarer", {"jour": LUNDI.isoformat()})
        assert action.state == ProposedAction.ECARTEE
        assert "veille" in action.detail

    def test_une_routine_visee_plus_souvent_que_proposee_est_refusee(self, user):
        """L'écart entre le rythme et le seuil absorbe les oublis (§11.9) ;
        là il serait négatif."""
        Track.objects.create(user=user, kind=Track.ENTRETIEN)
        action = _proposer(
            user, "routine.creer",
            {"nom": "Étirements", "jours": [0, 1], "cible": 5},
        )
        assert action.state == ProposedAction.ECARTEE
        assert "absorbe les oublis" in action.detail

    def test_regler_la_fenetre_du_soir(self, user):
        action = _proposer(
            user, "fenetre.regler", {"debut": "19:00", "fin": "23:30", "jours": [0, 1, 2, 3, 4]}
        )
        assistant.appliquer(action, user=user, today=LUNDI)

        fenetre = DayWindow.objects.get(profile=user.profile, weekday=0)
        assert fenetre.start_time.hour == 19 and fenetre.end_time.hour == 23

    def test_un_fuseau_inconnu_est_refuse(self, user):
        action = _proposer(user, "reglages.fuseau", {"fuseau": "Mars/Olympus"})
        assert action.state == ProposedAction.ECARTEE


# --------------------------------------------------------------------------
# Décor
# --------------------------------------------------------------------------

def _repondre(texte: str, actions: list[dict]) -> ScriptedProvider:
    fournisseur = ScriptedProvider([{"reponse": texte, "actions": actions}])
    set_provider(fournisseur)
    return fournisseur


def _proposer(user, cle: str, params: dict, *, today: date = LUNDI) -> ProposedAction:
    """Fait proposer une action par l'assistant, et rend la carte obtenue."""
    _repondre("Voilà ce que ça donnerait.", [{"action": cle, "params": params}])
    assistant.parler(user, f"fais {cle}", today=today)
    return ProposedAction.objects.filter(turn__conversation__user=user).order_by("-id").first()


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(
        user=user, track=atelier, name="Bestiaire", slot=1, weekly_commitment=3
    )
    return user
