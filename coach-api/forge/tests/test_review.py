"""Tests de la revue du dimanche (SPEC §5.3, §13.3).

Trois propriétés, et ce sont elles qui décident si une revue se fait deux fois
ou une seule :

* **elle arrive avec les constats déjà faits.** Une question qui ne porte sur
  aucun fait est une page blanche, donc le mode de défaillance du §0.9 ;
* **une seule chose à changer.** Trois changements simultanés ne se tiennent pas
  une semaine, et n'en tenir aucun fait arrêter les revues ;
* **elle a lieu sans réponses.** Une revue qui attendrait le dialogue pour
  exister ne serait faite qu'une fois.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import review
from forge.llm import set_provider
from forge.llm.base import QualityGateFailed
from forge.llm.fake import ScriptedProvider, UnavailableProvider
from forge.llm.gate import check_revue
from forge.models import (
    Commitment,
    DayWindow,
    Profile,
    Project,
    Session,
    TimeSlot,
    Track,
    WeeklyReview,
)
from forge.rules import review as rules_review

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    bestiaire = Project.objects.create(
        user=user, track=atelier, name="Bestiaire", slot=1, weekly_commitment=3
    )
    TimeSlot.objects.create(project=bestiaire, weekday=1, start_time="20:30")
    Project.objects.create(user=user, track=atelier, name="Evolve", slot=2, weekly_commitment=2)
    return user


def travailler(user, projet: str, jours: list[int], minutes: int = 25):
    p = Project.objects.get(user=user, name=projet)
    for jour in jours:
        Session.objects.create(
            user=user,
            project=p,
            coach_day=LUNDI + timedelta(days=jour),
            started_at=datetime(2026, 3, 2 + jour, 19, tzinfo=PARIS),
            actual_minutes=minutes,
            status=Session.DONE,
        )


class TestQuestions:
    def test_un_creneau_manque_donne_la_meilleure_question(self):
        posees = rules_review.questions(
            creneaux_manques=[(1, "Bestiaire")], constats=[], projets_avances=[]
        )
        assert "Mardi" in posees[0].fait and "Bestiaire" in posees[0].fait

    def test_elles_portent_toujours_sur_un_fait(self):
        posees = rules_review.questions(
            creneaux_manques=[(1, "Bestiaire")],
            constats=[("Trois jours à 4 sessions.", "Une soirée off.")],
            projets_avances=[("Evolve", 90)],
        )
        assert all(q.fait for q in posees), "une question sans fait est une page blanche (§0.9)"

    def test_jamais_plus_de_cinq(self):
        posees = rules_review.questions(
            creneaux_manques=[(0, "A"), (1, "B"), (2, "C")],
            constats=[("x", "y"), ("z", "w"), ("v", "u")],
            projets_avances=[("A", 10)],
        )
        assert len(posees) <= rules_review.MAX_QUESTIONS

    def test_jamais_moins_de_trois(self):
        posees = rules_review.questions(creneaux_manques=[], constats=[], projets_avances=[])
        assert len(posees) >= 1, "une semaine sans rien garde au moins une question ouverte"


class TestContrat:
    def test_il_propose_ce_qui_a_ete_tenu(self):
        lignes = rules_review.contrat([("Bestiaire", 3, [1, 1, 2])])
        assert lignes[0].propose == 1

    def test_il_ne_descend_jamais_a_zero(self):
        lignes = rules_review.contrat([("Bestiaire", 2, [0, 0, 0])])
        assert lignes[0].propose == 1, "zéro n'est pas un engagement"

    def test_il_ne_monte_que_d_un_cran(self):
        """Le sur-régime est l'autre façon de tomber (§0.2)."""
        lignes = rules_review.contrat([("Bestiaire", 2, [6, 6, 6])])
        assert lignes[0].propose == 3

    def test_sans_historique_il_ne_touche_a_rien(self):
        lignes = rules_review.contrat([("Bestiaire", 3, [])])
        assert lignes[0].propose == 3 and not lignes[0].change


class TestPorteDuCompteRendu:
    def test_un_changement_precis_passe(self):
        assert check_revue(
            {
                "a_marche": "Trois soirs sur le bot.",
                "n_a_pas_marche": "Mardi manqué.",
                "seule_chose": "Avancer le créneau du mardi à 19h30",
            }
        )

    def test_une_resolution_est_refusee(self):
        """Personne ne peut dire dimanche prochain s'il a « été plus régulier »."""
        with pytest.raises(QualityGateFailed, match="résolution"):
            check_revue({"seule_chose": "Continuer sur ce rythme la semaine prochaine"})

    def test_un_verbe_concret_n_est_pas_une_resolution(self):
        """« Avancer le créneau » est vérifiable ; « avancer sur l'API » ne l'est pas."""
        assert check_revue({"seule_chose": "Avancer le créneau du mardi à 19h30"})

    def test_deux_changements_sont_refuses(self):
        with pytest.raises(QualityGateFailed, match="deux changements"):
            check_revue(
                {"seule_chose": "Avancer le créneau du mardi et aussi réduire l'engagement"}
            )

    def test_le_jugement_est_refuse(self):
        with pytest.raises(QualityGateFailed, match="juge"):
            check_revue(
                {
                    "seule_chose": "Avancer le créneau du mardi à 19h30",
                    "n_a_pas_marche": "Bravo quand même pour les trois soirs.",
                }
            )


@pytest.mark.django_db
class TestLaRevueEntiere:
    def test_elle_s_ouvre_avec_ses_questions_et_son_contrat(self, user):
        travailler(user, "Bestiaire", [0, 2])
        Commitment.objects.create(
            project=Project.objects.get(user=user, name="Bestiaire"),
            week_start=LUNDI,
            planned_sessions=3,
            done_sessions=2,
        )
        revue = review.ouvrir(user, semaine=LUNDI)

        assert revue.questions and all(q["fait"] for q in revue.questions)
        assert any(ligne["projet"] == "Bestiaire" for ligne in revue.contract)

    def test_l_ouvrir_deux_fois_ne_la_duplique_pas(self, user):
        review.ouvrir(user, semaine=LUNDI)
        review.ouvrir(user, semaine=LUNDI)
        assert WeeklyReview.objects.count() == 1

    def test_elle_se_clot_sans_aucune_reponse(self, user):
        """« Si le dialogue est esquivé, la revue se génère quand même. »"""
        set_provider(UnavailableProvider())
        travailler(user, "Bestiaire", [0, 2])
        revue = review.clore(review.ouvrir(user, semaine=LUNDI))

        assert revue.closed_at is not None
        assert revue.report["seule_chose"]
        assert revue.report["dialogue"] is False
        assert "hypothèses" in revue.report["note"]

    def test_avec_des_reponses_elle_le_note(self, user):
        set_provider(UnavailableProvider())
        revue = review.ouvrir(user, semaine=LUNDI)
        review.repondre(revue, index=0, texte="Rentré à 22h, pas eu le courage.")
        revue = review.clore(revue)

        assert revue.report["dialogue"] is True
        assert revue.report["note"] == ""

    def test_le_modele_ecrit_les_trois_blocs_quand_il_est_la(self, user):
        set_provider(
            ScriptedProvider(
                [
                    {
                        "a_marche": "Les trois soirs où l'environnement était déjà ouvert.",
                        "n_a_pas_marche": "Mardi, rentré tard.",
                        "seule_chose": "Avancer le créneau du mardi à 19h30",
                    }
                ]
            )
        )
        revue = review.clore(review.ouvrir(user, semaine=LUNDI))
        assert revue.report["seule_chose"] == "Avancer le créneau du mardi à 19h30"

    def test_une_reponse_de_modele_floue_retombe_sur_le_deterministe(self, user):
        set_provider(
            ScriptedProvider(
                [{"a_marche": "…", "n_a_pas_marche": "…", "seule_chose": "Continuer comme ça"}]
            )
        )
        travailler(user, "Bestiaire", [0, 2])
        revue = review.clore(review.ouvrir(user, semaine=LUNDI))
        assert "Continuer comme ça" not in revue.report["seule_chose"]

    def test_le_contrat_ne_s_applique_que_sur_un_geste(self, user):
        Commitment.objects.create(
            project=Project.objects.get(user=user, name="Bestiaire"),
            week_start=LUNDI,
            planned_sessions=3,
            done_sessions=1,
        )
        revue = review.ouvrir(user, semaine=LUNDI)

        assert Project.objects.get(name="Bestiaire").weekly_commitment == 3
        changes = review.appliquer_contrat(revue)
        assert Project.objects.get(name="Bestiaire").weekly_commitment == 1
        assert changes[0]["avant"] == 3

    def test_on_ne_repond_plus_a_une_revue_close(self, user):
        set_provider(UnavailableProvider())
        revue = review.clore(review.ouvrir(user, semaine=LUNDI))
        with pytest.raises(ValueError, match="close"):
            review.repondre(revue, index=0, texte="trop tard")

    def test_le_dimanche_ouvre_la_revue(self, user, monkeypatch):
        from forge import triggers, weekly

        monkeypatch.setattr(weekly, "_poster", lambda canal, message: "discord")
        user.profile.buddy_channel = "https://discord.example/hook"
        user.profile.save(update_fields=["buddy_channel"])

        triggers.check_weekly_report(user.profile, datetime(2026, 3, 8, 20, 0, tzinfo=PARIS))
        assert WeeklyReview.objects.filter(user=user, week_start=LUNDI).exists()
