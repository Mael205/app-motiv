"""Modificateurs appliqués et fantôme de saison (SPEC §12.5, §12.7).

Deux mécaniques que la spec décrivait et que le code ne faisait pas : les
paramètres des modificateurs n'étaient lus par personne — la saison 5 était donc
identique à la saison 1, c'est-à-dire exactement ce qu'un modificateur existe
pour empêcher — et le fantôme n'avait ni courbe ni comparaison.

Les tests portent surtout sur les **neutres** et les **bornes**. Un modificateur
qui déborderait sur le streak, ou un fantôme qui bondirait le jour où sa saison
de référence s'arrête, produiraient des chiffres inexplicables — et un chiffre
inexplicable détruit la confiance plus vite qu'une règle dure.
"""

import pytest

from forge.rules import modifiers, phantom, seasons


class TestModificateurs:
    def test_une_cle_inconnue_est_neutre(self):
        """Une saison ouverte avec un modificateur retiré du catalogue doit se jouer."""
        assert modifiers.resolve("inexistant") == modifiers.NEUTRE
        assert modifiers.resolve(None) == modifiers.NEUTRE
        assert modifiers.resolve("") == modifiers.NEUTRE

    def test_le_neutre_ne_change_rien(self):
        """Ajouter la mécanique ne doit pas modifier les parties déjà jouées."""
        neutre = modifiers.NEUTRE

        assert neutre.early_multiplier == 1.0
        assert neutre.long_multiplier == 1.0
        assert neutre.degraded_enabled is True
        assert neutre.full_xp_sessions == 3
        assert neutre.stake_multiplier == 1
        assert modifiers.session_multiplier(neutre, minutes=50, started_hour=18) == 1.0

    def test_chaque_modificateur_du_catalogue_se_resout(self):
        for entree in seasons.MODIFIERS:
            effets = modifiers.resolve(entree["key"])

            assert effets.active
            assert effets.name
            assert effets.effet

    def test_aube_paie_le_matin(self):
        effets = modifiers.resolve("aube")

        assert modifiers.session_multiplier(effets, minutes=25, started_hour=18) > 1.0
        assert modifiers.session_multiplier(effets, minutes=25, started_hour=21) == 1.0

    def test_marathon_paie_les_longues_et_ferme_le_degrade(self):
        effets = modifiers.resolve("marathon")

        assert modifiers.session_multiplier(effets, minutes=50, started_hour=21) == 1.5
        assert modifiers.session_multiplier(effets, minutes=25, started_hour=21) == 1.0
        assert effets.degraded_enabled is False

    def test_fragmentation_ouvre_une_quatrieme_session(self):
        assert modifiers.resolve("fragmentation").full_xp_sessions == 4

    def test_siege_gonfle_le_boss_et_la_mise(self):
        effets = modifiers.resolve("siege")

        assert effets.boss_hp_multiplier > 1
        assert effets.stake_multiplier == 2

    def test_aucun_modificateur_ne_touche_au_streak_ni_aux_gardes(self):
        """Un modificateur change ce qui rapporte, jamais ce qui définit une journée tenue."""
        champs = set(modifiers.Effects.__dataclass_fields__)
        interdits = {"streak", "shields_lost", "garde_budget", "rank", "day_held"}

        assert not (champs & interdits)

    def test_les_primes_se_cumulent(self):
        """Écrit pour rester vrai si deux modificateurs coexistaient un jour."""
        cumul = modifiers.Effects(key="test", early_multiplier=1.3, long_multiplier=1.5)

        assert modifiers.session_multiplier(cumul, minutes=50, started_hour=18) == pytest.approx(1.95)

    def test_la_description_est_vide_sans_modificateur(self):
        assert modifiers.describe(modifiers.NEUTRE) == ""
        assert "Aube" in modifiers.describe(modifiers.resolve("aube"))


class TestFantome:
    def test_la_courbe_cumule_les_minutes(self):
        assert phantom.cumulative([30, 0, 50, 25]) == (30, 30, 80, 105)

    def test_une_courbe_ne_descend_jamais(self):
        points = phantom.cumulative([25, 0, 50, 0, 10])

        assert all(b >= a for a, b in zip(points, points[1:]))

    def test_la_courbe_se_prolonge_apres_son_dernier_jour(self):
        """Sinon l'écart bondirait le jour où la saison de référence s'arrête."""
        courbe = phantom.Curve("x", (10, 20, 30))

        assert courbe.at(10) == 30
        assert courbe.at(-5) == 10

    def test_sans_saison_passee_il_n_y_a_pas_de_fantome(self):
        """Le §12.7 le prévoit : la première saison est la référence des suivantes."""
        assert phantom.pick([], phantom.MEILLEURE) is None
        assert phantom.pick([phantom.Curve("vide", ())], phantom.MEILLEURE) is None

    def test_la_meilleure_est_celle_qui_totalise_le_plus(self):
        a = phantom.Curve("A", (10, 20, 30))
        b = phantom.Curve("B", (5, 40, 80))

        assert phantom.pick([a, b], phantom.MEILLEURE).label == "B"

    def test_la_derniere_est_la_plus_recente(self):
        a = phantom.Curve("A", (10, 20, 900))
        b = phantom.Curve("B", (5, 10, 15))

        assert phantom.pick([a, b], phantom.DERNIERE).label == "B"

    def test_la_moyenne_conserve_le_rythme(self):
        """Moyenne des cumuls, pas cumul des moyennes : la forme se compare."""
        lente = phantom.Curve("lente", (0, 0, 60))
        rapide = phantom.Curve("rapide", (60, 60, 60))

        moyenne = phantom.pick([lente, rapide], phantom.MOYENNE)

        assert moyenne.points == (30, 30, 60)

    def test_l_ecart_est_rendu_en_heures_lisibles(self):
        mienne = phantom.Curve("moi", (0, 100, 260))
        fantome = phantom.Curve("Ragnarök", (0, 60, 100))

        ligne = phantom.compare(mienne, fantome, day_index=2).line

        assert "+2h40" in ligne
        assert "Ragnarök" in ligne

    def test_l_ecart_negatif_dit_que_le_fantome_est_devant(self):
        mienne = phantom.Curve("moi", (0, 0, 20))
        fantome = phantom.Curve("Hellfest", (0, 0, 90))

        ligne = phantom.compare(mienne, fantome, day_index=2).line

        assert "devant" in ligne
        assert "1h10" in ligne

    def test_aucune_ligne_ne_juge(self):
        """Le §0.2 : le système n'est pas là pour motiver ni pour reprocher."""
        mienne = phantom.Curve("moi", (0, 0, 10))
        fantome = phantom.Curve("Nadir", (0, 0, 400))
        ligne = phantom.compare(mienne, fantome, day_index=2).line

        for mot in ("retard", "bravo", "courage", "mauvais", "déçu", "！", "!"):
            assert mot not in ligne

    def test_sans_fantome_la_ligne_explique_au_lieu_de_se_taire(self):
        ligne = phantom.compare(phantom.Curve("moi", (10,)), None, day_index=0).line

        assert "Première saison" in ligne

    def test_la_serie_montre_ou_l_adversaire_sera(self):
        """La courbe personnelle s'arrête au jour courant, celle du fantôme non."""
        mienne = phantom.Curve("moi", (10, 20))
        fantome = phantom.Curve("F", (5, 15, 30, 50))

        points = phantom.series(mienne, fantome, days=4)

        assert points[3]["mine"] is None
        assert points[3]["phantom"] == 50

    def test_chaque_choix_a_un_libelle(self):
        for choix in phantom.CHOIX:
            assert phantom.CHOIX_LABELS[choix]


class TestTraceDeLaCourse:
    """Ce que le graphique doit dire, et ce qu'il ne doit pas laisser croire."""

    def test_ma_courbe_s_arrete_au_jour_courant(self):
        """Une courbe qui continue à plat se lit « je n'ai rien fait ces jours-là »
        alors que ces jours ne sont pas encore arrivés — constaté à l'écran."""
        mienne = phantom.Curve("moi", (10, 30, 60))
        fantome = phantom.Curve("F", (5, 15, 30, 50, 80))

        points = phantom.series(mienne, fantome, days=5)

        assert [p["mine"] for p in points] == [10, 30, 60, None, None]

    def test_le_fantome_va_jusqu_au_bout(self):
        """On doit voir où l'adversaire SERA, pas seulement où il est."""
        points = phantom.series(
            phantom.Curve("moi", (10,)), phantom.Curve("F", (5, 15, 30)), days=3
        )

        assert [p["phantom"] for p in points] == [5, 15, 30]
