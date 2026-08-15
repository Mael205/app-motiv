"""Import d'un projet écrit en markdown (SPEC §4.5).

Le §5.6 — le choix entre modèle local et modèle distant — n'est pas construit,
et l'interrogation qui produit une bonne roadmap se fait donc ailleurs : dans un
chat, avec le prompt de ``docs/prompt-nouveau-projet.md``. Ce module est le point
d'entrée du résultat.

Le format est délibérément petit et tolérant, parce qu'il est écrit par un
modèle et relu par un humain sur un téléphone :

    # Outils Dofus 3 — rentabilité craft

    Branche: backend
    Couleur: #4FC4B4
    Emblème: ◈
    Engagement: 3

    ## Roadmap

    - [x] Scraper les prix de l'HDV (2)
    - [>] Modèle de coût de craft (2)
    - [ ] API de comparaison des recettes (3)
    - [ ] Interface de consultation (2)

``[ ]`` à faire, ``[>]`` en cours, ``[x]`` fait. Le nombre entre parenthèses est
l'estimation en sessions.

Le parseur ne rejette presque rien : il **avertit**. Une roadmap dont une étape
dépasse trois sessions reste importable, mais l'étape est signalée « à
découper » — le §4.5 traite une étape floue comme un défaut du système, et un
défaut se montre, il ne bloque pas la création.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import slots, verification

MAX_SESSIONS_PER_STEP = 3
DEFAULT_ESTIMATE = 2
DEFAULT_COLOR = "#E8A33D"
DEFAULT_EMBLEM = "◆"
DEFAULT_COMMITMENT = 3

TODO, DOING, DONE = "todo", "doing", "done"

_TITLE = re.compile(r"^#\s+(?P<name>.+?)\s*$")
_META = re.compile(r"^(?P<key>[A-Za-zÀ-ÿ]+)\s*:\s*(?P<value>.+?)\s*$")
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ESTIMATE = re.compile(r"\s*\((?P<n>\d+)(?:\s*sessions?)?\)\s*$", re.IGNORECASE)
_BULLET = re.compile(
    r"^\s*[-*+]\s*(?:\[(?P<mark>[ xX>])\]\s*)?(?P<label>.+?)\s*$"
)

# Les clés de métadonnées sont normalisées sans accent ni casse : le markdown
# vient d'un chat, pas d'un formulaire.
_META_KEYS = {
    "branche": "branch",
    "couleur": "color",
    "embleme": "emblem",
    "engagement": "weekly_commitment",
    "domaine": "domain",
    "verification": "verification",
    "depot": "repo_path",
}

_MARKS = {" ": TODO, "": TODO, ">": DOING, "x": DONE, "X": DONE}


@dataclass(frozen=True)
class ParsedStep:
    label: str
    state: str = TODO
    estimated_sessions: int = DEFAULT_ESTIMATE

    @property
    def needs_split(self) -> bool:
        return self.estimated_sessions > MAX_SESSIONS_PER_STEP


@dataclass
class ParsedProject:
    """Un projet lu depuis du markdown, pas encore écrit en base."""

    name: str = ""
    branch: str = ""
    domain: str = slots.CODE
    verification: str = verification.MANUELLE
    repo_path: str = ""
    color: str = DEFAULT_COLOR
    emblem: str = DEFAULT_EMBLEM
    weekly_commitment: int = DEFAULT_COMMITMENT
    steps: list[ParsedStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """Le minimum pour créer quelque chose : un nom et au moins une étape."""
        return bool(self.name) and bool(self.steps)

    @property
    def open_steps(self) -> int:
        return sum(1 for s in self.steps if s.state in (TODO, DOING))


def _strip_accents(value: str) -> str:
    table = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
    return value.lower().translate(table)


def parse(markdown: str) -> ParsedProject:
    """Lit un projet en markdown. N'écrit rien, ne lève rien : avertit."""
    parsed = ParsedProject()
    in_roadmap = False

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        if line.startswith("## "):
            in_roadmap = _strip_accents(line[3:]).strip().startswith("roadmap")
            continue

        title = _TITLE.match(line)
        if title and not line.startswith("##"):
            if not parsed.name:
                parsed.name = title.group("name")
            continue

        bullet = _BULLET.match(line)
        if bullet:
            parsed.steps.append(_step_from(bullet))
            continue

        if not in_roadmap:
            meta = _META.match(line)
            if meta:
                _apply_meta(parsed, meta.group("key"), meta.group("value"))

    _add_warnings(parsed)
    return parsed


def _step_from(match: re.Match[str]) -> ParsedStep:
    label = match.group("label")
    estimate = DEFAULT_ESTIMATE

    found = _ESTIMATE.search(label)
    if found:
        estimate = max(1, int(found.group("n")))
        label = label[: found.start()].rstrip()

    mark = match.group("mark")
    state = _MARKS.get(mark if mark is not None else "", TODO)
    return ParsedStep(label=label, state=state, estimated_sessions=estimate)


def _apply_meta(parsed: ParsedProject, key: str, value: str) -> None:
    field_name = _META_KEYS.get(_strip_accents(key))
    if field_name is None:
        return

    if field_name == "color":
        if _COLOR.match(value):
            parsed.color = value.upper()
        else:
            parsed.warnings.append(f"Couleur « {value} » ignorée : il faut un code du type #4FC4B4.")
    elif field_name == "weekly_commitment":
        digits = re.search(r"\d+", value)
        if digits:
            parsed.weekly_commitment = max(1, min(7, int(digits.group())))
    elif field_name == "emblem":
        parsed.emblem = value[:8]
    elif field_name == "verification":
        kind = verification.normalise(value)
        if kind:
            parsed.verification = kind
        else:
            parsed.warnings.append(
                f"Vérification « {value} » inconnue, « manuelle » retenue. "
                f"Attendues : {', '.join(verification.KINDS)}."
            )
    elif field_name == "repo_path":
        parsed.repo_path = value[:500]
    elif field_name == "domain":
        candidate = _strip_accents(value).strip()
        if candidate in slots.DOMAINS:
            parsed.domain = candidate
        else:
            parsed.warnings.append(
                f"Domaine « {value} » inconnu, « code » retenu par défaut. "
                f"Attendus : {', '.join(slots.DOMAINS)}."
            )
    else:
        parsed.branch = value[:32]


def _add_warnings(parsed: ParsedProject) -> None:
    """Les avertissements sont ce que l'écran de confirmation doit montrer."""
    if not parsed.name:
        parsed.warnings.append("Aucun titre trouvé : il faut une ligne « # Nom du projet ».")
    if not parsed.steps:
        parsed.warnings.append("Aucune étape trouvée : il faut au moins une ligne « - [ ] … ».")
        return

    for step in parsed.steps:
        if step.needs_split:
            parsed.warnings.append(
                f"« {step.label} » est estimée à {step.estimated_sessions} sessions. "
                "Au-delà de trois, l'étape est à découper (§4.5)."
            )

    if parsed.open_steps == 0:
        parsed.warnings.append(
            "Toutes les étapes sont faites : un projet actif doit garder une étape à faire ou en cours (§4.5)."
        )

    ready = verification.readiness(parsed.verification, has_path=bool(parsed.repo_path))
    if not ready.ready:
        parsed.warnings.append(ready.detail)

    doing = sum(1 for s in parsed.steps if s.state == DOING)
    if doing > 1:
        parsed.warnings.append(
            f"{doing} étapes sont marquées « en cours ». Une seule étape courante rend la proposition du soir nette."
        )
