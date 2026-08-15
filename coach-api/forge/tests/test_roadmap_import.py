"""Tests de l'import d'un projet en markdown (SPEC §4.5).

Le markdown vient d'un chat, pas d'un formulaire : le parseur doit encaisser
les variantes d'écriture sans rien perdre, et **avertir** plutôt que refuser.
Le seul vrai refus est un markdown sans titre ou sans étape.
"""

import pytest

from forge.rules.roadmap_import import DOING, DONE, TODO, parse

EXEMPLE = """
# Outils Dofus 3 — rentabilité craft

Branche: backend
Couleur: #4FC4B4
Emblème: ◈
Engagement: 3

## Roadmap

- [x] Scraper les prix de l'HDV (2)
- [>] Modèle de coût de craft (2)
- [ ] API de comparaison des recettes (3)
- [ ] Interface de consultation (2)
"""


class TestLectureNominale:
    def test_titre_et_metadonnees(self):
        projet = parse(EXEMPLE)
        assert projet.name == "Outils Dofus 3 — rentabilité craft"
        assert projet.branch == "backend"
        assert projet.color == "#4FC4B4"
        assert projet.emblem == "◈"
        assert projet.weekly_commitment == 3

    def test_etapes_dans_l_ordre_avec_leurs_etats(self):
        etapes = parse(EXEMPLE).steps
        assert [e.state for e in etapes] == [DONE, DOING, TODO, TODO]
        assert etapes[0].label == "Scraper les prix de l'HDV"
        assert etapes[2].estimated_sessions == 3

    def test_projet_lisible_est_valide(self):
        projet = parse(EXEMPLE)
        assert projet.valid
        assert projet.open_steps == 3
        assert projet.warnings == []


class TestTolerance:
    """Le markdown est écrit par un modèle : les variantes ne doivent rien casser."""

    def test_puces_etoiles_et_plus(self):
        projet = parse("# P\n\n## Roadmap\n* [ ] Une étape\n+ [ ] Une autre\n")
        assert len(projet.steps) == 2

    def test_case_sans_marqueur_vaut_a_faire(self):
        projet = parse("# P\n\n## Roadmap\n- Une étape sans case\n")
        assert projet.steps[0].state == TODO

    def test_estimation_ecrite_en_toutes_lettres(self):
        projet = parse("# P\n\n## Roadmap\n- [ ] Une étape (2 sessions)\n")
        assert projet.steps[0].estimated_sessions == 2
        assert projet.steps[0].label == "Une étape"

    def test_estimation_absente_prend_le_defaut(self):
        projet = parse("# P\n\n## Roadmap\n- [ ] Une étape\n")
        assert projet.steps[0].estimated_sessions == 2

    def test_x_majuscule_et_accents_de_cle(self):
        projet = parse("# P\n\nEmbleme: ✦\n\n## Roadmap\n- [X] Faite\n")
        assert projet.steps[0].state == DONE
        assert projet.emblem == "✦"

    def test_sans_section_roadmap_les_puces_comptent_quand_meme(self):
        projet = parse("# P\n\n- [ ] Une étape\n")
        assert projet.valid and len(projet.steps) == 1

    def test_valeurs_par_defaut_si_aucune_metadonnee(self):
        projet = parse("# P\n\n- [ ] Une étape\n")
        assert projet.color == "#E8A33D"
        assert projet.weekly_commitment == 3
        assert projet.branch == ""


class TestAvertissements:
    def test_etape_trop_grosse_est_signalee_sans_bloquer(self):
        projet = parse("# P\n\n## Roadmap\n- [ ] Étape fleuve (6)\n")
        assert projet.valid, "une étape trop grosse n'empêche pas la création"
        assert any("à découper" in w for w in projet.warnings)

    def test_roadmap_entierement_faite_est_signalee(self):
        projet = parse("# P\n\n## Roadmap\n- [x] Faite (1)\n")
        assert any("à faire ou en cours" in w for w in projet.warnings)

    def test_plusieurs_etapes_en_cours_sont_signalees(self):
        projet = parse("# P\n\n## Roadmap\n- [>] Une (1)\n- [>] Deux (1)\n")
        assert any("en cours" in w for w in projet.warnings)

    def test_couleur_invalide_ignoree_et_signalee(self):
        projet = parse("# P\n\nCouleur: bleu\n\n## Roadmap\n- [ ] Une étape\n")
        assert projet.color == "#E8A33D"
        assert any("Couleur" in w for w in projet.warnings)

    def test_engagement_borne_a_sept(self):
        projet = parse("# P\n\nEngagement: 12\n\n## Roadmap\n- [ ] Une étape\n")
        assert projet.weekly_commitment == 7


class TestRefus:
    def test_sans_titre(self):
        projet = parse("## Roadmap\n- [ ] Une étape\n")
        assert not projet.valid
        assert any("titre" in w for w in projet.warnings)

    def test_sans_etape(self):
        projet = parse("# Un projet\n\nBranche: backend\n")
        assert not projet.valid
        assert any("étape" in w for w in projet.warnings)

    def test_markdown_vide(self):
        assert not parse("").valid


@pytest.mark.django_db
class TestCreation:
    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return user

    def test_projet_cree_avec_sa_roadmap(self, user):
        from forge import services
        from forge.models import RoadmapStep

        project = services.create_project_from_markdown(user, EXEMPLE)
        assert project.name == "Outils Dofus 3 — rentabilité craft"
        assert project.slot == 1
        assert project.steps.count() == 4
        assert project.steps.filter(state=RoadmapStep.DONE).first().done_at is not None

    def test_les_slots_se_remplissent_dans_l_ordre(self, user):
        from forge import services

        # Domaines variés : la règle de diversité du §4.3 est testée à part.
        domaines = ("code", "code", "corps")
        slots = [
            services.create_project_from_markdown(
                user, f"# P{i}\n\nDomaine: {d}\n\n- [ ] Étape\n"
            ).slot
            for i, d in enumerate(domaines)
        ]
        assert slots == [1, 2, 3]

    def test_le_quatrieme_projet_part_au_frigo(self, user):
        from forge import services
        from forge.models import Project

        for i, d in enumerate(("code", "code", "corps")):
            services.create_project_from_markdown(user, f"# P{i}\n\nDomaine: {d}\n\n- [ ] Étape\n")
        quatrieme = services.create_project_from_markdown(
            user, "# Quatrième\n\nDomaine: savoir\n\n- [ ] Étape\n"
        )
        assert quatrieme.status == Project.FRIDGE
        assert quatrieme.slot is None

    def test_markdown_illisible_refuse(self, user):
        from forge import services

        with pytest.raises(ValueError):
            services.create_project_from_markdown(user, "trois lignes de prose sans rien")

    def test_apercu_n_ecrit_rien(self, user):
        from forge import services
        from forge.models import Project

        apercu = services.preview_project(EXEMPLE)
        assert apercu["valid"] and len(apercu["steps"]) == 4
        assert not Project.objects.filter(user=user).exists()
