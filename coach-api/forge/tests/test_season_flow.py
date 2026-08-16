"""Le cycle d'une saison : clôture, offre, ouverture (SPEC §12.2, §12.6, §7.4).

Deux choses se jouent ici et rien d'autre dans le système ne leur ressemble.

**La mise est le seul endroit où quelque chose se perd.** Le §12.6 le veut :
un enjeu réel, sans conséquence matérielle. Une mise résolue deux fois
doublerait ou effacerait des Éclats sans que personne ne comprenne pourquoi —
d'où l'insistance sur l'idempotence.

**Le titre raté existe.** Le §12.3 dit qu'une collection sans trous n'a aucune
valeur. Un système qui n'enregistrerait que les réussites mentirait sur ce qui
s'est passé, et c'est testé comme une promesse et non comme un calcul.
"""

import random
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import season_flow, services
from forge.models import Profile, Project, Season, Session, Track
from forge.rules import phantom as phantom_rules
from forge.rules.calendar import coach_day


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    profile.shards = 500
    profile.save()
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Evolve", branch="moteur_de_jeu", slot=1)
    return user


@pytest.fixture
def today(user):
    p = user.profile
    return coach_day(timezone.now(), p.timezone_name, p.day_rollover_hour)


def travailler(user, saison, *, minutes: int, day):
    projet = Project.objects.get(user=user)
    debut = timezone.now() - timedelta(days=2)
    return Session.objects.create(
        user=user,
        project=projet,
        season=saison,
        planned_minutes=minutes,
        actual_minutes=minutes,
        status=Session.DONE,
        coach_day=day,
        started_at=debut,
        ended_at=debut + timedelta(minutes=minutes),
    )


class TestCloture:
    def test_une_saison_finie_est_a_clore(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=50)

        assert season_flow.pending_close(user, today=today) == saison

    def test_une_saison_en_cours_n_est_pas_a_clore(self, user, today):
        services.open_season(user, starts_on=today - timedelta(days=2), stake=50)

        assert season_flow.pending_close(user, today=today) is None

    def test_un_boss_mort_termine_la_saison_en_avance(self, user, today):
        """§12.4 : tuer le boss déclenche la séquence de fin en avance."""
        saison = services.open_season(user, starts_on=today - timedelta(days=2), stake=50)
        saison.boss.damage_taken = saison.boss.max_hp
        saison.boss.save()

        assert season_flow.pending_close(user, today=today) == saison

    def test_le_score_est_en_minutes_travaillees(self, user, today):
        """En minutes et non en XP : comparer des XP comparerait des règles."""
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=0)
        travailler(user, saison, minutes=50, day=today - timedelta(days=39))
        travailler(user, saison, minutes=25, day=today - timedelta(days=38))

        bilan = season_flow.close_season(user, saison, today=today)

        assert bilan["score"] == 75
        assert bilan["hours"] == 1.2

    def test_le_titre_rate_est_decerne_franchement(self, user, today):
        """Une collection sans trous n'a aucune valeur (§12.3)."""
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=0)

        bilan = season_flow.close_season(user, saison, today=today)

        assert "Déserteur" in bilan["title"]
        assert bilan["won"] is False

    def test_aucun_titre_ne_contient_de_jugement(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=0)
        bilan = season_flow.close_season(user, saison, today=today)

        for mot in ("nul", "raté", "honte", "décevant", "!"):
            assert mot not in bilan["title"].lower()

    def test_une_saison_gagnee_double_la_mise(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=100)
        saison.boss.damage_taken = saison.boss.max_hp
        saison.boss.save()
        avant = user.profile.shards

        bilan = season_flow.close_season(user, saison, today=today)
        user.profile.refresh_from_db()

        assert bilan["won"] is True
        assert user.profile.shards >= avant + saison.stake_shards
        assert bilan["stake_delta"] == saison.stake_shards

    def test_une_saison_perdue_perd_la_mise(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=100)
        avant = user.profile.shards

        bilan = season_flow.close_season(user, saison, today=today)
        user.profile.refresh_from_db()

        assert bilan["stake_delta"] == -saison.stake_shards
        assert user.profile.shards < avant

    def test_les_eclats_ne_passent_jamais_sous_zero(self, user, today):
        user.profile.shards = 10
        user.profile.save()
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=500)

        season_flow.close_season(user, saison, today=today)
        user.profile.refresh_from_db()

        assert user.profile.shards == 0

    def test_la_cloture_est_idempotente(self, user, today):
        """Appelée à l'ouverture de l'app ET par un déclencheur : une mise
        résolue deux fois doublerait des Éclats sans raison visible."""
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=100)

        season_flow.close_season(user, saison, today=today)
        user.profile.refresh_from_db()
        apres_une = user.profile.shards

        saison.refresh_from_db()
        second = season_flow.close_season(user, saison, today=today)
        user.profile.refresh_from_db()

        assert second["already_closed"] is True
        assert second["cards"] == []
        assert user.profile.shards == apres_une

    def test_la_cloture_tire_une_carte(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=0)

        bilan = season_flow.close_season(user, saison, today=today, rng=random.Random(1))

        assert len(bilan["cards"]) == 1

    def test_une_saison_gagnee_en_tire_deux(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=40), stake=0)
        saison.boss.damage_taken = saison.boss.max_hp
        saison.boss.save()

        bilan = season_flow.close_season(user, saison, today=today, rng=random.Random(1))

        assert len(bilan["cards"]) == 2


class TestOffre:
    def test_l_offre_n_ecrit_rien(self, user, today):
        """Une saison ouverte par un appel de lecture serait un engagement
        pris à la place de quelqu'un."""
        avant = Season.objects.count()

        season_flow.next_offer(user, today=today)

        assert Season.objects.count() == avant

    def test_trois_modificateurs_sont_proposes(self, user, today):
        """Un choix, pas une subissance (§12.5)."""
        assert len(season_flow.next_offer(user, today=today)["modifiers"]) == 3

    def test_chaque_modificateur_annonce_son_prix(self, user, today):
        """Un modificateur dont on découvre le coût trois semaines plus tard
        n'a pas été choisi."""
        for m in season_flow.next_offer(user, today=today)["modifiers"]:
            assert m["boss_hp"] > 0
            assert m["stake_multiplier"] >= 1
            assert isinstance(m["hard"], bool)

    def test_les_fantomes_annoncent_leur_total(self, user, today):
        """Choisir « ma meilleure saison » sans savoir ce qu'elle vaut revient
        à choisir au hasard."""
        for f in season_flow.next_offer(user, today=today)["phantoms"]:
            assert f["label"]
            assert "hours" in f

    def test_sans_saison_passee_aucun_fantome_n_est_disponible(self, user, today):
        offres = season_flow.next_offer(user, today=today)["phantoms"]

        assert all(not f["available"] for f in offres)

    def test_la_saison_suivante_ne_commence_jamais_dans_le_passe(self, user, today):
        """Sinon elle naîtrait avec des jours déjà manqués."""
        saison = services.open_season(user, starts_on=today - timedelta(days=60), stake=0)
        season_flow.close_season(user, saison, today=today)

        offre = season_flow.next_offer(user, today=today)

        assert offre["starts_on"] >= today.isoformat()

    def test_deux_jours_de_pause_apres_une_saison_recente(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=27), stake=0)
        saison.boss.damage_taken = saison.boss.max_hp
        saison.boss.save()
        season_flow.close_season(user, saison, today=today)

        offre = season_flow.next_offer(user, today=today)

        assert offre["starts_on"] > today.isoformat()


class TestOuverture:
    def test_le_modificateur_choisi_est_applique(self, user, today):
        offre = season_flow.next_offer(user, today=today)
        choisi = offre["modifiers"][1]["key"]

        saison = season_flow.open_next(user, today=today, modifier_key=choisi)

        assert saison.modifier_key == choisi

    def test_un_modificateur_hors_des_trois_est_refuse(self, user, today):
        """Accepter n'importe quelle clé laisserait prendre le plus avantageux
        à chaque saison, et la saison 5 redeviendrait la saison 1."""
        proposes = {m["key"] for m in season_flow.next_offer(user, today=today)["modifiers"]}
        autre = next(
            k for k in ("aube", "marathon", "siege", "discipline", "deux_fronts", "fragmentation")
            if k not in proposes
        )

        with pytest.raises(ValueError, match="proposés"):
            season_flow.open_next(user, today=today, modifier_key=autre)

    def test_un_choix_de_fantome_inconnu_est_refuse(self, user, today):
        with pytest.raises(ValueError, match="fantôme"):
            season_flow.open_next(user, today=today, phantom_choice="inventé")

    def test_le_fantome_choisi_est_fige(self, user, today):
        saison = season_flow.open_next(user, today=today, phantom_choice=phantom_rules.DERNIERE)

        assert saison.phantom_choice == phantom_rules.DERNIERE

    def test_siege_double_la_mise_a_l_ouverture(self, user, today):
        offre = season_flow.next_offer(user, today=today)
        siege = next((m for m in offre["modifiers"] if m["key"] == "siege"), None)
        if siege is None:
            pytest.skip("Siège n'est pas dans les trois proposés pour cet index")

        saison = season_flow.open_next(user, today=today, modifier_key="siege", stake=100)

        assert saison.stake_shards == 200

    def test_le_boss_suit_le_modificateur_retenu(self, user, today):
        offre = season_flow.next_offer(user, today=today)
        attendu = {m["key"]: m["boss_hp"] for m in offre["modifiers"]}
        choisi = offre["modifiers"][0]["key"]

        saison = season_flow.open_next(user, today=today, modifier_key=choisi)

        assert saison.boss.max_hp == attendu[choisi]

    def test_sans_choix_le_plan_decide(self, user, today):
        """Ouvrir sans rien choisir doit rester possible et cohérent."""
        saison = season_flow.open_next(user, today=today)

        assert saison.modifier_key
        assert saison.phantom_choice == phantom_rules.MEILLEURE


class TestMortDuBoss:
    """Le §12.4 : tuer le boss déclenche la fin de saison en avance."""

    def test_le_boss_tombe_au_moment_ou_il_tombe(self, user, today):
        """C'est le franchissement qui se met en scène, pas l'état — sinon la
        séquence se rejouerait à chaque session jusqu'à la clôture."""
        saison = services.open_season(user, starts_on=today - timedelta(days=2), stake=0)
        saison.boss.damage_taken = saison.boss.max_hp - 10
        saison.boss.save()

        projet = Project.objects.get(user=user)
        session = services.start_session(user, projet, planned_minutes=25)
        session.started_at = timezone.now() - timedelta(minutes=25)
        session.save(update_fields=["started_at"])

        resultat = services.end_session(session, next_action="suite")

        assert resultat["boss_killed"] is not None
        assert resultat["boss_killed"]["name"] == saison.boss.name

    def test_un_boss_deja_mort_ne_se_retue_pas(self, user, today):
        saison = services.open_season(user, starts_on=today - timedelta(days=2), stake=0)
        saison.boss.damage_taken = saison.boss.max_hp * 2
        saison.boss.save()

        projet = Project.objects.get(user=user)
        session = services.start_session(user, projet, planned_minutes=25)
        session.started_at = timezone.now() - timedelta(minutes=25)
        session.save(update_fields=["started_at"])

        assert services.end_session(session, next_action="suite")["boss_killed"] is None

    def test_un_boss_vivant_ne_declenche_rien(self, user, today):
        services.open_season(user, starts_on=today - timedelta(days=2), stake=0)

        projet = Project.objects.get(user=user)
        session = services.start_session(user, projet, planned_minutes=25)
        session.started_at = timezone.now() - timedelta(minutes=25)
        session.save(update_fields=["started_at"])

        assert services.end_session(session, next_action="suite")["boss_killed"] is None
