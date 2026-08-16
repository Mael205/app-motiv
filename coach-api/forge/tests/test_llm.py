"""Tests de la couche modèle et de sa porte de qualité (SPEC §5.6, §0.9, §4.5).

Aucun appel réseau. Ce qui est vérifié ici n'est pas la qualité d'un modèle —
elle ne se teste pas dans une suite unitaire — mais **la solidité de ce qui
l'entoure** :

* la porte refuse-t-elle une réponse qui propose plusieurs pistes (§0.9) ;
* refuse-t-elle une tâche floue du type « avancer sur » (§4.5) ;
* l'application reste-t-elle entière quand aucun identifiant n'existe.

Le dernier point est le plus important : sans identifiant est **l'état par
défaut** de l'app, pas un cas d'erreur exotique.
"""

import pytest

from forge.llm import Task, get_provider, set_provider
from forge.llm.base import LLMUnavailable, QualityGateFailed
from forge.llm.fake import ScriptedProvider, UnavailableProvider
from forge.llm.gate import check_briefing, check_debrief, gate
from forge.llm.router import OPUS, SONNET, route_for

PROJETS = {"Bestiaire — app mobile", "Evolve — prototype 4v1 UE5"}


def briefing(**champs) -> dict:
    base = {
        "projet": "Bestiaire — app mobile",
        "tache": "Écrire l'écran de fiche d'espèce et son test de rendu",
        "minutes": 25,
        "pourquoi": "c'est l'étape en cours",
        "definition_de_fini": "le test passe",
    }
    base.update(champs)
    return base


class TestRoutage:
    """Le jugement va au modèle le plus capable, la transformation au plus rapide."""

    def test_le_briefing_passe_par_opus(self):
        assert route_for(Task.BRIEFING).model == OPUS

    def test_l_entretien_de_projet_aussi(self):
        """Une roadmap floue se paie pendant des semaines (§4.5)."""
        assert route_for(Task.ENTRETIEN_PROJET).model == OPUS

    def test_le_debrief_passe_par_sonnet(self):
        """Structurer des notes déjà écrites : la réponse est dans l'entrée."""
        assert route_for(Task.DEBRIEF).model == SONNET

    def test_une_tache_inconnue_ne_devine_pas_a_la_baisse(self):
        route = route_for("tache_qui_n_existe_pas")
        assert route.model == OPUS

    def test_chaque_route_dit_pourquoi(self):
        for task in Task:
            assert route_for(task).why, f"{task} n'explique pas son choix de modèle"


class TestPorteBriefing:
    """Le §0.9 : le système présente une action déjà décidée, jamais un choix."""

    def test_un_briefing_net_passe(self):
        resultat = check_briefing(briefing(), projets_connus=PROJETS)
        assert resultat["minutes"] == 25

    def test_deux_pistes_sont_refusees(self):
        """Le mode de défaillance que le produit existe pour empêcher."""
        with pytest.raises(QualityGateFailed, match="plusieurs pistes"):
            check_briefing(
                briefing(tache="Écrire le test de collision, sinon finir l'écran de fin"),
                projets_connus=PROJETS,
            )

    def test_une_tache_floue_est_refusee(self):
        with pytest.raises(QualityGateFailed, match="floue"):
            check_briefing(briefing(tache="Avancer sur le moteur de rendu"), projets_connus=PROJETS)

    def test_une_liste_deguisee_est_refusee(self):
        with pytest.raises(QualityGateFailed, match="liste"):
            check_briefing(
                briefing(tache="Trois choses :\n- le test\n- l'écran\n- le build"),
                projets_connus=PROJETS,
            )

    def test_un_projet_invente_est_refuse(self):
        """Afficher une hallucination coûte plus cher que ne rien afficher."""
        with pytest.raises(QualityGateFailed, match="inconnu"):
            check_briefing(briefing(projet="Projet Fantôme"), projets_connus=PROJETS)

    def test_une_duree_hors_des_trois_est_refusee(self):
        with pytest.raises(QualityGateFailed, match="hors des trois"):
            check_briefing(briefing(minutes=40), projets_connus=PROJETS)

    def test_une_tache_trop_courte_est_refusee(self):
        with pytest.raises(QualityGateFailed, match="trop courte"):
            check_briefing(briefing(tache="Le test"), projets_connus=PROJETS)

    def test_le_motif_du_refus_est_lisible(self):
        """Une porte silencieuse ne s'améliore jamais."""
        with pytest.raises(QualityGateFailed) as echec:
            check_briefing(briefing(tache="Continuer le bot"), projets_connus=PROJETS)
        assert "continuer" in echec.value.reason.lower()
        assert echec.value.payload is not None


class TestPorteDebrief:
    def test_un_debrief_complet_passe(self):
        resultat = check_debrief(
            {
                "resume": "Écran de fiche terminé.",
                "amorce": "Ouvrir species.tsx et brancher le bouton de retour",
                "blocages": ["l'API renvoie 500 sur les espèces sans photo"],
            }
        )
        assert resultat["blocages"] == ["l'API renvoie 500 sur les espèces sans photo"]

    def test_sans_amorce_c_est_un_echec(self):
        """Le §11.3 la rend obligatoire : c'est le prix du démarrage à froid."""
        with pytest.raises(QualityGateFailed, match="amorce"):
            check_debrief({"resume": "Bien avancé."})

    def test_une_amorce_floue_est_refusee(self):
        with pytest.raises(QualityGateFailed, match="floue"):
            check_debrief({"amorce": "Continuer là où je me suis arrêté"})


class TestFournisseurAbsent:
    """Sans identifiant est l'état par défaut, pas un cas d'erreur."""

    def test_le_fournisseur_absent_leve_proprement(self):
        with pytest.raises(LLMUnavailable, match="ant auth login"):
            UnavailableProvider().structured(task=Task.BRIEFING, system="", prompt="", schema={})

    def test_l_indisponibilite_se_distingue_d_une_mauvaise_reponse(self):
        """Deux causes, deux gestes : configurer l'auth, ou revoir le prompt."""
        assert not issubclass(LLMUnavailable, QualityGateFailed)
        assert not issubclass(QualityGateFailed, LLMUnavailable)


class TestFournisseurScripte:
    def test_il_rend_les_reponses_dans_l_ordre(self):
        fournisseur = ScriptedProvider([{"a": 1}, {"b": 2}])
        assert fournisseur.structured(
            task=Task.BRIEFING, system="s", prompt="p", schema={}
        ).content == {"a": 1}
        assert fournisseur.structured(
            task=Task.DEBRIEF, system="s", prompt="p", schema={}
        ).content == {"b": 2}

    def test_il_note_ce_qu_on_lui_a_demande(self):
        fournisseur = ScriptedProvider([{"ok": True}])
        fournisseur.structured(task=Task.BRIEFING, system="règles", prompt="état", schema={})
        assert fournisseur.calls[0]["task"] is Task.BRIEFING
        assert fournisseur.calls[0]["system"] == "règles"

    def test_il_refuse_de_repondre_sans_script(self):
        """Un test qui appelle plus que prévu doit échouer bruyamment."""
        with pytest.raises(AssertionError, match="plus de réponse préparée"):
            ScriptedProvider([]).structured(task=Task.BRIEFING, system="", prompt="", schema={})


class TestSelectionDuFournisseur:
    def test_l_override_est_respecte(self):
        faux = ScriptedProvider([{"x": 1}])
        set_provider(faux)
        try:
            assert get_provider() is faux
        finally:
            set_provider(None)

    def test_la_porte_generique_dispatche(self):
        assert gate(Task.BRIEFING, briefing(), projets_connus=PROJETS)["minutes"] == 25
        assert gate(Task.DECOUPAGE, {"libre": "passe tel quel"}) == {"libre": "passe tel quel"}
