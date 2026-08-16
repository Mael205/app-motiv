"""Tests des profils de lancement (SPEC §8.1, et surtout §8 sécurité).

    coach-api/.venv/Scripts/python -m pytest coach-agent

La propriété vérifiée ici n'est pas « le lancement fonctionne » — c'est
**rien ne sort de la liste blanche**. Le §8 la pose en règle non négociable :

> Le serveur ne peut jamais faire exécuter une commande arbitraire.

C'est précisément parce que le nom du projet vient du réseau que le calcul du
plan est une fonction pure : on peut lui envoyer des noms hostiles et vérifier
qu'il ne rend jamais autre chose que ce qui est écrit dans le fichier local,
sans jamais rien exécuter.
"""

import pytest

from profiles import Plan, Profiles, launch, load_profiles

LISTE = Profiles(
    entries={
        "Bestiaire — app mobile": {
            "folders": [r"C:\Users\mael2\bestiaire-app"],
            "urls": ["http://localhost:8081"],
        },
        "Evolve": {"executables": [r"C:\Program Files\Editor\editor.exe"]},
    }
)


class TestListeBlanche:
    def test_un_projet_declare_rend_son_plan(self):
        plan = LISTE.plan_for("Bestiaire — app mobile")
        assert plan.folders == (r"C:\Users\mael2\bestiaire-app",)
        assert plan.urls == ("http://localhost:8081",)

    def test_un_projet_inconnu_ne_lance_rien(self):
        assert LISTE.plan_for("Projet Inventé").empty

    def test_la_casse_et_les_espaces_sont_tolerés(self):
        assert not LISTE.plan_for("  evolve  ").empty

    def test_un_fichier_absent_est_un_cas_normal(self):
        """Ne pas avoir de profils n'est pas une erreur, c'est l'état initial."""
        from pathlib import Path

        assert load_profiles(Path("n-existe-pas.toml")).entries == {}


class TestRienNeSortDeLaListe:
    """Le nom du projet vient du réseau : il ne doit jamais devenir une commande."""

    @pytest.mark.parametrize(
        "hostile",
        [
            "Bestiaire — app mobile; rm -rf /",
            "../../etc/passwd",
            "$(calc.exe)",
            "Evolve && shutdown /s",
            "",
        ],
    )
    def test_un_nom_hostile_ne_produit_aucun_plan(self, hostile):
        assert LISTE.plan_for(hostile).empty

    def test_le_plan_ne_contient_que_des_valeurs_du_fichier(self):
        plan = LISTE.plan_for("Bestiaire — app mobile")
        declarees = set(LISTE.entries["Bestiaire — app mobile"]["folders"]) | set(
            LISTE.entries["Bestiaire — app mobile"]["urls"]
        )
        assert set(plan.folders) | set(plan.urls) <= declarees
        assert plan.commands == (), "aucune commande n'était déclarée"

    def test_les_entrees_vides_sont_ignorees(self):
        liste = Profiles(entries={"P": {"folders": ["", "   ", "C:/vrai"]}})
        assert liste.plan_for("P").folders == ("C:/vrai",)


class TestExecution:
    def test_la_simulation_n_execute_rien(self):
        faits = launch(
            Plan(project="P", folders=("C:/x",), commands=("echo bonjour",)), dry_run=True
        )
        assert all(f.startswith("[simulation]") for f in faits)
        assert len(faits) == 2

    def test_un_chemin_faux_n_empeche_pas_le_reste(self):
        """Un environnement à moitié ouvert reste plus utile qu'une erreur."""
        faits = launch(Plan(project="P", folders=("Z:/nulle-part-du-tout",)))
        assert len(faits) == 1
        assert faits[0].startswith("échec") or faits[0].startswith("ouvert")

    def test_le_resume_est_lisible(self):
        plan = Plan(project="P", folders=("a", "b"), urls=("u",))
        assert plan.summary() == "2 dossiers, 1 onglet"
        assert Plan(project="P").summary() == "rien"
