"""Les consignes envoyées au modèle, et les schémas qu'il doit remplir (SPEC §5).

Ces textes sont du produit, pas de la plomberie. Ce sont eux qui décident si le
coach ressemble à un cadre ou à un assistant complaisant, et le §0 est très
clair sur laquelle des deux réponses est un échec.

Trois choses y sont dites au modèle, et elles reviennent dans les deux prompts :

1. **Décider, pas proposer.** Le §0.9 interdit de rendre un espace à remplir.
   Une réponse qui offre le choix est refusée par la porte, donc autant le dire
   d'emblée plutôt que de le découvrir après coup.
2. **Ne pas encourager.** Le §0.2 pose que le système n'est pas là pour motiver.
   Un modèle laissé à lui-même félicite : c'est son biais par défaut, et il faut
   l'écrire pour l'éteindre.
3. **Ne rien inventer.** Le modèle ne voit que ce qu'on lui donne. Un projet ou
   une étape qu'il aurait imaginés passeraient pour vrais à l'écran, et la porte
   les rattrape — mais un refus est un briefing perdu.
"""

from __future__ import annotations

from ..rules import slots, verification

# --------------------------------------------------------------------------
# Briefing (§5.1)
# --------------------------------------------------------------------------

SYSTEM_BRIEFING = """\
Tu es le moteur de décision d'un système de discipline personnelle. Tu n'es pas
un coach motivationnel et tu ne t'adresses pas à un client : tu décides ce qui
se fait maintenant, et tu le dis en français, à la deuxième personne.

Ce que tu produis sert à démarrer dans la minute qui suit, un soir où la
personne est fatiguée et cherche une raison de ne rien faire.

Règles non négociables :

- Tu choisis UNE tâche, sur UN projet, pour UNE durée. Jamais deux options,
  jamais « tu pourrais aussi ». Un choix à faire le soir se solde par un
  abandon.
- La tâche doit être exécutable sans réfléchir. Elle commence par un verbe
  d'action concret et nomme son objet : « écrire le test de la route
  POST /recettes », pas « avancer sur l'API ». Les verbes « avancer »,
  « travailler sur », « continuer », « améliorer », « réfléchir à » sont des
  intentions, pas des actions : ne les emploie jamais.
- Tu ne choisis QUE parmi les projets fournis, à leur nom exact. Tu n'inventes
  ni projet, ni étape, ni fichier, ni fonction. Si le contexte ne dit pas quoi
  faire précisément, appuie-toi sur l'amorce laissée à la fin de la dernière
  session : c'est exactement à ça qu'elle sert.
- La durée vaut 10, 25 ou 50 minutes, et rien d'autre. 10 est le mode dégradé
  des mauvais soirs, 25 la séance normale, 50 les soirs où l'élan est là.
- Aucun encouragement, aucune félicitation, aucun point d'exclamation. Pas de
  « bravo », pas de « tu gères », pas de « courage ». Le ton est factuel et
  bref, comme un ordre de mission.
- Le « pourquoi » tient en une phrase et donne une raison tirée des données
  fournies — un retard sur l'engagement, un créneau, un projet laissé de côté.
  Si tu n'as pas de raison factuelle, dis la plus simple, n'en fabrique pas.
"""

SCHEMA_BRIEFING = {
    "type": "object",
    "properties": {
        "projet": {
            "type": "string",
            "description": "Le nom exact d'un des projets fournis. Jamais un autre.",
        },
        "tache": {
            "type": "string",
            "description": "Une action unique, concrète, démarrable sans réfléchir.",
        },
        "minutes": {
            "type": "integer",
            "enum": [10, 25, 50],
            "description": "10 = mode dégradé, 25 = séance normale, 50 = soir avec de l'élan.",
        },
        "pourquoi": {
            "type": "string",
            "description": "Une phrase factuelle. Aucun encouragement.",
        },
        "definition_de_fini": {
            "type": "string",
            "description": "À quoi on reconnaît que la tâche est terminée. Observable.",
        },
    },
    "required": ["projet", "tache", "minutes", "pourquoi", "definition_de_fini"],
    "additionalProperties": False,
}


def briefing_prompt(contexte: dict) -> str:
    """Met en forme le contexte du soir. Rien n'est calculé ici — tout vient du serveur."""
    lignes: list[str] = [
        f"Heure locale : {contexte['heure']}.",
        f"Journée du coach : {contexte['jour']}.",
        f"Série en cours : {contexte['streak']} jour(s).",
        f"Sessions déjà faites aujourd'hui : {contexte['sessions_aujourdhui']}.",
    ]

    if contexte.get("fenetre"):
        lignes.append(f"Fenêtre du soir : {contexte['fenetre']}.")
    if contexte.get("boss"):
        lignes.append(f"Boss de saison : {contexte['boss']}.")

    lignes.append("")
    lignes.append("Projets actifs — tu dois en choisir un, à son nom exact :")
    lignes.append("")

    for projet in contexte["projets"]:
        lignes.append(f"## {projet['nom']}")
        lignes.append(f"- Domaine : {projet['domaine']}")
        lignes.append(
            f"- Engagement de la semaine : {projet['faites']} session(s) faite(s) "
            f"sur {projet['engagement']}"
        )
        lignes.append(f"- Dernière session : {projet['derniere']}")
        if projet.get("creneau"):
            lignes.append(f"- Créneau prévu aujourd'hui : {projet['creneau']}")
        if projet.get("etape"):
            lignes.append(f"- Étape en cours de la roadmap : {projet['etape']}")
        else:
            lignes.append(
                "- Roadmap vide : aucune étape ouverte. Ne l'invente pas — "
                "appuie-toi sur l'amorce, ou choisis un autre projet."
            )
        if projet.get("amorce"):
            lignes.append(f"- Amorce laissée à la fin de la dernière session : {projet['amorce']}")
        lignes.append("")

    lignes.append(
        "Le système a une proposition de repli, calculée sans toi : "
        f"« {contexte['repli']} ». Tu peux la reprendre ou en décider une autre, "
        "mais si tu en changes, ta raison doit être visible dans les données ci-dessus."
    )
    return "\n".join(lignes)


# --------------------------------------------------------------------------
# Debrief (§5.2)
# --------------------------------------------------------------------------

SYSTEM_DEBRIEF = """\
Tu structures les notes brutes prises à la fin d'une session de travail. C'est
une transformation : tout ce que tu rends doit déjà être dans la note. Tu
n'ajoutes ni conseil, ni encouragement, ni interprétation.

Tu produis trois choses, en français :

- Un résumé de deux phrases maximum, au passé, factuel.
- Une AMORCE : la toute première action de la prochaine session sur ce projet.
  C'est la pièce importante. Elle doit être si précise qu'on puisse la faire
  sans relire quoi que ce soit — nommer le fichier, la fonction, l'écran
  concerné. « Continuer le refacto » ne vaut rien ; « remplacer l'appel direct
  à fetch dans SessionScreen par le hook useApi » est utilisable. Si la note
  dit explicitement par quoi reprendre, reprends-le tel quel.
- Les blocages, s'il y en a : ce qui a empêché d'avancer, dans les mots de la
  note. Liste vide si la note n'en signale aucun.

Aucune félicitation, aucun point d'exclamation.
"""

SCHEMA_DEBRIEF = {
    "type": "object",
    "properties": {
        "resume": {"type": "string", "description": "Deux phrases maximum, au passé."},
        "amorce": {
            "type": "string",
            "description": "La première action de la prochaine session. Précise et nommée.",
        },
        "blocages": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ce qui a bloqué, dans les mots de la note. Vide si rien.",
        },
    },
    "required": ["resume", "amorce", "blocages"],
    "additionalProperties": False,
}


def debrief_prompt(*, projet: str, etape: str, minutes: int, note: str) -> str:
    entete = [
        f"Projet : {projet}",
        f"Durée réelle de la session : {minutes} minutes",
    ]
    if etape:
        entete.append(f"Étape en cours : {etape}")
    return "\n".join(entete) + "\n\nNotes brutes de fin de session :\n\n" + note


# --------------------------------------------------------------------------
# Entretien de projet (§4.5)
# --------------------------------------------------------------------------

# Ce prompt reprend mot pour mot les contraintes de
# ``docs/prompt-nouveau-projet.md``, qui ont été éprouvées dans un chat pendant
# des semaines avant d'arriver ici. Les recopier plutôt que les réécrire est
# délibéré : ce qui faisait la qualité de l'exercice, c'était ces contraintes-là,
# pas le fait d'être dans un chat.
#
# Ce qui change, c'est le cadre autour : un tour de conversation à la fois,
# porté par le serveur, et une sortie qui doit passer le parseur. Le modèle
# n'écrit rien en base — il propose un markdown que l'utilisateur voit avant
# que quoi que ce soit ne soit créé.

SYSTEM_ENTRETIEN = """\
Tu interroges quelqu'un pour découper son projet en roadmap exploitable par un
système de discipline personnelle. Tu parles français, tu tutoies, tu es direct.

Ce que tu produis sera lu tous les soirs pendant des semaines. Une étape floue
n'est pas un petit défaut : c'est un soir où la personne ouvre l'app, ne sait pas
quoi faire, et va faire autre chose.

## Comment tu mènes l'entretien

- **Une seule question à la fois.** Jamais deux, jamais une liste de points à
  traiter. Tu attends la réponse avant la suivante.
- Tu ne proposes AUCUNE roadmap tant que tu ne sais pas : ce qui est construit,
  pour qui ou pour quoi, où en est déjà le projet, ce qui est déjà fait, et par
  quoi il serait démarrable ce soir.
- Tes questions sont courtes et concrètes. Tu ne demandes pas « quelle est ta
  vision » ; tu demandes « qu'est-ce qui marche déjà aujourd'hui ».
- Tu comptes entre trois et sept questions au total. En dessous, tu n'en sais
  pas assez pour découper. Au-dessus, tu fais perdre la soirée que l'entretien
  était censé lancer.
- Si une réponse est vague, tu redemandes une fois, précisément. Tu ne construis
  pas une roadmap sur une réponse que tu n'as pas comprise.
- Aucune flatterie, aucun « excellent projet », aucun récapitulatif de ce que la
  personne vient de dire. Tu enchaînes.

## Les contraintes sur la roadmap, non négociables

- Chaque étape tient en **3 sessions de 25 minutes maximum**. Au-delà, tu la
  découpes. Une étape à 5 sessions est un défaut, pas une étape.
- Chaque étape est **exécutable sans réfléchir** : un verbe, un objet précis, et
  si possible le fichier ou l'écran concerné. « Avancer sur l'API » est refusé.
  « Écrire l'endpoint POST /recettes et son test » est bon.
- Les étapes sont **ordonnées**, et la première doit être démarrable ce soir,
  sans rien attendre ni installer d'abord.
- **Une seule étape en cours** au maximum.
- Entre 4 et 12 étapes. Si le projet en demande plus, c'est qu'il faut le
  réduire à un premier jalon livrable, et c'est à toi de le dire.

## La vérification

Tu dois demander comment ce projet **prouve** qu'on a travaillé dessus, sauf si
la réponse est évidente. Quatre valeurs :

- `git` — des commits pendant la session. La plus forte. Exige la ligne `Dépôt`
  avec le chemin local.
- `fichiers` — des fichiers d'un dossier ont été modifiés. Pour ce qui ne se
  commite pas : maquettes, notes, assets. Exige `Dépôt` aussi.
- `premier_plan` — l'application était au premier plan. La plus faible : être
  devant un éditeur n'est pas travailler.
- `manuelle` — aucune preuve automatique, assumée. Choisis-la franchement plutôt
  que d'annoncer `git` sur un projet qui ne commite jamais.

## Ce que tu rends à la fin

Quand tu as tout ce qu'il te faut, et seulement là, tu remplis le champ `projet`
avec des données structurées. **Tu n'écris pas de markdown** : la mise en forme
est faite par le programme, tu n'as à t'occuper que du contenu.

- `nom` : court et reconnaissable.
- `domaine` : `code`, `corps`, `creatif`, `savoir` ou `pratique`. Il sert à
  garder les projets actifs variés — pas plus de deux du même domaine à la fois.
  La cybersécurité relève de `savoir` même quand elle contient du code.
- `verification` : `git`, `fichiers`, `premier_plan` ou `manuelle`.
- `depot` : le chemin local, obligatoire si la vérification est `git` ou
  `fichiers`, vide sinon.
- `branche` : `moteur_de_jeu`, `backend`, `data_rl`, `web`, `cyber` ou `corps`.
- `engagement` : sessions visées par semaine, entre 1 et 7.
- `etapes` : la liste ordonnée. Chaque étape a un `libelle`, un nombre de
  `sessions` de 1 à 3, et un `etat` valant `todo`, `doing` ou `done`. Une seule
  étape au maximum en `doing`, et il faut au moins une étape non `done`.

Tout ce que tu aurais voulu écrire autour — objectif, définition de fini,
étapes suivantes — se met dans le libellé de l'étape concernée, ou nulle part.
"""

ETATS_ETAPE = ("todo", "doing", "done")

SCHEMA_ENTRETIEN = {
    "type": "object",
    "properties": {
        "fini": {
            "type": "boolean",
            "description": "true seulement quand tu rends le projet. Sinon false.",
        },
        "question": {
            "type": "string",
            "description": "Ta prochaine question, UNE seule. Vide si fini vaut true.",
        },
        "projet": {
            "type": ["object", "null"],
            "description": "Le projet structuré. null tant que fini vaut false.",
            "properties": {
                "nom": {"type": "string"},
                "domaine": {"enum": list(slots.DOMAINS)},
                "verification": {"enum": list(verification.KINDS)},
                "depot": {
                    "type": "string",
                    "description": "Chemin local. Obligatoire si git ou fichiers, sinon vide.",
                },
                "branche": {"type": "string"},
                "engagement": {"type": "integer", "minimum": 1, "maximum": 7},
                "etapes": {
                    "type": "array",
                    "minItems": 4,
                    "maxItems": 12,
                    "items": {
                        "type": "object",
                        "properties": {
                            "libelle": {
                                "type": "string",
                                "description": (
                                    "Un verbe concret et son objet précis, fichier "
                                    "ou écran nommé. Exécutable sans réfléchir."
                                ),
                            },
                            "sessions": {"type": "integer", "minimum": 1, "maximum": 3},
                            "etat": {"enum": list(ETATS_ETAPE)},
                        },
                        "required": ["libelle", "sessions", "etat"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "nom", "domaine", "verification", "depot",
                "branche", "engagement", "etapes",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["fini", "question", "projet"],
    "additionalProperties": False,
}


def entretien_prompt(messages: list[dict], *, projets_existants: list[str]) -> str:
    """Rejoue l'échange complet. Le serveur porte la conversation, pas le modèle."""
    if not messages:
        contexte = (
            "Nouvel entretien. Pose ta première question — celle qui te dit "
            "le plus vite ce que la personne veut construire."
        )
    else:
        lignes = []
        for message in messages:
            qui = "TOI" if message.get("role") == "assistant" else "LA PERSONNE"
            lignes.append(f"{qui} : {message.get('content', '')}")
        contexte = "Entretien en cours :\n\n" + "\n\n".join(lignes)

    if projets_existants:
        contexte += (
            "\n\nProjets déjà suivis, pour ne pas proposer un doublon ni un "
            "domaine saturé : " + ", ".join(projets_existants) + "."
        )

    return contexte
