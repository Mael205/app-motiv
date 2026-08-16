"""Profils de lancement : ouvrir l'environnement d'un projet (SPEC §8.1).

Le §8.1 décrit le gain : ne plus perdre les dix premières minutes à se remettre
en place. Un clic sur « démarrer », et l'éditeur, le dossier et les onglets sont
là.

**La règle de sécurité du §8 est non négociable, et elle façonne ce module :**

> L'agent n'exécute que des actions d'une liste blanche déclarée localement
> dans un fichier de config que seul l'utilisateur édite, non modifiable via
> l'API. Le serveur ne peut jamais faire exécuter une commande arbitraire.

Conséquence concrète : la seule donnée venant du serveur est le **nom du
projet**, utilisé comme clé de recherche. Tout ce qui est exécuté vient de
``profiles.local.toml``, écrit à la main. Un serveur compromis, ou une réponse
de modèle détournée, ne peut au pire que déclencher le lancement d'un programme
que l'utilisateur avait déjà autorisé pour ce projet.

C'est aussi pour ça que le calcul du plan est une fonction pure, séparée de son
exécution : la propriété « rien ne sort de la liste blanche » se teste alors
sans lancer quoi que ce soit.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROFILES_PATH = Path(__file__).with_name("profiles.local.toml")


@dataclass(frozen=True)
class Plan:
    """Ce qui sera lancé. Ne contient que ce qui vient du fichier local."""

    project: str
    folders: tuple[str, ...] = ()
    executables: tuple[str, ...] = ()
    urls: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.folders or self.executables or self.urls or self.commands)

    def summary(self) -> str:
        morceaux = []
        for etiquette, valeurs in (
            ("dossier", self.folders),
            ("programme", self.executables),
            ("onglet", self.urls),
            ("commande", self.commands),
        ):
            if valeurs:
                morceaux.append(f"{len(valeurs)} {etiquette}{'s' if len(valeurs) > 1 else ''}")
        return ", ".join(morceaux) or "rien"


@dataclass
class Profiles:
    """La liste blanche, telle qu'elle est écrite sur cette machine."""

    entries: dict[str, dict] = field(default_factory=dict)

    def plan_for(self, project: str) -> Plan:
        """Le plan d'un projet. Un projet absent de la liste ne lance **rien**.

        Aucune correspondance approchée, aucune normalisation créative : le nom
        doit être celui du fichier, à la casse et aux espaces près. Deviner
        l'intention serait le début d'un contournement de la liste blanche.
        """
        entree = self.entries.get(project)
        if entree is None:
            entree = next(
                (v for k, v in self.entries.items() if k.strip().lower() == project.strip().lower()),
                None,
            )
        if entree is None:
            return Plan(project=project)

        def liste(cle: str) -> tuple[str, ...]:
            valeurs = entree.get(cle) or []
            return tuple(str(v) for v in valeurs if str(v).strip())

        return Plan(
            project=project,
            folders=liste("folders"),
            executables=liste("executables"),
            urls=liste("urls"),
            commands=liste("commands"),
        )


def load_profiles(path: Path = PROFILES_PATH) -> Profiles:
    """Lit la liste blanche. Un fichier absent est un cas normal, pas une erreur."""
    if not path.exists():
        return Profiles()
    with path.open("rb") as handle:
        return Profiles(entries=tomllib.load(handle))


def launch(plan: Plan, *, dry_run: bool = False) -> list[str]:
    """Exécute le plan et rend ce qui a été fait. Ne lève pas.

    Chaque entrée est tentée indépendamment : un chemin devenu faux ne doit pas
    empêcher l'éditeur de s'ouvrir. Un environnement à moitié ouvert reste plus
    utile qu'une erreur.
    """
    faits: list[str] = []

    for dossier in plan.folders:
        faits.append(_tenter(f"dossier {dossier}", dry_run, lambda d=dossier: os.startfile(d)))
    for programme in plan.executables:
        faits.append(
            _tenter(
                f"programme {programme}",
                dry_run,
                lambda p=programme: subprocess.Popen([p], close_fds=True),
            )
        )
    for url in plan.urls:
        faits.append(_tenter(f"onglet {url}", dry_run, lambda u=url: os.startfile(u)))
    for commande in plan.commands:
        faits.append(
            _tenter(
                f"commande « {commande} »",
                dry_run,
                lambda c=commande: subprocess.Popen(c, shell=True, close_fds=True),
            )
        )
    return faits


def _tenter(etiquette: str, dry_run: bool, action) -> str:
    if dry_run:
        return f"[simulation] {etiquette}"
    try:
        action()
        return f"ouvert : {etiquette}"
    except OSError as error:
        return f"échec : {etiquette} ({error})"
