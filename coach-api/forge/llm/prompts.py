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
