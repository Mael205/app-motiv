"""Preuve de travail par fichiers modifiés (SPEC §6, §8.3).

Git ne couvre pas tout. Apprendre ne produit pas de commit, un niveau Unreal se
construit en modifiant des assets pendant des heures avant qu'on pense à
commiter, et un entraînement RL écrit des checkpoints sans qu'on touche au
dépôt. Pour ces cas-là, la trace la plus proche du réel est la date de
modification des fichiers.

C'est une preuve **plus faible** qu'un commit : ouvrir un fichier dans certains
éditeurs suffit à le toucher. Elle reste largement supérieure à rien, et comme
tout le reste elle n'invalide jamais une session (§6).

Deux précautions, parce que ce scan tourne pendant que l'utilisateur attend :

* les dossiers qui contiennent des milliers de fichiers générés sont **élagués**
  avant d'être parcourus, pas filtrés après ;
* le parcours a un budget de fichiers. Au-delà, il s'arrête et le dit, plutôt
  que de faire attendre indéfiniment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Élagués à la descente : ce sont des sorties de build, pas du travail.
EXCLUDED_DIRS = frozenset(
    {
        ".git", ".hg", ".svn",
        "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".venv", "venv", "env",
        "dist", "build", "out", "target", "bin", "obj",
        # Unreal : régénérés à chaque compilation, et énormes.
        "Binaries", "Intermediate", "DerivedDataCache", "Saved", "Build",
        ".idea", ".vscode", ".vs",
    }
)

MAX_FILES_SCANNED = 40_000
MAX_LISTED = 40


@dataclass(frozen=True)
class ModifiedFile:
    """Un fichier touché pendant la fenêtre. Le chemin, jamais le contenu."""

    relative_path: str
    at: datetime


@dataclass(frozen=True)
class FolderActivity:
    """``files`` n'est qu'un échantillon lisible ; ``total`` est le compte réel.

    Les confondre ferait afficher « 40 fichiers » sur une session qui en a
    touché six cents — une preuve qui sous-estime le travail est un bug, pas une
    prudence.
    """

    path: str
    files: tuple[ModifiedFile, ...]
    total: int = 0
    available: bool = True
    detail: str = ""
    scanned: int = 0
    truncated: bool = False


def files_modified_between(folder: str, start: datetime, end: datetime) -> FolderActivity:
    """Fichiers du dossier modifiés entre deux instants. Ne lève jamais.

    Un dossier absent n'est pas une erreur du système : c'est une absence de
    preuve, et l'appelant l'affiche comme telle.
    """
    root = Path(folder)
    if not root.is_dir():
        return FolderActivity(
            path=folder, files=(), available=False, detail="Dossier introuvable."
        )

    found: list[ModifiedFile] = []
    scanned = 0
    truncated = False

    for current, dirnames, filenames in os.walk(root, onerror=lambda _: None):
        # Élagage en place : os.walk ne descendra pas dans ce qu'on retire ici.
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")]

        for name in filenames:
            scanned += 1
            if scanned > MAX_FILES_SCANNED:
                truncated = True
                break

            full = Path(current) / name
            try:
                mtime = full.stat().st_mtime
            except OSError:
                continue

            at = datetime.fromtimestamp(mtime, tz=timezone.utc)
            if start <= at <= end:
                try:
                    relative = str(full.relative_to(root))
                except ValueError:
                    relative = name
                found.append(ModifiedFile(relative_path=relative, at=at))

        if truncated:
            break

    found.sort(key=lambda f: f.at)
    detail = ""
    if truncated:
        detail = (
            f"Parcours arrêté à {MAX_FILES_SCANNED} fichiers. "
            "Déclare un sous-dossier plus précis pour une mesure complète."
        )

    return FolderActivity(
        path=folder,
        files=tuple(found[:MAX_LISTED]),
        total=len(found),
        detail=detail,
        scanned=scanned,
        truncated=truncated,
    )
