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

from unittest.mock import patch

import pytest

from forge.llm import Task, get_provider, set_provider
from forge.llm.claude_code import ClaudeCodeBackend
from forge.llm.base import LLMUnavailable, QualityGateFailed
from forge.llm.fake import ScriptedProvider, UnavailableProvider
from forge.llm.gate import check_briefing, check_debrief, gate
from forge.llm.router import OPUS, RESERVE_RAISONNEMENT, SONNET, route_for

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
        with pytest.raises(LLMUnavailable, match="connecte-toi"):
            UnavailableProvider().structured(task=Task.BRIEFING, system="", prompt="", schema={})

    def test_le_message_dit_le_geste_a_faire_pas_seulement_l_echec(self):
        """Un message qui ne dit pas quoi faire fait perdre une soirée à chercher.

        Il en a d'ailleurs fait perdre une : la version précédente renvoyait vers
        « ant auth login », une commande qui n'existe pas.
        """
        message = UnavailableProvider().reason
        assert "claude" in message

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


class TestBudgetDeSortie:
    """Le raisonnement est décompté de ``max_tokens`` sur Opus 5 (§5.6).

    Ces tests existent à cause d'un vrai défaut : les premiers budgets étaient
    calibrés sur la seule réponse visible, ce qui aurait tronqué chaque briefing
    au milieu du raisonnement — un échec qui ressemble à une panne d'API alors
    que c'est un réglage. Ils gardent l'invariant plutôt que la valeur.
    """

    def test_chaque_route_laisse_de_la_place_a_la_reponse(self):
        for task in Task:
            route = route_for(task)
            assert route.reponse_visible > 0, f"{task.value} tronquerait sa réponse"

    def test_le_briefing_garde_de_quoi_ecrire_apres_avoir_pense(self):
        assert route_for(Task.BRIEFING).reponse_visible >= 1000

    def test_l_effort_eleve_reserve_plus_que_l_effort_bas(self):
        assert RESERVE_RAISONNEMENT["high"] > RESERVE_RAISONNEMENT["low"]


class TestBackendCLI:
    """Le backend qui passe par l'abonnement. Aucun sous-processus lancé ici."""

    def test_la_lecture_tolere_un_bloc_de_code(self):
        """Le CLI n'impose pas de schéma : il rend parfois du markdown."""
        assert ClaudeCodeBackend._json_de('```json\n{"a": 1}\n```') == {"a": 1}

    def test_la_lecture_tolere_une_phrase_avant_le_json(self):
        assert ClaudeCodeBackend._json_de('Voici :\n{"a": 1}') == {"a": 1}

    def test_une_reponse_sans_json_leve_indisponible(self):
        """Pas une exception nue : l'appelant doit pouvoir retomber sur le repli."""
        with pytest.raises(LLMUnavailable):
            ClaudeCodeBackend._json_de("je ne peux pas répondre")

    def test_le_cli_absent_est_une_indisponibilite_pas_un_plantage(self):
        backend = ClaudeCodeBackend(executable=None)
        backend._executable = None
        with patch("forge.llm.claude_code.cli_path", return_value=None):
            with pytest.raises(LLMUnavailable, match="introuvable"):
                backend.structured(task=Task.BRIEFING, system="s", prompt="p", schema={})

    def test_aucun_outil_n_est_pretee_au_modele(self):
        """Le §8 interdit au serveur de faire exécuter quoi que ce soit."""
        argv = ClaudeCodeBackend(executable="claude")._argv(route_for(Task.BRIEFING), system="s")

        assert argv[argv.index("--allowedTools") + 1] == ""
        for interdit in ("Bash", "Edit", "Write", "Read"):
            assert interdit in argv

    def test_les_reglages_du_depot_sont_ignores(self):
        """Le prompt contient du texte écrit par l'utilisateur et par un modèle."""
        argv = ClaudeCodeBackend(executable="claude")._argv(route_for(Task.BRIEFING), system="s")

        assert argv[argv.index("--setting-sources") + 1] == ""
        assert "--strict-mcp-config" in argv

    def test_converse_refuse_les_outils_au_lieu_de_les_ignorer(self):
        """Accepter puis ignorer donnerait une réponse fausse sans le dire."""
        with pytest.raises(LLMUnavailable, match="exécuter"):
            ClaudeCodeBackend(executable="claude").converse(
                task=Task.BRIEFING, system="s", messages=[], tools=[{"name": "x"}]
            )
