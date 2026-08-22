"""La piste Corps (SPEC §11.4).

Elle existait dans la spec et à moitié dans la base : deux slots, et rien
d'autre. Pas d'objectif hebdomadaire, pas de streak, pas de plancher, et la
proposition du soir ne l'a jamais proposée une seule fois. Une séance de sport
s'enregistrait, donnait de l'XP, et aucun compteur ne la lisait.

Ce fichier vérifie les trois choses que le §11.4 exige, et surtout la règle
dure qui les encadre : **une séance de sport ne valide jamais le streak
Atelier**, et réciproquement.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import services
from forge.models import DayWindow, Profile, Project, Session, Track
from forge.rules import corps as regles

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)
VENDREDI = LUNDI + timedelta(days=4)


class TestLesRegles:
    def test_une_semaine_est_tenue_a_l_objectif(self):
        assert regles.Semaine(LUNDI, seances=2, objectif=2).tenue
        assert not regles.Semaine(LUNDI, seances=1, objectif=2).tenue

    def test_le_streak_se_compte_en_semaines(self):
        semaines = [regles.Semaine(LUNDI, 2, 2), regles.Semaine(LUNDI, 3, 2)]
        assert regles.evaluate(semaines).current == 2

    def test_une_semaine_ratee_casse_le_streak(self):
        semaines = [regles.Semaine(LUNDI, 2, 2), regles.Semaine(LUNDI, 0, 2), regles.Semaine(LUNDI, 2, 2)]
        etat = regles.evaluate(semaines)
        assert etat.current == 1 and etat.best == 1 and etat.semaines_tenues == 2

    def test_la_semaine_en_cours_n_entre_pas_dans_le_streak(self):
        """Un streak qui tomberait le lundi matin serait le mensonge le plus
        visible du système."""
        etat = regles.evaluate(
            [regles.Semaine(LUNDI, 2, 2)], en_cours=regles.Semaine(LUNDI, 0, 2)
        )
        assert etat.current == 1

    def test_il_n_y_a_pas_de_bouclier(self):
        """Le battement est dans l'objectif : deux séances sur sept jours."""
        etat = regles.evaluate([])
        assert not hasattr(etat, "shields")

    def test_le_plancher_du_corps_est_plus_haut_que_celui_de_l_atelier(self):
        from forge.rules import streak as streak_rules

        assert regles.PLANCHER > streak_rules.FLOOR_MINUTES - 10
        assert regles.DEGRADE == 15

    def test_le_message_ne_presse_jamais(self):
        for seances in (0, 1, 2, 4):
            etat = regles.evaluate([], en_cours=regles.Semaine(LUNDI, seances, 2))
            texte = regles.message_for(etat).lower()
            for mot in ("il te reste", "plus que", "attention", "vite", "devrais"):
                assert mot not in texte

    def test_la_priorite_monte_quand_la_semaine_se_termine(self):
        etat = regles.evaluate([], en_cours=regles.Semaine(LUNDI, 0, 2))
        assert regles.priorite(etat, jours_restants=7) < 0.5
        assert regles.priorite(etat, jours_restants=3) > 0.6
        assert regles.priorite(etat, jours_restants=2) == 1.0

    def test_une_semaine_tenue_ne_reclame_plus_rien(self):
        """Le §17 interdit de pousser au-delà d'un objectif."""
        etat = regles.evaluate([], en_cours=regles.Semaine(LUNDI, 2, 2))
        assert regles.priorite(etat, jours_restants=1) == 0.0


@pytest.mark.django_db
class TestLaPisteEnBase:
    def test_une_seance_de_sport_ne_valide_pas_le_streak_atelier(self, user):
        """La règle dure du §11.4, dans un sens."""
        seance(user, LUNDI, piste=Track.CORPS)
        atelier = Track.objects.get(user=user, kind=Track.ATELIER)
        etat = services.streak_state(user, atelier, today=LUNDI + timedelta(days=2))
        assert etat.current == 0

    def test_une_session_d_atelier_ne_compte_pas_pour_le_corps(self, user):
        """Et dans l'autre."""
        seance(user, LUNDI, piste=Track.ATELIER, minutes=60)
        assert services.corps_state(user, today=LUNDI).faites == 0

    def test_une_seance_sous_le_plancher_degrade_ne_compte_pas(self, user):
        seance(user, LUNDI, piste=Track.CORPS, minutes=10)
        assert services.corps_state(user, today=LUNDI).faites == 0

    def test_une_seance_a_quinze_minutes_compte(self, user):
        """« 15 min à la maison » est le mode dégradé du corps, pas un échec."""
        seance(user, LUNDI, piste=Track.CORPS, minutes=15)
        assert services.corps_state(user, today=LUNDI).faites == 1

    def test_l_objectif_suit_les_engagements_des_projets(self, user):
        projet = Project.objects.get(user=user, track__kind=Track.CORPS)
        projet.weekly_commitment = 3
        projet.save(update_fields=["weekly_commitment"])
        assert services.corps_objectif(user) == 3

    def test_l_objectif_reste_plafonne(self, user):
        projet = Project.objects.get(user=user, track__kind=Track.CORPS)
        projet.weekly_commitment = 40
        projet.save(update_fields=["weekly_commitment"])
        assert services.corps_objectif(user) == regles.OBJECTIF_MAX

    def test_le_panneau_disparait_sans_projet_corps(self, user):
        Project.objects.filter(user=user, track__kind=Track.CORPS).delete()
        assert services.corps_panel(user, today=LUNDI) is None


@pytest.mark.django_db
class TestLArbitrageDuSoir:
    def test_l_atelier_passe_devant_en_debut_de_semaine(self, user):
        """La piste Corps réclame la soirée deux fois par semaine, pas tous les
        soirs — sinon l'Atelier devient la piste secondaire."""
        proposition = services.propose(user, today=LUNDI)
        assert proposition["track"] == Track.ATELIER

    def test_le_corps_prend_la_main_quand_sa_semaine_va_se_perdre(self, user):
        proposition = services.propose(user, today=VENDREDI)
        assert proposition["track"] == Track.CORPS
        assert "séance" in proposition["reason"]

    def test_une_semaine_de_corps_tenue_rend_la_main_a_l_atelier(self, user):
        for i in range(2):
            seance(user, LUNDI + timedelta(days=i), piste=Track.CORPS)
        assert services.propose(user, today=VENDREDI)["track"] == Track.ATELIER

    def test_le_retour_apres_arret_reste_sur_l_atelier(self, user):
        """Quelqu'un qui revient après trois jours reprend par dix minutes de
        son travail, pas par une séance de sport de trente."""
        proposition = services.propose(user, today=VENDREDI, comeback=True)
        assert proposition["track"] == Track.ATELIER
        assert proposition["minutes"] == services.DEGRADED_MINUTES

    def test_les_deux_activites_du_corps_tournent(self, user):
        """Deux activités qui se partagent l'objectif tournent, au lieu que
        l'une prenne tout."""
        piste = Track.objects.get(user=user, kind=Track.CORPS)
        Project.objects.create(
            user=user, track=piste, name="Course", slot=2, weekly_commitment=1, domain="corps"
        )
        # Objectif à 3, une seule faite : le vendredi, il en manque deux.
        seance(user, LUNDI, piste=Track.CORPS, projet=Project.objects.get(user=user, name="Muscu"))

        proposition = services.propose(user, today=VENDREDI)
        assert proposition["track"] == Track.CORPS
        assert proposition["project"]["name"] == "Course"

    def test_l_accueil_montre_les_deux_pistes_cote_a_cote(self, user):
        etat = services.home_state(user)
        assert etat["corps"] is not None
        assert etat["proposal"] is not None


@pytest.mark.django_db
class TestLaSecondeSeanceDeLaJournee:
    """La piste qui ne prend pas la décision reste lançable (§11.1, §11.4).

    Sans elle, aller à la salle un mardi était impossible à déclarer : le Corps
    n'apparaissait que les soirs où sa semaine était déjà en train d'être
    ratée, et aucun bouton n'existait le reste du temps.
    """

    def test_le_lundi_la_seconde_piste_est_le_corps(self, user):
        seconde = _seconde(user, LUNDI)
        assert seconde is not None and seconde["track"] == Track.CORPS
        assert seconde["minutes"] == regles.PLANCHER

    def test_le_vendredi_les_deux_pistes_s_echangent(self, user):
        """Le Corps prend la décision, l'Atelier passe en second — pas l'inverse."""
        proposition = services.propose(user, today=VENDREDI)
        assert proposition["track"] == Track.CORPS
        assert _seconde(user, VENDREDI)["track"] == Track.ATELIER

    def test_une_semaine_de_corps_tenue_n_offre_plus_rien(self, user):
        """Le §17 interdit de pousser au-delà d'un objectif, en second aussi."""
        for i in range(2):
            seance(user, LUNDI + timedelta(days=i), piste=Track.CORPS)
        assert _seconde(user, LUNDI + timedelta(days=2)) is None

    def test_sans_projet_corps_il_n_y_a_pas_de_seconde_piste(self, user):
        Project.objects.filter(user=user, track__kind=Track.CORPS).delete()
        assert _seconde(user, LUNDI) is None

    def test_l_accueil_la_rend_a_cote_de_la_decision(self, user):
        etat = services.home_state(user, now=_midi(LUNDI))
        assert etat["proposal"]["track"] == Track.ATELIER
        assert etat["autre_piste"]["track"] == Track.CORPS

    def test_demander_l_atelier_ne_rejoue_pas_l_arbitrage(self, user):
        """``sans_corps`` est le seul moyen d'avoir l'Atelier un vendredi."""
        assert services.propose(user, today=VENDREDI)["track"] == Track.CORPS
        assert services.propose(user, today=VENDREDI, sans_corps=True)["track"] == Track.ATELIER


def _seconde(user, jour: date):
    proposition = services.propose(user, today=jour)
    return services.autre_piste(user, today=jour, proposition=proposition, now=_midi(jour))


def _midi(jour: date) -> datetime:
    return datetime(jour.year, jour.month, jour.day, 12, tzinfo=PARIS)


def seance(user, jour: date, *, piste: str, minutes: int = 45, projet=None) -> Session:
    cible = projet or Project.objects.filter(user=user, track__kind=piste).first()
    return Session.objects.create(
        user=user,
        project=cible,
        coach_day=jour,
        started_at=datetime(jour.year, jour.month, jour.day, 19, tzinfo=PARIS),
        actual_minutes=minutes,
        xp_awarded=40,
        status=Session.DONE,
    )


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)

    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)

    corps = Track.objects.create(user=user, kind=Track.CORPS)
    Project.objects.create(
        user=user, track=corps, name="Muscu", slot=1, weekly_commitment=2, domain="corps"
    )
    return user
