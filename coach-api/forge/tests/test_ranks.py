"""Tests du rang, devenu l'axe de fiabilité (SPEC §4.4, §4.3).

Le point que ces tests protègent tient en une phrase : **le rang ne doit jamais
pouvoir se gagner au volume**. L'XP monte en enchaînant les sessions, et
enchaîner les sessions est le mode de défaillance du §0.2. Si un jour quelqu'un
rebranche le rang sur l'XP, le système récompensera la dispersion par la
permission de se disperser davantage.

Le second invariant est la monotonie : un rang acquis ne se reprend jamais
(§17).
"""

from datetime import date, timedelta

import pytest

from forge.rules.ranks import (
    BASE_SLOTS,
    RANK_ORDER,
    next_rank,
    rank_for,
    rewards_for,
    unlock_label,
    weeks_kept,
)

LUNDI = date(2026, 3, 2)


def semaines(*tenues: bool, start: date = LUNDI):
    """Une liste de (lundi, tenu), un élément par semaine."""
    return [(start + timedelta(weeks=i), t) for i, t in enumerate(tenues)]


class TestEchelle:
    def test_on_commence_au_rang_F(self):
        assert rank_for(0) == "F"

    def test_les_paliers_sont_atteignables(self):
        assert rank_for(1) == "E"
        assert rank_for(2) == "D"
        assert rank_for(4) == "C"
        assert rank_for(6) == "B"
        assert rank_for(9) == "A"
        assert rank_for(14) == "S"
        assert rank_for(20) == "SS"

    def test_entre_deux_paliers_on_garde_le_precedent(self):
        assert rank_for(5) == "C"
        assert rank_for(8) == "B"
        assert rank_for(13) == "A"

    def test_le_rang_ne_redescend_jamais(self):
        rangs = [RANK_ORDER.index(rank_for(n)) for n in range(0, 40)]
        assert rangs == sorted(rangs)

    def test_le_quatrieme_slot_arrive_en_six_semaines(self):
        """Une saison et demie : assez long pour prouver, assez court pour être vu."""
        assert rewards_for(rank_for(5)).slots == BASE_SLOTS
        assert rewards_for(rank_for(6)).slots == 4


class TestRecompenses:
    def test_les_paliers_intermediaires_donnent_de_la_souplesse(self):
        """Un bouclier et un jour off de plus : ça aide à rester, pas à forcer."""
        assert rewards_for("D").extra_shields == 1
        assert rewards_for("C").extra_days_off == 1

    def test_les_recompenses_se_cumulent(self):
        haut = rewards_for("A")
        assert haut.slots == 5 and haut.extra_shields == 1 and haut.extra_days_off == 1

    def test_les_deux_derniers_rangs_ne_donnent_aucun_pouvoir(self):
        """S et SS sont du prestige. Le plafond de slots reste à cinq."""
        assert rewards_for("S").slots == rewards_for("SS").slots == 5

    def test_le_rang_F_n_ouvre_que_le_socle(self):
        base = rewards_for("F")
        assert base.slots == BASE_SLOTS
        assert base.extra_shields == 0 and base.extra_days_off == 0


class TestSemainesTenues:
    def test_une_semaine_ne_compte_que_si_tout_est_tenu(self):
        """Tenir deux projets sur trois n'est pas tenir sa semaine."""
        assert weeks_kept([(LUNDI, True), (LUNDI, True), (LUNDI, False)]) == 0
        assert weeks_kept([(LUNDI, True), (LUNDI, True)]) == 1

    def test_les_semaines_se_cumulent(self):
        assert weeks_kept(semaines(True, True, True)) == 3

    def test_une_mauvaise_semaine_n_en_retire_aucune(self):
        avant = weeks_kept(semaines(True, True))
        apres = weeks_kept(semaines(True, True, False, False))
        assert apres == avant == 2, "le rang ne redescend jamais (§17)"

    def test_une_semaine_sans_engagement_ne_compte_pas(self):
        """Ne rien promettre n'est pas tenir sa parole."""
        assert weeks_kept([]) == 0

    def test_le_prochain_palier_dit_ce_qui_manque(self):
        assert next_rank(5) == ("B", 1)
        assert next_rank(0) == ("E", 1)

    def test_au_sommet_il_n_y_a_plus_de_palier(self):
        assert next_rank(50) is None

    def test_le_prochain_deblocage_est_annonce(self):
        assert "quatrième slot" in unlock_label("C")
        assert "bouclier" in unlock_label("E")
        assert unlock_label("A") is None


@pytest.mark.django_db
class TestRangEnBase:
    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return user

    def test_sans_historique_on_est_rang_F_avec_trois_slots(self, user):
        from forge import services

        etat = services.rank_state(user, today=LUNDI)
        assert etat["code"] == "F" and etat["slots"] == 3

    def test_le_rang_monte_avec_les_engagements_tenus(self, user):
        from forge import services
        from forge.models import Commitment, Project, Track

        track = Track.objects.create(user=user, kind=Track.ATELIER)
        projet = Project.objects.create(user=user, track=track, name="P", slot=1)
        for i in range(6):
            Commitment.objects.create(
                project=projet,
                week_start=LUNDI - timedelta(weeks=i + 1),
                planned_sessions=3,
                done_sessions=3,
            )

        etat = services.rank_state(user, today=LUNDI)
        assert etat["weeks_kept"] == 6
        assert etat["code"] == "B"
        assert etat["slots"] == 4, "le quatrième slot s'ouvre au rang B"

    def test_enchainer_les_sessions_ne_monte_pas_le_rang(self, user):
        """Le cœur du sujet : du volume sans engagement tenu ne donne aucun droit."""
        from forge import services
        from forge.models import Commitment, Project, Track

        track = Track.objects.create(user=user, kind=Track.ATELIER)
        projet = Project.objects.create(user=user, track=track, name="P", slot=1)
        for i in range(6):
            Commitment.objects.create(
                project=projet,
                week_start=LUNDI - timedelta(weeks=i + 1),
                planned_sessions=5,
                done_sessions=2,       # beaucoup de sessions, engagement manqué
            )

        etat = services.rank_state(user, today=LUNDI)
        assert etat["code"] == "F"
        assert etat["slots"] == 3

    def test_le_slot_supplementaire_est_reellement_attribuable(self, user):
        from forge import services
        from forge.models import Commitment, Project, Track

        track = Track.objects.create(user=user, kind=Track.ATELIER)
        base = Project.objects.create(user=user, track=track, name="Socle", slot=1)
        for i in range(6):
            Commitment.objects.create(
                project=base, week_start=LUNDI - timedelta(weeks=i + 1),
                planned_sessions=3, done_sessions=3,
            )
        Project.objects.create(user=user, track=track, name="B", slot=2, domain="code")
        Project.objects.create(user=user, track=track, name="C", slot=3, domain="savoir")

        assert services.free_slot(user, "corps", today=LUNDI) == 4
