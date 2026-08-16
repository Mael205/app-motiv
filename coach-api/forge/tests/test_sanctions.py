"""Le prix du décrochage (SPEC §14).

Ces tests gardent des **promesses**, pas des calculs. Le §14 est la mécanique
la plus facile à faire dériver du produit : chaque sanction ajoutée paraît
justifiée prise seule, et l'empilement produit le mode de défaillance n°1 du
§0.3 — l'abandon définitif. Les quatre invariants sont donc testés comme des
garde-fous, pas comme des détails de calcul :

1. **Réparable en dix minutes.** Une session dégradée éteint tout ce qui est
   réparable. Si un jour une sanction survit à la session du soir sans qu'on
   l'ait décidé, c'est ici que ça se voit.
2. **Jamais rétroactive.** L'XP, les heures, les étapes et le rang ne bougent
   pas. La seule chose qui parte est une part de la mise, et elle ne part
   qu'une fois.
3. **Jamais morale.** Aucun mot de reproche dans un texte affiché.
4. **Jamais sociale.** Rien ne sort de l'app — testé par l'absence de tout
   canal dans le chemin des sanctions.

Le point le plus subtil est l'idempotence. La régénération du boss et le
prélèvement sur la mise sont posés à **chaque lecture de l'accueil**, qui est
appelé toutes les dix secondes par le front : une écriture qui s'ajouterait au
lieu de se recalculer viderait le boss de son sens en une soirée.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import season_flow, services
from forge.models import Profile, Project, Season, Session, Track
from forge.rules import sanctions as sanction_rules
from forge.rules import seasons as season_rules
from forge.rules import slots as slot_rules
from forge.rules import streak as streak_rules
from forge.rules.calendar import coach_day


# --------------------------------------------------------------------------
# Les règles pures
# --------------------------------------------------------------------------

class TestPaliers:
    def evalue(self, **kwargs):
        base = dict(missed_run=0, current_streak=0, broken_once=False, validated_today=False)
        return sanction_rules.evaluate(**{**base, **kwargs})

    def test_aucune_sanction_sans_jour_rate(self):
        assert not self.evalue().active

    def test_palier_1_eteint_la_vitrine_et_le_sas(self):
        s = self.evalue(missed_run=1)
        assert s.showcase_locked and s.relax_revoked
        assert not s.slots_frozen, "geler un slot au premier jour raté n'est pas dans le §14"

    def test_palier_2_ajoute_le_gel_et_le_blocage_anticipe(self):
        s = self.evalue(missed_run=2, broken_once=True, debt_minutes=10)
        assert s.showcase_locked, "les paliers s'empilent, le §14 le dit"
        assert s.slots_frozen and s.early_block
        assert s.debt_minutes == 10

    def test_palier_3_change_de_registre(self):
        """« Plus aucune sanction ajoutée. Les paliers 1 et 2 restent actifs. »"""
        deux = self.evalue(missed_run=2, broken_once=True)
        trois = self.evalue(missed_run=6, broken_once=True)

        ajoutees = [
            champ
            for champ in ("showcase_locked", "relax_revoked", "slots_frozen", "early_block")
            if getattr(trois, champ) and not getattr(deux, champ)
        ]
        assert not ajoutees, f"le palier 3 a ajouté {ajoutees}"
        assert trois.comeback, "il change de registre, il ne punit pas plus"

    def test_le_niveau_plafonne_a_trois(self):
        assert self.evalue(missed_run=12).level == 3


class TestReparation:
    """Invariant 1 : toute sanction s'annule par une seule session dégradée."""

    def test_la_session_du_jour_eteint_tout_ce_qui_est_reparable(self):
        for rate in (1, 2, 3, 9):
            s = sanction_rules.evaluate(
                missed_run=rate, current_streak=0, broken_once=True, validated_today=True
            )
            assert not s.showcase_locked
            assert not s.relax_revoked
            assert not s.slots_frozen
            assert not s.early_block
            assert not s.comeback
            assert not s.season_exit_offered

    def test_la_dette_ne_s_eteint_pas_avec_la_session_du_jour(self):
        """La dette **est** le seuil de la journée : l'annuler serait ne pas l'avoir."""
        s = sanction_rules.evaluate(
            missed_run=2, current_streak=0, broken_once=True, validated_today=True, debt_minutes=10
        )
        assert s.debt_minutes == 10

    def test_la_dette_n_est_plus_rappelee_une_fois_la_session_posee(self):
        """La rappeler à quelqu'un qui vient de s'y mettre en ferait une remarque."""
        s = sanction_rules.evaluate(
            missed_run=2, current_streak=0, broken_once=False, validated_today=True, debt_minutes=10
        )
        assert sanction_rules.lines(s) == []

    def test_le_titre_en_sursis_demande_trois_journees_d_affilee(self):
        def sursis(streak: int) -> bool:
            return sanction_rules.evaluate(
                missed_run=0, current_streak=streak, broken_once=True, validated_today=True
            ).title_reprieve

        assert sursis(1), "une soirée ne rend pas un titre qui a été mis en sursis"
        assert sursis(2)
        assert not sursis(3)

    def test_sans_cassure_aucun_sursis(self):
        assert not sanction_rules.evaluate(
            missed_run=0, current_streak=0, broken_once=False, validated_today=False
        ).title_reprieve


class TestPorteDeSortie:
    def test_la_sortie_n_est_pas_offerte_au_palier_3(self):
        """Trois jours d'arrêt, c'est une rampe de retour — pas une saison à jeter."""
        for rate in (3, 4, 5):
            s = sanction_rules.evaluate(
                missed_run=rate, current_streak=0, broken_once=True, validated_today=False
            )
            assert not s.season_exit_offered

    def test_au_dela_de_cinq_jours_la_sortie_est_offerte(self):
        s = sanction_rules.evaluate(
            missed_run=6, current_streak=0, broken_once=True, validated_today=False
        )
        assert s.season_exit_offered


class TestMise:
    def test_chaque_cassure_entame_un_quart_de_la_mise_d_origine(self):
        assert sanction_rules.stake_forfeit(100, 0) == 0
        assert sanction_rules.stake_forfeit(100, 1) == 25
        assert sanction_rules.stake_forfeit(100, 2) == 50

    def test_le_prelevement_ne_s_adoucit_pas_a_mesure_qu_on_decroche(self):
        """Un quart du **reste** ferait coûter chaque cassure moins que la précédente."""
        pas = [
            sanction_rules.stake_forfeit(200, n + 1) - sanction_rules.stake_forfeit(200, n)
            for n in range(3)
        ]
        assert len(set(pas)) == 1, f"les cassures ne coûtent pas pareil : {pas}"

    def test_on_ne_peut_pas_devoir_plus_qu_on_n_a_engage(self):
        assert sanction_rules.stake_forfeit(100, 9) == 100

    def test_sans_mise_rien_n_est_preleve(self):
        assert sanction_rules.stake_forfeit(0, 4) == 0


class TestTon:
    """Invariant 3 : la sanction est un état de fait, jamais un jugement."""

    INTERDITS = (
        "rechute",
        "volonté",
        "discipline",
        "échec",
        "bravo",
        "perdu",
        "faute",
        "sérieux",
        "encore",
        "dommage",
    )

    def toutes_les_lignes(self) -> list[str]:
        lignes: list[str] = []
        for rate in range(0, 8):
            s = sanction_rules.evaluate(
                missed_run=rate, current_streak=0, broken_once=True, validated_today=False,
                debt_minutes=10,
            )
            lignes += sanction_rules.lines(
                s, boss_regen_minutes=45, shards_forfeited=25, frozen_slots=1
            )
        return lignes

    def test_aucun_mot_de_jugement(self):
        for ligne in self.toutes_les_lignes():
            for mot in self.INTERDITS:
                assert mot not in ligne.lower(), f"« {mot} » n'a rien à faire dans « {ligne} »"

    def test_le_cout_du_boss_est_dit_en_minutes(self):
        """Le §14 l'exige : un chiffre qu'on ne sait pas convertir n'est pas une sanction."""
        s = sanction_rules.evaluate(
            missed_run=1, current_streak=0, broken_once=False, validated_today=False
        )
        assert any("45 min" in ligne for ligne in sanction_rules.lines(s, boss_regen_minutes=45))

    def test_la_mise_entamee_ne_se_repete_pas_tous_les_soirs(self):
        """Un prélèvement définitif n'est jamais « éteint » : le répéter serait un reproche.

        Trouvé à l'écran sur le compte de démonstration : la ligne s'affichait
        chaque soir pour une cassure vieille de deux semaines.
        """
        apres = sanction_rules.evaluate(
            missed_run=1, current_streak=0, broken_once=True, validated_today=False
        )
        assert not any("Mise" in ligne for ligne in sanction_rules.lines(apres, shards_forfeited=30))

        le_soir_meme = sanction_rules.evaluate(
            missed_run=2, current_streak=0, broken_once=True, validated_today=False
        )
        assert any(
            "Mise" in ligne for ligne in sanction_rules.lines(le_soir_meme, shards_forfeited=30)
        )

    def test_le_palier_3_ne_recite_rien(self):
        """« Pas de bilan de ce qui a été perdu » — la liste est vide, pas adoucie."""
        s = sanction_rules.evaluate(
            missed_run=4, current_streak=0, broken_once=True, validated_today=False, debt_minutes=10
        )
        assert sanction_rules.lines(s, boss_regen_minutes=45, shards_forfeited=25) == []


# --------------------------------------------------------------------------
# Le comportement réel, base à l'appui
# --------------------------------------------------------------------------

@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    profile.shards = 500
    profile.save()
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Evolve", slot=1, domain=slot_rules.CODE)
    return user


@pytest.fixture
def today(user):
    p = user.profile
    return coach_day(timezone.now(), p.timezone_name, p.day_rollover_hour)


def travaille(user, *, il_y_a: int, minutes: int = 30, saison=None):
    """Pose une session validée il y a ``il_y_a`` jours."""
    projet = Project.objects.get(user=user)
    p = user.profile
    jour = coach_day(timezone.now(), p.timezone_name, p.day_rollover_hour) - timedelta(days=il_y_a)
    debut = timezone.now() - timedelta(days=il_y_a)
    return Session.objects.create(
        user=user,
        project=projet,
        season=saison,
        planned_minutes=minutes,
        actual_minutes=minutes,
        status=Session.DONE,
        coach_day=jour,
        started_at=debut,
        ended_at=debut + timedelta(minutes=minutes),
    )


@pytest.mark.django_db
class TestBossQuiRegenere:
    """Le §14 le dit en minutes, et le champ existait sans que rien ne l'écrive."""

    def test_le_boss_recupere_une_session_par_jour_rate(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=10))
        travaille(user, il_y_a=3, minutes=300, saison=saison)
        boss = saison.boss
        boss.damage_taken = 1000
        boss.save()

        etat = services.home_state(user)

        boss.refresh_from_db()
        assert boss.regen == 2 * season_rules.BOSS_REGEN_ON_MISSED_DAY
        assert etat["sanctions"]["boss_regen_minutes"] == 90

    def test_relire_l_accueil_ne_double_pas_la_regeneration(self, user, today):
        """L'accueil est relu toutes les dix secondes : un incrément le viderait."""
        saison = services.open_season(user, starts_on=today - timedelta(days=10))
        travaille(user, il_y_a=3, minutes=300, saison=saison)
        saison.boss.damage_taken = 1000
        saison.boss.save()

        for _ in range(5):
            services.home_state(user)

        saison.boss.refresh_from_db()
        assert saison.boss.regen == 2 * season_rules.BOSS_REGEN_ON_MISSED_DAY

    def test_un_boss_intact_ne_remonte_pas_au_dessus_de_son_maximum(self, user, today):
        """Rendre de la vie jamais retirée ferait passer la barre au-dessus de 100 %."""
        saison = services.open_season(user, starts_on=today - timedelta(days=10))
        travaille(user, il_y_a=4, minutes=10, saison=saison)

        services.home_state(user)

        saison.boss.refresh_from_db()
        assert saison.boss.current_hp <= saison.boss.max_hp
        assert saison.boss.ratio <= 1.0

    def test_un_boss_mort_ne_ressuscite_pas(self, user, today):
        """Sa mort a joué sa séquence et clos la saison : la défaire serait rétroactif."""
        saison = services.open_season(user, starts_on=today - timedelta(days=10))
        travaille(user, il_y_a=4, minutes=300, saison=saison)
        boss = saison.boss
        boss.damage_taken = boss.max_hp
        boss.save()

        services.home_state(user)

        boss.refresh_from_db()
        assert boss.is_dead
        assert boss.regen == 0

    def test_la_dette_se_preleve_quand_le_boss_a_de_la_vie_a_rendre(self, user, today):
        """Rater un jour avant d'avoir touché le boss ne doit pas annuler le coût."""
        saison = services.open_season(user, starts_on=today - timedelta(days=10))
        travaille(user, il_y_a=3, minutes=300, saison=saison)
        services.home_state(user)          # aucun dégât encore : rien à rendre

        saison.boss.refresh_from_db()
        assert saison.boss.current_hp == saison.boss.max_hp

        saison.boss.damage_taken = 1000
        saison.boss.save()
        services.home_state(user)

        saison.boss.refresh_from_db()
        assert saison.boss.current_hp == saison.boss.max_hp - 1000 + 90


@pytest.mark.django_db
class TestMiseEntamee:
    """Le seul prélèvement irréversible du produit. Il ne se joue qu'une fois."""

    def prepare(self, user, today):
        # Modificateur neutre imposé : « Siège » double la mise (§12.5), et une
        # arithmétique de test qui dépend du tirage de saison ne se relit pas.
        saison = services.open_season(
            user, starts_on=today - timedelta(days=10), stake=100, modifier_key="aube"
        )
        travaille(user, il_y_a=3, minutes=30, saison=saison)   # puis deux jours ratés
        return saison

    def test_un_streak_casse_entame_un_quart_de_la_mise(self, user, today):
        saison = self.prepare(user, today)

        services.home_state(user)

        saison.refresh_from_db()
        user.profile.refresh_from_db()
        assert saison.stake_forfeited == 25
        assert user.profile.shards == 475

    def test_le_prelevement_ne_se_rejoue_pas_a_chaque_lecture(self, user, today):
        self.prepare(user, today)

        for _ in range(5):
            services.home_state(user)

        user.profile.refresh_from_db()
        assert user.profile.shards == 475

    def test_la_cloture_ne_reprend_pas_la_part_deja_partie(self, user, today):
        """Rejouer la mise entière à la clôture la ferait payer deux fois."""
        saison = self.prepare(user, today)
        services.home_state(user)
        saison.refresh_from_db()

        user.profile.refresh_from_db()
        avant = user.profile.shards

        saison.ends_on = today - timedelta(days=1)
        saison.save(update_fields=["ends_on"])
        bilan = season_flow.close_season(user, saison, today=today)

        assert bilan["stake_forfeited"] == 25
        assert bilan["stake_delta"] == -75, "il ne restait que trois quarts sur la table"

        # La clôture tire aussi des cartes, qui rapportent des Éclats : on
        # mesure donc ce que la **mise** a coûté, pas le solde final.
        loot = sum(carte["shards"] for carte in bilan["cards"])
        user.profile.refresh_from_db()
        assert user.profile.shards == avant - 75 + loot, "100 Éclats en tout, jamais 125"

    def test_sans_mise_rien_n_est_preleve(self, user, today):
        services.open_season(user, starts_on=today - timedelta(days=10), stake=0)
        travaille(user, il_y_a=3, minutes=30)

        services.home_state(user)

        user.profile.refresh_from_db()
        assert user.profile.shards == 500


@pytest.mark.django_db
class TestVitrineEtSlots:
    def test_la_vitrine_se_ferme_au_premier_jour_rate(self, user, today):
        travaille(user, il_y_a=2, minutes=30)

        assert services.sanctions_for(user, today=today).showcase_locked

    def test_dix_minutes_rouvrent_la_vitrine(self, user, today):
        travaille(user, il_y_a=2, minutes=30)
        travaille(user, il_y_a=0, minutes=10)

        assert not services.sanctions_for(user, today=today).showcase_locked

    def test_le_slot_gagne_est_gele_au_palier_2(self, user, today):
        """Le droit d'en ouvrir un de plus est suspendu, pas repris (§4.3)."""
        travaille(user, il_y_a=3, minutes=30)
        atelier = Track.objects.get(user=user)
        for i in (2, 3):
            Project.objects.create(
                user=user, track=atelier, name=f"P{i}", slot=i,
                domain=slot_rules.CREATIF if i == 3 else slot_rules.CODE,
            )

        # Le rang ouvre un quatrième slot, mais deux jours ratés le gèlent.
        from unittest.mock import patch

        with patch.object(services, "rank_state", return_value={"slots": 4, "code": "B"}):
            assert services.free_slot(user, slot_rules.SAVOIR, today=today) is None

    def test_le_gel_ne_deloge_aucun_projet(self, user, today):
        """« Les projets ne sont pas supprimés, le slot est gelé jusqu'à la reprise. »"""
        travaille(user, il_y_a=3, minutes=30)
        atelier = Track.objects.get(user=user)
        quatrieme = Project.objects.create(
            user=user, track=atelier, name="Quatrième", slot=4, domain=slot_rules.SAVOIR
        )

        services.home_state(user)

        quatrieme.refresh_from_db()
        assert quatrieme.status == Project.ACTIVE
        assert quatrieme.slot == 4


@pytest.mark.django_db
class TestRampeDeRetour:
    def test_apres_trois_jours_la_proposition_tombe_a_dix_minutes(self, user, today):
        travaille(user, il_y_a=5, minutes=30)

        etat = services.home_state(user)

        assert etat["sanctions"]["comeback"]
        assert etat["proposal"]["minutes"] == 10

    def test_l_accueil_du_palier_3_n_enumere_rien(self, user, today):
        travaille(user, il_y_a=5, minutes=30)

        assert services.home_state(user)["sanctions"]["lines"] == []

    def test_la_sortie_de_saison_n_est_offerte_qu_au_dela_de_cinq_jours(self, user, today):
        services.open_season(user, starts_on=today - timedelta(days=10), stake=40)
        travaille(user, il_y_a=4, minutes=30)

        assert season_flow.exit_offer(user, today=today) is None

    def test_la_sortie_annonce_son_prix(self, user, today):
        services.open_season(
            user, starts_on=today - timedelta(days=10), stake=40, modifier_key="aube"
        )
        travaille(user, il_y_a=7, minutes=30)
        services.home_state(user)          # prélève déjà le quart du palier 2

        offre = season_flow.exit_offer(user, today=today)

        assert offre is not None
        assert offre["stake_at_risk"] == 30, "ce qu'il reste sur la table, pas la mise d'origine"


@pytest.mark.django_db
class TestRienDeRetroactif:
    """Invariant 2, et le socle de crédibilité du système tout entier."""

    def test_aucune_sanction_ne_retire_d_xp_d_heures_ni_de_rang(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=10), stake=100)
        session = travaille(user, il_y_a=6, minutes=50, saison=saison)
        session.xp_awarded = 420
        session.save()

        avant = services.home_state(user)
        for _ in range(3):
            apres = services.home_state(user)

        assert apres["progression"]["total_xp"] == avant["progression"]["total_xp"] == 420
        assert apres["rank"]["weeks_kept"] == avant["rank"]["weeks_kept"]
        assert Session.objects.get(pk=session.pk).actual_minutes == 50

    def test_le_streak_reste_la_seule_source_du_palier(self, user, today):
        """Deux lectures du même historique ne doivent jamais donner deux paliers."""
        travaille(user, il_y_a=3, minutes=30)

        etat = services.home_state(user)
        atelier = Track.objects.get(user=user)
        state = services.streak_state(user, atelier, today=today)

        assert etat["sanctions"]["level"] == state.sanction_level


class TestPlancherProgressif:
    """Le §4.1 après la décision du 16 août 2026.

    Ce qui monte est l'exigence, jamais la fragilité. Le test qui compte est le
    second : si un jour le mode dégradé se met à suivre le rang, c'est toute la
    protection contre « j'ai rien fait donc j'arrête » qui tombe.
    """

    def test_le_plancher_monte_avec_le_rang(self):
        assert streak_rules.floor_for("F") == 25
        assert streak_rules.floor_for("C") == 25
        assert streak_rules.floor_for("B") == 30
        assert streak_rules.floor_for("A") == 35

    def test_le_mode_degrade_ne_monte_jamais(self):
        """L'issue de secours du soir où l'on rentre à 22h ne bouge pas."""
        from forge.services import DEGRADED_MINUTES

        assert DEGRADED_MINUTES == 10

    def test_le_plancher_plafonne_a_35(self):
        for rang in ("A", "S", "SS"):
            assert streak_rules.floor_for(rang) == streak_rules.MAX_FLOOR_MINUTES

    def test_un_rang_inconnu_reste_au_plancher_de_base(self):
        assert streak_rules.floor_for("") == streak_rules.FLOOR_MINUTES

    def test_la_dette_s_ajoute_au_plancher_du_rang_et_pas_a_la_constante(self):
        """Au rang B, deux jours ratés demandent 40 min, pas 35."""
        etat = streak_rules.StreakState(missed_run=2, floor_minutes=30)
        assert etat.required_minutes == 40

    def test_sans_dette_le_plancher_du_rang_est_le_seuil(self):
        assert streak_rules.StreakState(missed_run=0, floor_minutes=35).required_minutes == 35
