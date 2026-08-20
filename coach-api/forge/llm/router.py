"""Quel modèle pour quelle tâche, et à quel effort (SPEC §5.6).

Deux modèles, choisis sur un critère unique : **la tâche demande-t-elle un
jugement ou une transformation ?**

Structurer des notes brutes en trois phrases est une transformation — l'entrée
contient déjà la réponse. Décider ce qu'on fait ce soir à 21h30 quand on est
fatigué, en pesant l'engagement hebdomadaire, le retard relatif et l'état du
boss, est un jugement : c'est là que la qualité du modèle se voit, et c'est le
moment où le système gagne ou perd sa crédibilité.

L'effort suit la même logique. Il est réglé bas sur les tâches mécaniques parce
qu'y mettre plus ne change rien au résultat, et haut là où la réponse engage la
soirée.

**Le piège du budget de sortie.** Sur Opus 5 le raisonnement est actif par
défaut et ses jetons sont décomptés de ``max_tokens``. Un budget calibré sur la
seule réponse visible fait donc tronquer la réponse *au milieu du
raisonnement* — il ne reste rien à afficher, et l'échec ressemble à une panne
d'API alors que c'est un réglage. Les budgets ci-dessous sont dimensionnés
« raisonnement compris », d'où leur générosité apparente : ce sont des plafonds,
pas des consommations, et un plafond trop haut ne coûte rien tant qu'il n'est
pas atteint.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Task

OPUS = "claude-opus-5"
SONNET = "claude-sonnet-5"

# Ce qu'on réserve au raisonnement, en plus de la réponse visible. La règle est
# simple : un effort élevé pense longtemps, et ce temps se paie en jetons pris
# sur le même budget que la sortie.
RESERVE_RAISONNEMENT = {"low": 1000, "medium": 4000, "high": 8000}


# Le délai d'attente par défaut. Il est court **exprès** : le briefing part
# pendant que l'écran est déjà utilisable, et le §7 interdit de faire attendre
# quoi que ce soit sur le chemin critique du soir. Mieux vaut le repli
# déterministe qu'une app qui se fige.
TIMEOUT_DEFAUT = 150


@dataclass(frozen=True)
class Route:
    model: str
    effort: str
    max_tokens: int
    why: str
    # Toutes les tâches n'ont pas la même urgence. Le briefing doit tenir dans
    # l'attente d'un écran ; l'entretien de projet est une séance qu'on ouvre
    # exprès, et il produit un parcours de dix blocs avec leurs ressources —
    # 150 s ne suffisent pas, et l'abandonner à mi-chemin coûte bien plus cher
    # que d'attendre.
    timeout: int = TIMEOUT_DEFAUT
    # Le modèle peut-il aller chercher ses sources ?
    #
    # Réservé à l'entretien, et pour une raison mesurée : une roadmap écrite de
    # mémoire nomme des ressources qui ont changé de prix, d'adresse ou de
    # contenu depuis l'entraînement. C'était l'écart le plus visible avec le
    # même exercice fait dans un chat — celui-ci cherche, et cite. Partout
    # ailleurs le modèle transforme du texte déjà fourni : chercher n'y
    # apporterait rien et coûterait des secondes sur le chemin du soir.
    recherche_web: bool = False

    @property
    def reponse_visible(self) -> int:
        """Ce qui reste pour le texte rendu, une fois le raisonnement payé.

        Sert aux tests plus qu'au code : c'est la grandeur qu'on veut garder
        positive et confortable quand on retouche un budget.
        """
        return self.max_tokens - RESERVE_RAISONNEMENT.get(self.effort, 0)


# Le briefing et l'entretien de projet décident de la soirée ou d'un mois de
# travail : ils passent par le modèle le plus capable. Le reste transforme du
# texte déjà écrit et n'y gagnerait rien.
ROUTES: dict[Task, Route] = {
    Task.BRIEFING: Route(
        model=OPUS,
        effort="high",
        max_tokens=10000,
        why="décide de la soirée — le seul moment où un mauvais choix coûte une session",
    ),
    Task.GARDIEN: Route(
        model=OPUS,
        effort="medium",
        max_tokens=6000,
        why="dernière chance de la soirée, et une seule phrase à écrire : le "
        "jugement porte sur le découpage, pas sur la rédaction",
    ),
    Task.ENTRETIEN_PROJET: Route(
        model=OPUS,
        effort="high",
        max_tokens=24000,
        # La recherche ajoute des allers-retours avant le premier mot écrit.
        # Sept minutes pour un parcours de deux ans documenté restent un bon
        # échange : c'est une séance qu'on ouvre exprès, pas un écran d'attente.
        timeout=600,
        recherche_web=True,
        why="une roadmap floue se paie pendant des semaines (§4.5), et une "
        "ressource citée de mémoire a pu changer de prix ou d'adresse",
    ),
    Task.IMPORT_MARKDOWN: Route(
        model=SONNET,
        effort="medium",
        max_tokens=12000,
        timeout=240,
        why="relire un markdown déjà écrit pour le remettre au format est une "
        "transformation : la réponse est entièrement dans l'entrée",
    ),
    Task.REVUE_HEBDO: Route(
        model=OPUS,
        effort="high",
        max_tokens=16000,
        timeout=300,
        why="analyse dialoguée : il faut arriver avec les constats déjà faits (§5.3)",
    ),
    Task.BILAN: Route(
        model=SONNET,
        effort="low",
        max_tokens=2500,
        why="une phrase de constat sur des chiffres déjà calculés, et elle est facultative",
    ),
    Task.DEBRIEF: Route(
        model=SONNET,
        effort="low",
        max_tokens=3000,
        why="structurer des notes déjà écrites — la réponse est dans l'entrée",
    ),
    Task.ASSISTANT: Route(
        model=OPUS,
        effort="high",
        max_tokens=16000,
        why="il agit sur l'app : une action mal comprise se voit dans les données, "
        "pas dans un texte qu'on relit",
    ),
    Task.DECOUPAGE: Route(
        model=SONNET,
        effort="high",
        max_tokens=20000,
        timeout=300,
        # Ce tour arrive des mois après l'entretien qui a écrit le bloc. Une
        # adresse, un découpage de chapitres, un prix ont eu le temps de
        # changer, et découper un bloc sur une ressource morte donne dix soirées
        # perdues avant que quiconque s'en aperçoive.
        recherche_web=True,
        why="le bloc est déjà décidé : reste à le rendre faisable, ce qui est "
        "une transformation — mais sur des sources qui ont pu bouger depuis",
    ),
}


def route_for(task: Task) -> Route:
    """La route d'une tâche. Une tâche inconnue prend le chemin prudent."""
    return ROUTES.get(
        task,
        Route(
            model=OPUS,
            effort="high",
            max_tokens=10000,
            why="tâche inconnue : on ne devine pas à la baisse",
        ),
    )
