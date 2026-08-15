"""Tests de la piste Entretien (SPEC §11.9).

Deux invariants sont surveillés ici, parce que ce sont eux qui empêchent la
piste de redevenir l'habit tracker que le §0 refuse :

* **aucun compteur ne redescend** — une mauvaise semaine n'ajoute rien et ne
  retire rien ;
* **aucune XP** — une routine se paie en Éclats, et seulement jusqu'à son
  objectif hebdomadaire.
"""

from datetime import date, timedelta

import pytest

from forge.rules.calendar import week_start
from forge.rules.routines import (
    AVANT_COUCHER,
    REVEIL,
    SHARDS_PER_CHECK,
    Routine,
    held_weeks,
    piste_held_weeks,
    piste_week_held,
    shards_for_check,
    today_panel,
    week_state,
)

LUNDI = date(2026, 3, 2)


def jours(*offsets: int, start: date = LUNDI) -> list[date]:
    return [start + timedelta(days=o) for o in offsets]


SKINCARE = Routine(key="skincare", name="Skincare du soir", weekly_target=6, anchor=AVANT_COUCHER)
ETIREMENTS = Routine(key="etirements", name="Étirements", weekly_target=4, anchor=REVEIL)


class TestRythmeEtSeuil:
    """Le rythme d'apparition et le seuil hebdomadaire sont deux réglages distincts."""

    def test_routine_sans_jours_est_proposee_tous_les_jours(self):
        assert all(SKINCARE.is_due(LUNDI + timedelta(days=i)) for i in range(7))

    def test_routine_avec_jours_n_est_proposee_que_ces_jours_la(self):
        muscu = Routine(key="muscu", name="Gainage", weekly_target=2, weekdays=(1, 3))
        assert muscu.is_due(LUNDI + timedelta(days=1))
        assert not muscu.is_due(LUNDI)

    def test_le_battement_est_l_ecart_entre_rythme_et_seuil(self):
        # Proposée 7 jours, objectif 6 : un oubli toléré. C'est le bouclier du §4.2,
        # exprimé dans le cadre hebdomadaire.
        assert SKINCARE.slack == 1
        assert ETIREMENTS.slack == 3

    def test_un_battement_nul_est_une_chaine_cassable(self):
        stricte = Routine(key="s", name="Stricte", weekly_target=7)
        assert stricte.slack == 0


class TestSemaine:
    def test_semaine_tenue_au_seuil_exact(self):
        state = week_state(SKINCARE, jours(0, 1, 2, 3, 4, 5), LUNDI)
        assert state.done == 6 and state.held

    def test_un_oubli_isole_ne_casse_rien(self):
        # Six coches sur sept jours : la semaine tient malgré le mardi manqué.
        state = week_state(SKINCARE, jours(0, 2, 3, 4, 5, 6), LUNDI)
        assert state.held
        assert state.remaining == 0

    def test_semaine_non_tenue_sous_le_seuil(self):
        state = week_state(SKINCARE, jours(0, 1, 2), LUNDI)
        assert not state.held
        assert state.remaining == 3
        assert state.label == "3 / 6"

    def test_les_coches_d_une_autre_semaine_ne_comptent_pas(self):
        state = week_state(SKINCARE, jours(-3, -2, 0), LUNDI)
        assert state.done == 1

    def test_semaine_calee_sur_le_lundi_comme_le_reste_du_systeme(self):
        dimanche = LUNDI + timedelta(days=6)
        assert week_state(SKINCARE, jours(0), dimanche).week_start == week_start(LUNDI)


class TestEclats:
    """La récompense s'éteint au seuil, le fait reste enregistré (§4.4, §11.9)."""

    def test_une_coche_sous_le_seuil_rapporte(self):
        assert shards_for_check(SKINCARE, checks_before_in_week=0) == SHARDS_PER_CHECK
        assert shards_for_check(SKINCARE, checks_before_in_week=5) == SHARDS_PER_CHECK

    def test_au_dela_du_seuil_la_coche_ne_rapporte_plus(self):
        assert shards_for_check(SKINCARE, checks_before_in_week=6) == 0
        assert shards_for_check(SKINCARE, checks_before_in_week=7) == 0

    def test_le_plafond_suit_l_objectif_de_chaque_routine(self):
        assert shards_for_check(ETIREMENTS, checks_before_in_week=3) == SHARDS_PER_CHECK
        assert shards_for_check(ETIREMENTS, checks_before_in_week=4) == 0


class TestCompteursMonotones:
    def test_semaines_tenues_ne_redescendent_jamais(self):
        bonne = jours(0, 1, 2, 3, 4, 5)
        mauvaise = jours(7, 8)
        avant = held_weeks(SKINCARE, bonne)
        apres = held_weeks(SKINCARE, bonne + mauvaise)
        assert avant == 1
        assert apres == avant, "une mauvaise semaine ne doit rien retirer"

    def test_semaine_de_piste_tenue_si_toutes_les_routines_tiennent(self):
        checks = {
            "skincare": jours(0, 1, 2, 3, 4, 5),
            "etirements": jours(0, 2, 4, 6),
        }
        assert piste_week_held([SKINCARE, ETIREMENTS], checks, LUNDI)

    def test_une_routine_en_dessous_suffit_a_ne_pas_tenir_la_semaine(self):
        checks = {
            "skincare": jours(0, 1, 2, 3, 4, 5),
            "etirements": jours(0),
        }
        assert not piste_week_held([SKINCARE, ETIREMENTS], checks, LUNDI)

    def test_piste_vide_n_est_pas_tenue(self):
        assert not piste_week_held([], {}, LUNDI)
        assert piste_held_weeks([], {}) == 0

    def test_cumul_des_semaines_tenues_sur_plusieurs_semaines(self):
        checks = {
            "skincare": jours(0, 1, 2, 3, 4, 5) + jours(7, 8, 9, 10, 11, 12),
            "etirements": jours(0, 2, 4, 6) + jours(7, 9, 11, 13),
        }
        assert piste_held_weeks([SKINCARE, ETIREMENTS], checks) == 2


class TestPanneauDuJour:
    def test_ne_montre_que_ce_qui_est_du_aujourd_hui(self):
        gainage = Routine(key="g", name="Gainage", weekly_target=2, weekdays=(1, 3))
        entries = today_panel([SKINCARE, gainage], {}, LUNDI)
        assert [e.routine.key for e in entries] == ["skincare"]

    def test_ordre_par_ancre_selon_le_deroule_de_la_journee(self):
        entries = today_panel([SKINCARE, ETIREMENTS], {}, LUNDI)
        # Le réveil avant le coucher, quel que soit l'ordre d'entrée.
        assert [e.routine.key for e in entries] == ["etirements", "skincare"]

    def test_etat_de_la_coche_du_jour(self):
        entries = today_panel([SKINCARE], {"skincare": jours(0)}, LUNDI)
        assert entries[0].checked_today

    def test_eclats_annonces_avant_la_coche(self):
        entries = today_panel([SKINCARE], {"skincare": jours(-1)}, LUNDI)
        assert entries[0].shards_if_checked == SHARDS_PER_CHECK

    def test_rien_annonce_sur_une_routine_deja_cochee(self):
        entries = today_panel([SKINCARE], {"skincare": jours(0)}, LUNDI)
        assert entries[0].shards_if_checked == 0

    def test_rien_annonce_au_dela_du_seuil_hebdomadaire(self):
        entries = today_panel([SKINCARE], {"skincare": jours(-6, -5, -4, -3, -2, -1)}, LUNDI)
        # Semaine précédente : le seuil de la semaine en cours est intact.
        assert entries[0].shards_if_checked == SHARDS_PER_CHECK

        atteint = today_panel([ETIREMENTS], {"etirements": jours(0, 1, 2, 3)}, LUNDI + timedelta(days=4))
        assert atteint[0].shards_if_checked == 0


@pytest.mark.django_db
class TestServiceEtIsolationDesPistes:
    """La règle dure du §11.4, étendue à l'Entretien : les pistes ne se valident jamais."""

    @pytest.fixture
    def routine(self, django_user_model):
        from forge.models import Profile, Routine as RoutineModel, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        track = Track.objects.create(user=user, kind=Track.ENTRETIEN)
        return RoutineModel.objects.create(
            user=user, track=track, name="Skincare du soir", weekly_target=6, anchor=AVANT_COUCHER
        )

    def test_cocher_credite_des_eclats(self, routine):
        from forge import services

        result = services.check_routine(routine, day=LUNDI)
        routine.user.profile.refresh_from_db()
        assert result["created"] and result["shards"] == SHARDS_PER_CHECK
        assert routine.user.profile.shards == SHARDS_PER_CHECK

    def test_recocher_le_meme_jour_ne_rapporte_rien(self, routine):
        from forge import services

        services.check_routine(routine, day=LUNDI)
        again = services.check_routine(routine, day=LUNDI)
        routine.user.profile.refresh_from_db()
        assert not again["created"] and again["shards"] == 0
        assert routine.user.profile.shards == SHARDS_PER_CHECK

    def test_bonus_de_semaine_tenue_paye_une_seule_fois(self, routine):
        from forge import services
        from forge.rules.routines import WEEK_HELD_BONUS

        gains = [services.check_routine(routine, day=LUNDI + timedelta(days=i))["shards"] for i in range(7)]
        # Six coches payées, la sixième porte le bonus, la septième ne rapporte rien.
        assert gains == [3, 3, 3, 3, 3, 3 + WEEK_HELD_BONUS, 0]

    def test_annuler_une_coche_reprend_exactement_ce_qu_elle_avait_donne(self, routine):
        from forge import services

        services.check_routine(routine, day=LUNDI)
        services.uncheck_routine(routine, day=LUNDI)
        routine.user.profile.refresh_from_db()
        assert routine.user.profile.shards == 0

    def test_une_routine_ne_cree_aucune_session_ni_journee_validee(self, routine):
        from forge import services
        from forge.models import DayStatus, Session

        services.check_routine(routine, day=LUNDI)
        assert not Session.objects.filter(user=routine.user).exists()
        assert not DayStatus.objects.filter(user=routine.user).exists()

    def test_aucune_xp_n_est_accordee_par_une_routine(self, routine):
        from forge import services
        from forge.models import Session

        services.check_routine(routine, day=LUNDI)
        total = sum(Session.objects.filter(user=routine.user).values_list("xp_awarded", flat=True))
        assert total == 0

    def test_panneau_expose_le_compteur_cumule(self, routine):
        from forge import services

        for i in range(6):
            services.check_routine(routine, day=LUNDI + timedelta(days=i))
        panel = services.routine_panel(routine.user, today=LUNDI + timedelta(days=6))
        assert panel["held_weeks"] == 1
        assert panel["week_held"]
        assert panel["groups"][0]["routines"][0]["week_label"] == "6 / 6"
