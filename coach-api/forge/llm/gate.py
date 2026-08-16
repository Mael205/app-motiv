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


def gate(task: Task, payload: dict, **contexte) -> dict:
    """Applique la porte correspondant à la tâche.

    Une tâche sans porte passe telle quelle — mais elle est nommée ici, pour
    qu'ajouter une tâche oblige à se demander ce qui la rendrait inutilisable.
    """
    if task is Task.BRIEFING:
        return check_briefing(payload, projets_connus=contexte["projets_connus"])
    if task is Task.DEBRIEF:
        return check_debrief(payload)
    return payload
