"""Tests de l'XP, du plafond de régime, des niveaux et des rangs."""

import pytest

from forge.rules.xp import (
    MOMENTUM_CAP,
    degressivity_for,
    level_for,
    momentum,
    progression,
    rank_for,
    session_xp,
    xp_threshold,
)


def xp(**kwargs) -> int:
    defaults = dict(
        minutes=25,
        rank_in_day=1,
        is_first_of_day=True,
        started_hour=19,
        streak=0,
        days_worked_this_week=1,
    )
    return session_xp(**{**defaults, **kwargs}).total


class TestCalculDeBase:
    def test_session_plancher_du_soir(self):
        # 25 min + 20 (première) + 10 (avant 20h), aucun multiplicateur.
        assert xp() == 55

    def test_bonus_avant_vingt_heures_perdu_apres(self):
        assert xp(started_hour=21) == 45

    def test_seconde_session_du_jour_sans_bonus_de_premiere(self):
        assert xp(rank_in_day=2, is_first_of_day=False) == 35

    def test_multiplicateur_de_streak_plafonne_a_une_fois_et_demie(self):
        assert xp(streak=10) == round(55 * 1.5)
        assert xp(streak=40) == xp(streak=10)


class TestModeDegrade:
    def test_le_degrade_garde_son_bonus_de_premiere_session(self):
        """Décision assumée : le point dur est le démarrage, pas la durée."""
        assert xp(minutes=10) == 40

    def test_le_degrade_rapporte_moins_qu_une_session_pleine(self):
        assert xp(minutes=10) < xp(minutes=25) < xp(minutes=50)


class TestPlafondDeRegime:
    """Le trou du diagnostic §0.2 : sans plafond, le sur-régime produit le crash."""

    def test_les_trois_premieres_sessions_comptent_plein(self):
        assert degressivity_for(1) == degressivity_for(2) == degressivity_for(3) == 1.0

    def test_la_quatrieme_compte_a_moitie(self):
        assert degressivity_for(4) == 0.5
        assert xp(rank_in_day=4, is_first_of_day=False) == round(35 * 0.5)

    def test_la_cinquieme_ne_rapporte_plus_rien(self):
        assert xp(rank_in_day=5, is_first_of_day=False) == 0

    def test_le_depassement_est_explique_et_pas_puni(self):
        breakdown = session_xp(
            minutes=25, rank_in_day=5, is_first_of_day=False,
            started_hour=21, streak=3,
        )
        assert breakdown.total == 0
        assert breakdown.base == 25, "les minutes restent comptées"
        assert breakdown.notes, "l'utilisateur doit savoir pourquoi"

    def test_rang_de_session_invalide(self):
        with pytest.raises(ValueError):
            degressivity_for(0)


class TestMomentum:
    def test_monte_avec_les_jours_travailles(self):
        assert momentum(1) == 1.0
        assert momentum(3) == pytest.approx(1.10)

    def test_plafonne(self):
        assert momentum(20) == MOMENTUM_CAP


class TestNiveauxEtRangs:
    def test_seuils_croissants(self):
        seuils = [xp_threshold(n) for n in range(1, 8)]
        ecarts = [b - a for a, b in zip(seuils, seuils[1:])]
        assert seuils[0] == 0
        assert ecarts == sorted(ecarts), "la courbe doit être croissante"

    def test_niveau_depuis_xp(self):
        assert level_for(0) == 1
        assert level_for(99) == 1
        assert level_for(100) == 2
        assert level_for(299) == 2
        assert level_for(300) == 3

    def test_echelle_de_rangs(self):
        assert rank_for(1) == "F"
        assert rank_for(9) == "E"
        assert rank_for(25) == "B"
        assert rank_for(80) == "SS"

    def test_rang_ne_redescend_jamais(self):
        niveaux = list(range(1, 120))
        rangs = [rank_for(n) for n in niveaux]
        ordre = ["F", "E", "D", "C", "B", "A", "S", "SS"]
        indices = [ordre.index(r) for r in rangs]
        assert indices == sorted(indices)

    def test_progression_prete_pour_la_barre_dxp(self):
        p = progression(150)
        assert p["level"] == 2
        assert 0 <= p["ratio"] <= 1
        assert p["into_level"] == 50
