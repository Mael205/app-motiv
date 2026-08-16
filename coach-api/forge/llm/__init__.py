"""La couche modèle du coach (SPEC §5, §5.6).

Le reste de l'application ne connaît que ``get_provider()`` et les erreurs de
``base``. Elle ne sait pas quel modèle a répondu, ni s'il y en a eu un.

**L'IA est facultative, par construction.** Sans identifiant, ``get_provider()``
rend un fournisseur qui lève proprement, et chaque appelant a un chemin de repli
déterministe. Une app de discipline qui cesserait de fonctionner parce qu'une
API est injoignable serait une app qu'on n'ouvre pas le soir où elle sert.
"""

from __future__ import annotations

from django.conf import settings

from .base import (
    LLMProvider,
    LLMResponse,
    LLMUnavailable,
    QualityGateFailed,
    Task,
    Usage,
)
from .gate import gate
from .router import route_for

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMUnavailable",
    "QualityGateFailed",
    "Task",
    "Usage",
    "gate",
    "route_for",
    "get_provider",
    "set_provider",
]

_override: LLMProvider | None = None


def set_provider(provider: LLMProvider | None) -> None:
    """Impose un fournisseur. Réservé aux tests."""
    global _override
    _override = provider


def get_provider() -> LLMProvider:
    """Le fournisseur courant.

    L'ordre n'est pas cosmétique : **le CLI passe avant le SDK** parce qu'il
    consomme l'abonnement déjà payé, là où le SDK ouvre une facturation à la
    clé. Sur une machine où les deux sont disponibles, le bon défaut est celui
    qui ne coûte rien de plus.

    Ne vérifie aucun identifiant ici. Les deux backends résolvent les leurs au
    premier appel, et échouer au démarrage rendrait l'app inutilisable alors
    que tout le reste fonctionne sans IA.
    """
    if _override is not None:
        return _override

    if not getattr(settings, "COACH_AI_ENABLED", True):
        from .fake import UnavailableProvider

        return UnavailableProvider("l'IA est désactivée dans les réglages")

    choix = getattr(settings, "COACH_AI_BACKEND", "auto")

    if choix in ("cli", "auto"):
        from .claude_code import ClaudeCodeBackend, cli_path

        if choix == "cli" or cli_path():
            return ClaudeCodeBackend()

    from .anthropic_backend import AnthropicBackend

    return AnthropicBackend()
