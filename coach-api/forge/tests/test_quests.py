"""Tests des quêtes du jour et de la semaine (SPEC §4.4, §11.9).

Deux propriétés décident si les quêtes servent à quelque chose :

* **elles paient en Éclats, jamais en XP.** L'XP mesure le travail réel ; une
  quête qui en donnerait ferait payer deux fois la même session, et le §4.4
  interdit toute récompense en XP sans travail réel ;
* **elles sont vraies.** Une quête bonus dont la condition est déjà impossible,
  ou dont l'avancement ne correspond pas aux faits, apprend à ignorer le
  panneau — et un panneau ignoré ne vaut pas mieux que pas de panneau.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import quests
from forge.models import (
    Commitment,
    DayWindow,
    Profile,
    Project,
    Quest,
    RoadmapStep,
    Session,
    Track,
)
from forge.rules import quests as regles

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


def contexte(**champs) -> regles.Contexte:
    base = dict(
        plancher_minutes=25,
        avant_vingt_heures=True,
        etape_presque_finie=False,
        projet_en_retard="",
        routines_du_jour=0,
        corps_actif=False,
        engagements_pris=3,
        jours_valides_semaine=0,
    )
    base.update(champs)
    return regles.Contexte(**base)


class TestLesRegles:
    def test_la_quete_plancher_ne_paie_rien(self):
        """Elle est déjà payée par la session elle-même."""
        plancher = regles.du_jour(contexte(), jour=LUNDI)[0]
        assert plancher.kind == regles.PLANCHER and plancher.reward_shards == 0

    def test_la_quete_plancher_annonce_le_plancher_du_rang(self):
        plancher = regles.du_jour(contexte(plancher_minutes=35), jour=LUNDI)[0]
        assert "35 minutes" in plancher.label

    def test_la_bonus_ne_propose_que_des_conditions_vraies(self):
        """Proposer « termine une étape » sans étape entamée est décoratif."""
        quetes = regles.du_jour(
            contexte(avant_vingt_heures=False, etape_presque_finie=False), jour=LUNDI
        )
        assert len(quetes) == 1, "aucune candidate vraie, donc pas de quête bonus"

    def test_la_bonus_est_figee_par_la_date(self):
        """Rafraîchir l'accueil ne doit pas rebattre les cartes."""
        ctx = contexte(etape_presque_finie=True, projet_en_retard="Bestiaire", corps_actif=True)
        premier = regles.du_jour(ctx, jour=LUNDI)[1]
        second = regles.du_jour(ctx, jour=LUNDI)[1]
        assert premier.code == second.code

    def test_elle_change_d_un_jour_a_l_autre(self):
        ctx = contexte(etape_presque_finie=True, projet_en_retard="Bestiaire", corps_actif=True)
        codes = {regles.du_jour(ctx, jour=LUNDI + timedelta(days=i))[1].code for i in range(4)}
        assert len(codes) > 1

    def test_la_quete_hebdo_se_cale_sur_le_contrat(self):
        """Deux objectifs concurrents, et c'est le contrat qui perdrait."""
        hebdo = regles.de_la_semaine(contexte(engagements_pris=4), jour=LUNDI)
        assert hebdo.target == 4 and "engagements" in hebdo.label

    def test_sans_engagement_elle_demande_cinq_journees(self):
        hebdo = regles.de_la_semaine(contexte(engagements_pris=0), jour=LUNDI)
        assert hebdo.target == 5


@pytest.mark.django_db
class TestLePanneau:
    @pytest.fixture
    def user(self):
        User = get_user_model()
        user = User.objects.create_user(username="test", password="test")
        profile = Profile.objects.create(user=user)
        for weekday in range(7):
            DayWindow.objects.create(profile=profile, weekday=weekday)
        atelier = Track.objects.create(user=user, kind=Track.ATELIER)
        projet = Project.objects.create(
            user=user, track=atelier, name="Bestiaire", slot=1, weekly_commitment=3
        )
        RoadmapStep.objects.create(
            project=projet, order=0, label="Écran de fiche", state=RoadmapStep.DOING
        )
        return user

    def travailler(self, user, *, heure: int = 19, minutes: int = 25):
        Session.objects.create(
            user=user,
            project=Project.objects.get(user=user),
            coach_day=LUNDI,
            started_at=datetime(2026, 3, 2, heure, tzinfo=PARIS),
            actual_minutes=minutes,
            status=Session.DONE,
        )

    def test_les_quetes_se_posent_une_seule_fois(self, user):
        """Le lundi, la quête hebdo porte la même date : trois lignes, pas six."""
        quests.panneau(user, today=LUNDI)
        apres_un = Quest.objects.filter(user=user).count()
        quests.panneau(user, today=LUNDI)

        assert Quest.objects.filter(user=user).count() == apres_un
        assert Quest.objects.filter(user=user).exclude(kind=Quest.HEBDO).count() <= 2

    def test_l_avancement_se_lit_dans_les_faits(self, user):
        avant = quests.panneau(user, today=LUNDI)["quetes"][0]
        assert avant["progress"] == 0

        self.travailler(user)
        apres = quests.panneau(user, today=LUNDI)["quetes"][0]
        assert apres["progress"] == 1 and apres["done"]

    def test_la_bonus_avant_20h_compte_l_heure_reelle(self, user):
        quests.panneau(user, today=LUNDI)
        self.travailler(user, heure=21)

        panneau = quests.panneau(user, today=LUNDI)
        bonus = [q for q in panneau["quetes"] if q["kind"] == Quest.BONUS]
        if bonus and "avant 20h" in bonus[0]["label"]:
            assert not bonus[0]["done"], "21h n'est pas avant 20h"

    def test_les_eclats_sont_credites_une_seule_fois(self, user):
        Quest.objects.create(
            user=user,
            kind=Quest.BONUS,
            date=LUNDI,
            label="Une session sur Bestiaire",
            target=1,
            reward_xp=regles.ECLATS_BONUS,
        )
        self.travailler(user)

        quests.panneau(user, today=LUNDI)
        premier = Profile.objects.get(user=user).shards
        quests.panneau(user, today=LUNDI)

        assert premier == regles.ECLATS_BONUS
        assert Profile.objects.get(user=user).shards == premier

    def test_aucune_quete_ne_donne_d_xp(self, user):
        """Le §4.4 : l'XP mesure le travail réel, et rien d'autre n'en produit."""
        self.travailler(user)
        quests.panneau(user, today=LUNDI)
        assert Session.objects.get(user=user).xp_awarded == 0, "aucune XP posée par une quête"

    def test_la_quete_hebdo_suit_les_engagements(self, user):
        Commitment.objects.create(
            project=Project.objects.get(user=user),
            week_start=LUNDI,
            planned_sessions=3,
            done_sessions=2,
        )
        panneau = quests.panneau(user, today=LUNDI)
        hebdo = next(q for q in panneau["quetes"] if q["kind"] == Quest.HEBDO)
        assert hebdo["progress"] == 2 and hebdo["target"] == 3

    def test_le_panneau_est_ordonne(self, user):
        ordre = [q["kind"] for q in quests.panneau(user, today=LUNDI)["quetes"]]
        assert ordre[0] == Quest.PLANCHER
        assert ordre[-1] == Quest.HEBDO
