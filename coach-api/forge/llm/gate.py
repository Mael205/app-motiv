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

# Le biais par défaut d'un modèle est d'encourager, et le §17 l'interdit — « pas
# de bravo, tu es incroyable », et pas un mot de jugement sur ce qui n'a pas été
# fait. C'est au gardien que ça coûte le plus cher : c'est la notification d'un
# soir raté, et un reproche y fait fermer l'app pour de bon.
MOTS_DE_MORALE = (
    "allez",
    "courage",
    "bravo",
    "tu devrais",
    "il faut vraiment",
    "encore temps",
    "au moins ça",
    "ne rien faire",
)

# Le §17 : « pas de bravo, tu es incroyable ». Ces mots-là ne coûtent rien à
# l'écran, mais dans un bilan lu par un tiers ils décrédibilisent le suivant —
# un compte-rendu qui félicite chaque semaine ne dit plus rien quand la semaine
# a vraiment été bonne.
MOTS_DE_FELICITATION = (
    "bravo",
    "félicitations",
    "felicitations",
    "impressionnant",
    "excellent",
    "superbe",
    "magnifique",
    "continue comme ça",
    "fier",
)

# Le vocabulaire de la bonne résolution. Distinct des verbes flous ci-dessus :
# « avancer le créneau du mardi à 19h30 » est parfaitement concret, alors que
# « avancer sur l'API » ne l'est pas. Ce qui disqualifie une résolution n'est pas
# son verbe, c'est qu'elle ne se vérifie pas — personne ne peut dire dimanche
# prochain s'il a « été plus régulier ».
RESOLUTIONS = (
    "être plus",
    "etre plus",
    "plus régulier",
    "plus regulier",
    "essayer",
    "continuer",
    "faire mieux",
    "faire plus",
    "davantage",
    "s'y remettre",
    "tenir bon",
    "rester motivé",
    "rester motive",
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

# Un gardien se lit sur un écran verrouillé. Android coupe autour de cette
# longueur, et une tâche coupée au milieu ne se démarre pas. C'est aussi le seul
# indice mécanique qu'on a d'une tâche trop grosse pour dix minutes : ce qui
# demande trois lignes à décrire n'en est pas une.
LONGUEUR_MAXIMALE_GARDIEN = 120

# Le §4.7 demande « une phrase de synthèse ». Deux cents caractères en laissent
# une vraie, et refusent le paragraphe qui commenterait la semaine.
LONGUEUR_MAXIMALE_BILAN = 200

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


def check_gardien(payload: dict) -> dict:
    """Valide la tâche de dix minutes du gardien du soir (§5.4).

    Mêmes refus que le briefing sur le flou et les listes — c'est le même
    diagnostic —, plus deux contraintes propres à la notification : elle doit
    tenir sur un écran verrouillé, et elle ne doit pas faire la morale. Un
    gardien qui commente la journée au lieu de donner un geste transforme le
    dernier rappel du soir en reproche, et le §17 l'interdit.

    Le refus est ici moins coûteux qu'ailleurs : le repli déterministe existe,
    il est juste moins bien découpé.
    """
    tache = _texte(payload, "tache")

    if not tache:
        raise QualityGateFailed("gardien sans tâche", payload)
    if len(tache) < LONGUEUR_MINIMALE:
        raise QualityGateFailed(f"tâche trop courte pour être exécutable : « {tache} »", payload)
    if len(tache) > LONGUEUR_MAXIMALE_GARDIEN:
        raise QualityGateFailed(
            f"tâche de {len(tache)} caractères : trop longue pour une notification, "
            "et probablement trop grosse pour dix minutes (§5.4)",
            payload,
        )

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
                "le gardien propose plusieurs pistes au lieu d'en choisir une (§0.9)",
                payload,
            )

    if re.search(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s", tache):
        raise QualityGateFailed("la tâche est une liste, pas une action unique (§0.9)", payload)

    if "!" in tache:
        raise QualityGateFailed("un gardien n'a pas de point d'exclamation (§17)", payload)

    for mot in MOTS_DE_MORALE:
        if re.search(rf"\b{re.escape(mot)}\b", bas):
            raise QualityGateFailed(
                f"« {mot} » est un jugement sur la journée, pas un geste à faire (§17)",
                payload,
            )

    return {"tache": tache}


def check_revue(payload: dict) -> dict:
    """Valide le compte-rendu de la revue du dimanche (§13.3).

    Deux refus, et ce sont les deux façons connues de rendre une revue inutile :

    - **plusieurs choses à changer.** Le §13.3 en demande une seule, et la raison
      est mécanique : trois changements simultanés ne se tiennent pas une
      semaine, et n'en tenir aucun fait arrêter les revues ;
    - **une intention vague.** « Être plus régulier » ne se vérifie pas dimanche
      prochain, donc ne se corrige jamais. C'est le même défaut que le briefing
      flou du §4.5, au niveau de la semaine.
    """
    seule = _texte(payload, "seule_chose")
    if not seule:
        raise QualityGateFailed("revue sans chose à changer", payload)
    if len(seule) < LONGUEUR_MINIMALE:
        raise QualityGateFailed(f"changement trop vague : « {seule} »", payload)

    bas = seule.lower()

    for resolution in RESOLUTIONS:
        if resolution in bas:
            raise QualityGateFailed(
                f"« {resolution} » est une résolution, pas un changement : "
                "ça ne se vérifie pas dimanche prochain",
                payload,
            )

    if re.search(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s", seule):
        raise QualityGateFailed("le §13.3 demande UNE chose à changer, pas une liste", payload)

    for marqueur in (" et aussi ", " ainsi que ", " puis ", " également "):
        if marqueur in f" {bas} ":
            raise QualityGateFailed(
                "deux changements au lieu d'un : trois choses à la fois n'en font aucune",
                payload,
            )

    for mot in MOTS_DE_MORALE + MOTS_DE_FELICITATION:
        if re.search(rf"\b{re.escape(mot)}\b", f"{bas} {_texte(payload, 'n_a_pas_marche').lower()}"):
            raise QualityGateFailed(
                f"« {mot} » juge la personne : la revue décrit des soirées (§17)", payload
            )

    return {
        "a_marche": _texte(payload, "a_marche"),
        "n_a_pas_marche": _texte(payload, "n_a_pas_marche"),
        "seule_chose": seule,
    }


def check_bilan(payload: dict) -> dict:
    """Valide la phrase envoyée à l'ami (§4.7).

    Le lecteur n'est pas l'utilisateur, et c'est ce qui change tout : un
    encouragement rend le bilan suivant moins crédible, un reproche fait d'un
    ami un juge. La porte refuse donc le registre avant le contenu.

    Elle ne vérifie pas ici l'absence des données interdites — ``weekly`` le
    fait sur le texte **complet**, juste avant l'envoi, parce que c'est là que
    la fuite compterait.
    """
    phrase = _texte(payload, "phrase")

    if not phrase:
        raise QualityGateFailed("bilan sans phrase", payload)
    if len(phrase) > LONGUEUR_MAXIMALE_BILAN:
        raise QualityGateFailed(
            f"phrase de {len(phrase)} caractères : le §4.7 en demande une, pas un paragraphe",
            payload,
        )
    if "!" in phrase:
        raise QualityGateFailed("un bilan n'a pas de point d'exclamation (§17)", payload)

    bas = phrase.lower()
    for mot in MOTS_DE_MORALE + MOTS_DE_FELICITATION:
        if re.search(rf"\b{re.escape(mot)}\b", bas):
            raise QualityGateFailed(
                f"« {mot} » : le bilan constate, il ne juge pas (§4.7, §17)", payload
            )

    return {"phrase": phrase}


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


# Ce qu'un assistant dit quand il croit avoir agi. C'est le mode de
# défaillance propre à cette tâche : le modèle propose, mais son biais naturel
# est de raconter qu'il a fait — et quelqu'un qui lit « c'est réglé » ne clique
# pas sur « Appliquer », donc la modification n'a jamais lieu et l'app paraît
# cassée. Un faux « c'est fait » coûte plus cher qu'un refus.
FAUX_ACCOMPLI = (
    "c'est fait",
    "c'est réglé",
    "c'est bon, j'ai",
    "j'ai renommé",
    "j'ai créé",
    "j'ai fusionné",
    "j'ai supprimé",
    "j'ai archivé",
    "j'ai modifié",
    "j'ai changé",
    "j'ai appliqué",
    "j'ai mis à jour",
    "voilà, c'est",
)

LONGUEUR_MAXIMALE_ASSISTANT = 700


def check_assistant(payload: dict, *, cles_connues: tuple[str, ...]) -> dict:
    """Valide un tour d'assistant : le texte, et la forme des actions proposées.

    La porte ne juge pas si l'action est *pertinente* — ça, seul l'aperçu
    avant/après le montre, et c'est à l'utilisateur d'en décider. Elle refuse
    trois choses : le faux accompli, le ton, et une clé d'action hors
    catalogue.

    La clé hors catalogue ne devrait jamais arriver, l'énumération du schéma la
    rendant impossible. On la vérifie quand même : le jour où un backend
    n'applique pas le schéma — un modèle local, un mode dégradé —, c'est cette
    ligne qui tient le mur, et elle ne coûte rien.
    """
    texte = _texte(payload, "reponse")
    if not texte:
        raise QualityGateFailed("réponse vide", payload)
    if len(texte) > LONGUEUR_MAXIMALE_ASSISTANT:
        raise QualityGateFailed(
            f"réponse de {len(texte)} caractères : le détail va dans les cartes "
            "d'action, pas dans le paragraphe",
            payload,
        )

    bas = texte.lower()
    for faux in FAUX_ACCOMPLI:
        if faux in bas:
            raise QualityGateFailed(
                f"l'assistant dit « {faux} » alors que rien n'est appliqué : "
                "il propose, l'utilisateur applique",
                payload,
            )
    for mot in MOTS_DE_FELICITATION:
        if mot in bas:
            raise QualityGateFailed(f"félicitation interdite (§17) : « {mot} »", payload)

    actions = payload.get("actions")
    if actions is None:
        actions = []
    if not isinstance(actions, list):
        raise QualityGateFailed("« actions » n'est pas une liste", payload)

    propres = []
    for action in actions:
        if not isinstance(action, dict):
            raise QualityGateFailed("action illisible", payload)
        cle = action.get("action")
        if cle not in cles_connues:
            raise QualityGateFailed(f"action hors catalogue : « {cle} »", payload)
        params = action.get("params")
        propres.append({"action": cle, "params": params if isinstance(params, dict) else {}})

    return {"reponse": texte, "actions": propres}


def gate(task: Task, payload: dict, **contexte) -> dict:
    """Applique la porte correspondant à la tâche.

    Une tâche sans porte passe telle quelle — mais elle est nommée ici, pour
    qu'ajouter une tâche oblige à se demander ce qui la rendrait inutilisable.
    """
    if task is Task.BRIEFING:
        return check_briefing(payload, projets_connus=contexte["projets_connus"])
    if task is Task.GARDIEN:
        return check_gardien(payload)
    if task is Task.BILAN:
        return check_bilan(payload)
    if task is Task.REVUE_HEBDO:
        return check_revue(payload)
    if task is Task.DEBRIEF:
        return check_debrief(payload)
    if task is Task.ENTRETIEN_PROJET:
        return check_entretien(payload)
    if task is Task.ASSISTANT:
        return check_assistant(payload, cles_connues=contexte["cles_connues"])
    return payload
