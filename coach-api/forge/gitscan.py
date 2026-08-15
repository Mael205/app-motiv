"""Lecture des dépôts git déclarés (SPEC §8.3).

Ce qui a été commité pendant une session est la preuve de travail la moins
falsifiable qui existe, et elle ne coûte aucune saisie : c'est exactement ce que
le §6 cherche. Le module lit, il n'écrit jamais dans un dépôt.

Seul le sujet des commits est remonté — pas le diff, pas le contenu des
fichiers. De quoi pré-remplir un debrief, pas de quoi reconstituer le travail.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

TIMEOUT_SECONDS = 10
SEPARATOR = "\x1f"


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str
    at: datetime
    insertions: int = 0
    deletions: int = 0


@dataclass(frozen=True)
class RepoActivity:
    path: str
    commits: tuple[Commit, ...]
    available: bool = True
    detail: str = ""

    @property
    def total(self) -> int:
        return len(self.commits)


def commits_between(repo_path: str, start: datetime, end: datetime) -> RepoActivity:
    """Commits d'un dépôt entre deux instants. Ne lève jamais.

    Un dépôt absent, déplacé ou cassé n'est pas une erreur du système : c'est
    une absence de preuve, et l'appelant l'affiche comme telle.
    """
    path = Path(repo_path)
    if not (path / ".git").exists():
        return RepoActivity(path=repo_path, commits=(), available=False, detail="Pas un dépôt git.")

    fmt = SEPARATOR.join(["%H", "%s", "%cI"])
    command = [
        "git",
        "-C",
        str(path),
        "log",
        f"--since={start.isoformat()}",
        f"--until={end.isoformat()}",
        f"--pretty=format:{fmt}",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return RepoActivity(path=repo_path, commits=(), available=False, detail=str(error))

    if result.returncode != 0:
        return RepoActivity(
            path=repo_path, commits=(), available=False, detail=result.stderr.strip()[:200]
        )

    commits = []
    for line in result.stdout.splitlines():
        parts = line.split(SEPARATOR)
        if len(parts) != 3:
            continue
        sha, subject, iso = parts
        try:
            at = datetime.fromisoformat(iso)
        except ValueError:
            continue
        commits.append(Commit(sha=sha[:8], subject=subject, at=at))

    return RepoActivity(path=repo_path, commits=tuple(commits))
