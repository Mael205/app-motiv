"""Tests du bilan quotidien (SPEC §13.1).

Ce qui compte ici n'est pas le calcul — c'est le **ton**. Un bilan lu tous les
matins est l'endroit où le jugement revient le plus facilement, et le §17
l'interdit. Trois lignes de commentaire sur une mauvaise soirée, chaque matin, et
l'app se ferme pour de bon.

D'où les deux propriétés vérifiées : la phrase ne contient que des chiffres, et
le bilan se tait les jours où il n'aurait rien à dire.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import daily as daily_service
from forge import triggers
from forge.models import DayWindow, NotificationLog, Profile, Project, Session, Signal, Track
from forge.rules import daily

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)

# Les mots qui n'ont rien à faire dans un constat : ils jugent au lieu de dire.
JUGEMENTS = ("seulement", "déjà", "encore", "faudrait", "devrais", "bravo", "!")


class TestLaPhrase:
    def test_elle_dit_des_chiffres_et_rien_d_autre(self):
        bilan = daily.composer(
            disponibles=185, travaillees=50, signaux={"scroll_passif": 80}
        )
        assert bilan.phrase == "3h05 disponibles, 50 min travaillées, 1h20 de scroll."

    def test_elle_ne_juge_jamais(self):
        for travaillees in (0, 10, 50, 300):
            bilan = daily.composer(
                disponibles=185,
                travaillees=travaillees,
                signaux={"scroll_passif": 200},
                creneau_prevu=True,
            )
            bas = bilan.phrase.lower()
            for mot in JUGEMENTS:
                assert mot not in bas, f"« {mot} » juge la journée : {bilan.phrase}"

    def test_le_creneau_manque_est_constate_sans_commentaire(self):
        bilan = daily.composer(
            disponibles=185, travaillees=0, signaux={}, creneau_prevu=True, creneau_tenu=False
        )
        assert bilan.phrase.endswith("Créneau prévu, pas tenu.")

    def test_le_scroll_sous_le_seuil_n_est_pas_mentionne(self):
        """Trois minutes de mesure sont du bruit, pas un fait."""
        bilan = daily.composer(disponibles=185, travaillees=50, signaux={"scroll_passif": 3})
        assert "scroll" not in bilan.phrase


class TestLaBarre:
    def test_la_part_travaillee(self):
        bilan = daily.composer(disponibles=200, travaillees=50, signaux={})
        assert bilan.part_travaillee == 0.25

    def test_elle_ne_depasse_jamais_un(self):
        """Une soirée qui déborde la fenêtre ne fait pas une barre à 130 %."""
        bilan = daily.composer(disponibles=100, travaillees=180, signaux={})
        assert bilan.part_travaillee == 1.0

    def test_une_fenetre_vide_ne_divise_pas_par_zero(self):
        assert daily.composer(disponibles=0, travaillees=0, signaux={}).part_travaillee == 0.0


class TestRepartition:
    def test_le_travail_vient_avant_le_reste(self):
        bilan = daily.composer(
            disponibles=200,
            travaillees=50,
            signaux={"scroll_passif": 90, "travail_projet": 50, "jeu": 40},
        )
        assert [libelle for libelle, _ in bilan.repartition] == [
            "Travail projet",
            "Scroll passif",
            "Jeux",
        ]

    def test_les_categories_negligeables_disparaissent(self):
        bilan = daily.composer(
            disponibles=200, travaillees=50, signaux={"travail_projet": 50, "jeu": 2}
        )
        assert all(libelle != "Jeux" for libelle, _ in bilan.repartition)


@pytest.mark.django_db
class TestEnBaseEtDeclencheur:
    @pytest.fixture
    def profile(self):
        User = get_user_model()
        user = User.objects.create_user(username="test", password="test")
        profile = Profile.objects.create(user=user)
        for weekday in range(7):
            DayWindow.objects.create(profile=profile, weekday=weekday)
        atelier = Track.objects.create(user=user, kind=Track.ATELIER)
        Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
        return profile

    def test_lit_la_fenetre_les_sessions_et_les_sondes(self, profile):
        projet = Project.objects.get(user=profile.user)
        Session.objects.create(
            user=profile.user,
            project=projet,
            coach_day=LUNDI,
            started_at=datetime(2026, 3, 2, 19, tzinfo=PARIS),
            actual_minutes=50,
            status=Session.DONE,
        )
        Signal.objects.create(
            user=profile.user, source="agent", category="scroll_passif", minutes=80, day=LUNDI
        )

        bilan = daily_service.du_jour(profile.user, jour=LUNDI)
        assert bilan.disponibles == 300, "fenêtre 18h–23h"
        assert bilan.travaillees == 50
        assert "1h20 de scroll" in bilan.phrase

    def test_le_declencheur_pousse_apres_la_bascule(self, profile):
        projet = Project.objects.get(user=profile.user)
        Session.objects.create(
            user=profile.user,
            project=projet,
            coach_day=LUNDI,
            started_at=datetime(2026, 3, 2, 19, tzinfo=PARIS),
            actual_minutes=25,
            status=Session.DONE,
        )
        fired = triggers.check_daily_report(
            profile, datetime(2026, 3, 3, 4, 1, tzinfo=PARIS)
        )
        assert fired and fired[0]["day"] == LUNDI.isoformat()
        assert NotificationLog.objects.filter(kind=triggers.DAILY).exists()

    def test_il_se_tait_quand_il_n_a_rien_a_dire(self, profile):
        """Un compteur de zéros tous les matins devient un compteur de reproches."""
        assert triggers.check_daily_report(profile, datetime(2026, 3, 3, 4, 1, tzinfo=PARIS)) == []

    def test_il_ne_part_pas_a_n_importe_quelle_heure(self, profile):
        assert triggers.check_daily_report(profile, datetime(2026, 3, 3, 9, 0, tzinfo=PARIS)) == []
