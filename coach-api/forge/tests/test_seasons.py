"""Tests des saisons : identité, boss, modificateurs, fantôme, titres."""

from datetime import date

from forge.rules.seasons import (
    SEASON_DAYS,
    boss_hp,
    damage_of,
    ghost_delta,
    next_season_start,
    pick_identity,
    plan_season,
    propose_modifiers,
    title_for,
)


from forge.rules import seasons  # noqa: E402


class TestIdentite:
    def test_une_saison_a_toujours_un_nom_et_un_accent(self):
        for i in range(20):
            identity = pick_identity(i)
            assert identity["name"] and identity["accent"].startswith("#")

    def test_chaque_voie_traverse_ses_douze_sans_repetition(self):
        """Douze saisons sur une même voie, douze noms différents.

        L'ordre est **fixe** depuis le 20 août 2026, et c'est le contraire de la
        règle précédente : les identités étaient tirées dans une permutation qui
        changeait chaque année, pour que deux années ne se ressemblent pas. Ça
        empêchait la répétition et empêchait aussi toute histoire.
        """
        from forge.rules.seasons import TRAME

        for voie, ligne in TRAME.items():
            cles = [
                seasons.identite_de_voie(voie, position)["key"]
                for position in range(len(ligne))
            ]
            assert len(set(cles)) == len(ligne), voie

    def test_les_deux_voies_ne_partagent_aucun_nom(self):
        """Sinon une saison ratée pourrait porter le nom d'un sommet."""
        from forge.rules.seasons import TRAME, VOIE_BRAISES, VOIE_CIMES

        cimes = {i["key"] for i in TRAME[VOIE_CIMES]}
        braises = {i["key"] for i in TRAME[VOIE_BRAISES]}
        assert cimes.isdisjoint(braises)

    def test_on_commence_toujours_par_l_eveil(self):
        assert pick_identity(1)["key"] == "eveil"
        assert pick_identity(0)["key"] == "eveil", "l'essai aussi : c'est un éveil"

    def test_une_saison_tenue_monte_une_saison_ratee_descend(self):
        assert seasons.voie_apres(True) == seasons.VOIE_CIMES
        assert seasons.voie_apres(False) == seasons.VOIE_BRAISES
        assert seasons.voie_apres(None) == seasons.VOIE_CIMES, "on commence en haut"

    def test_trois_modificateurs_proposes_et_distincts(self):
        propositions = propose_modifiers(0)
        assert len(propositions) == 3
        assert len({m["key"] for m in propositions}) == 3


class TestDureeEtEnchainement:
    def test_une_saison_dure_quatre_semaines(self):
        plan = plan_season(0, date(2026, 3, 2))
        assert plan.days_total == SEASON_DAYS
        assert plan.ends_on == date(2026, 3, 29)

    def test_deux_jours_de_pause_entre_deux_saisons(self):
        plan = plan_season(0, date(2026, 3, 2))
        suivante = next_season_start(plan.ends_on)
        assert (suivante - plan.ends_on).days == 3, "2 jours neutres puis reprise"


class TestBoss:
    def test_la_vie_du_boss_monte_de_cinq_pourcent(self):
        assert boss_hp(10_000) == 10_500

    def test_premiere_saison_dimensionnee_sur_le_contrat(self):
        assert boss_hp(None, contract_sessions_per_week=3) >= 1500

    def test_les_degats_viennent_du_travail_reel(self):
        assert damage_of(minutes=25) == 25
        assert damage_of(steps_done=1) == 60
        assert damage_of(minutes=50, steps_done=1, commitments_kept=1) == 155

    def test_aucun_degat_sans_travail(self):
        assert damage_of() == 0


class TestFantome:
    def test_avance_sur_le_fantome(self):
        mine = [0, 100, 250, 400]
        ghost = [0, 90, 180, 270]
        assert ghost_delta(3, mine, ghost) == 130

    def test_retard_sur_le_fantome(self):
        assert ghost_delta(2, [0, 50, 60], [0, 90, 180]) == -120

    def test_fantome_absent_a_la_premiere_saison(self):
        assert ghost_delta(5, [0, 100], []) == 100


class TestTitres:
    def test_le_titre_rate_existe_aussi(self):
        assert title_for(0.1, "Ragnarök") == "Déserteur de Ragnarök"

    def test_echelle_complete(self):
        assert title_for(1.0, "Hellfest") == "Vainqueur de Hellfest"
        assert title_for(0.8, "Hellfest") == "Survivant de Hellfest"
        assert title_for(0.5, "Hellfest") == "Vétéran de Hellfest"
