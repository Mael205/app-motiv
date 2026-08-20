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


class TestPlanDetaille:
    """Un plan de travail documenté, et pas seulement une liste de tâches (§4.5).

    Le modèle produisait des roadmaps maigres — un libellé, un nombre de
    sessions — parce que rien d'autre ne pouvait traverser le format pivot.
    Une étape qui dit « réviser le réseau » sans nommer sa ressource, son
    périmètre et son critère de sortie est une intention : le soir venu elle
    demande de décider quoi faire, ce que le §4.5 refuse.

    Ces tests gardent le transport, pas la qualité rédactionnelle — celle-là
    dépend du modèle. Mais sans le transport, aucune qualité ne survit.
    """

    RICHE = {
        "nom": "Carnet de labs offensifs",
        "domaine": "savoir",
        "verification": "git",
        "depot": "~/labs-cyber",
        "branche": "cyber",
        "engagement": 3,
        "objectif": "Compromettre une machine Easy inconnue en moins de 3 h sans aide.",
        "cadre": "Articles 323-1 et suivants : lab local ou autorisation écrite. Jamais depuis un réseau pro.",
        "parcours": [
            {
                "nom": "Bloc A — Fondamentaux",
                "resultat": "Ligne de commande et réseau acquis",
                "ressource": "OverTheWire Bandit",
                "url": "https://overthewire.org/wargames/bandit/",
                "charge": "25–40 h",
                "critere_sortie": "niveau 34 terminé, et tu expliques find et xargs sans notes",
            },
            {
                "nom": "Bloc B — Sécurité web",
                "resultat": "Les six familles de failles web",
                "ressource": "PortSwigger Web Security Academy",
                "url": "https://portswigger.net/web-security",
                "charge": "200–280 h",
                "critere_sortie": "100 % des labs Apprentice et Practitioner validés",
            },
        ],
        "etapes": [
            {
                "libelle": "Terminer les niveaux 0 à 10 de Bandit",
                "sessions": 3,
                "etat": "doing",
                "ressource": "OverTheWire Bandit",
                "url": "https://overthewire.org/wargames/bandit/",
                "perimetre": "niveaux 0 à 10 seulement, dans l'ordre",
                "charge": "6–8 h",
                "critere_sortie": "niveau 10 atteint sans avoir ouvert un writeup",
            },
            {"libelle": "Créer le dépôt ~/labs-cyber avec un writeup.md type", "sessions": 1, "etat": "todo"},
            {"libelle": "Terminer les niveaux 11 à 20 de Bandit", "sessions": 3, "etat": "todo"},
            {"libelle": "Écrire trois scripts bash utiles et les commiter", "sessions": 2, "etat": "todo"},
        ],
        "ecartees": [
            {"nom": "TryHackMe", "raison": "redondant avec HTB, et le tier gratuit est bridé"},
            {"nom": "Linux Journey", "raison": "redondant avec Bandit"},
        ],
    }

    def _aller_retour(self):
        from forge.rules.roadmap_import import render
        return parse(render(self.RICHE))

    def test_l_objectif_et_le_cadre_traversent(self):
        projet = self._aller_retour()
        assert projet.objective.startswith("Compromettre")
        assert "323-1" in projet.frame

    def test_une_metadonnee_ajoutee_n_ecrase_plus_la_branche(self):
        # Le parseur affectait à la branche toute clé qu'il ne traitait pas :
        # ajouter « Objectif » suffisait à la remplacer sans rien signaler.
        assert self._aller_retour().branch == "cyber"

    def test_le_parcours_porte_ressource_charge_et_critere(self):
        blocs = self._aller_retour().parcours
        assert [b.name for b in blocs] == ["Bloc A — Fondamentaux", "Bloc B — Sécurité web"]
        assert blocs[1].url == "https://portswigger.net/web-security"
        assert blocs[1].load == "200–280 h"
        assert "Practitioner" in blocs[1].exit_criterion

    def test_une_etape_porte_son_perimetre_et_sa_sortie(self):
        etape = self._aller_retour().steps[0]
        assert etape.resource == "OverTheWire Bandit"
        assert etape.scope == "niveaux 0 à 10 seulement, dans l'ordre"
        assert etape.load == "6–8 h"
        assert "sans avoir ouvert un writeup" in etape.exit_criterion

    def test_une_etape_nue_reste_valide(self):
        # Tout n'a pas de ressource : « appeler le plombier » n'en a pas.
        etape = self._aller_retour().steps[1]
        assert etape.label.startswith("Créer le dépôt")
        assert (etape.resource, etape.load, etape.scope) == ("", "", "")

    def test_les_ecartees_ne_deviennent_pas_des_etapes(self):
        # Avant le découpage en sections, toute puce du document devenait une
        # étape : deux ressources écartées auraient créé deux étapes fantômes.
        projet = self._aller_retour()
        assert len(projet.steps) == 4
        assert [(e.name, e.reason) for e in projet.ecartees] == [
            ("TryHackMe", "redondant avec HTB, et le tier gratuit est bridé"),
            ("Linux Journey", "redondant avec Bandit"),
        ]

    def test_l_aller_retour_est_stable(self):
        # Deux passages doivent donner le même document : c'est ce qui garantit
        # qu'aucun champ ne se perd en route.
        from forge.rules.roadmap_import import render
        premier = render(self.RICHE)
        assert render(self.RICHE) == premier

    def test_les_blocs_du_parcours_ne_comptent_pas_dans_les_sessions(self):
        # Le parcours est l'échelle des mois. S'il tombait dans les étapes, le
        # projet afficherait 200 h dans une case prévue pour 3 sessions.
        projet = self._aller_retour()
        assert all(s.estimated_sessions <= 3 for s in projet.steps)
        assert projet.open_steps == 4


class TestBranchesNonTechniques:
    """Cuisine, danse et cursus ont désormais leur branche (§12.9).

    L'arbre ne couvrait que du code et du corps, ce qui forçait un projet de
    cuisine à se déclarer « backend » pour exister — et faussait les heures
    cumulées, le palier et le titre qui en dérivent.
    """

    def test_les_neuf_branches_sont_completes(self):
        from forge.rules import skills

        for cle in skills.BRANCHES:
            assert cle in skills.BRANCH_LABELS
            assert cle in skills.BRANCH_COLORS
            assert len(skills.TITLES[cle]) == len(skills.TIER_HOURS)

    def test_une_branche_non_technique_donne_un_titre(self):
        from forge.rules import skills

        etat = skills.branch_state(skills.ARTISANAT, minutes=60 * 30)
        assert etat.label == "Artisanat & cuisine"
        assert etat.title == "Tourne-main"

    def test_un_projet_de_danse_se_lit_dans_le_markdown(self):
        projet = parse(
            "# Danse — enchaînements\n\nDomaine: creatif\nBranche: scene\n\n"
            "- [ ] Tenir l'enchaînement A sur 8 temps, filmé (2)\n"
        )
        assert projet.branch == "scene"
        assert projet.valid


@pytest.mark.django_db
class TestPlanDetaillePersiste:
    """Le plan détaillé doit survivre à l'écriture en base, pas seulement au parseur.

    C'est le défaut que ces tests gardent, et il avait déjà eu lieu : le
    parseur lisait l'objectif, le parcours, les écartées et les cinq attributs
    d'étape, et ``create_project_from_markdown`` ne recopiait que les six
    champs d'origine. L'entretien de projet du §4.5 faisait donc produire au
    modèle une information que l'écriture jetait **sans rien signaler** — le
    pire des deux modes de perte, parce qu'il ne laisse pas de trace.

    Un test d'aller-retour sur le markdown ne l'attrape pas : il s'arrête avant
    la base. Celui-ci commence là où l'autre finit.
    """

    @pytest.fixture
    def user(self, django_user_model):
        from forge.models import Profile

        user = django_user_model.objects.create_user(username="arthur", password="coach")
        Profile.objects.create(user=user)
        return user

    @pytest.fixture
    def projet(self, user):
        from forge import services
        from forge.rules.roadmap_import import render

        return services.create_project_from_markdown(user, render(TestPlanDetaille.RICHE))

    def test_l_objectif_et_le_cadre_sont_en_base(self, projet):
        assert projet.objective.startswith("Compromettre")
        assert "323-1" in projet.frame

    def test_les_attributs_d_etape_sont_en_base(self, projet):
        etape = projet.steps.first()
        assert etape.resource == "OverTheWire Bandit"
        assert etape.scope == "niveaux 0 à 10 seulement, dans l'ordre"
        assert etape.load == "6–8 h"
        assert "sans avoir ouvert un writeup" in etape.exit_criterion

    def test_le_parcours_est_en_base_dans_l_ordre(self, projet):
        blocs = list(projet.parcours.all())
        assert [b.name for b in blocs] == ["Bloc A — Fondamentaux", "Bloc B — Sécurité web"]
        assert blocs[1].load == "200–280 h"
        assert "Practitioner" in blocs[1].exit_criterion

    def test_les_ecartees_gardent_leur_raison(self, projet):
        assert [(e.name, e.reason) for e in projet.ecartees.all()] == [
            ("TryHackMe", "redondant avec HTB, et le tier gratuit est bridé"),
            ("Linux Journey", "redondant avec Bandit"),
        ]

    def test_un_projet_maigre_ne_fabrique_ni_bloc_ni_ecartee(self, user):
        # L'absence doit rester l'absence : un projet sans parcours n'a pas de
        # bloc vide, sans quoi l'écran afficherait une section creuse.
        from forge import services

        projet = services.create_project_from_markdown(user, EXEMPLE)
        assert projet.parcours.count() == 0
        assert projet.ecartees.count() == 0
        assert projet.objective == "" and projet.frame == ""

    def test_l_apercu_montre_ce_qui_sera_ecrit(self):
        # Un aperçu qui cache la moitié du document laisse valider une roadmap
        # qu'on n'a pas vue.
        from forge import services
        from forge.rules.roadmap_import import render

        apercu = services.preview_project(render(TestPlanDetaille.RICHE))
        assert apercu["objective"].startswith("Compromettre")
        assert len(apercu["parcours"]) == 2
        assert len(apercu["ecartees"]) == 2
        assert apercu["steps"][0]["exit_criterion"]

    def test_l_etape_en_cours_passe_avant_les_etapes_non_touchees(self, projet):
        # Défaut trouvé en écrivant le test suivant : ``order_by("-state")``
        # triait des chaînes, et « todo » passe devant « doing » en ordre
        # décroissant. Une étape déjà commencée était donc doublée par la
        # première étape non touchée, sans que rien ne le montre.
        assert projet.current_step.label == "Terminer les niveaux 0 à 10 de Bandit"

    def test_la_decision_du_soir_porte_le_critere_de_sortie(self, user, projet):
        # Le critère ne sert à rien dans une fiche qu'on ne relit pas : il doit
        # arriver jusqu'à la proposition du soir, avant de commencer.
        from datetime import date

        from forge import services

        proposition = services.propose(user, today=date(2026, 8, 19))
        assert proposition is not None
        assert "writeup" in proposition["step"]["exit_criterion"]


# Un document tel qu'un chat le rend quand on ne lui impose pas le format :
# métadonnées en gras, titres de niveau trois, liste numérotée, tableau. Aucune
# de ces formes n'était lue — et le pire, aucune n'était signalée.
MARKDOWN_DE_CHAT = """
# Roadmap Cybersécurité

**Domaine :** savoir
**Vérification :** git
**Dépôt :** ~/labs-cyber
**Objectif :** Compromettre une machine Easy en moins de 3 h.

---

## Le parcours (24 mois)

### Bloc A — Fondamentaux Linux

**Ressource principale :** OverTheWire Bandit
**Adresse :** https://overthewire.org/wargames/bandit/
**Charge :** 25-40 h
**Critère de sortie :** niveau 34 terminé

### Bloc B — Sécurité web

**Ressource principale :** PortSwigger Web Security Academy
**Charge :** 200-280 h

## La roadmap du bloc A

1. Terminer les niveaux 0 à 10 de Bandit (3 sessions)
   - Ressource : OverTheWire Bandit
   - Périmètre : niveaux 0 à 10 seulement
2. Créer le dépôt ~/labs-cyber avec un writeup.md type (1 session)
3. Terminer les niveaux 11 à 20 de Bandit (3 sessions)

## Ressources écartées

| Ressource | Raison |
|---|---|
| TryHackMe | redondant avec HTB |
"""


class TestMarkdownDeChat:
    """Ce qu'un modèle écrit quand personne ne lui impose le format.

    Chaque test ici correspond à une perte silencieuse constatée sur un vrai
    collage : le document se présentait comme parfaitement lu et rendait treize
    étapes fantômes tirées de ses propres métadonnées.
    """

    def test_le_gras_n_est_pas_une_puce(self):
        projet = parse(MARKDOWN_DE_CHAT)
        assert all(not e.label.startswith("*") for e in projet.steps)

    def test_les_metadonnees_en_gras_sont_lues(self):
        projet = parse(MARKDOWN_DE_CHAT)
        assert projet.domain == "savoir"
        assert projet.verification == "git"
        assert projet.repo_path == "~/labs-cyber"
        assert projet.objective.startswith("Compromettre")

    def test_les_listes_numerotees_sont_des_etapes(self):
        projet = parse(MARKDOWN_DE_CHAT)
        libelles = [e.label for e in projet.steps]

        assert len(projet.steps) == 3
        assert "Terminer les niveaux 0 à 10 de Bandit" in libelles
        assert projet.steps[0].estimated_sessions == 3

    def test_une_sous_puce_est_un_attribut_pas_une_etape(self):
        projet = parse(MARKDOWN_DE_CHAT)
        assert projet.steps[0].resource == "OverTheWire Bandit"
        assert "niveaux 0 à 10" in projet.steps[0].scope

    def test_un_titre_de_section_n_a_pas_besoin_de_commencer_par_son_mot(self):
        """« ## Le parcours (24 mois) » ouvre bien la section parcours."""
        projet = parse(MARKDOWN_DE_CHAT)
        assert len(projet.parcours) == 2
        assert projet.parcours[0].name.startswith("Bloc A")
        assert projet.parcours[0].url.endswith("/bandit/")
        assert projet.parcours[0].exit_criterion == "niveau 34 terminé"

    def test_les_ecartees_se_lisent_dans_un_tableau(self):
        projet = parse(MARKDOWN_DE_CHAT)
        assert [(e.name, e.reason) for e in projet.ecartees] == [
            ("TryHackMe", "redondant avec HTB")
        ]

    def test_la_barre_de_separation_n_est_pas_une_etape(self):
        projet = parse(MARKDOWN_DE_CHAT)
        assert all(e.label.strip("-") for e in projet.steps)

    def test_rien_ne_se_perd_en_silence(self):
        projet = parse(MARKDOWN_DE_CHAT)
        assert projet.ignorees == []

    def test_ce_qui_n_est_pas_compris_est_dit(self):
        """Le défaut le plus coûteux était le silence, pas l'incompréhension."""
        projet = parse("# P\n\n- [ ] Une étape (1)\n\nUne phrase libre au milieu.\n")

        assert projet.ignorees == ["Une phrase libre au milieu."]
        assert any("n'ont pas été comprises" in a for a in projet.warnings)
