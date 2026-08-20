"""Tests du briefing, du debrief et de l'entretien (SPEC §5.1, §5.2, §4.5, §0.9).

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
from forge.models import (
    JournalEntry,
    Profile,
    Project,
    ProjectInterview,
    RoadmapStep,
    Session,
    Track,
)
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


PROJET_VALIDE = {
    "nom": "Analyseur Smash",
    "domaine": "code",
    "verification": "git",
    "depot": "C:/Dev/analyseur-smash",
    "branche": "data_rl",
    "engagement": 3,
    "etapes": [
        {
            "libelle": "Écrire le test qui reproduit le crash à 4 joueurs",
            "sessions": 2,
            "etat": "doing",
            "critere_sortie": "le test échoue sur la version actuelle et nomme la ligne fautive",
        },
        {
            "libelle": "Lire le bloc Event Payloads dynamiquement dans parser.py",
            "sessions": 2,
            "etat": "todo",
            "critere_sortie": "les tailles d'événements sont lues du fichier, plus aucune constante",
        },
        {
            "libelle": "Parser Game Start et les ports réellement actifs",
            "sessions": 3,
            "etat": "todo",
            "critere_sortie": "un replay à 3 joueurs rend trois ports, pas quatre",
        },
        {
            "libelle": "Rejouer la banque de replays en batch et corriger les restes",
            "sessions": 2,
            "etat": "todo",
            "critere_sortie": "les 200 replays de la banque passent sans exception",
        },
    ],
    # Le parcours n'est plus facultatif côté porte : trois blocs au minimum,
    # chacun avec sa ressource et son critère. Voir ``gate.MIN_BLOCS``.
    "parcours": [
        {
            "nom": "Lecture du format",
            "resultat": "je lis un .slp sans bibliothèque tierce",
            "ressource": "Spécification du format Slippi",
            "url": "https://github.com/project-slippi/slippi-wiki",
            "charge": "20–30 h",
            "cout": "Gratuit",
            "optionnel": False,
            "critere_sortie": "un replay quelconque rend ses métadonnées complètes",
        },
        {
            "nom": "Statistiques de partie",
            "resultat": "je calcule dégâts, stocks et ouvertures",
            "ressource": "slippi-js, en lecture",
            "url": "https://github.com/project-slippi/slippi-js",
            "charge": "40–60 h",
            "cout": "Gratuit",
            "optionnel": False,
            "critere_sortie": "mes chiffres égalent ceux de slippi-js sur dix replays",
        },
        {
            "nom": "Analyse comparée",
            "resultat": "je sors les tendances d'un joueur sur une saison",
            "ressource": "pandas, documentation officielle",
            "url": "https://pandas.pydata.org/docs/",
            "charge": "30–50 h",
            "cout": "Gratuit",
            "optionnel": False,
            "critere_sortie": "un rapport de saison sort en une commande",
        },
    ],
}


def tour_question(texte="Qu'est-ce qui marche déjà aujourd'hui dans ce projet ?") -> dict:
    return {"fini": False, "question": texte, "projet": None}


def tour_final(**champs) -> dict:
    """Le tour de conclusion. ``champs`` remplace des clés du projet valide."""
    return {"fini": True, "question": "", "projet": {**PROJET_VALIDE, **champs}}


class TestEntretien:
    """L'entretien du §4.5 — le seul service sans repli déterministe."""

    def test_l_entretien_s_ouvre_sur_une_question(self, user):
        set_provider(ScriptedProvider([tour_question()]))
        etat = coaching.interview_start(user)

        assert etat["status"] == "en_cours"
        assert etat["messages"][0]["role"] == "assistant"
        assert etat["markdown"] == ""

    def test_l_echange_complet_est_renvoye_a_chaque_tour(self, user):
        """Le serveur porte la conversation : elle survit à tout redémarrage."""
        fournisseur = ScriptedProvider([tour_question("Première ?"), tour_question("Deuxième ?")])
        set_provider(fournisseur)

        etat = coaching.interview_start(user)
        entretien = ProjectInterview.objects.get(id=etat["id"])
        coaching.interview_reply(entretien, answer="c'est un outil d'analyse de replays")

        envoye = fournisseur.calls[1]["prompt"]
        assert "Première ?" in envoye
        assert "analyse de replays" in envoye

    def test_les_projets_existants_sont_transmis(self, user):
        """Pour ne pas proposer un doublon ni saturer un domaine (§4.3)."""
        fournisseur = ScriptedProvider([tour_question()])
        set_provider(fournisseur)
        coaching.interview_start(user)

        assert "Bestiaire" in fournisseur.calls[0]["prompt"]

    def test_la_roadmap_arrive_a_la_fin_et_rien_n_est_cree(self, user):
        set_provider(ScriptedProvider([tour_question(), tour_final()]))

        etat = coaching.interview_start(user)
        entretien = ProjectInterview.objects.get(id=etat["id"])
        etat = coaching.interview_reply(entretien, answer="rien encore, je pars de zéro")

        assert etat["status"] == "propose"
        assert "Analyseur Smash" in etat["markdown"]
        assert not Project.objects.filter(name="Analyseur Smash").exists()

    def test_l_import_passe_par_le_meme_parseur_que_le_collage(self, user):
        """Le chemin de l'IA n'a aucun privilège sur celui qu'on emprunte sans elle."""
        set_provider(ScriptedProvider([tour_final()]))
        etat = coaching.interview_start(user)
        entretien = ProjectInterview.objects.get(id=etat["id"])

        projet = coaching.interview_import(entretien)

        assert projet.name == "Analyseur Smash"
        assert projet.steps.count() == 4
        assert projet.verification == "git"
        entretien.refresh_from_db()
        assert entretien.status == "importe"

    def test_une_reponse_vide_est_refusee(self, user):
        set_provider(ScriptedProvider([tour_question()]))
        etat = coaching.interview_start(user)
        entretien = ProjectInterview.objects.get(id=etat["id"])

        with pytest.raises(ValueError):
            coaching.interview_reply(entretien, answer="   ")

    def test_la_reponse_est_gardee_meme_si_le_modele_echoue_ensuite(self, user):
        """Réessayer doit reprendre l'entretien, pas le recommencer."""
        set_provider(ScriptedProvider([tour_question()]))
        etat = coaching.interview_start(user)
        entretien = ProjectInterview.objects.get(id=etat["id"])

        set_provider(UnavailableProvider())
        with pytest.raises(coaching.InterviewUnavailable):
            coaching.interview_reply(entretien, answer="un outil d'analyse de replays")

        entretien.refresh_from_db()
        assert entretien.messages[-1]["content"] == "un outil d'analyse de replays"

    def test_l_entretien_s_arrete_de_questionner_au_bout_du_compte(self, user):
        """Un entretien plus long que la session qu'il devait lancer a échoué."""
        questions = [tour_question(f"Question {i} ?") for i in range(coaching.MAX_QUESTIONS)]
        set_provider(ScriptedProvider([*questions, tour_final()]))

        etat = coaching.interview_start(user)
        entretien = ProjectInterview.objects.get(id=etat["id"])
        for i in range(coaching.MAX_QUESTIONS):
            etat = coaching.interview_reply(entretien, answer=f"réponse {i}")

        assert etat["status"] == "propose"
        assert any("Assez de questions" in m["content"] for m in entretien.messages)


class TestEntretienSansModele:
    """Sans repli possible : il faut le dire, pas le masquer."""

    def test_sans_modele_l_entretien_ne_pretend_pas_marcher(self, user):
        with pytest.raises(coaching.InterviewUnavailable):
            coaching.interview_start(user)

    def test_l_indisponibilite_de_l_entretien_ne_se_confond_pas_avec_celle_du_modele(self):
        """Deux gestes opposés : renvoyer vers le collage, ou retomber sur le repli."""
        assert not issubclass(coaching.InterviewUnavailable, LLMUnavailable)


class TestPorteDeLaRoadmap:
    """Ce qui rattrape une roadmap inexploitable avant qu'elle ne coûte des semaines.

    Le modèle ne rend plus de markdown mais des champs, et le serveur écrit le
    format. Ce n'est pas une simplification de confort : trois essais réels ont
    montré qu'un modèle à qui l'on demande ce format produit régulièrement un
    document plus agréable à lire et inexploitable — métadonnées en gras, étapes
    numérotées — où le parseur perdait la vérification « git » et le chemin du
    dépôt **sans rien signaler**. Trois tours de reproche n'y ont rien changé.

    Le format est donc juste par construction, et il ne reste à contrôler ici que
    ce qu'un schéma ne sait pas dire.
    """

    def _refus(self, user, tour):
        """Le même mauvais tour à chaque essai : la reprise a lieu, puis on renonce."""
        set_provider(ScriptedProvider([tour] * coaching.MAX_ESSAIS))
        with pytest.raises(coaching.InterviewUnavailable) as capture:
            coaching.interview_start(user)
        return str(capture.value)

    def test_un_refus_donne_droit_a_une_reprise_avec_le_motif(self, user):
        """Sans repli, abandonner sur une réponse mal tournée serait absurde."""
        fournisseur = ScriptedProvider(
            [{"fini": True, "question": "", "projet": None}, tour_question()]
        )
        set_provider(fournisseur)

        etat = coaching.interview_start(user)

        assert etat["status"] == "en_cours"
        assert len(fournisseur.calls) == 2
        assert "refusée" in fournisseur.calls[1]["prompt"]
        assert "sans projet" in fournisseur.calls[1]["prompt"]

    def test_la_reprise_n_a_pas_lieu_indefiniment(self, user):
        """Un modèle qui ne corrige pas au second essai ne corrigera pas au dixième."""
        fournisseur = ScriptedProvider([{"fini": True, "question": "", "projet": None}] * 6)
        set_provider(fournisseur)

        with pytest.raises(coaching.InterviewUnavailable):
            coaching.interview_start(user)

        assert len(fournisseur.calls) == coaching.MAX_ESSAIS

    def test_le_markdown_est_ecrit_par_le_serveur_pas_par_le_modele(self, user):
        """Le format devient juste par construction : plus rien à plaider."""
        set_provider(ScriptedProvider([tour_final()]))
        etat = coaching.interview_start(user)

        assert etat["markdown"].startswith("# Analyseur Smash")
        assert "Vérification: git" in etat["markdown"]
        assert "Dépôt: C:/Dev/analyseur-smash" in etat["markdown"]
        assert "- [>] Écrire le test qui reproduit le crash à 4 joueurs (2)" in etat["markdown"]

    def test_une_etape_floue_est_refusee(self, user):
        floue = [{"libelle": "Avancer sur le parseur de replays", "sessions": 2, "etat": "todo"}]
        motif = self._refus(user, tour_final(etapes=PROJET_VALIDE["etapes"][:3] + floue))

        assert "floue" in motif
        assert "verbe concret" in motif

    def test_une_roadmap_trop_courte_est_refusee(self, user):
        assert "Découpe" in self._refus(user, tour_final(etapes=PROJET_VALIDE["etapes"][:2]))

    def test_une_roadmap_trop_longue_dit_quoi_faire(self, user):
        """Un reproche formulé en conseil ne converge pas ; une consigne chiffrée si.

        Constaté en vrai : « il faut réduire le projet » a fait passer de 34
        étapes à 17, puis à 17 encore.
        """
        trop = [
            {"libelle": f"Écrire le module numéro {i} dans mod{i}.py", "sessions": 2, "etat": "todo"}
            for i in range(15)
        ]
        motif = self._refus(user, tour_final(etapes=trop))

        assert "maximum 12" in motif
        assert "supprime le reste" in motif

    def test_une_roadmap_entierement_faite_est_refusee(self, user):
        finies = [{**e, "etat": "done"} for e in PROJET_VALIDE["etapes"]]
        assert "par quoi commencer" in self._refus(user, tour_final(etapes=finies))

    def test_deux_etapes_en_cours_sont_refusees(self, user):
        deux = [{**e, "etat": "doing"} for e in PROJET_VALIDE["etapes"]]
        assert "étape courante" in self._refus(user, tour_final(etapes=deux))

    def test_une_verification_annoncee_sans_les_moyens_est_refusee(self, user):
        """Le §6 : se croire vérifié est pire que le manuel assumé."""
        motif = self._refus(user, tour_final(depot=""))

        assert "manuelle" in motif

    def test_un_domaine_invente_est_refuse(self, user):
        assert "inconnu" in self._refus(user, tour_final(domaine="jeu-video"))

    def test_une_verification_inventee_est_refusee(self, user):
        assert "inconnue" in self._refus(user, tour_final(verification="magique"))

    def test_une_question_en_deux_propositions_reste_acceptee(self, user):
        """« C'est quoi, et pourquoi maintenant ? » est une question, en français.

        La version stricte de cette règle refusait des questions parfaitement
        bonnes et tuait l'entretien, faute de repli. Le test garde le réglage
        corrigé, pas celui qu'on aurait deviné.
        """
        set_provider(
            ScriptedProvider([tour_question("C'est quoi le projet, et pourquoi maintenant ?")])
        )

        assert coaching.interview_start(user)["status"] == "en_cours"

    def test_un_questionnaire_est_refuse(self, user):
        """La dérive réelle : le modèle vide son sac au lieu d'interroger."""
        tour = tour_question("C'est quoi ? Où en es-tu ? Tu utilises quoi ? Et pour quand ?")
        assert "questionnaire" in self._refus(user, tour)

    def test_une_question_en_liste_a_puces_est_refusee(self, user):
        tour = tour_question("Dis-moi :\n- ce que tu construis\n- où tu en es")
        assert "liste" in self._refus(user, tour)

    def test_une_question_avec_un_projet_est_refusee(self, user):
        tour = {"fini": False, "question": "Encore une chose ?", "projet": PROJET_VALIDE}
        assert "choisir" in self._refus(user, tour)

    def test_un_entretien_fini_sans_projet_est_refuse(self, user):
        assert "sans projet" in self._refus(user, {"fini": True, "question": "", "projet": None})


class TestExigenceDuParcours:
    """Le parcours est ce qui tient quelqu'un sur des mois (§4.5).

    Le schéma savait déjà exiger des blocs ; il ne savait pas exiger qu'ils
    disent quelque chose. Un parcours dont les blocs n'ont ni ressource ni
    critère est une table des matières.
    """

    def _refus(self, user, tour):
        set_provider(ScriptedProvider([tour] * coaching.MAX_ESSAIS))
        with pytest.raises(coaching.InterviewUnavailable) as capture:
            coaching.interview_start(user)
        return str(capture.value)

    def test_un_parcours_d_un_seul_bloc_est_refuse(self, user):
        motif = self._refus(user, tour_final(parcours=PROJET_VALIDE["parcours"][:1]))
        assert "bloc(s) de parcours" in motif

    def test_un_bloc_sans_ressource_est_refuse(self, user):
        nu = [{**PROJET_VALIDE["parcours"][0], "ressource": ""}, *PROJET_VALIDE["parcours"][1:]]
        assert "ressource principale" in self._refus(user, tour_final(parcours=nu))

    def test_un_bloc_sans_critere_de_sortie_est_refuse(self, user):
        nu = [{**PROJET_VALIDE["parcours"][0], "critere_sortie": ""}, *PROJET_VALIDE["parcours"][1:]]
        assert "critère de sortie" in self._refus(user, tour_final(parcours=nu))

    def test_un_parcours_sans_adresses_est_refuse(self, user):
        """Écrit de mémoire : aucune ressource ne s'ouvre le soir venu."""
        aveugle = [{**bloc, "url": ""} for bloc in PROJET_VALIDE["parcours"]]
        assert "portent une adresse" in self._refus(user, tour_final(parcours=aveugle))

    def test_une_etape_sans_critere_de_sortie_est_refusee(self, user):
        sans = [{**PROJET_VALIDE["etapes"][0], "critere_sortie": ""}, *PROJET_VALIDE["etapes"][1:]]
        assert "critère de sortie" in self._refus(user, tour_final(etapes=sans))


DOCUMENT_RANGE = {
    "lisible": True,
    "probleme": "",
    "projet": {
        "nom": "Carnet de cuisine",
        "domaine": "pratique",
        "verification": "manuelle",
        "depot": "",
        "branche": "artisanat",
        "engagement": 2,
        "objectif": "Tenir un dîner de quatre plats pour six sans recette.",
        "parcours": [],
        "etapes": [
            {"libelle": "Réussir une sauce béarnaise sans la faire trancher", "sessions": 2, "etat": "todo"},
        ],
        "ecartees": [],
    },
}


class TestRelectureDuMarkdown:
    """Le secours du collage : ranger un document qu'aucune règle n'attendait.

    La porte y est plus basse que celle de l'entretien, et c'est délibéré — le
    modèle transcrit un document que quelqu'un a déjà écrit. Le refuser parce
    que l'original est perfectible reviendrait à refuser le seul chemin qui
    marche sans IA.
    """

    def test_le_document_range_revient_au_format_canonique(self):
        set_provider(ScriptedProvider([DOCUMENT_RANGE]))
        markdown = coaching.relire_markdown("des notes en vrac")

        assert markdown.startswith("# Carnet de cuisine")
        assert "Domaine: pratique" in markdown
        assert "- [ ] Réussir une sauce béarnaise sans la faire trancher (2)" in markdown

    def test_une_seule_etape_suffit_et_le_parcours_est_facultatif(self):
        """Les planchers de l'entretien forceraient le modèle à inventer."""
        set_provider(ScriptedProvider([DOCUMENT_RANGE]))
        assert coaching.relire_markdown("des notes en vrac")

    def test_un_document_illisible_le_dit_au_lieu_de_fabriquer(self):
        set_provider(
            ScriptedProvider(
                [{"lisible": False, "probleme": "aucune tâche concrète", "projet": None}]
            )
        )
        with pytest.raises(coaching.InterviewUnavailable, match="aucune tâche"):
            coaching.relire_markdown("bonjour")

    def test_sans_modele_la_relecture_echoue_sans_emporter_le_collage(self):
        set_provider(UnavailableProvider())
        with pytest.raises(coaching.InterviewUnavailable):
            coaching.relire_markdown("# P\n- [ ] Une étape (1)\n")

    def test_la_relecture_ne_voit_pas_les_projets_deja_suivis(self):
        """Les lui donner l'inviterait à harmoniser, donc à modifier."""
        fournisseur = ScriptedProvider([DOCUMENT_RANGE])
        set_provider(fournisseur)
        coaching.relire_markdown("des notes en vrac")

        assert fournisseur.calls[0]["prompt"].strip().endswith("des notes en vrac")
