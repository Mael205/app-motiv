"""Ce qui se passe quand le boss de saison tombe (SPEC §12.4).

Écrit pour répondre à une question — *la saison est-elle finie ? un nouveau boss
apparaît-il ?* — et gardé parce que la réponse n'était écrite nulle part.
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import season_flow, services
from forge.models import Profile, Project, RoadmapStep, Season, Session, Track
from forge.rules import seasons as season_rules

DEBUT = date(2026, 3, 2)


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="boss", password="test")
    Profile.objects.create(user=user)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    projet = Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
    for i in range(40):
        RoadmapStep.objects.create(project=projet, order=i, label=f"Étape {i}")
    services.open_season(user, starts_on=DEBUT, stake=100)
    return user


def seance_extra(user, *, jour: date, minutes: int) -> Session:
    """Une séance posée un jour où aucune saison ne tourne."""
    debut = timezone.now()
    return Session.objects.create(
        user=user,
        project=Project.objects.get(user=user),
        season=None,
        coach_day=jour,
        started_at=debut,
        ended_at=debut,
        planned_minutes=minutes,
        actual_minutes=minutes,
        status=Session.DONE,
    )


def tuer_le_boss(user, *, jour: date) -> Season:
    """Termine des étapes jusqu'à ce que le boss tombe. 60 points par étape."""
    saison = Season.objects.get(user=user, status=Season.RUNNING)
    for step in RoadmapStep.objects.filter(project__user=user, state=RoadmapStep.TODO):
        services.complete_step(user, step, today=jour)
        saison.boss.refresh_from_db()
        if saison.boss.is_dead:
            break
    return saison


class TestBossAbattu:
    def test_le_boss_mort_termine_la_saison_en_avance(self, user):
        saison = tuer_le_boss(user, jour=DEBUT + timedelta(days=10))
        assert saison.boss.is_dead
        assert season_flow.is_over(saison, today=DEBUT + timedelta(days=10))

    def test_la_cloture_decerne_le_titre_et_double_la_mise(self, user):
        jour = DEBUT + timedelta(days=10)
        saison = tuer_le_boss(user, jour=jour)
        eclats_avant = user.profile.shards

        bilan = season_flow.close_season(user, saison, today=jour)
        saison.refresh_from_db()
        user.profile.refresh_from_db()

        assert saison.status == Season.CLOSED
        assert saison.title_awarded
        assert user.profile.shards >= eclats_avant + 100, "la mise revient doublée"
        assert len(bilan["cards"]) == 2

    def test_la_cloture_date_le_jour_reel_et_non_la_fin_prevue(self, user):
        jour = DEBUT + timedelta(days=10)
        saison = tuer_le_boss(user, jour=jour)
        season_flow.close_season(user, saison, today=jour)
        saison.refresh_from_db()

        assert saison.closed_on == jour
        assert saison.closed_on < saison.ends_on, "la victoire est en avance"


class TestModeExtra:
    """Les jours qui restent après la victoire (§12.4).

    Ils étaient **vides** : la saison suivante ne démarrait qu'après la date de
    fin prévue, donc un boss tué au jour 11 ouvrait vingt jours sans boss, sans
    fantôme et sans modificateur. Le §12.4 les prévoyait pourtant : « les jours
    restants alimentent directement le score de la saison suivante ».
    """

    @pytest.fixture
    def apres_la_victoire(self, user):
        jour = DEBUT + timedelta(days=10)
        saison = tuer_le_boss(user, jour=jour)
        season_flow.close_season(user, saison, today=jour)
        offre = season_flow.next_offer(user, today=jour)
        suivante = services.open_season(
            user, starts_on=date.fromisoformat(offre["starts_on"])
        )
        return jour, saison, suivante

    def test_la_saison_suivante_est_engagee_et_attend_sa_date(self, user, apres_la_victoire):
        jour, _, suivante = apres_la_victoire
        assert suivante.starts_on > jour
        assert services.current_season(user, today=jour) is None
        assert season_flow.saison_a_venir(user, today=jour) == suivante

    def test_elle_n_est_plus_reproposee(self, user, apres_la_victoire):
        """Sans cette garde, accepter l'offre en créait une seconde, puis une troisième."""
        jour, _, _ = apres_la_victoire
        assert season_flow.next_offer(user, today=jour) is None

    def test_le_travail_des_jours_extra_alimente_la_saison_suivante(self, user, apres_la_victoire):
        jour, _, suivante = apres_la_victoire
        # Une séance posée pendant l'extra : aucune saison ne tourne, donc
        # ``start_session`` ne lui en attache aucune — c'est cette absence que
        # ``minutes_extra`` va retrouver, bornée par les dates.
        seance_extra(user, jour=jour + timedelta(days=3), minutes=50)

        assert season_flow.minutes_extra(user, suivante) == 50
        assert season_flow.season_score(user, suivante) == 50

    def test_le_travail_d_avant_la_victoire_n_y_entre_pas(self, user, apres_la_victoire):
        """La fenêtre commence à la clôture réelle, sinon la saison gagnée serait
        comptée deux fois — une fois dans son score, une fois dans l'extra."""
        jour, _, suivante = apres_la_victoire
        seance_extra(user, jour=jour - timedelta(days=2), minutes=40)

        assert season_flow.minutes_extra(user, suivante) == 0

    def test_l_etat_extra_dit_ce_qui_attend_et_ce_qui_est_mis_de_cote(self, user, apres_la_victoire):
        jour, _, suivante = apres_la_victoire
        etat = season_flow.etat_extra(user, today=jour)

        assert etat["name"] == suivante.name
        assert etat["days_until"] == (suivante.starts_on - jour).days
        assert etat["minutes"] == 0

    def test_l_extra_s_arrete_quand_la_saison_commence(self, user, apres_la_victoire):
        _, _, suivante = apres_la_victoire
        assert season_flow.etat_extra(user, today=suivante.starts_on) is None
        assert services.current_season(user, today=suivante.starts_on) == suivante


class TestVieDuProchainBoss:
    """Elle suit les **dégâts infligés**, jamais les minutes seules.

    Les dégâts viennent aussi des étapes de roadmap — soixante points chacune.
    Mesurer la performance en minutes faisait donc rétrécir le boss à chaque
    saison gagnée par l'avancement plutôt que par le volume, ce qui est
    exactement l'inverse de ce que le ×1,05 du §12.4 promet.
    """

    def test_un_boss_abattu_ne_rend_jamais_le_suivant_plus_faible(self, user):
        jour = DEBUT + timedelta(days=10)
        saison = tuer_le_boss(user, jour=jour)
        season_flow.close_season(user, saison, today=jour)

        offre = season_flow.next_offer(user, today=jour)
        assert saison.final_score < saison.boss.max_hp, "tué surtout par des étapes"
        assert offre["boss"]["hp"] >= saison.boss.max_hp

    def test_le_debordement_du_dernier_coup_ne_compte_pas(self, user):
        """Sinon la barre monterait d'un hasard : le coup fatal dépasse presque toujours."""
        jour = DEBUT + timedelta(days=10)
        saison = tuer_le_boss(user, jour=jour)
        assert saison.boss.damage_taken >= saison.boss.max_hp
        assert services.puissance_de_saison(user, saison) == saison.boss.max_hp
