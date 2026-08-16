"""Tests du briefing et du debrief (SPEC §5.1, §5.2, §0.9).

Aucun appel réseau : le fournisseur est toujours factice. Ce n'est pas une
limite de la suite, c'est son sujet. La qualité d'un modèle ne se teste pas
ici ; ce qui se teste, et ce qui casserait vraiment quelque chose, c'est le
comportement du coach **quand le modèle rate**.

D'où la répartition des tests ci-dessous : un seul vérifie le cas nominal, tous
les autres vérifient que l'utilisateur voit quand même une action décidée quand
le modèle est absent, lent, muet, hors sujet, ou qu'il hallucine un projet.
C'est le chemin qu'on emprunte un soir de panne, et c'est celui qui n'est jamais
essayé à la main.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import coaching, services
from forge.llm import set_provider
from forge.llm.base import LLMUnavailable
from forge.llm.fake import ScriptedProvider, UnavailableProvider
from forge.models import JournalEntry, Profile, Project, RoadmapStep, Session, Track
from forge.rules.calendar import coach_day


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    projet = Project.objects.create(
        user=user, track=atelier, name="Bestiaire", slot=1, weekly_commitment=3
    )
    RoadmapStep.objects.create(
        project=projet, label="Écran de fiche d'espèce", order=1, state=RoadmapStep.DOING
    )
    Project.objects.create(user=user, track=atelier, name="Evolve", slot=2, weekly_commitment=2)
    today = coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour)
    services.open_season(user, starts_on=today, stake=100)
    return user


@pytest.fixture(autouse=True)
def sans_reseau():
    """Aucun test ne doit pouvoir joindre un modèle réel, même par accident."""
    set_provider(UnavailableProvider())
    yield
    set_provider(None)


def reponse_briefing(**champs) -> dict:
    base = {
        "projet": "Bestiaire",
        "tache": "Écrire le composant FicheEspece et son test de rendu",
        "minutes": 50,
        "pourquoi": "deux sessions de retard sur l'engagement de la semaine",
        "definition_de_fini": "le test de rendu passe",
    }
    base.update(champs)
    return base


class TestBriefingNominal:
    def test_le_modele_peut_ameliorer_la_proposition(self, user):
        set_provider(ScriptedProvider([reponse_briefing()]))
        resultat = coaching.briefing(user)

        assert resultat["source"] == coaching.SOURCE_MODELE
        assert resultat["amorce"] == "Écrire le composant FicheEspece et son test de rendu"
        assert resultat["minutes"] == 50
        assert resultat["definition_de_fini"] == "le test de rendu passe"

    def test_l_identifiant_du_projet_vient_de_la_base_pas_du_modele(self, user):
        """Le modèle nomme, le serveur résout. Il ne choisit jamais un id."""
        set_provider(ScriptedProvider([reponse_briefing(projet="Evolve")]))
        resultat = coaching.briefing(user)

        assert resultat["project"]["id"] == Project.objects.get(name="Evolve").id

    def test_le_contexte_envoye_contient_les_projets_et_leur_retard(self, user):
        fournisseur = ScriptedProvider([reponse_briefing()])
        set_provider(fournisseur)
        coaching.briefing(user)

        envoye = fournisseur.calls[0]["prompt"]
        assert "Bestiaire" in envoye
        assert "Evolve" in envoye
        assert "0 session(s) faite(s) sur 3" in envoye

    def test_l_amorce_precedente_est_transmise(self, user):
        """Sans elle, le modèle ne peut que paraphraser l'étape (§11.3)."""
        projet = Project.objects.get(name="Bestiaire")
        session = Session.objects.create(
            user=user,
            project=projet,
            planned_minutes=25,
            actual_minutes=25,
            status=Session.DONE,
            coach_day=timezone.now().date(),
            started_at=timezone.now() - timedelta(hours=1),
        )
        JournalEntry.objects.create(
            session=session, raw_note="", next_action="reprendre le tri par famille"
        )

        fournisseur = ScriptedProvider([reponse_briefing()])
        set_provider(fournisseur)
        coaching.briefing(user)

        assert "reprendre le tri par famille" in fournisseur.calls[0]["prompt"]


class TestBriefingQuandLeModeleRate:
    """Le seul groupe qui compte vraiment : l'app doit rester utilisable."""

    def test_sans_identifiant_la_proposition_deterministe_est_rendue(self, user):
        resultat = coaching.briefing(user)

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE
        assert resultat["project"]["name"] in {"Bestiaire", "Evolve"}
        assert resultat["minutes"] in (10, 25, 50)

    def test_la_raison_de_l_absence_d_ia_est_dite_pas_masquee(self, user):
        set_provider(UnavailableProvider("le CLI « claude » est introuvable"))
        resultat = coaching.briefing(user)

        assert "introuvable" in resultat["ai_note"]

    def test_un_projet_hallucine_fait_tomber_sur_le_repli(self, user):
        """Afficher un projet qui n'existe pas coûte plus cher que ne rien afficher."""
        set_provider(ScriptedProvider([reponse_briefing(projet="Projet Fantôme")]))
        resultat = coaching.briefing(user)

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE
        assert "inconnu" in resultat["ai_note"]

    def test_une_reponse_qui_offre_le_choix_est_refusee(self, user):
        """§0.9 : une liste à arbitrer un soir de fatigue se solde par YouTube."""
        set_provider(
            ScriptedProvider(
                [reponse_briefing(tache="Écrire la fiche d'espèce ou bien finir le tri")]
            )
        )
        resultat = coaching.briefing(user)

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE
        assert "plusieurs pistes" in resultat["ai_note"]

    def test_une_tache_floue_est_refusee(self, user):
        set_provider(ScriptedProvider([reponse_briefing(tache="Avancer sur le Bestiaire")]))
        resultat = coaching.briefing(user)

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE

    def test_une_duree_inventee_est_refusee(self, user):
        """Trois durées existent (§4.1). 35 minutes n'en fait pas partie."""
        set_provider(ScriptedProvider([reponse_briefing(minutes=35)]))
        resultat = coaching.briefing(user)

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE

    def test_une_reponse_vide_est_refusee(self, user):
        set_provider(ScriptedProvider([{}]))
        resultat = coaching.briefing(user)

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE

    def test_une_reponse_en_texte_libre_est_refusee(self, user):
        """Un modèle qui répond en prose malgré le schéma ne casse rien."""
        set_provider(ScriptedProvider(["Ce soir tu devrais avancer sur le Bestiaire."]))
        resultat = coaching.briefing(user)

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE

    def test_le_repli_garde_toujours_une_action_decidee(self, user):
        """Quel que soit l'échec, il y a un projet, une durée et une raison."""
        for mauvaise in ({}, "prose", reponse_briefing(minutes=35), reponse_briefing(projet="X")):
            set_provider(ScriptedProvider([mauvaise]))
            resultat = coaching.briefing(user)

            assert resultat["project"]["name"]
            assert resultat["minutes"] in (10, 25, 50)
            assert resultat["reason"]


class TestBriefingSansProjet:
    def test_aucun_projet_actif_ne_produit_aucun_briefing(self, db):
        """On ne demande rien à un modèle quand il n'y a rien à décider."""
        User = get_user_model()
        vide = User.objects.create_user(username="vide", password="x")
        Profile.objects.create(user=vide)
        Track.objects.create(user=vide, kind=Track.ATELIER)

        fournisseur = ScriptedProvider([])
        set_provider(fournisseur)

        assert coaching.briefing(vide) is None
        assert fournisseur.calls == []


class TestDebrief:
    @pytest.fixture
    def session(self, user):
        return Session.objects.create(
            user=user,
            project=Project.objects.get(name="Bestiaire"),
            planned_minutes=25,
            actual_minutes=25,
            status=Session.DONE,
            coach_day=timezone.now().date(),
            started_at=timezone.now() - timedelta(minutes=25),
        )

    def test_structure_une_note_brute(self, session):
        set_provider(
            ScriptedProvider(
                [
                    {
                        "resume": "Écran de fiche monté, données branchées.",
                        "amorce": "brancher le filtre par famille dans FicheEspece",
                        "blocages": ["le tri par famille n'est pas décidé"],
                    }
                ]
            )
        )
        resultat = coaching.debrief(session, note="fait l'écran, reste le filtre")

        assert resultat["source"] == coaching.SOURCE_MODELE
        assert resultat["amorce"].startswith("brancher le filtre")
        assert resultat["blocages"] == ["le tri par famille n'est pas décidé"]

    def test_une_note_vide_n_appelle_aucun_modele(self, session):
        fournisseur = ScriptedProvider([])
        set_provider(fournisseur)

        resultat = coaching.debrief(session, note="   ")

        assert resultat["amorce"] == ""
        assert fournisseur.calls == []

    def test_sans_ia_la_note_est_rendue_telle_quelle(self, session):
        resultat = coaching.debrief(session, note="fait l'écran, reste le filtre")

        assert resultat["resume"] == "fait l'écran, reste le filtre"
        assert resultat["source"] == coaching.SOURCE_DETERMINISTE

    def test_sans_ia_aucune_amorce_n_est_fabriquee(self, session):
        """Une amorce inventée serait validée par réflexe et ferait démarrer à faux."""
        resultat = coaching.debrief(session, note="fait l'écran, reste le filtre")

        assert resultat["amorce"] == ""

    def test_une_amorce_floue_est_refusee(self, session):
        set_provider(
            ScriptedProvider(
                [{"resume": "ok", "amorce": "continuer le travail commencé", "blocages": []}]
            )
        )
        resultat = coaching.debrief(session, note="fait l'écran")

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE
        assert resultat["amorce"] == ""

    def test_un_debrief_sans_amorce_est_refuse(self, session):
        """Le §11.3 en fait le prix du démarrage à froid : sans elle, rien."""
        set_provider(ScriptedProvider([{"resume": "ok", "blocages": []}]))
        resultat = coaching.debrief(session, note="fait l'écran")

        assert resultat["source"] == coaching.SOURCE_DETERMINISTE

    def test_le_debrief_n_ecrit_rien_en_base(self, session):
        set_provider(
            ScriptedProvider(
                [
                    {
                        "resume": "Écran monté.",
                        "amorce": "brancher le filtre par famille dans FicheEspece",
                        "blocages": [],
                    }
                ]
            )
        )
        coaching.debrief(session, note="fait l'écran")

        assert not JournalEntry.objects.filter(session=session).exists()
