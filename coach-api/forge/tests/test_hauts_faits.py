"""Les hauts faits, et ce qui les rend atteignables (§12.3, §12.8).

Ce fichier existe à cause d'un défaut précis : quatre hauts faits étaient
déclarés, deux seulement étaient décernés, et les reliques du §12.8 en
réclamaient trois qui n'avaient aucun code pour les accorder. Quatre reliques
sur cinq étaient donc inatteignables — pas rares : impossibles.

Le premier test est celui qui compte. Les autres vérifient qu'un haut fait
récompense bien ce qu'il prétend récompenser, et surtout qu'aucun ne peut
tomber sans travail réel.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import achievements, services
from forge.models import (
    Achievement,
    DayOff,
    DayWindow,
    Hiatus,
    Profile,
    Project,
    RoadmapStep,
    Session,
    Signal,
    Track,
)
from forge.rules import achievements as regles
from forge.rules import relics as relic_rules
from forge.rules import signals as signal_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


class TestLeCatalogue:
    def test_chaque_relique_a_un_haut_fait_qui_existe(self):
        """Le défaut d'origine, transformé en garde."""
        for relique in relic_rules.CATALOGUE:
            assert relique.achievement in regles.PAR_CLE, (
                f"« {relique.label} » est inatteignable : son haut fait "
                f"« {relique.achievement} » n'existe pas."
            )

    def test_chaque_haut_fait_regarde_un_fait_mesure(self):
        for haut_fait in regles.CATALOGUE:
            assert haut_fait.fait in regles.FAITS, haut_fait.key

    def test_les_cles_sont_uniques(self):
        cles = [a.key for a in regles.CATALOGUE]
        assert len(set(cles)) == len(cles)

    def test_les_seuils_montent_dans_une_meme_famille(self):
        """Deux hauts faits sur le même fait doivent se franchir dans l'ordre."""
        par_fait: dict[str, list[int]] = {}
        for haut_fait in regles.CATALOGUE:
            par_fait.setdefault(haut_fait.fait, []).append(haut_fait.seuil)
        for fait, seuils in par_fait.items():
            assert len(set(seuils)) == len(seuils), fait

    def test_atteints_rend_tout_ce_qui_est_franchi(self):
        obtenus = {a.key for a in regles.atteints({"heures_totales": 600})}
        assert {"centurion", "quintal"} <= obtenus
        assert "mille" not in obtenus

    def test_le_prochain_est_trie_par_part_parcourue(self):
        """« 9 sur 10 » est plus proche que « 90 sur 1000 », alors que la
        distance brute dit l'inverse."""
        proches = regles.prochain(
            {"etapes_finies": 9, "heures_totales": 90}, acquis=set(), combien=2
        )
        assert proches[0]["part"] >= proches[1]["part"]


@pytest.mark.django_db
class TestCeQuiLesDeclenche:
    def test_la_premiere_session_donne_le_premier_sang(self, user):
        travailler(user, LUNDI)
        assert "premier_sang" in _cles(achievements.synchroniser(user))

    def test_synchroniser_est_idempotent(self, user):
        travailler(user, LUNDI)
        achievements.synchroniser(user)
        assert achievements.synchroniser(user) == []

    def test_un_haut_fait_ne_se_reprend_jamais(self, user):
        """Le §17 l'interdit, et c'est ce qui oblige à ne s'appuyer que sur des
        grandeurs qui ne redescendent pas."""
        travailler(user, LUNDI)
        achievements.synchroniser(user)
        Session.objects.filter(user=user).delete()

        achievements.synchroniser(user)
        assert Achievement.objects.filter(user=user, key="premier_sang").exists()

    def test_la_plus_longue_serie_est_le_fait_brut(self, user):
        for i in range(4):
            travailler(user, LUNDI + timedelta(days=i))
        travailler(user, LUNDI + timedelta(days=20))
        assert achievements.faits(user)["plus_longue_serie"] == 4

    def test_les_branches_de_la_semaine(self, user):
        atelier = Track.objects.get(user=user)
        for i, branche in enumerate(("ue5", "cyber", "backend")):
            projet = Project.objects.create(
                user=user, track=atelier, name=f"P{i}", branch=branche
            )
            travailler(user, LUNDI + timedelta(days=i), projet=projet)
        assert achievements.faits(user)["branches_dans_une_semaine"] == 3

    def test_un_projet_sans_etape_n_est_pas_termine(self, user):
        """Trois roadmaps vides donneraient « Maître d'œuvre »."""
        assert achievements.faits(user)["projets_termines"] == 0

    def test_un_projet_dont_toutes_les_etapes_sont_faites_compte(self, user):
        projet = Project.objects.get(user=user)
        for i in range(2):
            RoadmapStep.objects.create(
                project=projet, label=f"E{i}", order=i, state=RoadmapStep.DONE
            )
        assert achievements.faits(user)["projets_termines"] == 1

    def test_une_semaine_sans_sonde_n_est_pas_une_semaine_sans_scroll(self, user):
        """Sans cette garde, désinstaller l'agent décernerait « Ermite » (§11.10)."""
        assert achievements.faits(user)["semaines_sans_scroll"] == 0

    def test_une_semaine_observee_et_propre_compte(self, user):
        semaine = LUNDI - timedelta(days=14)
        for i in range(3):
            Signal.objects.create(
                user=user, day=semaine + timedelta(days=i),
                category="code", minutes=60, source=signal_rules.AGENT,
            )
        assert achievements.faits(user)["semaines_sans_scroll"] == 1

    def test_une_semaine_observee_avec_du_scroll_ne_compte_pas(self, user):
        semaine = LUNDI - timedelta(days=14)
        Signal.objects.create(
            user=user, day=semaine, category="code", minutes=60, source=signal_rules.AGENT
        )
        Signal.objects.create(
            user=user, day=semaine, category=signal_rules.SCROLL_PASSIF,
            minutes=30, source=signal_rules.AGENT,
        )
        assert achievements.faits(user)["semaines_sans_scroll"] == 0

    def test_sortir_de_veille_et_travailler_le_jour_meme(self, user):
        debut = LUNDI + timedelta(days=1)
        fin = debut + timedelta(days=5)
        Hiatus.objects.create(user=user, starts_on=debut, ends_on=fin)
        travailler(user, fin + timedelta(days=1))
        assert achievements.faits(user)["retours_de_veille"] == 1

    def test_les_jours_off_declares_se_comptent(self, user):
        for i in range(3):
            DayOff.objects.create(user=user, date=LUNDI + timedelta(days=i))
        assert achievements.faits(user)["jours_off_declares"] == 3

    def test_le_panneau_montre_l_acquis_et_les_prochains(self, user):
        travailler(user, LUNDI)
        achievements.synchroniser(user)
        panneau = achievements.panneau(user)

        assert panneau["total"] == len(regles.CATALOGUE)
        assert any(o["key"] == "premier_sang" for o in panneau["obtenus"])
        assert len(panneau["prochains"]) <= 3
        assert all(p["key"] != "premier_sang" for p in panneau["prochains"])


@pytest.mark.django_db
class TestLesBonusEnfinAppliques:
    """Trois mécaniques étaient calculées, affichées, et jamais reçues.

    Un bonus qu'on voit sans le recevoir est pire que pas de bonus : il fait
    douter de tout le reste.
    """

    def test_la_relique_donne_vraiment_un_bouclier(self, user):
        from forge.models import OwnedRelic

        avant = services.starting_shields(user, today=LUNDI)
        OwnedRelic.objects.create(user=user, key="coeur_increvable", equipped=True)
        assert services.starting_shields(user, today=LUNDI) == avant + 1

    def test_le_stock_reste_plafonne(self, user):
        from forge.models import OwnedRelic
        from forge.rules import streak as streak_rules

        for cle in ("coeur_increvable", "serment_tenu"):
            OwnedRelic.objects.create(user=user, key=cle, equipped=True)
        assert services.starting_shields(user, today=LUNDI) <= streak_rules.MAX_SHIELDS

    def test_la_relique_donne_vraiment_un_jour_off(self, user):
        from forge.models import OwnedRelic

        avant = services.days_off_allowed(user, today=LUNDI)
        OwnedRelic.objects.create(user=user, key="souffle_du_retour", equipped=True)
        assert services.days_off_allowed(user, today=LUNDI) == avant + 1

    def test_le_modificateur_remplace_au_lieu_de_s_ajouter(self, user):
        """« Discipline » donne trois boucliers *et* interdit les jours off :
        c'est un échange, pas un cumul."""
        from forge.models import OwnedRelic, Season

        OwnedRelic.objects.create(user=user, key="coeur_increvable", equipped=True)
        saison = Season.objects.filter(user=user).first()
        saison.modifier_key = "discipline"
        saison.save(update_fields=["modifier_key"])

        assert services.starting_shields(user, today=LUNDI, season=saison) == 3
        assert services.days_off_allowed(user, today=LUNDI, season=saison) == 0


def travailler(user, jour: date, *, projet=None) -> Session:
    return Session.objects.create(
        user=user,
        project=projet or Project.objects.filter(user=user).first(),
        coach_day=jour,
        started_at=datetime(jour.year, jour.month, jour.day, 19, tzinfo=PARIS),
        actual_minutes=25,
        xp_awarded=40,
        status=Session.DONE,
    )


def _cles(nouveaux: list[dict]) -> set[str]:
    return {n["key"] for n in nouveaux}


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1, branch="ue5")
    services.open_season(user, starts_on=LUNDI, stake=0)
    return user
