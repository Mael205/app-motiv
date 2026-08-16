"""Le backend qui passe par l'abonnement, via le CLI Claude Code (SPEC §5.6).

**Pourquoi un sous-processus plutôt que le SDK.** Le SDK Python s'authentifie
par clé API — facturée à l'usage, séparément de l'abonnement. Le CLI ``claude``,
lui, est déjà connecté sur cette machine avec le compte de l'utilisateur. Le
faire tourner en mode ``--print`` est donc le seul chemin qui réponde à la
demande telle qu'elle a été posée : *utiliser mon abonnement, pas ouvrir une
seconde ligne de facturation*.

Le §5.6 prévoyait « hybride local/distant » et une abstraction assez étroite
pour qu'un fournisseur se remplace sans toucher aux appelants. C'est exactement
ce qui est exercé ici : ce module n'expose rien de plus que ``AnthropicBackend``,
et le service de briefing ne sait pas lequel des deux lui a répondu.

**Ce que ce backend ne fait pas, volontairement.**

Le CLI est un agent : il sait lire des fichiers et lancer des commandes. Un
briefing n'a besoin d'aucun des deux, et le §8 pose que le serveur ne doit
jamais pouvoir faire exécuter quoi que ce soit. Chaque appel part donc outils
coupés, réglages du dépôt ignorés, et depuis un dossier vide. Ce n'est pas une
précaution de principe : le prompt contient du texte que l'utilisateur a écrit,
et du texte qu'un modèle a écrit avant lui.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile

from .base import LLMProvider, LLMResponse, LLMUnavailable, Task, Usage
from .router import route_for

logger = logging.getLogger(__name__)

# Au-delà, on considère que le CLI ne répondra pas. Un briefing qui met deux
# minutes à venir a déjà échoué à son but — on est censé démarrer maintenant.
TIMEOUT_SECONDS = 150

# Le CLI rend parfois le JSON dans un bloc de code. Le tolérer coûte trois
# lignes ; le refuser coûterait un briefing perdu pour un détail de mise en
# forme dont le modèle n'est pas averti.
CLOTURE_MARKDOWN = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


def cli_path() -> str | None:
    """Le chemin du CLI, ou ``None`` s'il n'est pas installé."""
    return shutil.which("claude")


class ClaudeCodeBackend(LLMProvider):
    """Fournisseur distant passant par le CLI, donc par l'abonnement."""

    def __init__(self, *, executable: str | None = None, timeout: int = TIMEOUT_SECONDS):
        self._executable = executable
        self._timeout = timeout

    # -- exécution ------------------------------------------------------

    def _resolve(self) -> str:
        chemin = self._executable or cli_path()
        if not chemin:
            raise LLMUnavailable(
                "le CLI « claude » est introuvable — installe-le avec "
                "« npm install -g @anthropic-ai/claude-code », puis connecte-toi avec « claude »"
            )
        return chemin

    def _argv(self, route, *, system: str) -> list[str]:
        return [
            self._resolve(),
            "--print",
            "--output-format", "json",
            "--model", route.model,
            # Le réglage qui décide de la qualité réelle. Sans lui, un entretien
            # de projet rend une roadmap plausible au lieu d'une roadmap juste,
            # et la différence ne se voit qu'au bout de trois semaines de travail
            # sur des étapes mal découpées.
            "--effort", route.effort,
            "--system-prompt", system,
            # Aucun outil : ce backend produit du texte, il n'agit pas.
            "--allowedTools", "",
            "--disallowedTools", "Bash", "Edit", "Write", "Read", "WebFetch", "WebSearch",
            "--permission-mode", "default",
            # Ni les réglages du dépôt, ni ses serveurs MCP, ni son CLAUDE.md.
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]

    def _run(self, route, *, system: str, prompt: str) -> dict:
        argv = self._argv(route, system=system)

        # Un dossier vide et jetable : le CLI découvre son contexte depuis son
        # répertoire courant, et il n'a rien à découvrir ici.
        with tempfile.TemporaryDirectory(prefix="coach-llm-") as neutre:
            try:
                acheve = subprocess.run(
                    argv,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self._timeout,
                    cwd=neutre,
                    env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
                )
            except subprocess.TimeoutExpired as error:
                raise LLMUnavailable(
                    f"le CLI n'a pas répondu en {self._timeout} s — briefing abandonné"
                ) from error
            except OSError as error:
                raise LLMUnavailable(f"impossible de lancer le CLI : {error}") from error

        if acheve.returncode != 0:
            detail = (acheve.stderr or acheve.stdout or "").strip()[:400]
            raise LLMUnavailable(f"le CLI a échoué (code {acheve.returncode}) : {detail}")

        try:
            enveloppe = json.loads(acheve.stdout)
        except ValueError as error:
            raise LLMUnavailable(
                f"sortie du CLI illisible : {acheve.stdout[:200]!r}"
            ) from error

        if enveloppe.get("is_error"):
            raise LLMUnavailable(f"le CLI a rendu une erreur : {enveloppe.get('result', '')!s:.300}")

        return enveloppe

    # -- lecture de l'enveloppe ------------------------------------------

    @staticmethod
    def _usage(enveloppe: dict) -> Usage:
        brut = enveloppe.get("usage") or {}
        return Usage(
            input_tokens=brut.get("input_tokens") or 0,
            output_tokens=brut.get("output_tokens") or 0,
            cache_read_tokens=brut.get("cache_read_input_tokens") or 0,
        )

    @staticmethod
    def _json_de(texte: str) -> dict:
        """Extrait l'objet JSON d'une réponse, bloc de code toléré."""
        nu = CLOTURE_MARKDOWN.sub("", texte.strip())
        try:
            return json.loads(nu)
        except ValueError:
            pass

        # Dernier recours : le premier objet accolade-à-accolade. Utile quand le
        # modèle préface d'une phrase malgré la consigne.
        debut, fin = nu.find("{"), nu.rfind("}")
        if debut != -1 and fin > debut:
            try:
                return json.loads(nu[debut : fin + 1])
            except ValueError:
                pass

        raise LLMUnavailable(f"réponse non-JSON malgré la consigne : {texte[:200]!r}")

    # -- interface -------------------------------------------------------

    def structured(self, *, task: Task, system: str, prompt: str, schema: dict) -> LLMResponse:
        route = route_for(task)

        # Le CLI n'expose pas les schémas de sortie de l'API : le schéma est
        # donc porté par le prompt. C'est moins contraignant, et c'est
        # précisément pourquoi la porte de qualité n'est pas facultative ici.
        consigne = (
            f"{prompt}\n\n"
            "Réponds UNIQUEMENT par un objet JSON conforme à ce schéma, "
            "sans texte avant ni après, sans bloc de code :\n"
            f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
        )

        enveloppe = self._run(route, system=system, prompt=consigne)
        return LLMResponse(
            content=self._json_de(enveloppe.get("result") or ""),
            model=route.model,
            task=task,
            usage=self._usage(enveloppe),
            stop_reason=enveloppe.get("stop_reason") or "end_turn",
        )

    def converse(
        self, *, task: Task, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        """Un tour de conversation. **Sans outils** — voir l'en-tête du module.

        Le Protocol de ``base`` prévoit ce refus : un fournisseur qui ne sait pas
        tout faire lève et sert quand même le reste.
        """
        if tools:
            raise LLMUnavailable(
                "ce backend ne prête pas d'outils au modèle : le serveur ne fait rien exécuter (§8)"
            )

        route = route_for(task)
        echange = "\n\n".join(
            f"{m.get('role', 'user')} : {m.get('content', '')}" for m in messages
        )
        enveloppe = self._run(route, system=system, prompt=echange)
        return LLMResponse(
            content={"blocks": [{"type": "text", "text": enveloppe.get("result") or ""}]},
            model=route.model,
            task=task,
            usage=self._usage(enveloppe),
            stop_reason=enveloppe.get("stop_reason") or "end_turn",
        )
