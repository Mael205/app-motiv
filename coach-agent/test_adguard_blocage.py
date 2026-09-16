"""Le blocage par le résolveur (SPEC §8.5, §9.1, §17).

Comme pour le fichier hosts, ce qui est vérifié n'est pas que ça bloque — ça
demande un vrai AdGuard — mais **ce que ça ne ferme pas** et ce que ça ne casse
pas : les règles de l'utilisateur, YouTube avant le couvre-feu, et les jeux.
"""

import adguard_blocage as ab

CATEGORIES = {
    "reseaux": ["tiktok.com", "x.com", "instagram.com"],
    "scroll_passif": ["youtube.com/shorts", "reddit.com"],
    "jeux": ["steam.exe", "dofus.com"],
    "travail_hors_projet": ["outlook.office.com"],
}


class TestCeQuiSeFerme:
    def test_rien_sans_niveau(self):
        assert ab.domaines_pour("", CATEGORIES) == []

    def test_le_soir_ferme_les_reseaux_et_le_scroll(self):
        fermes = ab.domaines_pour("projet", CATEGORIES)

        assert "tiktok.com" in fermes and "reddit.com" in fermes

    def test_le_soir_ne_ferme_pas_youtube(self):
        """§9.1 : un chemin n'est pas un domaine, et chercher n'est pas scroller."""
        fermes = ab.domaines_pour("projet", CATEGORIES)

        assert not any("youtube" in d for d in fermes)

    def test_la_nuit_ferme_youtube_en_entier(self):
        fermes = ab.domaines_pour("nuit", CATEGORIES)

        assert "youtube.com" in fermes and "youtu.be" in fermes

    def test_ni_les_jeux_ni_le_travail_ne_ferment_jamais(self):
        """§17 : pas de blocage des jeux. Jamais."""
        for niveau in ("projet", "nuit"):
            fermes = ab.domaines_pour(niveau, CATEGORIES)
            assert "dofus.com" not in fermes
            assert "outlook.office.com" not in fermes
            assert not any(d.endswith(".exe") for d in fermes)

    def test_la_regle_ferme_les_sous_domaines_et_rien_d_autre(self):
        assert ab.regles(["x.com"]) == ["||x.com^"]


class TestLesReglesDeLUtilisateur:
    def test_le_bloc_du_coach_s_ajoute_sans_toucher_au_reste(self):
        avant = ["||pub.example^", "@@||banque.example^"]

        apres = ab.avec_le_bloc(avant, ["||tiktok.com^"])

        assert apres[:2] == avant
        assert "||tiktok.com^" in apres

    def test_appliquer_deux_fois_donne_le_meme_resultat(self):
        avant = ["||pub.example^"]

        une = ab.avec_le_bloc(avant, ["||tiktok.com^"])
        deux = ab.avec_le_bloc(une, ["||tiktok.com^"])

        assert une == deux

    def test_le_retrait_rend_exactement_les_regles_d_origine(self):
        avant = ["||pub.example^", "@@||banque.example^"]

        assert ab.sans_le_bloc(ab.avec_le_bloc(avant, ["||x.com^"])) == avant

    def test_sans_rien_a_fermer_le_bloc_disparait(self):
        avant = ["||pub.example^"]

        assert ab.avec_le_bloc(ab.avec_le_bloc(avant, ["||x.com^"]), []) == avant
