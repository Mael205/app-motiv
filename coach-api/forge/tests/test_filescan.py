"""Tests de la preuve par fichiers modifiés (SPEC §6, §8.3).

Ce moyen existe pour les projets que git ne couvre pas : apprendre ne produit
pas de commit, un niveau Unreal se construit en modifiant des assets pendant des
heures, un entraînement RL écrit des checkpoints sans qu'on touche au dépôt.

Deux pièges sont surveillés ici :

* **l'élagage** — un scan qui descend dans ``node_modules`` fait attendre
  l'utilisateur pour compter des fichiers qui ne sont pas son travail ;
* **le compte réel** — l'échantillon affiché ne doit jamais être confondu avec
  le nombre de fichiers touchés, sinon la preuve sous-estime le travail.
"""

import os
from datetime import timedelta

import pytest
from django.utils import timezone

from forge.filescan import MAX_LISTED, files_modified_between


def touch(path, *, when=None):
    """Crée un fichier et lui donne une date de modification choisie."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    if when is not None:
        stamp = when.timestamp()
        os.utime(path, (stamp, stamp))


@pytest.fixture
def dossier(tmp_path):
    """Un dossier de projet réaliste : du travail, et beaucoup de bruit généré."""
    maintenant = timezone.now()
    touch(tmp_path / "notes" / "cyber.md", when=maintenant - timedelta(minutes=10))
    touch(tmp_path / "notes" / "nmap.md", when=maintenant - timedelta(minutes=5))
    touch(tmp_path / "vieux.md", when=maintenant - timedelta(days=30))
    # Bruit : ne doit jamais être parcouru.
    touch(tmp_path / "node_modules" / "paquet" / "index.js", when=maintenant)
    touch(tmp_path / ".git" / "objects" / "ab" / "cdef", when=maintenant)
    touch(tmp_path / "Intermediate" / "Build" / "truc.obj", when=maintenant)
    return tmp_path


class TestFenetre:
    def test_les_fichiers_de_la_fenetre_sont_remontes(self, dossier):
        activity = files_modified_between(
            str(dossier), timezone.now() - timedelta(hours=1), timezone.now() + timedelta(minutes=1)
        )
        assert activity.available
        assert activity.total == 2
        noms = {f.relative_path for f in activity.files}
        assert noms == {os.path.join("notes", "cyber.md"), os.path.join("notes", "nmap.md")}

    def test_un_fichier_ancien_ne_compte_pas(self, dossier):
        activity = files_modified_between(
            str(dossier), timezone.now() - timedelta(hours=1), timezone.now() + timedelta(minutes=1)
        )
        assert all("vieux" not in f.relative_path for f in activity.files)

    def test_hors_fenetre_rien_n_est_remonte(self, dossier):
        activity = files_modified_between(
            str(dossier), timezone.now() - timedelta(days=8), timezone.now() - timedelta(days=7)
        )
        assert activity.available and activity.total == 0

    def test_les_fichiers_sont_ordonnes_dans_le_temps(self, dossier):
        activity = files_modified_between(
            str(dossier), timezone.now() - timedelta(hours=1), timezone.now() + timedelta(minutes=1)
        )
        dates = [f.at for f in activity.files]
        assert dates == sorted(dates)


class TestElagage:
    """Les sorties de build ne sont pas du travail, et ne doivent pas être parcourues."""

    def test_node_modules_git_et_intermediate_sont_ignores(self, dossier):
        activity = files_modified_between(
            str(dossier), timezone.now() - timedelta(hours=1), timezone.now() + timedelta(minutes=1)
        )
        chemins = " ".join(f.relative_path for f in activity.files)
        for bruit in ("node_modules", ".git", "Intermediate"):
            assert bruit not in chemins

    def test_les_dossiers_elagues_ne_sont_meme_pas_comptes(self, dossier):
        """L'élagage se fait à la descente : ces fichiers ne sont jamais visités."""
        activity = files_modified_between(
            str(dossier), timezone.now() - timedelta(hours=1), timezone.now() + timedelta(minutes=1)
        )
        assert activity.scanned == 3, "seuls les 3 fichiers hors bruit doivent être visités"


class TestEchantillonEtCompte:
    def test_le_total_ne_se_confond_pas_avec_l_echantillon(self, tmp_path):
        maintenant = timezone.now()
        for i in range(MAX_LISTED + 15):
            touch(tmp_path / f"f{i}.txt", when=maintenant - timedelta(minutes=1))

        activity = files_modified_between(
            str(tmp_path), maintenant - timedelta(hours=1), maintenant + timedelta(minutes=1)
        )
        assert activity.total == MAX_LISTED + 15, "le compte doit être réel"
        assert len(activity.files) == MAX_LISTED, "l'échantillon reste lisible"


class TestAbsenceDePreuve:
    def test_dossier_inexistant(self, tmp_path):
        activity = files_modified_between(
            str(tmp_path / "nulle-part"), timezone.now() - timedelta(hours=1), timezone.now()
        )
        assert not activity.available
        assert "introuvable" in activity.detail

    def test_un_fichier_n_est_pas_un_dossier(self, tmp_path):
        cible = tmp_path / "fichier.txt"
        touch(cible)
        activity = files_modified_between(
            str(cible), timezone.now() - timedelta(hours=1), timezone.now()
        )
        assert not activity.available


@pytest.mark.django_db
class TestPreuveDeSession:
    @pytest.fixture
    def projet(self, dossier, django_user_model):
        from forge.models import Profile, Project, ProjectRepo, Track

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        track = Track.objects.create(user=user, kind=Track.ATELIER)
        project = Project.objects.create(
            user=user, track=track, name="Roadmap cyber", slot=1, verification="fichiers"
        )
        ProjectRepo.objects.create(project=project, path=str(dossier))
        return project

    def test_la_session_remonte_les_fichiers_touches(self, projet):
        from forge import services

        session = services.start_session(projet.user, projet, planned_minutes=25)
        session.started_at = timezone.now() - timedelta(hours=1)
        session.save(update_fields=["started_at"])

        evidence = services.session_evidence(session)
        assert evidence["verification"] == "fichiers"
        assert evidence["files_total"] == 2
        assert "cyber.md" in evidence["suggested_note"]
        assert evidence["commits"] == [], "on ne lit pas git sur un projet en « fichiers »"

    def test_un_projet_manuel_ne_cherche_aucune_trace(self, projet):
        from forge import services

        projet.verification = "manuelle"
        projet.save(update_fields=["verification"])
        session = services.start_session(projet.user, projet, planned_minutes=25)

        evidence = services.session_evidence(session)
        assert evidence["files_total"] == 0 and evidence["commits"] == []
        assert "déclaration manuelle" in evidence["detail"]

    def test_fichiers_sans_chemin_declare_le_dit(self, projet):
        from forge import services
        from forge.models import ProjectRepo

        ProjectRepo.objects.filter(project=projet).delete()
        session = services.start_session(projet.user, projet, planned_minutes=25)

        evidence = services.session_evidence(session)
        assert "n'est pas vérifié" in evidence["detail"]
