"""Tests de l'XP, du plafond de régime, des niveaux et des rangs."""

import pytest

from forge.rules.xp import (
    MOMENTUM_CAP,
    PONCTUALITE_BONUS,
    TOLERANCE_MINUTES,
    a_l_heure,
    degressivity_for,
    level_for,
    momentum,
    progression,
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
        # 25 min + 20 (première session). Aucun créneau déclaré : rien à tenir,
        # donc rien à primer.
        assert xp() == 45

    def test_seconde_session_du_jour_sans_bonus_de_premiere(self):
        assert xp(rank_in_day=2, is_first_of_day=False) == 25

    def test_multiplicateur_de_streak_plafonne_a_une_fois_et_demie(self):
        assert xp(streak=10) == round(45 * 1.5)
        assert xp(streak=40) == xp(streak=10)


class TestPrimeDePonctualite:
    """Le rendez-vous tenu, et non l'heure de l'horloge (§11.2, 20 août 2026).

    La règle qu'elle remplace payait « avant 20h » : elle récompensait le matin,
    ignorait un créneau déclaré à 21h, et se contredisait avec une app qui
    annonce une heure précise. Celle-ci paie la parole tenue, à n'importe quelle
    heure.
    """

    def test_dans_la_demi_heure_du_creneau(self):
        assert xp(ecart_au_creneau=0) == 45 + PONCTUALITE_BONUS
        assert xp(ecart_au_creneau=TOLERANCE_MINUTES) == 45 + PONCTUALITE_BONUS

    def test_hors_de_la_demi_heure(self):
        assert xp(ecart_au_creneau=TOLERANCE_MINUTES + 1) == 45

    def test_l_heure_du_creneau_n_a_aucune_importance(self):
        """Un créneau de 22h tenu vaut exactement un créneau de 18h tenu."""
        assert xp(started_hour=22, ecart_au_creneau=5) == xp(started_hour=18, ecart_au_creneau=5)

    def test_sans_creneau_il_n_y_a_rien_a_tenir(self):
        """Pas une punition : l'absence de promesse. Le §17 interdit le malus."""
        assert xp(ecart_au_creneau=None) == xp(ecart_au_creneau=999)
        assert not a_l_heure(None)

    def test_arriver_tres_en_avance_n_est_pas_etre_a_l_heure(self):
        """Sinon la prime redeviendrait « avant l'heure », la règle retirée."""
        assert not a_l_heure(-120)
        assert a_l_heure(-15)

    def test_la_relique_ne_touche_que_sa_ligne(self):
        detail = session_xp(
            minutes=25,
            rank_in_day=1,
            is_first_of_day=True,
            started_hour=19,
            streak=0,
            ecart_au_creneau=0,
            punctuality_bonus_ratio=0.5,
        )
        assert detail.punctual == round(PONCTUALITE_BONUS * 1.5)
        assert detail.base == 25 and detail.first_of_day == 20


class TestModeDegrade:
    def test_le_degrade_garde_son_bonus_de_premiere_session(self):
        """Décision assumée : le point dur est le démarrage, pas la durée."""
        assert xp(minutes=10) == 30

    def test_le_degrade_rapporte_moins_qu_une_session_pleine(self):
        assert xp(minutes=10) < xp(minutes=25) < xp(minutes=50)


class TestPlafondDeRegime:
    """Le trou du diagnostic §0.2 : sans plafond, le sur-régime produit le crash."""

    def test_les_trois_premieres_sessions_comptent_plein(self):
        assert degressivity_for(1) == degressivity_for(2) == degressivity_for(3) == 1.0

    def test_la_quatrieme_compte_a_moitie(self):
        assert degressivity_for(4) == 0.5
        assert xp(rank_in_day=4, is_first_of_day=False) == round(25 * 0.5)

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

    def test_l_xp_ne_decide_plus_du_rang(self):
        """Le rang mesure la fiabilité, pas le volume (SPEC §4.4).

        Ce test garde la séparation : si quelqu'un réintroduit un rang calculé
        depuis l'XP, le système recommencera à récompenser la dispersion.
        """
        from forge.rules import xp as module

        assert not hasattr(module, "rank_for")
        assert not hasattr(module, "RANKS")
        assert "rank" not in progression(50_000)

    def test_progression_prete_pour_la_barre_dxp(self):
        p = progression(150)
        assert p["level"] == 2
        assert 0 <= p["ratio"] <= 1
        assert p["into_level"] == 50
