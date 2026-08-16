"""Tests des services du jeu (SPEC §12, J2).

Les règles pures sont testées dans ``test_j2_rules``. Ici on vérifie le
branchement, et surtout **la frontière** : le §17 pose que le loot est de
l'apparence et jamais du pouvoir, et cette promesse ne tient que si rien dans
``progression`` ne peut toucher à une journée, un streak ou une garde.

C'est le genre de garantie qui se perd au premier refactoring si personne ne la
surveille — d'où les tests qui vérifient une absence plutôt qu'un résultat.
"""

import random
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import progression, services
from forge.models import (
    Achievement,
    LootCard,
    LootDraw,
    OwnedRelic,
    Profile,
    Project,
    RoadmapStep,
    Session,
    Track,
)
from forge.rules import loot as loot_rules
from forge.rules import skills as skill_rules
from forge.rules.calendar import coach_day, week_start


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    projet = Project.objects.create(
        user=user, track=atelier, name="Evolve", branch=skill_rules.MOTEUR_DE_JEU, slot=1
    )
    RoadmapStep.objects.create(project=projet, label="Étape", order=1, state=RoadmapStep.DOING)
    today = coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour)
    services.open_season(user, starts_on=today, stake=50)
    return user


def seance(user, *, minutes: int, days_ago: int = 0, branch: str | None = None):
    projet = Project.objects.get(user=user, name="Evolve")
    if branch and projet.branch != branch:
        projet = Project.objects.create(
            user=user, track=projet.track, name=f"Projet {branch}", branch=branch
        )
    debut = timezone.now() - timedelta(days=days_ago, hours=2)
    return Session.objects.create(
        user=user,
        project=projet,
        planned_minutes=minutes,
        actual_minutes=minutes,
        status=Session.DONE,
        coach_day=(timezone.now() - timedelta(days=days_ago)).date(),
        started_at=debut,
        ended_at=debut + timedelta(minutes=minutes),
    )


class TestArbre:
    def test_les_heures_s_agregent_par_branche_pas_par_projet(self, user):
        """La raison d'être du §12.9, vérifiée de bout en bout."""
        seance(user, minutes=600)
        seance(user, minutes=600, branch=skill_rules.MOTEUR_DE_JEU)

        assert progression.branch_minutes(user)[skill_rules.MOTEUR_DE_JEU] == 1200

    def test_un_projet_archive_compte_toujours(self, user):
        """Les heures ont été faites ; le §17 interdit de reprendre du travail réel."""
        seance(user, minutes=900)
        Project.objects.filter(user=user).update(status=Project.ARCHIVED)

        assert progression.branch_minutes(user)[skill_rules.MOTEUR_DE_JEU] == 900

    def test_un_projet_sans_branche_ne_casse_rien(self, user):
        projet = Project.objects.get(user=user, name="Evolve")
        projet.branch = ""
        projet.save(update_fields=["branch"])
        seance(user, minutes=300)

        assert progression.skill_tree(user)["shape"]["total_minutes"] == 0

    def test_le_franchissement_est_detecte_a_la_cloture(self, user):
        seance(user, minutes=9 * 60)
        derniere = seance(user, minutes=120)

        franchi = progression.branch_tier_crossed(user, derniere)

        assert franchi is not None
        assert franchi["tier"] == 1
        assert franchi["title"]

    def test_aucun_franchissement_quand_le_palier_ne_bouge_pas(self, user):
        seance(user, minutes=60)
        derniere = seance(user, minutes=60)

        assert progression.branch_tier_crossed(user, derniere) is None


class TestChaleur:
    def test_la_chaleur_suit_les_jours_reellement_travailles(self, user):
        for i in range(5):
            seance(user, minutes=25, days_ago=i)
        today = timezone.now().date()

        chaleur = progression.heat(user, today=today)

        assert chaleur["days_worked"] == 5
        assert chaleur["multiplier"] > 1.0

    def test_sans_seance_la_chaleur_est_eteinte(self, user):
        chaleur = progression.heat(user, today=timezone.now().date())

        assert chaleur["multiplier"] == 1.0
        assert chaleur["level"] == 0.0


class TestLoot:
    def test_un_tirage_range_la_carte_et_journalise(self, user):
        carte = progression.draw_card(user, reason="test", rng=random.Random(3))

        assert LootCard.objects.filter(user=user, key=carte["key"]).exists()
        assert LootDraw.objects.filter(user=user, key=carte["key"]).exists()

    def test_un_doublon_incremente_au_lieu_de_dupliquer_la_ligne(self, user):
        """Sinon l'inventaire d'une année devient une liste illisible."""
        rng = random.Random(0)
        premiere = progression.draw_card(user, reason="test", rng=rng)

        LootCard.objects.filter(user=user).update(copies=1)
        # On force le meme tirage en re-graine identique.
        progression.draw_card(user, reason="test", rng=random.Random(0))

        ligne = LootCard.objects.get(user=user, key=premiere["key"])
        assert ligne.copies == 2
        assert LootCard.objects.filter(user=user, key=premiere["key"]).count() == 1

    def test_un_doublon_rend_des_eclats(self, user):
        rng_seed = 11
        progression.draw_card(user, reason="test", rng=random.Random(rng_seed))
        avant = user.profile.shards

        progression.draw_card(user, reason="test", rng=random.Random(rng_seed))
        user.profile.refresh_from_db()

        assert user.profile.shards > avant

    def test_la_pitie_se_recalcule_depuis_le_journal(self, user):
        """Un compteur stocké dériverait, et une pitié déréglée se lit comme de la triche."""
        for _ in range(loot_rules.PITIE_RARE + 2):
            LootDraw.objects.create(user=user, key="x", rarity=loot_rules.COMMUN)

        depuis_rare, _ = progression._pity(user)

        assert depuis_rare >= loot_rules.PITIE_RARE

    def test_la_collection_montre_aussi_ce_qui_manque(self, user):
        """Une collection qui ne montre que le possédé ne donne aucune raison de continuer."""
        collection = progression.collection(user)

        assert collection["total"] == len(loot_rules.CATALOGUE)
        assert any(not c["owned"] for cartes in collection["slots"].values() for c in cartes)

    def test_un_seul_cosmetique_par_emplacement(self, user):
        LootCard.objects.create(user=user, key="theme_braise", rarity="commun", kind="theme")
        LootCard.objects.create(user=user, key="theme_glacier", rarity="commun", kind="theme")

        progression.equip_card(user, "theme_braise")
        equipes = progression.equip_card(user, "theme_glacier")

        assert equipes["theme"] == "theme_glacier"

    def test_reequiper_la_meme_carte_la_retire(self, user):
        LootCard.objects.create(user=user, key="theme_braise", rarity="commun", kind="theme")

        progression.equip_card(user, "theme_braise")
        equipes = progression.equip_card(user, "theme_braise")

        assert "theme" not in equipes

    def test_on_ne_peut_pas_equiper_une_carte_non_possedee(self, user):
        with pytest.raises(ValueError):
            progression.equip_card(user, "theme_eclipse")


class TestReliques:
    def test_un_haut_fait_debloque_sa_relique(self, user):
        obtenues = progression.grant_relics_for(user, ["increvable"])

        assert obtenues and obtenues[0]["key"] == "coeur_increvable"
        assert OwnedRelic.objects.filter(user=user, key="coeur_increvable").exists()

    def test_une_relique_n_est_pas_equipee_d_office(self, user):
        """Le §12.8 plafonne à trois : le choix appartient à l'utilisateur."""
        progression.grant_relics_for(user, ["increvable"])

        assert progression.relic_bonuses(user).extra_shields == 0

    def test_le_plafond_de_trois_est_applique(self, user):
        for cle in ("increvable", "retour_du_neant", "leve_tot", "ermite", "polyvalent"):
            progression.grant_relics_for(user, [cle])

        equipees = 0
        for relique in OwnedRelic.objects.filter(user=user):
            try:
                progression.toggle_relic(user, relique.key)
                equipees += 1
            except ValueError:
                pass

        assert equipees == 3

    def test_le_refus_dit_pourquoi(self, user):
        for cle in ("increvable", "retour_du_neant", "leve_tot", "ermite"):
            progression.grant_relics_for(user, [cle])
        for relique in list(OwnedRelic.objects.filter(user=user))[:3]:
            progression.toggle_relic(user, relique.key)

        restante = OwnedRelic.objects.filter(user=user, equipped=False).first()
        with pytest.raises(ValueError, match="maximum"):
            progression.toggle_relic(user, restante.key)

    def test_un_haut_fait_sans_relique_ne_donne_rien(self, user):
        assert progression.grant_relics_for(user, ["premier_sang"]) == []


class TestClotureDeSemaine:
    def test_la_cloture_est_idempotente(self, user):
        """Appelée par le déclencheur nocturne ET à l'ouverture : deux tirages
        pour une même semaine transformeraient un rythme en loterie."""
        semaine = week_start(timezone.now().date() - timedelta(days=7))
        for i in range(3):
            seance(user, minutes=25, days_ago=7 + i)

        premier = progression.close_week(user, week=semaine, rng=random.Random(1))
        second = progression.close_week(user, week=semaine, rng=random.Random(1))

        assert premier["already"] is False
        assert second["already"] is True
        assert second["drawn"] == []

    def test_une_semaine_vide_ne_tire_rien(self, user):
        semaine = week_start(timezone.now().date() - timedelta(days=7))

        assert progression.close_week(user, week=semaine, rng=random.Random(1))["drawn"] == []


class TestLaFrontiere:
    """Le loot est de l'apparence, jamais du pouvoir (§12.6, §17).

    Ces tests vérifient une **absence**. C'est la garantie qui se perd au premier
    refactoring si personne ne la surveille, et sa disparition serait invisible :
    l'app marcherait toujours, elle récompenserait juste la chance.
    """

    def test_equiper_un_cosmetique_ne_touche_a_aucune_journee(self, user):
        seance(user, minutes=25)
        LootCard.objects.create(user=user, key="theme_braise", rarity="commun", kind="theme")
        avant = list(
            Session.objects.filter(user=user).values_list("actual_minutes", "xp_awarded", "status")
        )

        progression.equip_card(user, "theme_braise")

        assert (
            list(Session.objects.filter(user=user).values_list("actual_minutes", "xp_awarded", "status"))
            == avant
        )

    def test_un_tirage_ne_donne_jamais_d_xp(self, user):
        seance(user, minutes=25)
        avant = Session.objects.filter(user=user).values_list("xp_awarded", flat=True).first()

        for _ in range(6):
            progression.draw_card(user, reason="test", rng=random.Random(9))

        assert Session.objects.filter(user=user).values_list("xp_awarded", flat=True).first() == avant

    def test_aucune_carte_du_catalogue_n_a_d_effet(self, user):
        """Les reliques ont un ``effect``, les cartes n'en ont pas — et c'est
        pour ça qu'elles vivent dans deux tables séparées."""
        assert not any(hasattr(c, "effect") for c in loot_rules.CATALOGUE)

    def test_les_reliques_et_les_cartes_ne_partagent_aucune_table(self, user):
        progression.grant_relics_for(user, ["increvable"])
        progression.draw_card(user, reason="test", rng=random.Random(2))

        cles_reliques = set(OwnedRelic.objects.filter(user=user).values_list("key", flat=True))
        cles_cartes = set(LootCard.objects.filter(user=user).values_list("key", flat=True))

        assert not (cles_reliques & cles_cartes)
