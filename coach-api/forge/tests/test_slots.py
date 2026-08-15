"""Tests des deux limites dures de l'attribution de slot (SPEC §4.3).

Trois projets actifs au maximum, et deux slots au maximum par domaine. La
seconde limite existe parce que trois projets de code dans les trois slots,
c'est une seule vie déguisée en trois.
"""

import pytest

from forge.rules.slots import (
    CODE,
    CORPS,
    SAVOIR,
    assign_slot,
    breaches_diversity,
    refused_reason,
    saturated_domains,
)


class TestAttribution:
    def test_premier_projet_prend_le_slot_un(self):
        assert assign_slot([], CODE) == 1

    def test_les_slots_se_remplissent_dans_l_ordre(self):
        assert assign_slot([(1, CODE)], CORPS) == 2
        assert assign_slot([(1, CODE), (2, CORPS)], SAVOIR) == 3

    def test_un_trou_est_repris(self):
        assert assign_slot([(1, CODE), (3, CORPS)], SAVOIR) == 2

    def test_aucun_slot_quand_les_trois_sont_pris(self):
        assert assign_slot([(1, CODE), (2, CORPS), (3, SAVOIR)], CORPS) is None


class TestDiversite:
    def test_deux_projets_du_meme_domaine_passent(self):
        assert assign_slot([(1, CODE)], CODE) == 2

    def test_le_troisieme_du_meme_domaine_est_refuse(self):
        assert assign_slot([(1, CODE), (2, CODE)], CODE) is None

    def test_mais_un_autre_domaine_prend_le_slot_restant(self):
        assert assign_slot([(1, CODE), (2, CODE)], CORPS) == 3

    def test_le_refus_de_diversite_s_explique_sans_reproche(self):
        raison = refused_reason([(1, CODE), (2, CODE)], CODE)
        assert "maximum" in raison and "frigo" in raison
        assert "slots sont pris" not in raison, "ce n'est pas la bonne raison"

    def test_le_refus_par_saturation_des_slots_a_sa_propre_raison(self):
        raison = refused_reason([(1, CODE), (2, CORPS), (3, SAVOIR)], CORPS)
        assert "slots sont pris" in raison

    def test_aucune_raison_quand_le_projet_passe(self):
        assert refused_reason([(1, CODE)], CORPS) is None

    def test_domaines_satures_listes(self):
        assert saturated_domains([(1, CODE), (2, CODE), (3, CORPS)]) == [CODE]


class TestHeritageDesDonneesAnciennes:
    """La règle ne déloge jamais un projet installé : ce serait une sanction (§17)."""

    def test_une_configuration_anterieure_est_constatee_pas_corrigee(self):
        taken = [(1, CODE), (2, CODE), (3, CODE)]
        assert breaches_diversity(taken) == CODE

    def test_une_configuration_conforme_ne_signale_rien(self):
        assert breaches_diversity([(1, CODE), (2, CODE), (3, CORPS)]) is None


@pytest.mark.django_db
class TestCreationAvecDomaine:
    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return user

    def markdown(self, name: str, domain: str) -> str:
        return f"# {name}\n\nDomaine: {domain}\n\n- [ ] Une étape\n"

    def test_le_domaine_est_lu_dans_le_markdown(self, user):
        from forge import services

        project = services.create_project_from_markdown(user, self.markdown("Muscu", "corps"))
        assert project.domain == "corps"

    def test_le_troisieme_projet_de_code_part_au_frigo(self, user):
        from forge import services
        from forge.models import Project

        services.create_project_from_markdown(user, self.markdown("A", "code"))
        services.create_project_from_markdown(user, self.markdown("B", "code"))
        troisieme = services.create_project_from_markdown(user, self.markdown("C", "code"))
        assert troisieme.status == Project.FRIDGE and troisieme.slot is None

    def test_mais_un_projet_corps_prend_le_troisieme_slot(self, user):
        from forge import services

        services.create_project_from_markdown(user, self.markdown("A", "code"))
        services.create_project_from_markdown(user, self.markdown("B", "code"))
        muscu = services.create_project_from_markdown(user, self.markdown("Muscu", "corps"))
        assert muscu.slot == 3

    def test_domaine_inconnu_signale_et_ramene_a_code(self, user):
        from forge import services

        apercu = services.preview_project(self.markdown("X", "jardinage"))
        assert apercu["domain"] == "code"
        assert any("jardinage" in w for w in apercu["warnings"])


class TestSlotsGagnes:
    """Un slot supplémentaire se gagne sur la régularité, jamais sur l'XP seule.

    C'est le point central du §4.3 : débloquer sur le rang seul récompenserait
    la dispersion par la permission de se disperser davantage, puisque l'XP monte
    avec le volume et que le volume est le mode de défaillance du §0.2.
    """

    def test_trois_slots_par_defaut(self):
        from forge.rules.slots import BASE_SLOTS, unlocked_slots

        assert unlocked_slots("F") == BASE_SLOTS
        assert unlocked_slots("SS") == BASE_SLOTS, "le rang seul ne débloque rien"

    def test_le_rang_sans_regularite_ne_debloque_pas(self):
        from forge.rules.slots import unlocked_slots

        assert unlocked_slots("A", weeks_kept=1, weeks_window=4) == 3
        assert unlocked_slots("S", weeks_kept=0, weeks_window=8) == 3

    def test_la_regularite_sans_le_rang_ne_debloque_pas_non_plus(self):
        from forge.rules.slots import unlocked_slots

        assert unlocked_slots("C", weeks_kept=4, weeks_window=4) == 3

    def test_quatrieme_slot_au_rang_A_avec_trois_semaines_tenues(self):
        from forge.rules.slots import unlocked_slots

        assert unlocked_slots("A", weeks_kept=3, weeks_window=4) == 4

    def test_cinquieme_slot_au_rang_S(self):
        from forge.rules.slots import unlocked_slots

        assert unlocked_slots("S", weeks_kept=6, weeks_window=8) == 5

    def test_le_plafond_absolu_est_cinq(self):
        from forge.rules.slots import unlocked_slots

        assert unlocked_slots("SS", weeks_kept=50, weeks_window=50) == 5

    def test_une_fenetre_trop_courte_ne_compte_pas(self):
        """Trois semaines tenues sur trois ne valent pas trois sur quatre."""
        from forge.rules.slots import unlocked_slots

        assert unlocked_slots("A", weeks_kept=3, weeks_window=3) == 3

    def test_le_prochain_deblocage_dit_ce_qui_manque(self):
        from forge.rules.slots import next_unlock

        message = next_unlock("B", weeks_kept=4, weeks_window=4)
        assert "rang A" in message
        message = next_unlock("A", weeks_kept=1, weeks_window=4)
        assert "engagements tenus" in message and "tu en as 1" in message

    def test_les_slots_ouverts_sont_reellement_attribuables(self):
        from forge.rules.slots import CODE, CORPS, SAVOIR, assign_slot

        pris = [(1, CODE), (2, CODE), (3, SAVOIR)]
        assert assign_slot(pris, CORPS, total_slots=3) is None
        assert assign_slot(pris, CORPS, total_slots=4) == 4


class TestEchangeDeSlot:
    """Le dimanche protège contre l'abandon, pas contre la réussite."""

    def test_le_dimanche_l_echange_est_ouvert(self):
        from forge.rules.slots import can_replace

        ok, _ = can_replace(weekday=6, project_finished=False, has_sessions=True)
        assert ok

    def test_en_semaine_on_ne_lache_pas_un_projet_en_cours(self):
        from forge.rules.slots import can_replace

        ok, raison = can_replace(weekday=1, project_finished=False, has_sessions=True)
        assert not ok and "dimanche" in raison

    def test_un_projet_termine_libere_son_slot_le_jour_meme(self):
        from forge.rules.slots import can_replace

        ok, raison = can_replace(weekday=1, project_finished=True, has_sessions=True)
        assert ok and "sans attendre" in raison

    def test_une_roadmap_finie_sans_session_ne_debloque_rien(self):
        """Sinon une roadmap d'une étape cochée contournerait le dimanche."""
        from forge.rules.slots import can_replace

        ok, raison = can_replace(weekday=1, project_finished=True, has_sessions=False)
        assert not ok and "aucune session" in raison

    def test_un_slot_vacant_doit_etre_repris_le_dimanche(self):
        from forge.rules.slots import must_fill_vacancy

        assert must_fill_vacancy(weekday=6, vacant=1)
        assert not must_fill_vacancy(weekday=2, vacant=1), "en semaine, la vacance est permise"
        assert not must_fill_vacancy(weekday=6, vacant=0)
