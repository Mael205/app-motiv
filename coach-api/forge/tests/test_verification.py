"""Tests du moyen de vérification déclaré par un projet (SPEC §6, §8.3).

Le cas qui compte n'est pas « git marche ». C'est celui-ci : **un projet qui
annonce une vérification sans en avoir les moyens croit être vérifié, ce qui
est pire que d'assumer une déclaration manuelle.** Il doit être signalé à la
création, pas découvert trois semaines plus tard.
"""

import pytest

from forge.rules.roadmap_import import parse
from forge.rules.verification import (
    FICHIERS,
    GIT,
    MANUELLE,
    PREMIER_PLAN,
    normalise,
    readiness,
)


class TestLecture:
    def test_les_quatre_moyens_sont_reconnus(self):
        assert normalise("git") == GIT
        assert normalise("fichiers") == FICHIERS
        assert normalise("premier_plan") == PREMIER_PLAN
        assert normalise("manuelle") == MANUELLE

    def test_les_variantes_d_ecriture_passent(self):
        assert normalise("Commits") == GIT
        assert normalise("premier plan") == PREMIER_PLAN
        assert normalise("ActivityWatch") == PREMIER_PLAN
        assert normalise("aucune") == MANUELLE

    def test_un_mot_inconnu_ne_devine_rien(self):
        assert normalise("magie") is None
        assert normalise("") is None


class TestOperationnel:
    def test_git_sans_depot_n_est_pas_pret(self):
        etat = readiness(GIT, has_path=False)
        assert not etat.ready
        assert "n'est pas vérifié" in etat.detail

    def test_git_avec_depot_est_pret(self):
        assert readiness(GIT, has_path=True).ready

    def test_fichiers_exige_aussi_un_chemin(self):
        assert not readiness(FICHIERS, has_path=False).ready

    def test_manuelle_est_toujours_prete(self):
        etat = readiness(MANUELLE, has_path=False)
        assert etat.ready and "assumé" in etat.detail

    def test_premier_plan_previent_de_sa_dependance(self):
        assert "ActivityWatch" in readiness(PREMIER_PLAN, has_path=False).detail


class TestDansLeMarkdown:
    def test_verification_et_depot_sont_lus(self):
        projet = parse(
            "# P\n\nVérification: git\nDépôt: C:/Dev/app-motiv\n\n- [ ] Une étape\n"
        )
        assert projet.verification == GIT
        assert projet.repo_path == "C:/Dev/app-motiv"
        assert projet.warnings == []

    def test_par_defaut_la_verification_est_manuelle(self):
        assert parse("# P\n\n- [ ] Une étape\n").verification == MANUELLE

    def test_git_annonce_sans_depot_est_signale(self):
        projet = parse("# P\n\nVérification: git\n\n- [ ] Une étape\n")
        assert projet.valid, "l'avertissement ne bloque pas la création"
        assert any("n'est pas vérifié" in w for w in projet.warnings)

    def test_moyen_inconnu_signale_et_ramene_a_manuelle(self):
        projet = parse("# P\n\nVérification: télépathie\n\n- [ ] Une étape\n")
        assert projet.verification == MANUELLE
        assert any("télépathie" in w for w in projet.warnings)


@pytest.mark.django_db
class TestCreation:
    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return user

    def test_le_depot_declare_est_cree_avec_le_projet(self, user):
        from forge import services
        from forge.models import ProjectRepo

        project = services.create_project_from_markdown(
            user, "# P\n\nVérification: git\nDépôt: C:/Dev/app-motiv\n\n- [ ] Une étape\n"
        )
        assert project.verification == "git"
        assert ProjectRepo.objects.filter(project=project, path="C:/Dev/app-motiv").exists()

    def test_la_verification_marche_des_la_premiere_session(self, user):
        """Le but du champ : plus aucun réglage entre la création et la preuve."""
        from forge import services

        project = services.create_project_from_markdown(
            user, "# P\n\nVérification: git\nDépôt: C:/Dev/app-motiv\n\n- [ ] Une étape\n"
        )
        session = services.start_session(user, project, planned_minutes=25)
        evidence = services.session_evidence(session)
        assert evidence["repos"] == ["C:/Dev/app-motiv"]

    def test_l_apercu_expose_le_moyen_avant_ecriture(self, user):
        from forge import services

        apercu = services.preview_project("# P\n\nVérification: git\nDépôt: /tmp/x\n\n- [ ] Une étape\n")
        assert apercu["verification"] == "git"
        assert apercu["verification_label"] == "Commits git"
        assert apercu["repo_path"] == "/tmp/x"
