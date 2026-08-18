"""Le contrat de saison, la trace longue, et « il y a quatre semaines ».

Trois ajouts de la section « Revenir » du 17 août 2026. Ils n'ont rien en
commun sur le plan technique et tout en commun sur le fond : chacun rend
visible quelque chose que le produit savait déjà mais ne montrait jamais.

Ce qui se teste :

* le contrat **ne bouge plus** une fois signé, sinon la clôture se compare à
  une cible déplacée en route ;
* la trace ne contient **aucun compteur qui puisse baisser** — un seul suffirait
  à annuler un écran qu'on ouvre en ayant déjà perdu quelque chose ;
* le rappel sort la note telle quelle, **sans commentaire**.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import review, season_flow, services, trace
from forge.models import (
    DayWindow,
    JournalEntry,
    Profile,
    Project,
    Season,
    Session,
    Track,
)
from forge.rules import contract as regles

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


class TestLesTermes:
    def test_zero_est_refuse(self):
        verdict = regles.verifier(0)
        assert not verdict.ok and "n'est pas un engagement" in verdict.raison

    def test_le_sur_regime_signe_d_avance_est_refuse(self):
        verdict = regles.verifier(regles.MAXIMUM + 1)
        assert not verdict.ok and "plafond de régime" in verdict.raison

    def test_les_termes_sont_ecrits_en_toutes_lettres(self):
        """Un nombre dans un champ ne se pèse pas ; un total sur la saison, si."""
        contrat = regles.Contrat(sessions_par_semaine=3, projets=("Bestiaire",), semaines=4)
        texte = " ".join(contrat.lignes)
        assert contrat.total == 12
        assert "12 sessions au total" in texte and "Bestiaire" in texte

    def test_le_bilan_ne_juge_pas(self):
        texte = regles.bilan(signe=12, fait=4)
        assert "Écart : 8" in texte
        for mot in ("seulement", "à peine", "faible", "relâché", "déjà"):
            assert mot not in texte.lower()


@pytest.mark.django_db
class TestLeContratSigne:
    def test_il_se_signe_a_l_ouverture(self, user):
        saison = services.open_season(
            user, starts_on=LUNDI, stake=0, contract_sessions_per_week=3
        )
        assert saison.signed and saison.contract_sessions_per_week == 3
        assert "Bestiaire" in saison.contract_projects

    def test_une_saison_sans_contrat_s_ouvre_quand_meme(self, user):
        """Refuser d'ouvrir ferait du rituel un formulaire."""
        saison = services.open_season(user, starts_on=LUNDI, stake=0)
        assert not saison.signed
        assert services.season_contract(user, saison) is None

    def test_il_ne_bouge_pas_quand_l_engagement_baisse(self, user):
        saison = services.open_season(
            user, starts_on=LUNDI, stake=0, contract_sessions_per_week=3
        )
        projet = Project.objects.get(user=user)
        projet.weekly_commitment = 1
        projet.save(update_fields=["weekly_commitment"])

        saison.refresh_from_db()
        assert saison.contract_sessions_per_week == 3

    def test_l_avancement_se_recalcule_depuis_les_faits(self, user):
        saison = services.open_season(
            user, starts_on=LUNDI, stake=0, contract_sessions_per_week=3
        )
        for i in range(2):
            travailler(user, LUNDI + timedelta(days=i), saison=saison)

        etat = services.season_contract(user, saison)
        assert etat["total"] == 12 and etat["done"] == 2

    def test_il_dimensionne_le_boss_de_la_premiere_saison(self, user):
        """Sans score précédent, la seule estimation honnête est celle qu'on
        vient d'annoncer soi-même."""
        petite = services.open_season(user, starts_on=LUNDI, stake=0, contract_sessions_per_week=2)
        Season.objects.all().delete()
        grande = services.open_season(user, starts_on=LUNDI, stake=0, contract_sessions_per_week=10)
        assert grande.boss.max_hp >= petite.boss.max_hp

    def test_il_est_relu_a_la_cloture(self, user):
        saison = services.open_season(
            user, starts_on=LUNDI, stake=0, contract_sessions_per_week=3
        )
        travailler(user, LUNDI, saison=saison)
        bilan = season_flow.close_season(user, saison, today=saison.ends_on + timedelta(days=1))
        assert bilan["contract"]["done"] == 1
        assert "Écart" in bilan["contract"]["line"]


@pytest.mark.django_db
class TestLaTraceLongue:
    def test_aucun_compteur_ne_redescend(self, user):
        """Un seul compteur qui baisserait annulerait l'écran entier."""
        travailler(user, LUNDI)
        avant = _valeurs(trace.longue(user))

        # Une semaine sans rien faire : le présent s'effondre, la trace non.
        apres = _valeurs(trace.longue(user))
        assert all(a <= b for a, b in zip(avant, apres))

        travailler(user, LUNDI + timedelta(days=30))
        encore = _valeurs(trace.longue(user))
        assert all(a <= b for a, b in zip(apres, encore))

    def test_elle_ne_porte_pas_le_streak_courant(self, user):
        """C'est exactement ce dont on vient de sortir."""
        travailler(user, LUNDI)
        labels = " ".join(c["label"] for c in trace.longue(user)["compteurs"]).lower()
        assert "meilleure série" in labels
        assert "série en cours" not in labels and "streak" not in labels

    def test_la_meilleure_serie_est_le_fait_brut(self, user):
        for i in range(3):
            travailler(user, LUNDI + timedelta(days=i))
        travailler(user, LUNDI + timedelta(days=10))
        assert _compteur(trace.longue(user), "Meilleure série") == 3

    def test_elle_date_le_premier_jour(self, user):
        travailler(user, LUNDI)
        assert trace.longue(user)["since"] == LUNDI.isoformat()

    def test_sans_rien_elle_ne_plante_pas(self, user):
        etat = trace.longue(user)
        assert etat["since"] is None
        assert all(c["value"] in (0, 0.0, 1) for c in etat["compteurs"])


@pytest.mark.django_db
class TestIlYAQuatreSemaines:
    def test_la_note_ressort_telle_quelle(self, user):
        session = travailler(user, LUNDI - timedelta(days=28))
        JournalEntry.objects.create(
            session=session, raw_note="Branché le raycast, ça marche à moitié.",
            next_action="finir la passe de collision",
        )
        rappel = review.il_y_a_quatre_semaines(user, semaine=LUNDI)
        assert rappel["note"] == "Branché le raycast, ça marche à moitié."
        assert rappel["project"] == "Bestiaire"

    def test_une_note_a_trois_jours_pres_fait_l_affaire(self, user):
        """Renoncer pour trois jours d'écart n'afficherait le bloc qu'une
        semaine sur deux."""
        session = travailler(user, LUNDI - timedelta(days=30))
        JournalEntry.objects.create(session=session, raw_note="Note du mois dernier.")
        assert review.il_y_a_quatre_semaines(user, semaine=LUNDI) is not None

    def test_rien_de_trop_vieux(self, user):
        session = travailler(user, LUNDI - timedelta(days=90))
        JournalEntry.objects.create(session=session, raw_note="Trop vieux.")
        assert review.il_y_a_quatre_semaines(user, semaine=LUNDI) is None

    def test_une_note_vide_ne_compte_pas(self, user):
        session = travailler(user, LUNDI - timedelta(days=28))
        JournalEntry.objects.create(session=session, raw_note="", next_action="x")
        assert review.il_y_a_quatre_semaines(user, semaine=LUNDI) is None


def travailler(user, jour: date, *, saison=None) -> Session:
    return Session.objects.create(
        user=user,
        project=Project.objects.filter(user=user).first(),
        season=saison,
        coach_day=jour,
        started_at=datetime(jour.year, jour.month, jour.day, 19, tzinfo=PARIS),
        actual_minutes=25,
        xp_awarded=40,
        status=Session.DONE,
    )


def _valeurs(etat: dict) -> list:
    return [c["value"] for c in etat["compteurs"]]


def _compteur(etat: dict, label: str):
    return next(c["value"] for c in etat["compteurs"] if c["label"] == label)


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1, branch="ue5")
    return user
