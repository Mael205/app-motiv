"""La ligne de la semaine : couverture, stabilité, et surtout le ton.

Le test du ton est le seul qui compte vraiment ici. Une table de quatre-vingt-
seize phrases est exactement l'endroit où le « bravo champion » du §5.2
rentrerait sans que personne ne s'en aperçoive : ça se lit bien, ça ne casse
rien, et le produit change de nature.
"""

from __future__ import annotations

import re

import pytest

from forge.rules import citations
from forge.rules import seasons as season_rules


CLES = [identite["key"] for identite in season_rules.SEASON_POOL]


# Les adjectifs par lesquels une ligne cesserait de nommer une situation pour
# noter celui qui la traverse. C'est de ça que le §5.2 protège, et de rien
# d'autre : le tutoiement, lui, est demandé.
QUALIFICATIFS = (
    "capable",
    "fort",
    "faible",
    "courageux",
    "lache",
    "lâche",
    "paresseux",
    "formidable",
    "exceptionnel",
    "nul",
    "meilleur que",
)

# La copule à la deuxième personne. L'adjectif ne compte que s'il vient après
# elle, dans la même proposition.
COPULE = re.compile(r"\btu\s+(?:n['’]\s*)?(?:es|etais|étais|seras|deviens|resteras)\b")


def qualification_du_lecteur(ligne: str) -> str:
    """L'adjectif rattaché **au lecteur**, s'il y en a un. Vide sinon.

    La présence seule ne suffit pas : dans « le courant paraît plus fort que
    toi », l'adjectif qualifie le courant. On ne le cherche donc qu'après une
    copule à la deuxième personne, et dans la même proposition qu'elle.
    """
    for proposition in re.split(r"[.!?;]", ligne.lower()):
        copule = COPULE.search(proposition)
        if copule is None:
            continue
        suite = proposition[copule.end() :]
        for mot in QUALIFICATIFS:
            if mot in suite:
                return mot
    return ""


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

    def test_aucune_ligne_ne_recopie_la_baseline_de_sa_saison(self):
        """La baseline s'affiche déjà en grand à l'ouverture de la saison. Une
        semaine qui la répète mot pour mot ne donne rien de neuf à lire — c'est
        ce que la première version faisait sur quinze saisons sur vingt-quatre.
        """
        for identite in season_rules.SEASON_POOL:
            baseline = identite["baseline"]
            for semaine, ligne in enumerate(citations.CITATIONS[identite["key"]], start=1):
                assert ligne != baseline, (
                    f"{identite['key']}, semaine {semaine} recopie sa baseline"
                )


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

    def test_aucune_ligne_ne_note_celui_qui_lit(self):
        """Le tutoiement est autorisé — le §5.2 le demande même, et la
        réécriture du 21 août 2026 s'y est alignée : les lignes tutoient et
        poussent.

        Ce qui reste interdit est de **qualifier** la personne. La garde a été
        resserrée deux fois : elle refusait d'abord toute occurrence de
        « tu es » et « tu as », donc aussi « ce que tu as monté » — un acte
        accompli, qui ne note personne ; puis la simple présence d'un adjectif,
        donc aussi « le courant paraît plus fort que toi », où l'adjectif
        qualifie le courant. Elle porte maintenant sur l'adjectif **rattaché au
        lecteur**, et sur rien d'autre.
        """
        for cle in CLES:
            for ligne in citations.CITATIONS[cle]:
                faute = qualification_du_lecteur(ligne)
                assert not faute, f"« {ligne} » note la personne ({cle}) : {faute}"

    def test_la_garde_attrape_ce_qu_elle_pretend_attraper(self):
        """Le test du test, et il n'est pas superflu.

        Une version intermédiaire de cette garde ne renvoyait jamais rien : les
        vingt-quatre saisons passaient au vert alors que « Tu es capable de le
        faire » serait passé aussi. Une garde qu'on ne met pas à l'épreuve est
        une garde qu'on croit avoir.
        """
        assert qualification_du_lecteur("Tu es capable de le faire.") == "capable"
        assert qualification_du_lecteur("Tu n'es pas nul, continue.") == "nul"
        assert qualification_du_lecteur("Tu deviens paresseux.") == "paresseux"

        # Ce qui doit passer : l'adjectif porte sur autre chose que le lecteur,
        # ou la phrase constate un acte au lieu de noter une personne.
        assert qualification_du_lecteur("Le courant paraît plus fort que toi.") == ""
        assert qualification_du_lecteur("Ce que tu as monté ne se redescend pas.") == ""
        assert qualification_du_lecteur("Tu tiens le fond. Prends appui dessus.") == ""

    def test_les_lignes_tutoient_vraiment(self):
        """La réécriture du 21 août avait un objet mesurable : vingt-deux lignes
        sur quatre-vingt-seize employaient le « l'on » littéraire et trois
        seulement tutoyaient, alors que le §5.2 demande « français, tutoiement,
        direct ». C'est ce qui les faisait sonner traduites.
        """
        tutoyantes = [
            ligne
            for cle in CLES
            for ligne in citations.CITATIONS[cle]
            if re.search(r"\b(tu|te|toi|ton|ta|tes)\b", ligne.lower())
            or re.search(r"\b\w+(?:e|s|ds)\b[ .!]", ligne)  # impératif : « avance. », « prends »
        ]
        assert len(tutoyantes) >= 72, f"seulement {len(tutoyantes)} lignes sur 96 s'adressent au lecteur"

    def test_plus_aucune_ligne_n_emploie_le_on_litteraire(self):
        for cle in CLES:
            for semaine, ligne in enumerate(citations.CITATIONS[cle], start=1):
                assert "l'on" not in ligne.lower(), (
                    f"« l'on » dans {cle}, semaine {semaine} : {ligne}"
                )

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
