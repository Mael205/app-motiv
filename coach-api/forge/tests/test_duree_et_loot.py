"""Ce qu'une séance longue vaut, et ce que l'effort change au tirage.

Tranché le 19 août 2026, sur les deux questions laissées ouvertes dans
``docs/a-faire.md``. Les deux réponses vont dans le même sens : le système
mesurait du **volume découpé en sessions** et ne voyait pas la différence entre
deux plongées de vingt-cinq minutes et une d'une heure. Il la voit maintenant,
et sans toucher au plafond de régime du §0.2 — qui compte des sessions, pas des
minutes, et que prolonger ne contourne donc pas.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import services
from forge.models import Profile, Project, RoadmapStep, Track
from forge.rules import loot as loot_rules
from forge.rules.calendar import coach_day
from forge.rules.xp import prime_de_duree, session_xp


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="duree", password="test")
    profile = Profile.objects.create(user=user)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    today = coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour)
    projet = Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
    RoadmapStep.objects.create(project=projet, order=1, label="Écran de liste")
    RoadmapStep.objects.create(project=projet, order=2, label="Filtres")
    services.open_season(user, starts_on=today, stake=100)
    return user


@pytest.fixture
def project(user):
    return Project.objects.get(user=user, name="Bestiaire")


def xp(**kwargs) -> int:
    defaults = dict(
        minutes=25,
        rank_in_day=1,
        is_first_of_day=True,
        started_hour=19,
        streak=0,
        days_worked_this_week=1,
    )
    return session_xp(**{**defaults, **kwargs}).total


class TestPrimeDeDuree:
    def test_sous_vingt_cinq_minutes_aucune_prime(self):
        assert prime_de_duree(10) == 0
        assert prime_de_duree(25) == 0

    def test_la_prime_est_par_tranche_et_non_sur_le_total(self):
        # Les 25 premières minutes gardent leur valeur, quoi qu'il arrive après.
        assert prime_de_duree(45) == round(20 * 0.5)
        assert prime_de_duree(50) == round(20 * 0.5 + 5 * 0.75)

    def test_une_longue_vaut_plus_que_la_meme_duree_coupee_en_deux(self):
        """La propriété qui justifie le calibrage, et la seule qui compte.

        Couper la soirée en deux paie **deux fois** les forfaits — première
        session du jour, démarrée avant 20h. Une prime plus faible que ce que le
        fractionnement duplique ferait dire à la mécanique l'inverse de ce
        qu'elle annonce.
        """
        une_longue = xp(minutes=50)
        deux_courtes = xp(minutes=25) + xp(minutes=25, rank_in_day=2, is_first_of_day=False)
        assert une_longue > deux_courtes

    def test_elle_tient_aussi_apres_vingt_heures(self):
        une_longue = xp(minutes=50, started_hour=21)
        deux_courtes = xp(minutes=25, started_hour=21) + xp(
            minutes=25, started_hour=21, rank_in_day=2, is_first_of_day=False
        )
        assert une_longue > deux_courtes

    def test_la_prime_ne_contourne_pas_le_plafond_de_regime(self):
        """Une cinquième séance de deux heures ne rapporte toujours rien (§0.2)."""
        assert xp(minutes=120, rank_in_day=5, is_first_of_day=False) == 0

    def test_le_detail_dit_la_prime(self):
        detail = session_xp(
            minutes=50, rank_in_day=1, is_first_of_day=True, started_hour=19, streak=0
        )
        assert detail.duration_premium == 14
        assert any("Prime de durée" in note for note in detail.notes)


class TestCarteDeSessionLongue:
    def test_rien_sous_le_plancher_normal(self):
        assert loot_rules.chance_de_carte(10) == 0.0
        assert loot_rules.chance_de_carte(24) == 0.0

    def test_la_chance_monte_avec_les_minutes(self):
        assert 0 < loot_rules.chance_de_carte(35) < loot_rules.chance_de_carte(50)

    def test_elle_plafonne(self):
        assert loot_rules.chance_de_carte(60) == loot_rules.SESSION_CHANCE_MAX
        assert loot_rules.chance_de_carte(240) == loot_rules.SESSION_CHANCE_MAX


class TestFaveurDEtape:
    def test_une_etape_expediee_ne_favorise_rien(self):
        assert loot_rules.faveur_pour(0) == 0.0

    def test_la_faveur_monte_puis_plafonne(self):
        assert loot_rules.faveur_pour(150) == 0.5
        assert loot_rules.faveur_pour(600) == 1.0

    def test_la_faveur_incline_sans_garantir(self):
        pleine = loot_rules.rarity_weights(draws_since_rare=0, draws_since_epic=0, faveur=1.0)
        neutre = loot_rules.rarity_weights(draws_since_rare=0, draws_since_epic=0)
        assert pleine[loot_rules.COMMUN] < neutre[loot_rules.COMMUN]
        assert pleine[loot_rules.RARE] > neutre[loot_rules.RARE]
        assert pleine[loot_rules.EPIQUE] > neutre[loot_rules.EPIQUE]
        # Rien n'est garanti : le commun reste possible.
        assert pleine[loot_rules.COMMUN] > 0
        assert sum(pleine.values()) == sum(neutre.values())


@pytest.mark.django_db
class TestProlongation:
    def test_prolonger_rehausse_l_objectif(self, user, project):
        session = services.start_session(user, project, planned_minutes=25)
        etat = services.extend_session(session, now=session.started_at + timedelta(minutes=20))
        assert etat["planned_minutes"] == 40
        assert etat["extensions"] == 1

    def test_prolonger_apres_le_terme_repart_de_maintenant(self, user, project):
        """Sinon le bouton ne changerait rien de visible : l'anneau resterait à zéro."""
        session = services.start_session(user, project, planned_minutes=25)
        etat = services.extend_session(session, now=session.started_at + timedelta(minutes=55))
        assert etat["planned_minutes"] == 70

    def test_une_seance_close_ne_se_prolonge_plus(self, user, project):
        session = services.start_session(user, project, planned_minutes=25)
        services.end_session(
            session, now=session.started_at + timedelta(minutes=25), next_action="x"
        )
        session.refresh_from_db()
        with pytest.raises(ValueError):
            services.extend_session(session)

    def test_les_minutes_prolongees_comptent_a_la_cloture(self, user, project):
        session = services.start_session(user, project, planned_minutes=25)
        services.extend_session(session, now=session.started_at + timedelta(minutes=24))
        session.refresh_from_db()
        result = services.end_session(
            session, now=session.started_at + timedelta(minutes=40), next_action="x"
        )
        assert result["minutes"] == 40
        assert result["objectif"] == 40
        assert result["extensions"] == 1


@pytest.mark.django_db
class TestEtapeEtEffort:
    def test_les_minutes_posees_sont_comptees_depuis_le_debut_de_l_etape(self, user, project):
        etape = project.steps.first()
        session = services.start_session(user, project, planned_minutes=50)
        etape.refresh_from_db()
        assert etape.doing_since is not None
        services.end_session(
            session, now=session.started_at + timedelta(minutes=50), next_action="x"
        )
        assert services.minutes_sur_etape(etape) == 50

    def test_une_etape_jamais_commencee_ne_vaut_aucune_faveur(self, user, project):
        etape = project.steps.last()
        assert etape.doing_since is None
        assert services.minutes_sur_etape(etape) == 0
