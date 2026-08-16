"""Le backend distant : Claude via le SDK officiel (SPEC §5.6).

L'authentification passe par **l'abonnement Claude**, pas par une clé API
facturée à part : le SDK résout ses identifiants dans l'ordre
``ANTHROPIC_API_KEY`` → ``ANTHROPIC_AUTH_TOKEN`` → profil OAuth déposé par
``ant auth login``. Un client construit sans argument prend donc le profil tout
seul. Rien à écrire dans le code, rien à stocker dans le dépôt.

**Dégradation plutôt que panne.** Ce backend a été écrit sans pouvoir être
essayé contre l'API — les identifiants n'existaient pas encore. Plutôt que de
parier sur l'acceptation de chaque paramètre, il envoie sa requête complète puis
retire un raffinement à la fois si l'API en refuse un, en disant lequel. Un
paramètre inconnu coûte alors une seconde et une ligne de journal, pas un
briefing perdu un soir où il fallait démarrer.
"""

from __future__ import annotations

import json
import logging

from .base import LLMProvider, LLMResponse, LLMUnavailable, Task, Usage
from .router import route_for

logger = logging.getLogger(__name__)

# Raffinements retirés un par un si l'API les refuse, du moins au plus coûteux
# à perdre. L'effort part en premier : sans lui la réponse reste correcte, elle
# est juste calibrée par défaut.
RAFFINEMENTS = ("effort", "fallbacks")


class AnthropicBackend(LLMProvider):
    """Fournisseur distant. Ne connaît ni la porte de qualité ni les règles métier."""

    def __init__(self, client=None):
        self._client = client
        self._degrade: set[str] = set()

    # -- client ---------------------------------------------------------

    @property
    def client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as error:  # pragma: no cover - dépendance déclarée
            raise LLMUnavailable("le paquet « anthropic » n'est pas installé") from error

        try:
            self._client = anthropic.Anthropic()
        except Exception as error:
            raise LLMUnavailable(f"client Anthropic impossible à construire : {error}") from error
        return self._client

    # -- appels ---------------------------------------------------------

    def _params(self, route, *, system: str, messages: list[dict]) -> dict:
        params: dict = {
            "model": route.model,
            "max_tokens": route.max_tokens,
            "system": system,
            "messages": messages,
        }
        if "effort" not in self._degrade:
            params["output_config"] = {"effort": route.effort}
        if "fallbacks" not in self._degrade:
            # Un refus de classificateur renverrait un 200 sans contenu ; la
            # relance côté serveur évite de rendre un briefing vide.
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"
        return params

    def _send(self, params: dict):
        """Envoie, en retirant un raffinement à la fois si l'API en refuse un."""
        import anthropic

        beta = "betas" in params
        endpoint = self.client.beta.messages if beta else self.client.messages

        try:
            return endpoint.create(**params)
        except anthropic.BadRequestError as error:
            message = str(error).lower()
            for raffinement in RAFFINEMENTS:
                if raffinement in self._degrade:
                    continue
                if raffinement in message or "unexpected" in message or "unknown" in message:
                    self._degrade.add(raffinement)
                    logger.warning(
                        "paramètre « %s » refusé par l'API, retiré pour la suite : %s",
                        raffinement,
                        error,
                    )
                    params.pop(raffinement, None)
                    params.pop("betas", None)
                    if raffinement == "effort":
                        params.pop("output_config", None)
                    return self._send(params)
            raise
        except anthropic.APIStatusError as error:
            raise LLMUnavailable(f"API Claude : {error}") from error
        except anthropic.APIConnectionError as error:
            raise LLMUnavailable("API Claude injoignable — vérifie la connexion") from error
        except anthropic.AuthenticationError as error:
            raise LLMUnavailable(
                "aucun identifiant Claude valide — lance « ant auth login »"
            ) from error

    def _usage(self, response) -> Usage:
        usage = getattr(response, "usage", None)
        if usage is None:
            return Usage()
        return Usage(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        )

    # -- interface ------------------------------------------------------

    def structured(self, *, task: Task, system: str, prompt: str, schema: dict) -> LLMResponse:
        route = route_for(task)
        params = self._params(route, system=system, messages=[{"role": "user", "content": prompt}])

        config = params.setdefault("output_config", {})
        config["format"] = {"type": "json_schema", "schema": schema}

        response = self._send(params)
        stop = getattr(response, "stop_reason", "end_turn")
        if stop == "refusal":
            return LLMResponse(content={}, model=route.model, task=task, stop_reason="refusal")

        texte = next(
            (b.text for b in response.content if getattr(b, "type", None) == "text"),
            "",
        )
        try:
            contenu = json.loads(texte)
        except ValueError as error:
            raise LLMUnavailable(f"réponse non-JSON malgré le schéma imposé : {error}") from error

        return LLMResponse(
            content=contenu,
            model=getattr(response, "model", route.model),
            task=task,
            usage=self._usage(response),
            stop_reason=stop,
        )

    def converse(
        self, *, task: Task, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        route = route_for(task)
        params = self._params(route, system=system, messages=messages)
        if tools:
            params["tools"] = tools

        response = self._send(params)
        stop = getattr(response, "stop_reason", "end_turn")

        blocs = []
        for bloc in response.content:
            kind = getattr(bloc, "type", None)
            if kind == "text":
                blocs.append({"type": "text", "text": bloc.text})
            elif kind == "tool_use":
                blocs.append(
                    {"type": "tool_use", "id": bloc.id, "name": bloc.name, "input": bloc.input}
                )

        return LLMResponse(
            content={"blocks": blocs},
            model=getattr(response, "model", route.model),
            task=task,
            usage=self._usage(response),
            stop_reason=stop,
        )
