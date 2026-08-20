"""La ligne de la semaine : couverture, stabilité, et surtout le ton.

Le test du ton est le seul qui compte vraiment ici. Une table de quatre-vingt-
seize phrases est exactement l'endroit où le « bravo champion » du §5.2
rentrerait sans que personne ne s'en aperçoive : ça se lit bien, ça ne casse
rien, et le produit change de nature.
"""

from __future__ import annotations

import pytest

from forge.rules import citations
from forge.rules import seasons as season_rules


CLES = [identite["key"] for identite in season_rules.SEASON_POOL]


class TestCouverture:
    def test_chaque_saison_de_la_trame_a_ses_quatre_semaines(self):
        for cle in CLES:
            lignes = citations.CITATIONS.get(cle)
            assert lignes, f"« {cle} » n'a aucune ligne : sa saison passerait quatre semaines muette"
            assert len(lignes) == citations.SEMAINES_PAR_SAISON

    def test_aucune_ligne_ne_se_repete_dans_une_saison(self):
        for cle in CLES:
            lignes = citations.CITATIONS[cle]
            assert len(set(lignes)) == len(lignes), f"deux semaines identiques dans « {cle} »"

    def test_aucune_ligne_ne_se_repete_entre_saisons(self):
        """Une ligne partagée ferait mentir le décor : elle dirait la même
        chose depuis l'Empyrée et depuis le fond du Styx."""
        toutes = [ligne for cle in CLES for ligne in citations.CITATIONS[cle]]
        doublons = {l for l in toutes if toutes.count(l) > 1}
        assert not doublons, f"lignes partagées entre saisons : {doublons}"


class TestLaSemaine:
    @pytest.mark.parametrize(
        "jour, attendue",
        [(0, 1), (6, 1), (7, 2), (13, 2), (14, 3), (20, 3), (21, 4), (27, 4)],
    )
    def test_les_vingt_huit_jours_se_partagent_en_quatre_semaines(self, jour, attendue):
        assert citations.semaine_de(jour) == attendue

    def test_les_bords_ne_sortent_jamais_des_quatre(self):
        """Un jour négatif — saison engagée qui attend sa date, §12.4 — et un
        vingt-neuvième jour d'une saison prolongée doivent tomber dans la
        table, jamais sur une cinquième semaine qui n'existe pas."""
        assert citations.semaine_de(-3) == 1
        assert citations.semaine_de(40) == citations.SEMAINES_PAR_SAISON

    def test_la_ligne_ne_bouge_pas_dans_la_semaine(self):
        """Aucun tirage : rouvrir l'application ne doit jamais servir une
        phrase de plus. Le §11.1 refuse de récompenser ce geste-là."""
        semaine = {citations.citation_de("hellfest", jour) for jour in range(7, 14)}
        assert len(semaine) == 1

    def test_la_ligne_change_d_une_semaine_a_l_autre(self):
        vues = {citations.citation_de("hellfest", jour * 7) for jour in range(4)}
        assert len(vues) == 4

    def test_une_cle_inconnue_ne_rend_rien(self):
        """Le vide plutôt qu'un emprunt : une saison d'archive sans ligne vaut
        mieux qu'une saison d'archive portant celle d'une autre."""
        assert citations.citation_de("vigie", 3) == ""


class TestLeTon:
    """Le §5.2 : « zéro flatterie, zéro bravo champion ». Le §11.10 en fait une
    règle, pas une préférence."""

    # Les mots de la flatterie et du jugement. `test_gardes.py` tient la même
    # liste pour les dépassements ; celle-ci y ajoute ce qui est propre au
    # registre de l'affiche motivante.
    INTERDITS = (
        "bravo",
        "champion",
        "félicitations",
        "courage",
        "volonté",
        "discipline",
        "échec",
        "rechute",
        "mérites",
        "fier",
        "crois en toi",
        "tu peux le faire",
        "never give up",
        "no pain",
    )

    def test_aucune_ligne_ne_flatte_ni_ne_juge(self):
        for cle in CLES:
            for semaine, ligne in enumerate(citations.CITATIONS[cle], start=1):
                bas = ligne.lower()
                for mot in self.INTERDITS:
                    assert mot not in bas, f"« {mot} » dans {cle}, semaine {semaine} : {ligne}"

    def test_aucune_ligne_ne_s_adresse_a_la_personne_pour_la_qualifier(self):
        """Le tutoiement est autorisé — le §5.2 le demande même. Ce qui ne
        l'est pas, c'est de commenter celui qui lit : le décor nomme la
        situation, jamais la valeur de la personne qui la traverse."""
        for cle in CLES:
            for ligne in citations.CITATIONS[cle]:
                bas = ligne.lower()
                assert "tu es " not in bas, f"« {ligne} » qualifie la personne ({cle})"
                assert "tu as " not in bas, f"« {ligne} » qualifie la personne ({cle})"

    def test_les_lignes_restent_courtes(self):
        """Une phrase de décor se lit d'un coup d'œil, à côté d'une décision.
        Passé cette longueur, elle devient un paragraphe qu'on saute."""
        for cle in CLES:
            for ligne in citations.CITATIONS[cle]:
                assert len(ligne) <= 90, f"trop longue ({len(ligne)}) dans « {cle} » : {ligne}"

    def test_chaque_ligne_est_une_phrase_finie(self):
        for cle in CLES:
            for ligne in citations.CITATIONS[cle]:
                assert ligne[0].isupper(), f"« {ligne} » ne commence pas par une majuscule"
                assert ligne.endswith((".", "…", "?", "!")), f"« {ligne} » ne se termine pas"
