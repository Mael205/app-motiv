"""La trame des saisons : deux voies, et le résultat qui décide (SPEC §12.2).

L'ordre des identités était tiré dans une permutation qui changeait chaque
année. Ça empêchait la répétition — et ça empêchait aussi toute histoire : une
saison tombait sans rapport avec la précédente, et son nom n'était qu'une
étiquette de couleur.

Ce qui se teste ici est la seule chose qui compte pour une trame : **qu'elle
suive ce qui s'est passé**. Une saison tenue ouvre les Cimes, une saison ratée
ouvre les Braises, et chaque voie reprend là où on l'avait laissée.
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from forge import season_flow, services
from forge.models import Profile, Project, RoadmapStep, Season, Track
from forge.rules import seasons as season_rules

DEBUT = date(2026, 3, 2)


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="trame", password="test")
    Profile.objects.create(user=user)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    projet = Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
    for i in range(80):
        RoadmapStep.objects.create(project=projet, order=i, label=f"Étape {i}")
    return user


def jouer_une_saison(user, *, depart: date, tenue: bool) -> Season:
    """Ouvre une saison, la gagne ou non, la clôt. Rend la saison close."""
    saison = services.open_season(user, starts_on=depart, stake=50)
    if tenue:
        for step in RoadmapStep.objects.filter(project__user=user, state=RoadmapStep.TODO):
            services.complete_step(user, step, today=depart)
            saison.boss.refresh_from_db()
            if saison.boss.is_dead:
                break
    season_flow.close_season(user, saison, today=saison.ends_on)
    saison.refresh_from_db()
    return saison


def parcours(user, resultats: list[bool]) -> list[Season]:
    """Enchaîne des saisons avec les résultats donnés, et rend leur suite."""
    depart = DEBUT
    for tenue in resultats:
        saison = jouer_une_saison(user, depart=depart, tenue=tenue)
        depart = season_rules.next_season_start(saison.ends_on)
    return list(Season.objects.filter(user=user).order_by("index"))


class TestLaVoieSuitLeResultat:
    def test_on_commence_par_l_eveil(self, user):
        saisons = parcours(user, [True])
        assert saisons[0].name == "L'Éveil"
        assert saisons[0].voie == season_rules.VOIE_CIMES

    def test_une_saison_tenue_ouvre_les_cimes(self, user):
        saisons = parcours(user, [True, True])
        assert saisons[0].reussie is True
        assert saisons[1].voie == season_rules.VOIE_CIMES
        assert saisons[1].name == season_rules.TRAME[season_rules.VOIE_CIMES][1]["name"]

    def test_une_saison_ratee_ouvre_les_braises(self, user):
        saisons = parcours(user, [False, False])
        assert saisons[0].reussie is False
        assert saisons[1].voie == season_rules.VOIE_BRAISES
        assert saisons[1].name == "Nadir", "le fond, puis on creuse"

    def test_la_voie_basse_ne_retire_rien(self, user):
        """Le §17 interdit d'ajouter une sanction : la trame décore, elle ne
        punit pas. Même mise engagée, même vie de boss qu'aux Cimes."""
        saisons = parcours(user, [False, False])
        basse = saisons[1]
        assert basse.stake_shards == 50
        assert basse.boss.max_hp > 0


class TestChaqueVoieAvanceASonRythme:
    def test_on_reprend_la_voie_basse_ou_on_l_avait_laissee(self, user):
        """Le point de la mécanique. Rater, remonter, rater de nouveau : la
        seconde chute ne rejoue pas Nadir, elle enchaîne sur le Purgatoire.

        La voie d'une saison est décidée par le résultat de **celle d'avant** :
        rater la première ouvre la deuxième aux Braises, la tenir ramène la
        troisième aux Cimes, et la rater de nouveau reprend la voie basse là où
        elle s'était arrêtée.
        """
        saisons = parcours(user, [False, True, False, True])

        assert saisons[1].name == "Nadir"                     # première chute
        assert saisons[2].voie == season_rules.VOIE_CIMES     # on remonte
        assert saisons[3].name == "Purgatoire", "la voie basse reprend au suivant"

    def test_une_annee_en_dents_de_scie_tricote_les_deux(self, user):
        saisons = parcours(user, [True, False, True, False, True])
        voies = [s.voie for s in saisons]
        assert voies == [
            season_rules.VOIE_CIMES,      # la première, toujours
            season_rules.VOIE_CIMES,      # après une tenue
            season_rules.VOIE_BRAISES,    # après une ratée
            season_rules.VOIE_CIMES,
            season_rules.VOIE_BRAISES,
        ]
        # Et aucune identité ne se répète tant que la voie n'a pas bouclé.
        assert len({s.key for s in saisons}) == len(saisons)


class TestCeQueLaTrameNeDecidePas:
    def test_le_boss_reste_tire_et_non_apparie(self, user):
        """La trame dit ce qu'on traverse, pas qui l'on affronte : deux saisons
        de même nom à deux tours d'écart doivent garder de quoi surprendre."""
        premier = season_rules.pick_boss(1)["key"]
        plus_tard = season_rules.pick_boss(1 + 12 * 2)["key"]
        assert premier != plus_tard

    def test_le_resultat_est_grave_et_non_recalcule(self, user):
        """Un seuil qui bougerait un jour réécrirait une histoire déjà vécue."""
        saisons = parcours(user, [False])
        assert saisons[0].reussie is False

        saisons[0].boss.damage_taken = saisons[0].boss.max_hp
        saisons[0].boss.save(update_fields=["damage_taken"])
        saisons[0].refresh_from_db()
        assert saisons[0].reussie is False, "close une fois, racontée pour toujours"

    def test_l_essai_ne_decide_de_rien(self, user):
        """Les jours passés à comprendre le système ne choisissent pas la voie."""
        essai = services.open_season(
            user, starts_on=DEBUT, essai=True, ends_on=DEBUT + timedelta(days=6)
        )
        season_flow.close_season(user, essai, today=essai.ends_on)
        essai.refresh_from_db()
        assert essai.reussie is False, "un essai sans boss abattu"

        voie, position = services.prochaine_voie(user)
        assert voie == season_rules.VOIE_CIMES
        assert position == 0
