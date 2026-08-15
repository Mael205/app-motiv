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


class TestIdentite:
    def test_une_saison_a_toujours_un_nom_et_un_accent(self):
        for i in range(20):
            identity = pick_identity(i)
            assert identity["name"] and identity["accent"].startswith("#")

    def test_les_saisons_recentes_ne_se_repetent_pas(self):
        deja = {"hellfest", "ragnarok"}
        for i in range(10):
            assert pick_identity(i, deja)["key"] not in deja

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
