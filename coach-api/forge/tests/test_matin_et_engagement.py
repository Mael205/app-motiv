"""Le rappel du matin, et l'engagement qu'on peut baisser en cours de semaine.

Deux ajouts courts qui répondent à deux manques différents. Le rappel du matin
sort l'amorce du seul moment où elle était lue — 21h, quand il est trop tard
pour y penser. L'engagement asymétrique répare une rigidité qui coûtait des
semaines ratées pour rien : subir une semaine qu'on sait intenable, c'est la
rater, et rater un engagement coûte le rang.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import triggers
from forge.models import (
    DayWindow,
    JournalEntry,
    NotificationLog,
    Profile,
    Project,
    RoadmapStep,
    Session,
    Track,
)
from forge.rules import slots as slot_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)
DIMANCHE = date(2026, 3, 8)


@pytest.fixture
def profile(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    projet = Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1)
    RoadmapStep.objects.create(
        project=projet, order=0, label="Écran de fiche d'espèce", state=RoadmapStep.DOING
    )
    return profile


def hier_soir(profile, amorce: str):
    session = Session.objects.create(
        user=profile.user,
        project=Project.objects.get(user=profile.user),
        coach_day=LUNDI - timedelta(days=1),
        started_at=datetime(2026, 3, 1, 19, tzinfo=PARIS),
        actual_minutes=25,
        status=Session.DONE,
    )
    JournalEntry.objects.create(session=session, next_action=amorce)


class TestRappelDuMatin:
    def test_il_redit_l_amorce_laissee_hier(self, profile):
        hier_soir(profile, "Brancher le raycast du mur de gauche")

        fired = triggers.check_morning(profile, datetime(2026, 3, 2, 8, 1, tzinfo=PARIS))
        log = NotificationLog.objects.get(user=profile.user, kind=triggers.MATIN)

        assert fired
        assert "Brancher le raycast du mur de gauche" in log.body

    def test_il_se_tait_a_une_autre_heure(self, profile):
        hier_soir(profile, "Brancher le raycast")
        assert triggers.check_morning(profile, datetime(2026, 3, 2, 12, 0, tzinfo=PARIS)) == []

    def test_il_se_desactive(self, profile):
        profile.morning_hour = None
        profile.save(update_fields=["morning_hour"])
        hier_soir(profile, "Brancher le raycast")
        assert triggers.check_morning(profile, datetime(2026, 3, 2, 8, 1, tzinfo=PARIS)) == []

    def test_il_ne_dit_pas_bonne_journee_quand_il_n_a_rien(self, profile):
        """Sans rien de précis, le silence : le bruit apprend à ignorer le reste."""
        Project.objects.filter(user=profile.user).update(status=Project.FRIDGE)
        assert triggers.check_morning(profile, datetime(2026, 3, 2, 8, 1, tzinfo=PARIS)) == []

    def test_une_seule_fois_par_jour(self, profile):
        hier_soir(profile, "Brancher le raycast")
        assert triggers.check_morning(profile, datetime(2026, 3, 2, 8, 1, tzinfo=PARIS))
        assert triggers.check_morning(profile, datetime(2026, 3, 2, 8, 3, tzinfo=PARIS)) == []


class TestEngagement:
    def test_baisser_est_possible_en_pleine_semaine(self):
        ok, _ = slot_rules.peut_changer_engagement(actuel=3, vise=2, weekday=LUNDI.weekday())
        assert ok

    def test_monter_attend_le_dimanche(self):
        """Une hausse prise un soir d'élan est le sur-régime du §0.2."""
        ok, motif = slot_rules.peut_changer_engagement(actuel=2, vise=4, weekday=LUNDI.weekday())
        assert not ok and "dimanche" in motif

    def test_monter_le_dimanche_passe(self):
        ok, _ = slot_rules.peut_changer_engagement(actuel=2, vise=4, weekday=DIMANCHE.weekday())
        assert ok

    def test_zero_n_est_pas_un_engagement(self):
        ok, motif = slot_rules.peut_changer_engagement(actuel=3, vise=0, weekday=DIMANCHE.weekday())
        assert not ok and "zéro" in motif

    def test_le_maximum_tient(self):
        ok, _ = slot_rules.peut_changer_engagement(actuel=3, vise=30, weekday=DIMANCHE.weekday())
        assert not ok

    @pytest.mark.django_db
    def test_baisser_par_l_api(self, client, profile):
        client.force_login(profile.user)
        projet = Project.objects.get(user=profile.user)

        reponse = client.post(
            f"/api/projects/{projet.id}/commitment",
            {"weekly_commitment": 1},
            content_type="application/json",
        )
        assert reponse.status_code == 200
        projet.refresh_from_db()
        assert projet.weekly_commitment == 1
