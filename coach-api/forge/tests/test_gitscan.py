"""Tests de la preuve de travail par git (SPEC §8.3, §6).

Ce qui a été commité pendant une session est la preuve la moins falsifiable qui
existe et ne coûte aucune saisie. Elle **n'invalide jamais** une session : un
dépôt absent est une absence de preuve, pas une faute.
"""

import subprocess
from datetime import timedelta

import pytest
from django.utils import timezone

from forge.gitscan import commits_between


def git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """Un vrai petit dépôt git, pas un simulacre."""
    path = tmp_path / "depot"
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    (path / "fichier.txt").write_text("un", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "Écrit la boucle de déplacement")
    return path


class TestLecture:
    def test_les_commits_de_la_fenetre_sont_remontes(self, repo):
        activity = commits_between(
            str(repo), timezone.now() - timedelta(hours=1), timezone.now() + timedelta(minutes=1)
        )
        assert activity.available
        assert activity.total == 1
        assert activity.commits[0].subject == "Écrit la boucle de déplacement"

    def test_hors_fenetre_rien_n_est_remonte(self, repo):
        activity = commits_between(
            str(repo), timezone.now() - timedelta(days=8), timezone.now() - timedelta(days=7)
        )
        assert activity.available and activity.total == 0

    def test_seul_le_sujet_est_lu_jamais_le_diff(self, repo):
        commit = commits_between(
            str(repo), timezone.now() - timedelta(hours=1), timezone.now() + timedelta(minutes=1)
        ).commits[0]
        champs = set(type(commit).__dataclass_fields__)
        assert "diff" not in champs and "patch" not in champs and "content" not in champs


class TestAbsenceDePreuve:
    """Un dépôt indisponible n'est jamais une erreur : c'est une absence de preuve."""

    def test_chemin_inexistant(self, tmp_path):
        activity = commits_between(
            str(tmp_path / "nulle-part"), timezone.now() - timedelta(hours=1), timezone.now()
        )
        assert not activity.available and activity.total == 0

    def test_dossier_sans_git(self, tmp_path):
        (tmp_path / "vide").mkdir()
        activity = commits_between(
            str(tmp_path / "vide"), timezone.now() - timedelta(hours=1), timezone.now()
        )
        assert not activity.available
        assert "dépôt git" in activity.detail


@pytest.mark.django_db
class TestPreuveDeSession:
    def test_la_session_recupere_ses_commits(self, repo, django_user_model):
        from forge import services
        from forge.models import Profile, Project, ProjectRepo, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        track = Track.objects.create(user=user, kind=Track.ATELIER)
        project = Project.objects.create(
            user=user, track=track, name="P", slot=1, verification="git"
        )
        ProjectRepo.objects.create(project=project, path=str(repo))

        session = services.start_session(user, project, planned_minutes=25)
        session.started_at = timezone.now() - timedelta(hours=1)
        session.save(update_fields=["started_at"])

        evidence = services.session_evidence(session)
        assert len(evidence["commits"]) == 1
        assert "boucle de déplacement" in evidence["suggested_note"]

    def test_un_depot_manquant_ne_casse_pas_la_session(self, django_user_model):
        from forge import services
        from forge.models import Profile, Project, ProjectRepo, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        track = Track.objects.create(user=user, kind=Track.ATELIER)
        project = Project.objects.create(
            user=user, track=track, name="P", slot=1, verification="git"
        )
        ProjectRepo.objects.create(project=project, path="C:/nulle-part-du-tout")

        session = services.start_session(user, project, planned_minutes=25)
        evidence = services.session_evidence(session)
        assert evidence["commits"] == []
        assert len(evidence["unavailable"]) == 1
