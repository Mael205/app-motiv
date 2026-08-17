"""L'abstraction du fournisseur de modèle, et sa porte de qualité (SPEC §5.6).

Le §5.6 impose deux choses : un backend **hybride local/distant**, et une
**porte de qualité obligatoire**. L'abstraction existe pour que le reste du code
ne sache jamais quel modèle a répondu — seulement si la réponse est utilisable.

La porte n'est pas une politesse. Le §0.9 dit que le système doit toujours
présenter *une seule action déjà décidée*, jamais un espace à remplir. Un
briefing qui rend trois pistes possibles est donc un **échec**, pas une réponse
imparfaite : il faut le refuser et retomber sur la proposition déterministe
plutôt que d'afficher une liste à arbitrer un soir de fatigue.

C'est pour ça que la porte vit ici, dans l'abstraction, et pas dans l'appelant :
un fournisseur qu'on brancherait plus tard — un modèle local via Ollama — passe
exactement par le même contrôle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Task(str, Enum):
    """Ce qu'on demande au modèle. Détermine le modèle appelé (voir ``router``).

    La distinction n'est pas cosmétique : elle sépare ce qui demande un
    **jugement** de ce qui demande une **transformation**. Résumer des notes en
    trois phrases est mécanique ; décider ce qu'on fait ce soir à 21h quand on
    est fatigué ne l'est pas.
    """

    BRIEFING = "briefing"                 # §5.1 — quoi faire maintenant
    GARDIEN = "gardien"                   # §5.4 — la tâche de dix minutes du soir
    DEBRIEF = "debrief"                   # §5.2 — structurer des notes brutes
    ENTRETIEN_PROJET = "entretien_projet" # §4.5 — interroger, produire une roadmap
    REVUE_HEBDO = "revue_hebdo"           # §5.3 — analyse dialoguée
    DECOUPAGE = "decoupage"               # §4.5 — découper une étape trop grosse


@dataclass(frozen=True)
class Usage:
    """Ce que l'appel a coûté. Affiché, jamais caché."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens


@dataclass(frozen=True)
class LLMResponse:
    """Une réponse de modèle, avec de quoi la juger."""

    content: dict | str
    model: str
    task: Task
    usage: Usage = field(default_factory=Usage)
    stop_reason: str = "end_turn"

    @property
    def refused(self) -> bool:
        """Le modèle a décliné. À traiter avant de lire ``content``."""
        return self.stop_reason == "refusal"


class LLMUnavailable(Exception):
    """Le fournisseur n'est pas joignable ou pas configuré.

    Distinct d'une mauvaise réponse : ici il n'y a **pas eu** de réponse. Les
    deux appellent des gestes opposés — configurer l'authentification d'un côté,
    revoir le prompt de l'autre — et les confondre a déjà coûté assez cher
    ailleurs dans ce projet.
    """


class QualityGateFailed(Exception):
    """La réponse est arrivée mais ne respecte pas le contrat.

    Porte le motif exact pour qu'il puisse être affiché et journalisé : une
    porte silencieuse ne s'améliore jamais.
    """

    def __init__(self, reason: str, payload: dict | str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.payload = payload


class LLMProvider(Protocol):
    """Ce que tout backend doit savoir faire.

    Volontairement étroit : deux méthodes. Un fournisseur local branché plus
    tard n'aura pas à réimplémenter la gestion d'outils s'il ne la supporte pas
    — il lèvera ``LLMUnavailable`` sur ``converse`` et servira quand même les
    briefings.
    """

    def structured(
        self,
        *,
        task: Task,
        system: str,
        prompt: str,
        schema: dict,
    ) -> LLMResponse:
        """Rend un objet conforme au schéma. Lève ``LLMUnavailable`` si absent."""
        ...

    def converse(
        self,
        *,
        task: Task,
        system: str,
        messages: list[dict],
        tools: list[dict],
    ) -> LLMResponse:
        """Un tour de conversation pouvant appeler des outils."""
        ...
