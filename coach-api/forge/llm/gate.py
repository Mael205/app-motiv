"""La porte de qualité (SPEC §5.6, §0.9, §4.5).

Le §5.6 la rend obligatoire, mais ne dit pas ce qu'elle vérifie. Ce module
répond à cette question, et la réponse vient du §0.9 :

> Le système doit **toujours présenter la prochaine action déjà décidée**,
> jamais un espace vide à remplir.

Un briefing qui rend « tu pourrais avancer sur le bot, ou finir l'écran de fin »
n'est donc pas une réponse imparfaite : c'est **le mode de défaillance que le
produit existe pour empêcher**. Un soir de fatigue, une liste à arbitrer se
solde par YouTube. La porte refuse ces réponses et laisse l'appelant retomber
sur la proposition déterministe, qui est peut-être moins fine mais qui décide.

Deuxième critère, du §4.5 : une tâche doit être **exécutable sans réfléchir**.
« Avancer sur l'API » est refusé, « écrire l'endpoint POST /recettes et son
test » est bon. La spec traite une étape floue comme un défaut du système, pas
comme un état normal — la porte applique ça au briefing.

La porte ne réécrit jamais une réponse. Elle accepte ou refuse, avec un motif :
une porte qui rafistole masque la dérive du modèle au lieu de la révéler.
"""

from __future__ import annotations

import re

from .base import QualityGateFailed, Task

# Verbes qui décrivent une intention, pas une action. Le §4.5 les refuse
# explicitement dans une roadmap ; un briefing n'a pas de raison d'être plus
# permissif, puisqu'il sert à démarrer dans la minute.
VERBES_FLOUS = (
    "avancer",
    "travailler sur",
    "continuer",
    "poursuivre",
    "regarder",
    "explorer",
    "réfléchir",
    "reflechir",
    "améliorer",
    "ameliorer",
    "peaufiner",
    "s'occuper",
)

# Marqueurs d'une réponse qui propose plusieurs pistes au lieu d'en choisir une.
MARQUEURS_DE_LISTE = (
    " ou bien ",
    " sinon ",
    " au choix",
    " tu peux soit ",
    " soit ",
)

DUREES_AUTORISEES = (10, 25, 50)
LONGUEUR_MINIMALE = 15

# Les bornes du §4.5. En dessous de quatre étapes, un projet n'est pas découpé :
# il est renommé en quatre morceaux. Au-delà de douze, la roadmap ne se relit
# plus, et le vrai geste est de réduire le projet à un premier jalon livrable.
MIN_ETAPES = 4
MAX_ETAPES = 12

# Au-delà, ce n'est plus une question mais un questionnaire. Deux sont tolérés
# parce qu'une question française en contient souvent une seconde de précision
# — « c'est quoi, et pourquoi maintenant ? » se répond d'un bloc.
MAX_INTERROGATIONS = 2


def _texte(payload: dict, cle: str) -> str:
    valeur = payload.get(cle)
    return valeur.strip() if isinstance(valeur, str) else ""


def check_briefing(payload: dict, *, projets_connus: set[str]) -> dict:
    """Valide un briefing. Lève ``QualityGateFailed`` avec le motif exact.

    ``projets_connus`` sont les noms des projets réellement actifs : un briefing
    qui nomme un projet inexistant est une hallucination, et l'afficher
    coûterait plus cher que ne rien afficher.
    """
    tache = _texte(payload, "tache")
    projet = _texte(payload, "projet")

    if not tache:
        raise QualityGateFailed("briefing sans tâche", payload)
    if not projet:
        raise QualityGateFailed("briefing sans projet", payload)

    if projet not in projets_connus:
        raise QualityGateFailed(
            f"projet « {projet} » inconnu — les projets actifs sont : "
            + ", ".join(sorted(projets_connus)),
            payload,
        )

    minutes = payload.get("minutes")
    if minutes not in DUREES_AUTORISEES:
        raise QualityGateFailed(
            f"durée {minutes!r} hors des trois autorisées {DUREES_AUTORISEES} (§4.1)",
            payload,
        )

    if len(tache) < LONGUEUR_MINIMALE:
        raise QualityGateFailed(f"tâche trop courte pour être exécutable : « {tache} »", payload)

    bas = tache.lower()

    for flou in VERBES_FLOUS:
        if bas.startswith(flou) or f" {flou} " in bas:
            raise QualityGateFailed(
                f"tâche floue : « {flou} » décrit une intention, pas une action (§4.5)",
                payload,
            )

    for marqueur in MARQUEURS_DE_LISTE:
        if marqueur in f" {bas} ":
            raise QualityGateFailed(
                "le briefing propose plusieurs pistes au lieu d'en choisir une (§0.9)",
                payload,
            )

    # Une tâche unique ne s'énumère pas. Des puces ou une numérotation trahissent
    # une liste déguisée en phrase.
    if re.search(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s", tache):
        raise QualityGateFailed("la tâche est une liste, pas une action unique (§0.9)", payload)

    return {
        "projet": projet,
        "tache": tache,
        "minutes": minutes,
        "pourquoi": _texte(payload, "pourquoi"),
        "definition_de_fini": _texte(payload, "definition_de_fini"),
    }


def check_debrief(payload: dict) -> dict:
    """Valide un debrief structuré (§5.2).

    L'amorce est le seul champ dont l'absence est fatale : le §11.3 en fait le
    prix payé pour le démarrage à froid de la prochaine session.
    """
    amorce = _texte(payload, "amorce")
    if not amorce:
        raise QualityGateFailed("debrief sans amorce — le §11.3 la rend obligatoire", payload)
    if len(amorce) < LONGUEUR_MINIMALE:
        raise QualityGateFailed(f"amorce trop vague pour démarrer : « {amorce} »", payload)

    bas = amorce.lower()
    for flou in VERBES_FLOUS:
        if bas.startswith(flou):
            raise QualityGateFailed(
                f"amorce floue : « {flou} » ne se démarre pas un soir de fatigue (§11.3)",
                payload,
            )

    blocages = payload.get("blocages")
    return {
        "resume": _texte(payload, "resume"),
        "amorce": amorce,
        "blocages": [b for b in blocages if isinstance(b, str)] if isinstance(blocages, list) else [],
    }


def check_entretien(payload: dict) -> dict:
    """Valide un tour d'entretien de projet (§4.5).

    Deux formes possibles, et une seule des deux à la fois : une question, ou un
    projet. Un modèle qui rendrait les deux aurait décidé à la place de
    l'utilisateur qu'il en savait assez.

    **Le modèle ne rend plus de markdown, il rend des champs.** Trois essais
    réels ont montré qu'il produit régulièrement un document plus agréable à
    lire et inexploitable : métadonnées en gras, étapes numérotées, sections en
    trop. Le parseur y perdait la vérification et le chemin du dépôt sans rien
    signaler — on aurait créé un projet qui se croit vérifié sans l'être, ce que
    le §6 traite comme pire que le manuel assumé. Trois tours de reproche n'ont
    pas corrigé le tir, et c'était la bonne leçon : une grammaire ne se fiabilise
    pas en la répétant plus fort.

    Le markdown est donc écrit **ici**, par ``roadmap_import.render``, à partir
    de champs validés. Le format est juste par construction, et il ne reste à
    contrôler que ce qu'un schéma ne sait pas dire : qu'une étape soit une action
    et pas une intention.
    """
    fini = bool(payload.get("fini"))
    question = _texte(payload, "question")
    projet = payload.get("projet")
    if not isinstance(projet, dict):
        projet = None

    if not fini:
        if not question:
            raise QualityGateFailed("tour d'entretien sans question ni projet", payload)
        if projet:
            raise QualityGateFailed(
                "le modèle pose une question ET rend un projet : il faut choisir",
                payload,
            )
        # Une question doit en être une seule — mais « c'est quoi, et pourquoi
        # maintenant ? » en est une seule, en français normal. Le seuil est donc
        # placé sur le vrai défaut, le questionnaire, et pas sur la ponctuation.
        #
        # Réglage corrigé après un essai réel : la version stricte refusait des
        # questions parfaitement bonnes, et comme l'entretien n'a pas de repli,
        # chaque refus coûtait la création du projet entière.
        if question.count("?") > MAX_INTERROGATIONS:
            raise QualityGateFailed(
                "l'entretien pose une question à la fois, pas un questionnaire",
                payload,
            )
        if re.search(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s", question):
            raise QualityGateFailed(
                "la question est une liste de points à traiter, pas une question",
                payload,
            )
        return {"fini": False, "question": question, "markdown": ""}

    if not projet:
        raise QualityGateFailed("entretien déclaré fini sans projet", payload)

    from ..rules import roadmap_import, slots, verification

    nom = str(projet.get("nom") or "").strip()
    if not nom:
        raise QualityGateFailed("le projet n'a pas de nom", payload)

    domaine = str(projet.get("domaine") or "").strip()
    if domaine not in slots.DOMAINS:
        raise QualityGateFailed(
            f"domaine « {domaine} » inconnu. Choisis parmi : {', '.join(slots.DOMAINS)}",
            payload,
        )

    verif = str(projet.get("verification") or "").strip()
    if verif not in verification.KINDS:
        raise QualityGateFailed(
            f"vérification « {verif} » inconnue. Choisis parmi : "
            + ", ".join(verification.KINDS),
            payload,
        )

    depot = str(projet.get("depot") or "").strip()
    pret = verification.readiness(verif, has_path=bool(depot))
    if not pret.ready:
        # Le §6 est catégorique : un projet qui se croit vérifié sans l'être est
        # pire qu'un projet en déclaration manuelle assumée.
        raise QualityGateFailed(
            f"{pret.detail} Donne le chemin du dépôt, ou passe la vérification "
            "en « manuelle » — annoncer une preuve qu'on n'a pas est pire que "
            "l'assumer (§6)",
            payload,
        )

    etapes = projet.get("etapes")
    if not isinstance(etapes, list):
        etapes = []

    if len(etapes) < MIN_ETAPES:
        raise QualityGateFailed(
            f"{len(etapes)} étape(s) seulement. Découpe-les en au moins "
            f"{MIN_ETAPES} étapes de 1 à 3 sessions chacune (§4.5)",
            payload,
        )
    if len(etapes) > MAX_ETAPES:
        raise QualityGateFailed(
            f"{len(etapes)} étapes, maximum {MAX_ETAPES}. Ne garde QUE le premier "
            f"jalon livrable et supprime le reste — rends au plus {MAX_ETAPES} "
            "étapes. La suite sera ajoutée quand ce jalon sera fini (§4.5)",
            payload,
        )

    ouvertes = [e for e in etapes if e.get("etat") != "done"]
    if not ouvertes:
        raise QualityGateFailed(
            "toutes les étapes sont faites. Laisse au moins une étape en « todo » "
            "ou « doing » : un projet actif doit avoir par quoi commencer (§4.5)",
            payload,
        )

    en_cours = [e for e in etapes if e.get("etat") == "doing"]
    if len(en_cours) > 1:
        raise QualityGateFailed(
            f"{len(en_cours)} étapes en « doing ». Une seule étape courante rend "
            "la proposition du soir nette (§4.5)",
            payload,
        )

    # Le point qui compte le plus, et le seul qu'un schéma ne sait pas exprimer.
    # Une étape floue se relit tous les soirs pendant des semaines, et c'est le
    # soir où l'on ne sait pas quoi faire qu'on fait autre chose.
    for etape in etapes:
        libelle = str(etape.get("libelle") or "").strip()
        if len(libelle) < LONGUEUR_MINIMALE:
            raise QualityGateFailed(
                f"l'étape « {libelle} » est trop courte pour être exécutable. "
                "Nomme le fichier, l'écran ou la fonction concernée (§4.5)",
                payload,
            )
        bas = libelle.lower()
        for flou in VERBES_FLOUS:
            if bas.startswith(flou) or f" {flou} " in bas:
                raise QualityGateFailed(
                    f"l'étape « {libelle} » est floue : « {flou} » décrit une "
                    "intention, pas une action. Réécris-la avec un verbe concret "
                    "et l'objet précis, fichier ou écran nommé (§4.5)",
                    payload,
                )

    markdown = roadmap_import.render(projet)

    # Ceinture et bretelles : le markdown qu'on vient d'écrire doit se relire.
    # Si l'aller-retour casse un jour, il vaut mieux l'apprendre ici que devant
    # un projet créé de travers.
    relu = roadmap_import.parse(markdown)
    if not relu.valid:  # pragma: no cover - garde un invariant, pas un cas réel
        raise QualityGateFailed(
            "le markdown rendu n'est pas relisible : " + " ; ".join(relu.warnings),
            payload,
        )

    return {"fini": True, "question": "", "markdown": markdown, "parsed": relu}


def gate(task: Task, payload: dict, **contexte) -> dict:
    """Applique la porte correspondant à la tâche.

    Une tâche sans porte passe telle quelle — mais elle est nommée ici, pour
    qu'ajouter une tâche oblige à se demander ce qui la rendrait inutilisable.
    """
    if task is Task.BRIEFING:
        return check_briefing(payload, projets_connus=contexte["projets_connus"])
    if task is Task.DEBRIEF:
        return check_debrief(payload)
    if task is Task.ENTRETIEN_PROJET:
        return check_entretien(payload)
    return payload
