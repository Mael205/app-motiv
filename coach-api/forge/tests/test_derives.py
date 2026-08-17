"""Tests des sept détections continues (SPEC §13.5).

Deux niveaux, et le premier est le plus important : les règles sont pures, donc
les cas rares — trois semaines d'engagement manqué, dix jours de sessions qui
glissent — se fabriquent en trois lignes au lieu d'attendre trois semaines.

Ce qui se vérifie surtout, c'est **le silence**. Un détecteur qui parle trop est
un détecteur qu'on apprend à ignorer, et un signal ignoré ne vaut pas mieux que
pas de signal du tout (§17 : pas de nagging, pas de jugement).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import detections
from forge.models import Commitment, Profile, Project, RoadmapStep, Session, Signal, Track
from forge.rules import derives

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


class TestProjetMort:
    def test_dix_jours_sans_session_le_declenche(self):
        d = derives.projet_mort("Bestiaire", 10)
        assert d and d.kind == derives.PROJET_MORT

    def test_neuf_jours_ne_disent_rien(self):
        assert derives.projet_mort("Bestiaire", 9) is None

    def test_il_propose_le_frigo_et_ne_supprime_rien(self):
        """Le §17 : le système ne retire jamais rien tout seul."""
        d = derives.projet_mort("Bestiaire", 14)
        assert "frigo" in d.proposition.lower()
        assert "dimanche" in d.proposition.lower()


class TestEtapeFigee:
    def test_trois_semaines_la_declenchent(self):
        d = derives.etape_figee("Bestiaire", "Écran de fiche", 21)
        assert d and "découper" in d.proposition.lower()

    def test_deux_semaines_ne_disent_rien(self):
        assert derives.etape_figee("Bestiaire", "Écran de fiche", 14) is None


class TestEngagementIrrealiste:
    def test_trois_semaines_manquees_de_suite(self):
        d = derives.engagement_irrealiste("Evolve", [(1, 3), (1, 3), (2, 3)])
        assert d and d.donnees["propose"] == 1

    def test_une_semaine_tenue_suffit_a_le_taire(self):
        assert derives.engagement_irrealiste("Evolve", [(1, 3), (3, 3), (1, 3)]) is None

    def test_moins_de_trois_semaines_d_historique_ne_suffit_pas(self):
        assert derives.engagement_irrealiste("Evolve", [(0, 3), (1, 3)]) is None

    def test_la_proposition_ne_descend_jamais_sous_une_session(self):
        d = derives.engagement_irrealiste("Evolve", [(0, 2), (0, 2), (0, 2)])
        assert d.donnees["propose"] == 1

    def test_rien_a_proposer_si_l_engagement_est_deja_au_plancher(self):
        """Descendre de 1 à 1 n'est pas une proposition, c'est du bruit."""
        assert derives.engagement_irrealiste("Evolve", [(0, 1), (0, 1), (0, 1)]) is None


class TestConcentration:
    def test_soixante_dix_pour_cent_sur_un_projet(self):
        d = derives.concentration({"Bestiaire": 300, "Evolve": 60})
        assert d and d.donnees["projet"] == "Bestiaire"

    def test_une_repartition_saine_ne_dit_rien(self):
        assert derives.concentration({"Bestiaire": 200, "Evolve": 180}) is None

    def test_une_semaine_presque_vide_ne_declenche_rien(self):
        """100 % d'une semaine à 25 minutes n'est pas une dérive."""
        assert derives.concentration({"Bestiaire": 25, "Evolve": 0}) is None

    def test_un_seul_projet_actif_n_est_pas_une_derive(self):
        assert derives.concentration({"Bestiaire": 600}) is None


class TestFinDeSoiree:
    def _dix_jours(self, heures: list[int]) -> list[tuple[date, int]]:
        return [(LUNDI + timedelta(days=i), h) for i, h in enumerate(heures)]

    def test_les_sessions_qui_glissent_sont_vues(self):
        glissement = self._dix_jours([1140] * 5 + [1230] * 5)   # 19h puis 20h30
        d = derives.fin_de_soiree(glissement)
        assert d and d.donnees["retard_minutes"] == 90

    def test_un_rythme_stable_ne_dit_rien(self):
        assert derives.fin_de_soiree(self._dix_jours([1140] * 10)) is None

    def test_un_soir_tardif_isole_ne_suffit_pas(self):
        assert derives.fin_de_soiree(self._dix_jours([1140] * 9 + [1350])) is None

    def test_moins_de_dix_jours_ne_conclut_rien(self):
        assert derives.fin_de_soiree(self._dix_jours([1140] * 4 + [1300] * 4)) is None


class TestMigrationScroll:
    def test_le_scroll_qui_passe_au_telephone(self):
        d = derives.migration_scroll(mobile_avant=60, mobile_apres=180, pc_avant=200, pc_apres=40)
        assert d and d.donnees["mobile_gagne"] == 120

    def test_les_deux_qui_baissent_ne_sont_pas_une_migration(self):
        assert derives.migration_scroll(mobile_avant=100, mobile_apres=40, pc_avant=200, pc_apres=50) is None

    def test_une_hausse_marginale_ne_dit_rien(self):
        assert derives.migration_scroll(mobile_avant=60, mobile_apres=70, pc_avant=200, pc_apres=50) is None


class TestSurRegime:
    def test_trois_jours_a_plus_de_trois_sessions(self):
        d = derives.sur_regime([4, 4, 5])
        assert d and "jour 6" in d.proposition

    def test_trois_sessions_pile_ne_sont_pas_un_sur_regime(self):
        assert derives.sur_regime([3, 3, 3]) is None

    def test_une_journee_calme_casse_la_serie(self):
        assert derives.sur_regime([5, 1, 5]) is None


@pytest.mark.django_db
class TestLectureEnBase:
    @pytest.fixture
    def user(self):
        User = get_user_model()
        user = User.objects.create_user(username="test", password="test")
        Profile.objects.create(user=user)
        atelier = Track.objects.create(user=user, kind=Track.ATELIER)
        Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
        Project.objects.create(user=user, track=atelier, name="Evolve", slot=2)
        return user

    def test_un_projet_jamais_touche_finit_par_remonter(self, user):
        Project.objects.filter(name="Bestiaire").update(
            created_at=datetime(2026, 1, 1, tzinfo=PARIS)
        )
        constats = detections.toutes(user, today=LUNDI)
        assert any(d.kind == derives.PROJET_MORT for d in constats)

    def test_une_session_recente_le_fait_taire(self, user):
        projet = Project.objects.get(name="Bestiaire")
        Session.objects.create(
            user=user,
            project=projet,
            coach_day=LUNDI - timedelta(days=1),
            started_at=datetime(2026, 3, 1, 19, tzinfo=PARIS),
            actual_minutes=25,
            status=Session.DONE,
        )
        morts = [
            d
            for d in detections.toutes(user, today=LUNDI)
            if d.kind == derives.PROJET_MORT and d.donnees["projet"] == "Bestiaire"
        ]
        assert not morts

    def test_l_etape_figee_se_compte_depuis_la_premiere_session(self, user):
        projet = Project.objects.get(name="Bestiaire")
        etape = RoadmapStep.objects.create(
            project=projet, order=0, label="Écran de fiche", state=RoadmapStep.DOING
        )
        RoadmapStep.objects.filter(pk=etape.pk).update(
            doing_since=datetime(2026, 2, 1, 19, tzinfo=PARIS)
        )
        constats = detections.toutes(user, today=LUNDI)
        assert any(d.kind == derives.ETAPE_FIGEE for d in constats)

    def test_les_constats_sortent_du_plus_urgent_au_moins_urgent(self, user):
        projet = Project.objects.get(name="Bestiaire")
        for jour in range(3):
            for _ in range(4):
                Session.objects.create(
                    user=user,
                    project=projet,
                    coach_day=LUNDI - timedelta(days=jour),
                    started_at=datetime(2026, 3, 2, 19, tzinfo=PARIS) - timedelta(days=jour),
                    actual_minutes=25,
                    status=Session.DONE,
                )
        constats = detections.toutes(user, today=LUNDI)
        assert constats[0].kind == derives.SUR_REGIME, "le sur-régime annonce un arrêt à venir"

    def test_aucun_constat_sur_une_base_neuve(self, user):
        Project.objects.all().update(created_at=datetime(2026, 3, 1, tzinfo=PARIS))
        assert detections.toutes(user, today=LUNDI) == []

    def test_la_migration_du_scroll_se_lit_dans_les_signaux(self, user):
        for jour in range(7):
            Signal.objects.create(
                user=user, source="agent", category="scroll_passif",
                minutes=40, day=LUNDI - timedelta(days=8 + jour),
            )
            Signal.objects.create(
                user=user, source="mobile", category="scroll_passif",
                minutes=5, day=LUNDI - timedelta(days=8 + jour),
            )
            Signal.objects.create(
                user=user, source="mobile", category="scroll_passif",
                minutes=45, day=LUNDI - timedelta(days=jour),
            )
        constats = detections.toutes(user, today=LUNDI)
        assert any(d.kind == derives.MIGRATION_SCROLL for d in constats)
