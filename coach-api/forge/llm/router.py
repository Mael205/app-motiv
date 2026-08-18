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


@dataclass(frozen=True)
class Route:
    model: str
    effort: str
    max_tokens: int
    why: str

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
        why="une roadmap floue se paie pendant des semaines (§4.5)",
    ),
    Task.REVUE_HEBDO: Route(
        model=OPUS,
        effort="high",
        max_tokens=16000,
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
        effort="medium",
        max_tokens=8000,
        why="découper une étape est mécanique une fois le contexte donné",
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
