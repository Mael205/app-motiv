"""Tests du bilan de saison comparé (SPEC §13.4, §5.5, §17).

Trois propriétés, et ce sont celles qui font qu'un bilan de fin de mois sert à
quelque chose :

* **les régressions sont dites.** Un bilan qui n'annoncerait que les bonnes
  nouvelles serait une brochure, et personne ne se corrige sur une brochure ;
* **sans jugement.** « 4h de moins que la moyenne » est un fait, « tu as
  relâché » est un reproche, et le §17 interdit le second ;
* **la date de rupture est calculée.** C'est la seule chose que le système
  apporte à la question de fin de saison — la cause, il vient la chercher.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import season_flow, seasonreport, services
from forge.models import (
    Commitment,
    DayStatus,
    DayWindow,
    Profile,
    Project,
    RoadmapStep,
    Season,
    Session,
    Track,
    WeeklyReview,
)
from forge.rules import season_compare

PARIS = ZoneInfo("Europe/Paris")
DEBUT = date(2026, 3, 2)


def chiffres(**champs) -> season_compare.Chiffres:
    base = dict(
        index=1,
        nom="Saison",
        heures=10.0,
        sessions=20,
        jours_tenus=20,
        jours=28,
        etapes=4,
        engagements_tenus=3,
        engagements_pris=4,
        fuite_minutes=600,
    )
    base.update(champs)
    return season_compare.Chiffres(**base)


class TestComparaison:
    def test_la_premiere_saison_ne_se_compare_a_rien(self):
        assert season_compare.comparer(chiffres(), []) == []

    def test_une_regression_est_dite(self):
        evolutions = season_compare.comparer(chiffres(heures=6.0), [chiffres(heures=12.0)])
        heures = next(e for e in evolutions if e.mesure == "Heures")
        assert heures.sens == "regression"
        assert "en dessous de la moyenne" in heures.phrase

    def test_moins_de_scroll_est_une_progression(self):
        """Sans le sens par mesure, une baisse du scroll passerait pour un recul."""
        evolutions = season_compare.comparer(
            chiffres(fuite_minutes=200), [chiffres(fuite_minutes=800)]
        )
        scroll = next(e for e in evolutions if e.mesure == "Scroll passif")
        assert scroll.sens == "progression"

    def test_un_petit_ecart_reste_stable(self):
        evolutions = season_compare.comparer(chiffres(heures=10.4), [chiffres(heures=10.0)])
        assert next(e for e in evolutions if e.mesure == "Heures").sens == "stable"

    def test_les_regressions_sont_annoncees_en_premier(self):
        evolutions = season_compare.comparer(
            chiffres(heures=4.0, sessions=40), [chiffres(heures=12.0, sessions=20)]
        )
        assert evolutions[0].sens == "regression"

    def test_aucun_jugement_dans_les_phrases(self):
        evolutions = season_compare.comparer(chiffres(heures=2.0, sessions=2), [chiffres()])
        for evolution in evolutions:
            bas = evolution.phrase.lower()
            for mot in ("relâché", "mauvais", "seulement", "hélas", "faible", "bravo"):
                assert mot not in bas

    def test_la_moyenne_porte_sur_toutes_les_saisons(self):
        """Comparer à la seule précédente ferait passer une oscillation pour une tendance."""
        evolutions = season_compare.comparer(
            chiffres(heures=10.0), [chiffres(heures=4.0), chiffres(heures=16.0)]
        )
        assert next(e for e in evolutions if e.mesure == "Heures").sens == "stable"


class TestRupture:
    def test_elle_trouve_le_debut_de_la_plus_longue_serie(self):
        jours = [
            (DEBUT, True),
            (DEBUT + timedelta(days=1), False),
            (DEBUT + timedelta(days=2), True),
            (DEBUT + timedelta(days=3), False),
            (DEBUT + timedelta(days=4), False),
            (DEBUT + timedelta(days=5), False),
        ]
        jour, longueur = season_compare.rupture(jours)
        assert jour == DEBUT + timedelta(days=3) and longueur == 3

    def test_un_jour_isole_n_est_pas_une_rupture(self):
        """Un jour raté est une soirée, pas une cassure."""
        jours = [(DEBUT, True), (DEBUT + timedelta(days=1), False), (DEBUT + timedelta(days=2), True)]
        assert season_compare.rupture(jours) is None

    def test_la_question_donne_la_date_et_demande_la_cause(self):
        texte = season_compare.question((date(2026, 3, 12), 4))
        assert "12/03" in texte and "Qu'est-ce qui s'est passé" in texte

    def test_sans_rupture_la_question_change_de_sens(self):
        assert "tenu" in season_compare.question(None)


class TestCauses:
    def test_elles_viennent_des_revues_du_dimanche(self):
        trouvees = season_compare.causes(
            [
                {"seule_chose": "Avancer le créneau du mardi à 19h30"},
                {"seule_chose": "Découper l'étape du parseur"},
            ]
        )
        assert trouvees == ["Avancer le créneau du mardi à 19h30", "Découper l'étape du parseur"]

    def test_la_meme_cause_trois_fois_n_en_fait_qu_une(self):
        trouvees = season_compare.causes([{"seule_chose": "Avancer le créneau"}] * 3)
        assert trouvees == ["Avancer le créneau"]

    def test_jamais_plus_de_trois(self):
        trouvees = season_compare.causes(
            [{"seule_chose": f"Cause {i}"} for i in range(8)]
        )
        assert len(trouvees) == season_compare.MAX_CAUSES


@pytest.mark.django_db
class TestBilanComplet:
    @pytest.fixture
    def user(self):
        User = get_user_model()
        user = User.objects.create_user(username="test", password="test")
        profile = Profile.objects.create(user=user)
        for weekday in range(7):
            DayWindow.objects.create(profile=profile, weekday=weekday)
        atelier = Track.objects.create(user=user, kind=Track.ATELIER)
        Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
        services.open_season(user, starts_on=DEBUT, stake=100)
        return user

    def test_il_arrive_dans_le_bilan_de_cloture(self, user):
        saison = Season.objects.get(user=user)
        bilan = season_flow._bilan(user, saison, today=saison.ends_on, deja=False)
        assert "comparaison" in bilan and bilan["comparaison"]["premiere"] is True

    def test_il_calcule_la_date_de_rupture(self, user):
        saison = Season.objects.get(user=user)
        atelier = Track.objects.get(user=user)
        for jour in range(6):
            DayStatus.objects.create(
                user=user,
                track=atelier,
                date=saison.starts_on + timedelta(days=jour),
                state=DayStatus.VALIDEE if jour < 3 else DayStatus.RATEE,
            )

        rapport = seasonreport.comparaison(user, saison)
        assert rapport["rupture"]["jour"] == (saison.starts_on + timedelta(days=3)).isoformat()

    def test_un_jour_neutre_ne_casse_rien(self, user):
        """Le §4.2 : un jour off déclaré est un état, pas un manquement."""
        saison = Season.objects.get(user=user)
        atelier = Track.objects.get(user=user)
        for jour in range(28):
            DayStatus.objects.create(
                user=user,
                track=atelier,
                date=saison.starts_on + timedelta(days=jour),
                state=DayStatus.NEUTRE if jour in (5, 6, 7) else DayStatus.VALIDEE,
            )
        assert seasonreport.comparaison(user, saison)["rupture"] is None

    def test_il_reprend_les_causes_des_revues_de_la_saison(self, user):
        saison = Season.objects.get(user=user)
        WeeklyReview.objects.create(
            user=user,
            week_start=saison.starts_on,
            report={"seule_chose": "Avancer le créneau du mardi à 19h30"},
        )
        rapport = seasonreport.comparaison(user, saison)
        assert rapport["causes"] == ["Avancer le créneau du mardi à 19h30"]

    def test_il_dit_la_part_passee_sur_le_coach(self, user):
        """§11.6 : information, jamais sanction tant que le projet n'est pas fini."""
        saison = Season.objects.get(user=user)
        atelier = Track.objects.get(user=user)
        coach = Project.objects.create(
            user=user, track=atelier, name="Le coach", is_coach_project=True
        )
        autre = Project.objects.get(name="Bestiaire")
        for projet, minutes in ((coach, 60), (autre, 180)):
            Session.objects.create(
                user=user,
                project=projet,
                coach_day=saison.starts_on,
                started_at=datetime(2026, 3, 2, 19, tzinfo=PARIS),
                actual_minutes=minutes,
                status=Session.DONE,
            )
        assert seasonreport.comparaison(user, saison)["part_du_coach"] == 0.25
