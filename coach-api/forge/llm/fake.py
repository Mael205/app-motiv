"""Un fournisseur factice, pour tester sans réseau ni jetons (SPEC §5.6).

Les tests du coach ne doivent appeler aucune API : ils doivent tourner hors
ligne, sans identifiant, et donner le même résultat à chaque exécution. Ce
fournisseur sert donc partout dans la suite de tests — et il sert aussi à
vérifier ce qui compte vraiment ici, qui n'est **pas** la qualité du modèle mais
la solidité de ce qui l'entoure : la porte de qualité refuse-t-elle bien une
réponse floue, l'appelant retombe-t-il bien sur la proposition déterministe.

C'est pour ça que ``ScriptedProvider`` sait aussi rendre de mauvaises réponses.
Un faux fournisseur qui ne saurait que bien répondre laisserait le chemin
d'échec — le seul qui compte un soir de fatigue — entièrement non testé.
"""

from __future__ import annotations

from .base import LLMProvider, LLMResponse, LLMUnavailable, Task, Usage


class ScriptedProvider(LLMProvider):
    """Rend des réponses préparées, dans l'ordre, et note ce qu'on lui a demandé."""

    def __init__(self, responses: list[dict | str] | None = None, *, model: str = "faux-modele"):
        self._responses = list(responses or [])
        self._model = model
        self.calls: list[dict] = []

    def _next(self, task: Task) -> LLMResponse:
        if not self._responses:
            raise AssertionError(
                f"le fournisseur factice n'a plus de réponse préparée (tâche {task.value})"
            )
        contenu = self._responses.pop(0)
        return LLMResponse(
            content=contenu,
            model=self._model,
            task=task,
            usage=Usage(input_tokens=100, output_tokens=50),
        )

    def structured(self, *, task: Task, system: str, prompt: str, schema: dict) -> LLMResponse:
        self.calls.append({"kind": "structured", "task": task, "system": system, "prompt": prompt})
        return self._next(task)

    def converse(
        self, *, task: Task, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        self.calls.append(
            {"kind": "converse", "task": task, "system": system, "messages": list(messages)}
        )
        return self._next(task)


class UnavailableProvider(LLMProvider):
    """Simule l'absence d'identifiant : le cas normal tant que rien n'est configuré.

    Ce n'est pas un cas d'erreur exotique — c'est l'état de l'application par
    défaut. L'app doit rester entièrement utilisable sans IA, et c'est ce
    fournisseur qui le prouve dans les tests.
    """

    def __init__(self, reason: str = "aucun identifiant Claude — lance « ant auth login »"):
        self.reason = reason

    def structured(self, **_kwargs) -> LLMResponse:
        raise LLMUnavailable(self.reason)

    def converse(self, **_kwargs) -> LLMResponse:
        raise LLMUnavailable(self.reason)
