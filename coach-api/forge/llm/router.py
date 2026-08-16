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
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import Task

OPUS = "claude-opus-5"
SONNET = "claude-sonnet-5"


@dataclass(frozen=True)
class Route:
    model: str
    effort: str
    max_tokens: int
    why: str


# Le briefing et l'entretien de projet décident de la soirée ou d'un mois de
# travail : ils passent par le modèle le plus capable. Le reste transforme du
# texte déjà écrit et n'y gagnerait rien.
ROUTES: dict[Task, Route] = {
    Task.BRIEFING: Route(
        model=OPUS,
        effort="high",
        max_tokens=2000,
        why="décide de la soirée — le seul moment où un mauvais choix coûte une session",
    ),
    Task.ENTRETIEN_PROJET: Route(
        model=OPUS,
        effort="high",
        max_tokens=4000,
        why="une roadmap floue se paie pendant des semaines (§4.5)",
    ),
    Task.REVUE_HEBDO: Route(
        model=OPUS,
        effort="high",
        max_tokens=4000,
        why="analyse dialoguée : il faut arriver avec les constats déjà faits (§5.3)",
    ),
    Task.DEBRIEF: Route(
        model=SONNET,
        effort="low",
        max_tokens=1000,
        why="structurer des notes déjà écrites — la réponse est dans l'entrée",
    ),
    Task.DECOUPAGE: Route(
        model=SONNET,
        effort="medium",
        max_tokens=1500,
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
            max_tokens=2000,
            why="tâche inconnue : on ne devine pas à la baisse",
        ),
    )
