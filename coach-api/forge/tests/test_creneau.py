"""Tests du remplissage d'un créneau (SPEC §4.1, §4.5).

Le défaut corrigé ici ne se voyait pas à la lecture : les boutons de durée
changeaient le chronomètre et rien d'autre. On pouvait donc choisir « dix
minutes » et recevoir une étape estimée à soixante-quinze, ou choisir
« soixante-quinze » et n'avoir qu'une étape de vingt-cinq à faire.
"""

from dataclasses import dataclass

from django.utils import timezone

import pytest

from forge.rules.creneau import crediter, minutes_de, plan_pour, reste_de


@dataclass
class Etape:
    """Le minimum dont la règle a besoin. Pas de base, pas de Django."""

    label: str
    estimated_sessions: int = 1
    state: str = "todo"
    minutes_done: int = 0


class TestMesures:
    def test_une_session_vaut_vingt_cinq_minutes(self):
        assert minutes_de(1) == 25 and minutes_de(3) == 75

    def test_le_reste_retire_ce_qui_est_deja_fait(self):
        assert reste_de(Etape("x", 2, minutes_done=20)) == 30

    def test_le_reste_ne_descend_pas_sous_zero(self):
        assert reste_de(Etape("x", 1, minutes_done=90)) == 0


class TestRemplissage:
    def test_une_etape_qui_rentre_pile(self):
        plan = plan_pour(25, [Etape("courte", 1)])

        assert len(plan.portions) == 1
        assert plan.portions[0].minutes == 25
        assert plan.portions[0].entiere and not plan.coupe

    def test_plusieurs_etapes_si_elles_tiennent(self):
        """Le geste demandé : une soirée longue couvre plusieurs étapes."""
        plan = plan_pour(75, [Etape("a", 1), Etape("b", 1), Etape("c", 1), Etape("d", 1)])

        assert [p.etape.label for p in plan.portions] == ["a", "b", "c"]
        assert plan.enchaine and plan.couvert == 75
        assert all(p.entiere for p in plan.portions)

    def test_l_ordre_de_la_roadmap_n_est_jamais_enjambe(self):
        """Sauter l'étape difficile pour une plus courte plus loin est la
        dérive que le §4.5 cherche à empêcher."""
        plan = plan_pour(25, [Etape("grosse", 3), Etape("courte", 1)])

        assert [p.etape.label for p in plan.portions] == ["grosse"]

    def test_une_etape_trop_longue_est_coupee_a_la_fraction(self):
        """« Une tâche prend 50 min et je choisis 25 : je fais la moitié. »"""
        plan = plan_pour(25, [Etape("longue", 2)])
        portion = plan.portions[0]

        assert portion.minutes == 25 and portion.reste_avant == 50
        assert portion.pourcentage == 50
        assert not portion.entiere and plan.coupe

    def test_une_etape_deja_entamee_reprend_ou_elle_s_est_arretee(self):
        """Sans ça, la moitié faite hier serait à refaire aujourd'hui."""
        plan = plan_pour(25, [Etape("longue", 2, minutes_done=25)])
        portion = plan.portions[0]

        assert portion.reste_avant == 25
        assert portion.entiere and portion.pourcentage == 100

    def test_l_enchainement_et_la_coupe_se_combinent(self):
        plan = plan_pour(75, [Etape("a", 1), Etape("b", 2)])

        assert [p.minutes for p in plan.portions] == [25, 50]
        assert not plan.coupe

        serre = plan_pour(50, [Etape("a", 1), Etape("b", 2)])
        assert [p.minutes for p in serre.portions] == [25, 25]
        assert serre.coupe and serre.portions[1].pourcentage == 50

    def test_le_reliquat_trop_court_n_ouvre_pas_d_etape(self):
        """Cinq minutes sur une étape ne sont pas un début de travail."""
        plan = plan_pour(28, [Etape("a", 1), Etape("b", 1)])

        assert len(plan.portions) == 1

    def test_une_etape_a_clore_prend_ce_qui_reste(self):
        """Temps estimé consommé sans que l'étape soit déclarée finie."""
        plan = plan_pour(50, [Etape("finie ?", 1, minutes_done=25)])
        portion = plan.portions[0]

        assert portion.a_clore and portion.minutes == 50

    def test_l_etape_en_cours_passe_en_tete(self):
        plan = plan_pour(25, [Etape("suivante", 1), Etape("entamee", 1, state="doing")])

        assert plan.portions[0].etape.label == "entamee"

    def test_les_etapes_faites_ne_comptent_pas(self):
        plan = plan_pour(25, [Etape("finie", 1, state="done"), Etape("suivante", 1)])
        assert plan.portions[0].etape.label == "suivante"

    def test_une_roadmap_sans_etape_ouverte_ne_propose_rien(self):
        assert plan_pour(25, [Etape("finie", 1, state="done")]).vide
        assert plan_pour(25, []).vide


class TestCredit:
    """Ce qui rend la coupe acceptable : le temps passé ne se perd pas."""

    def test_le_temps_va_aux_etapes_dans_l_ordre(self):
        plan = plan_pour(75, [Etape("a", 1), Etape("b", 2)])
        credits = crediter(plan.portions, 75)

        assert [(e.label, m) for e, m in credits] == [("a", 25), ("b", 50)]

    def test_une_seance_ecourtee_ne_credite_que_ce_qu_elle_a_dure(self):
        plan = plan_pour(75, [Etape("a", 1), Etape("b", 2)])
        credits = crediter(plan.portions, 30)

        assert [(e.label, m) for e, m in credits] == [("a", 25), ("b", 5)]

    def test_une_seance_prolongee_ne_deborde_pas_hors_du_plan(self):
        """Le temps en trop profite au travail prévu, il n'en ouvre pas d'autre."""
        plan = plan_pour(25, [Etape("a", 1), Etape("b", 1)])
        credits = crediter(plan.portions, 200)

        assert [(e.label, m) for e, m in credits] == [("a", 25)]


@pytest.mark.django_db
class TestSoireeComplete:
    """La règle vue depuis l'écran du soir, puis depuis la clôture."""

    @pytest.fixture
    def user(self, db):
        from django.contrib.auth import get_user_model

        from forge.models import Profile, Project, Track

        compte = get_user_model().objects.create_user(username="creneau", password="x")
        Profile.objects.create(user=compte)
        atelier = Track.objects.create(user=compte, kind=Track.ATELIER)
        Project.objects.create(
            user=compte, track=atelier, name="Cible", slot=1, weekly_commitment=3
        )
        return compte

    @pytest.fixture
    def projet(self, user):
        from forge.models import Project, RoadmapStep

        projet = Project.objects.filter(user=user, is_coach_project=False).first()
        projet.steps.all().delete()
        for ordre, (libelle, sessions) in enumerate(
            [("Étape longue", 2), ("Étape courte", 1), ("Étape suivante", 1)]
        ):
            RoadmapStep.objects.create(
                project=projet, order=ordre, label=libelle, estimated_sessions=sessions
            )
        return projet

    def test_le_creneau_long_annonce_plusieurs_etapes(self, user, projet):
        from datetime import date

        from forge import services

        proposition = services.propose(user, today=date(2026, 8, 20), minutes=75)

        assert [p["label"] for p in proposition["plan"]] == ["Étape longue", "Étape courte"]
        assert proposition["plan_enchaine"] and not proposition["plan_coupe"]

    def test_le_creneau_court_annonce_la_fraction(self, user, projet):
        from datetime import date

        from forge import services

        proposition = services.propose(user, today=date(2026, 8, 20), minutes=25)

        assert len(proposition["plan"]) == 1
        assert proposition["plan"][0]["pourcentage"] == 50
        assert proposition["plan_coupe"]

    def test_la_moitie_faite_hier_n_est_pas_a_refaire(self, user, projet):
        """Le bout à bout : on démarre, on clôt, la roadmap a bougé."""
        from datetime import timedelta

        from django.utils import timezone

        from forge import services

        debut = timezone.now() - timedelta(minutes=25)
        session = services.start_session(user, projet, planned_minutes=25, now=debut)
        assert [p["minutes"] for p in session.plan] == [25]

        services.end_session(session, now=timezone.now())

        longue = projet.steps.order_by("order").first()
        longue.refresh_from_db()
        assert longue.minutes_done == 25
        assert longue.minutes_restantes == 25
        assert longue.state != "done"      # le chronomètre ne clôt jamais (§6)

    def test_la_seance_suivante_reprend_le_reste(self, user, projet):
        from datetime import date, timedelta

        from django.utils import timezone

        from forge import services

        debut = timezone.now() - timedelta(minutes=25)
        session = services.start_session(user, projet, planned_minutes=25, now=debut)
        services.end_session(session, now=timezone.now())

        proposition = services.propose(user, today=date(2026, 8, 20), minutes=25)

        assert proposition["plan"][0]["label"] == "Étape longue"
        assert proposition["plan"][0]["reste_avant"] == 25
        assert proposition["plan"][0]["entiere"] is True


ETAPES_DU_BLOC = {
    "probleme": "",
    "etapes": [
        {
            "libelle": "Résoudre les niveaux 4 à 7 de Bandit et noter chaque usage de find",
            "sessions": 2,
            "etat": "todo",
            "ressource": "OverTheWire Bandit",
            "url": "https://overthewire.org/wargames/bandit/",
            "perimetre": "Niveaux 4 à 7 seulement",
            "charge": "50 min",
            "critere_sortie": "Les quatre mots de passe sont dans writeups/bandit.md, commités",
        },
        {
            "libelle": "Écrire notes/permissions.md avec cinq sorties de commande réelles",
            "sessions": 1,
            "etat": "todo",
            "critere_sortie": "Le fichier est commité et contient cinq sorties collées",
        },
        {
            "libelle": "Résoudre les niveaux 8 à 10 en chaînant sort, uniq et base64",
            "sessions": 2,
            "etat": "todo",
            "critere_sortie": "Chaque solution tient en une seule commande enchaînée",
        },
        {
            "libelle": "Rejouer de mémoire les niveaux 5 et 9, notes fermées",
            "sessions": 1,
            "etat": "todo",
            "critere_sortie": "Les deux niveaux refaits en moins de dix minutes chacun",
        },
    ],
}


@pytest.mark.django_db
class TestOuvertureDuBlocSuivant:
    """Le trou que le §4.5 laissait : la roadmap s'épuisait au premier bloc.

    L'entretien n'explose en étapes que le bloc en cours — c'est le bon
    découpage —, mais rien ne prenait le relais ensuite. Sur un parcours de
    quatorze blocs, le produit s'arrêtait au premier dixième.
    """

    @pytest.fixture
    def projet(self, db):
        from django.contrib.auth import get_user_model

        from forge import services
        from forge.models import Profile

        compte = get_user_model().objects.create_user(username="parcours", password="x")
        Profile.objects.create(user=compte)
        return services.create_project_from_markdown(
            compte,
            "# Pentest\n"
            "Domaine: savoir\n"
            "Branche: cyber\n"
            "Objectif: Compromettre un domaine Active Directory de laboratoire.\n"
            "\n## Parcours\n\n"
            "- Bloc A — Ligne de commande\n"
            "  Ressource: OverTheWire Bandit\n"
            "  Adresse: https://overthewire.org/wargames/bandit/\n"
            "  Sortie: niveau 20 atteint\n"
            "- Bloc B — Réseau\n"
            "  Ressource: Cours réseau de Lalitte\n"
            "  Sortie: un /22 découpé à la main\n"
            "\n## Roadmap\n\n"
            "- [ ] Se connecter en SSH à bandit0 et valider le niveau 1 (1)\n"
        )

    def test_les_etapes_initiales_appartiennent_au_premier_bloc(self, projet):
        etape = projet.steps.first()
        assert etape.bloc is not None
        assert etape.bloc.name.startswith("Bloc A")

    def test_on_n_ouvre_pas_un_bloc_tant_qu_il_reste_des_etapes(self, projet):
        from forge import services

        assert services.bloc_a_ouvrir(projet) is None

    def test_la_roadmap_vide_designe_le_bloc_courant(self, projet):
        from forge import services
        from forge.models import RoadmapStep

        projet.steps.update(state=RoadmapStep.DONE)

        bloc = services.bloc_a_ouvrir(projet)
        assert bloc is not None and bloc.name.startswith("Bloc A")

    def test_l_ouverture_ecrit_les_etapes_et_referme_le_bloc_precedent(self, projet):
        from forge import coaching
        from forge.llm import set_provider
        from forge.llm.fake import ScriptedProvider
        from forge.models import RoadmapStep

        # Bloc A fini : on ouvre donc le bloc A lui-même une première fois, puis
        # le bloc B. Ici on saute directement au second pour vérifier la
        # fermeture du précédent.
        projet.steps.update(state=RoadmapStep.DONE)
        projet.parcours.filter(order=0).update(done_at=timezone.now())

        set_provider(ScriptedProvider([ETAPES_DU_BLOC]))
        resultat = coaching.ouvrir_le_bloc_suivant(projet)

        assert resultat["created"] == 4
        assert resultat["bloc"]["name"].startswith("Bloc B")

        nouvelles = projet.steps.filter(state=RoadmapStep.TODO)
        assert nouvelles.count() == 4
        assert all(e.bloc.name.startswith("Bloc B") for e in nouvelles)
        # Les étapes du bloc A restent : le §17 interdit d'effacer ce qui a eu lieu.
        assert projet.steps.filter(state=RoadmapStep.DONE).count() == 1

    def test_le_modele_recoit_ce_qui_a_deja_ete_fait(self, projet):
        from forge import coaching
        from forge.llm import set_provider
        from forge.llm.fake import ScriptedProvider
        from forge.models import RoadmapStep

        projet.steps.update(state=RoadmapStep.DONE)
        fournisseur = ScriptedProvider([ETAPES_DU_BLOC])
        set_provider(fournisseur)
        coaching.ouvrir_le_bloc_suivant(projet)

        envoye = fournisseur.calls[0]["prompt"]
        assert "Se connecter en SSH à bandit0" in envoye     # ne pas le refaire écrire
        assert "Bloc B" in envoye                            # ne pas empiéter dessus
        assert "Compromettre un domaine" in envoye           # l'objectif du projet

    def test_une_ressource_morte_est_dite_au_lieu_d_etre_contournee(self, projet):
        from forge import coaching
        from forge.llm import set_provider
        from forge.llm.fake import ScriptedProvider
        from forge.models import RoadmapStep

        projet.steps.update(state=RoadmapStep.DONE)
        set_provider(
            ScriptedProvider([{"probleme": "Le cours a fermé en février 2026.", "etapes": []}])
        )

        with pytest.raises(coaching.InterviewUnavailable, match="a fermé"):
            coaching.ouvrir_le_bloc_suivant(projet)

    def test_la_proposition_annonce_le_bloc_a_ouvrir(self, projet):
        from datetime import date

        from forge import services
        from forge.models import RoadmapStep, Track

        projet.track = Track.objects.get_or_create(user=projet.user, kind=Track.ATELIER)[0]
        projet.save(update_fields=["track"])
        projet.steps.update(state=RoadmapStep.DONE)

        proposition = services.propose(projet.user, today=date(2026, 8, 20))

        assert proposition["next_bloc"]["name"].startswith("Bloc A")

    def test_sans_parcours_il_n_y_a_rien_a_ouvrir(self, db):
        from django.contrib.auth import get_user_model

        from forge import coaching, services
        from forge.models import Profile, RoadmapStep

        compte = get_user_model().objects.create_user(username="colle", password="x")
        Profile.objects.create(user=compte)
        projet = services.create_project_from_markdown(
            compte, "# Plomberie\n\n## Roadmap\n\n- [ ] Appeler le plombier (1)\n"
        )
        projet.steps.update(state=RoadmapStep.DONE)

        assert services.bloc_a_ouvrir(projet) is None
        with pytest.raises(ValueError, match="pas de parcours"):
            coaching.ouvrir_le_bloc_suivant(projet)
