"""Tests des deux limites dures de l'attribution de slot (SPEC §4.3).

Cinq projets actifs au départ, et deux slots au maximum par domaine. La
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

    def test_aucun_slot_quand_tous_sont_pris(self):
        pris = [(1, CODE), (2, CORPS), (3, SAVOIR), (4, "creatif"), (5, "pratique")]
        assert assign_slot(pris, CORPS) is None

    def test_cinq_slots_au_depart(self):
        from forge.rules.slots import BASE_SLOTS

        assert BASE_SLOTS == 5
        assert assign_slot([(1, CODE), (2, CORPS), (3, SAVOIR), (4, "creatif")], "pratique") == 5


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
        raison = refused_reason([(1, CODE), (2, CORPS), (3, SAVOIR)], CORPS, total_slots=3)
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


class TestSlotsOuverts:
    """L'échelle des rangs vit dans ``ranks.py`` ; ici on vérifie le branchement.

    Depuis la refonte du §4.4, une seule condition suffit : le rang **est** la
    régularité, il n'y a plus de double critère à croiser.
    """

    def test_le_socle_est_de_trois(self):
        from forge.rules.slots import BASE_SLOTS, unlocked_slots

        assert unlocked_slots("F") == BASE_SLOTS
        assert unlocked_slots("C") == BASE_SLOTS

    def test_le_rang_B_ouvre_le_sixieme(self):
        from forge.rules.slots import unlocked_slots

        assert unlocked_slots("B") == 6

    def test_le_rang_A_ouvre_le_septieme(self):
        from forge.rules.slots import ABSOLUTE_MAX_SLOTS, unlocked_slots

        assert unlocked_slots("A") == 7
        assert unlocked_slots("SS") == 7
        assert ABSOLUTE_MAX_SLOTS == 8, "la voie « Ampleur » ajoute le huitième"

    def test_la_piste_corps_ne_grandit_jamais(self):
        """Quatre activités physiques sont de la dispersion aussi (SPEC §11.4)."""
        from forge.rules.slots import CORPS_SLOTS, slots_for_track

        assert slots_for_track("corps", "F") == CORPS_SLOTS == 2
        assert slots_for_track("corps", "SS") == 2, "le rang n'ouvre pas de slot Corps"
        assert slots_for_track("atelier", "SS") == 7

    def test_les_slots_ouverts_sont_reellement_attribuables(self):
        from forge.rules.slots import CODE, CORPS, SAVOIR, assign_slot

        pris = [(1, CODE), (2, CODE), (3, SAVOIR)]
        assert assign_slot(pris, CORPS, total_slots=3) is None
        assert assign_slot(pris, CORPS, total_slots=4) == 4


class TestEchangeDeSlot:
    """La saison protège contre l'abandon, pas contre la réussite."""

    def test_entre_deux_saisons_l_echange_est_ouvert(self):
        from forge.rules.slots import can_replace

        ok, _ = can_replace(entre_saisons=True, project_finished=False, has_sessions=True)
        assert ok

    def test_en_saison_on_ne_lache_pas_un_projet_en_cours(self):
        from forge.rules.slots import can_replace

        ok, raison = can_replace(entre_saisons=False, project_finished=False, has_sessions=True)
        assert not ok and "saisons" in raison

    def test_un_projet_termine_libere_son_slot_le_jour_meme(self):
        from forge.rules.slots import can_replace

        ok, raison = can_replace(entre_saisons=False, project_finished=True, has_sessions=True)
        assert ok and "sans attendre" in raison

    def test_une_roadmap_finie_sans_session_ne_debloque_rien(self):
        """Sinon une roadmap d'une étape cochée contournerait la saison."""
        from forge.rules.slots import can_replace

        ok, raison = can_replace(entre_saisons=False, project_finished=True, has_sessions=False)
        assert not ok and "aucune session" in raison

    def test_un_slot_vacant_doit_etre_repris_entre_deux_saisons(self):
        from forge.rules.slots import must_fill_vacancy

        assert must_fill_vacancy(entre_saisons=True, vacant=1)
        assert not must_fill_vacancy(entre_saisons=False, vacant=1), "en saison, la vacance est permise"
        assert not must_fill_vacancy(entre_saisons=True, vacant=0)


@pytest.mark.django_db
class TestFenetreEntreDeuxSaisons:
    def test_fermee_pendant_la_saison_ouverte_apres(self, django_user_model):
        from datetime import date, timedelta

        from forge import services
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="u", password="p")
        Profile.objects.create(user=user)
        debut = date(2026, 9, 1)
        saison = services.open_season(user, starts_on=debut)

        assert services.entre_deux_saisons(user, today=debut - timedelta(days=1))
        assert not services.entre_deux_saisons(user, today=debut + timedelta(days=12))
        assert services.entre_deux_saisons(user, today=saison.ends_on + timedelta(days=1))

    def test_une_saison_en_veille_reste_fermee(self, django_user_model):
        from datetime import date

        from forge import services
        from forge.models import Profile, Season

        user = django_user_model.objects.create_user(username="u", password="p")
        Profile.objects.create(user=user)
        saison = services.open_season(user, starts_on=date(2026, 9, 1))
        saison.status = Season.PAUSED
        saison.save()

        assert not services.entre_deux_saisons(user, today=date(2026, 9, 10))
