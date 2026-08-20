"""Tests des règles du jeu : arbre, loot, reliques, momentum (SPEC §12).

Ces mécaniques rendent le système désirable (§16, J2). Un bug ici ne casse pas
le coach — il casse l'envie de l'ouvrir, ce qui revient au même d'après le §0.10.

Les tests portent donc surtout sur les **promesses**, pas sur les calculs :
aucune carte ne donne de pouvoir, aucun palier ne redescend, la chaleur ne
s'éteint jamais d'un coup, et trois reliques au maximum comptent.
"""

import random

import pytest

from forge.rules import loot, momentum, relics, skills


class TestArbreDeCompetences:
    def test_les_paliers_suivent_les_heures_cumulees(self):
        assert skills.tier_for(0) == 0
        assert skills.tier_for(9 * 60) == 0
        assert skills.tier_for(10 * 60) == 1
        assert skills.tier_for(400 * 60) == len(skills.TIER_HOURS)

    def test_un_palier_ne_redescend_jamais(self):
        """Les heures ont été faites ; le §17 interdit de reprendre du travail réel."""
        precedent = 0
        for minutes in range(0, 500 * 60, 3600):
            palier = skills.tier_for(minutes)
            assert palier >= precedent
            precedent = palier

    def test_les_branches_vides_sont_rendues(self):
        """Une branche à l'arrêt est l'information la plus utile de l'écran."""
        arbre = skills.tree({skills.BACKEND: 3000})

        assert len(arbre) == len(skills.BRANCHES)
        assert any(b.minutes == 0 for b in arbre)

    def test_deux_projets_de_la_meme_branche_s_additionnent(self):
        """Ce qu'un compteur par projet cache, et la raison d'être du §12.9."""
        etat = skills.branch_state(skills.MOTEUR_DE_JEU, 20 * 60 + 20 * 60)

        assert etat.hours == 40.0
        assert etat.tier == 2

    def test_le_franchissement_se_detecte_une_seule_fois(self):
        assert skills.newly_reached(9 * 60, 11 * 60) == 1
        assert skills.newly_reached(11 * 60, 12 * 60) is None

    def test_la_forme_dit_ce_qui_est_a_l_arret(self):
        forme = skills.shape(skills.tree({skills.BACKEND: 6000, skills.CORPS: 600}))

        assert forme["dominante"] == skills.BACKEND
        assert skills.CYBER in forme["a_l_arret"]
        assert forme["branches_actives"] == 2

    def test_chaque_branche_a_autant_de_titres_que_de_paliers(self):
        for branche in skills.BRANCHES:
            assert len(skills.TITLES[branche]) == len(skills.TIER_HOURS)


class TestLoot:
    def test_aucune_carte_ne_donne_de_pouvoir(self):
        """La promesse du §12.6 et du §17, tenue par un test plutôt qu'un commentaire."""
        cosmetiques = {"theme", "emblem", "frame", "title", "finisher"}

        assert {c.kind for c in loot.CATALOGUE} <= cosmetiques

    def test_chaque_rarete_a_des_cartes(self):
        for rarete in loot.RARETES:
            assert loot.PAR_RARETE[rarete], f"aucune carte {rarete}"

    def test_la_pitie_monte_la_chance_sans_la_forcer_d_un_coup(self):
        """Une pitié qui bascule sèchement se lit comme un système qui triche."""
        base = loot.rarity_weights(draws_since_rare=0, draws_since_epic=0)
        tendue = loot.rarity_weights(draws_since_rare=loot.PITIE_RARE, draws_since_epic=0)

        assert tendue[loot.RARE] > base[loot.RARE]
        assert tendue[loot.COMMUN] < base[loot.COMMUN]

    def test_la_pitie_finit_par_garantir_le_rare(self):
        poids = loot.rarity_weights(draws_since_rare=50, draws_since_epic=0)

        assert poids[loot.COMMUN] == 0

    def test_un_doublon_rend_des_eclats_et_une_nouveaute_non(self):
        """Aucun tirage n'est vide, mais la nouveauté est déjà la récompense."""
        carte = loot.PAR_CLE["theme_braise"]

        assert loot.shards_for(carte, duplicate=True) > 0
        assert loot.shards_for(carte, duplicate=False) == 0

    def test_le_tirage_est_reproductible(self):
        """Sans graine fixable, aucun test de tirage n'aurait de sens."""
        a = loot.draw(rng=random.Random(42))
        b = loot.draw(rng=random.Random(42))

        assert a[0].key == b[0].key

    def test_un_doublon_est_signale(self):
        carte, doublon = loot.draw(owned={c.key for c in loot.CATALOGUE}, rng=random.Random(1))

        assert doublon is True

    def test_la_semaine_paie_la_fiabilite_pas_le_volume(self):
        """Même séparation qu'au §4.4 : le sur-régime ne rapporte pas de carte."""
        assert loot.draws_for_week(days_kept=7, commitments_kept=False) == 1
        assert loot.draws_for_week(days_kept=3, commitments_kept=True) == 2
        assert loot.draws_for_week(days_kept=0, commitments_kept=True) == 0


class TestReliques:
    def test_une_relique_vient_d_un_haut_fait_jamais_d_un_tirage(self):
        """Elle récompense du travail réel, pas de la chance (§17)."""
        cles_de_loot = {c.key for c in loot.CATALOGUE}

        for relique in relics.CATALOGUE:
            assert relique.achievement
            assert relique.key not in cles_de_loot

    def test_trois_reliques_au_maximum_comptent(self):
        toutes = [r.key for r in relics.CATALOGUE]
        assert len(toutes) > relics.MAX_EQUIPEES

        cumul = relics.bonuses(toutes)
        trois = relics.bonuses(toutes[: relics.MAX_EQUIPEES])

        assert cumul == trois

    def test_le_plafond_s_applique_meme_a_une_ecriture_directe_en_base(self):
        """``bonuses`` est le seul chemin de calcul : la règle y est inviolable."""
        cumul = relics.bonuses([r.key for r in relics.CATALOGUE])

        assert cumul.extra_shields <= 1
        assert cumul.punctuality_bonus <= 0.05

    def test_aucune_relique_ne_touche_au_streak_ni_aux_gardes(self):
        """Une relique qui rendrait une journée tenue sans travail viderait le cœur."""
        effets = {r.effect for r in relics.CATALOGUE}
        interdits = {"streak", "garde", "rang", "jour_tenu"}

        assert not (effets & interdits)

    def test_le_refus_d_equiper_dit_pourquoi(self):
        """Un refus muet dans une interface de jeu se lit comme un bug."""
        equipees = [r.key for r in relics.CATALOGUE[: relics.MAX_EQUIPEES]]
        ok, motif = relics.can_equip(equipees, relics.CATALOGUE[4].key)

        assert ok is False
        assert str(relics.MAX_EQUIPEES) in motif

    def test_les_bonus_s_additionnent_jamais_ne_se_multiplient(self):
        seule = relics.bonuses(["montre_de_gousset"])
        assert seule.punctuality_bonus == pytest.approx(0.05)


class TestMomentum:
    def test_la_jauge_monte_avec_les_jours_travailles(self):
        froid = momentum.evaluate([False] * 7)
        chaud = momentum.evaluate([True] * 7)

        assert froid.multiplier == momentum.MULT_MIN
        assert chaud.multiplier == momentum.MULT_MAX

    def test_un_jour_rate_tiedit_mais_n_eteint_pas(self):
        """L'anti-fragilité du §4.2 : revenir doit rester moins cher que tenir."""
        avant = momentum.evaluate([True] * 5)
        apres = momentum.evaluate([True] * 5 + [False])

        assert apres.level < avant.level
        assert apres.level > 0

    def test_revenir_rapporte_plus_que_l_absence_n_a_coute(self):
        """L'asymétrie chiffrée : deux jours manqués pour effacer un jour fait."""
        assert momentum.CHAUFFE > momentum.REFROIDIT

    def test_la_jauge_ne_descend_jamais_sous_zero(self):
        assert momentum.evaluate([False] * 30).level == 0.0

    def test_la_jauge_ne_depasse_jamais_son_plafond(self):
        assert momentum.evaluate([True] * 60).multiplier == momentum.MULT_MAX

    def test_la_fenetre_est_glissante_pas_calendaire(self):
        """Sinon le dimanche soir serait le pire moment de la semaine pour travailler."""
        longue = momentum.evaluate([True] * 20).level
        courte = momentum.evaluate([True] * momentum.FENETRE).level

        assert longue == courte

    def test_le_refroidissement_est_signale(self):
        assert momentum.evaluate([True, True, False]).cooling is True
        assert momentum.evaluate([False, True]).cooling is False

    def test_chaque_niveau_a_un_libelle(self):
        for jours in range(8):
            etat = momentum.evaluate([True] * jours)
            assert etat.label and etat.detail
