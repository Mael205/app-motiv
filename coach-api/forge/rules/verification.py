"""Comment un projet prouve qu'on a travaillé dessus (SPEC §6, §8.3).

Le §6 veut un streak crédible à ses propres yeux. Une session déclarée sans
aucune trace est exactement ce qui rend un compteur décoratif — et un compteur
décoratif ne tient personne.

Chaque projet déclare donc son moyen de vérification à sa création. Quatre
niveaux, du plus fort au plus faible :

``git``
    Les commits pendant la fenêtre de session. La preuve la moins falsifiable
    qui existe, et elle ne coûte aucune saisie.

``fichiers``
    Des fichiers du dossier déclaré ont été modifiés pendant la session. Plus
    faible qu'un commit, mais fonctionne quand le travail ne se commite pas :
    assets Unreal, notes, maquettes.

``premier_plan``
    L'application déclarée était au premier plan (ActivityWatch, §8.4). Le plus
    faible : être devant un éditeur n'est pas travailler. Utile là où rien
    d'autre n'existe.

``manuelle``
    Aucune preuve automatique. Ce n'est pas un défaut — c'est le bon choix pour
    ce qui n'en laisse pas, et le déclarer explicitement vaut mieux que faire
    croire à une vérification qui n'existe pas.

**Aucun de ces moyens n'invalide jamais une session.** Le §6 est explicite : la
preuve d'activité s'affiche, elle ne juge pas. Une session sans trace reste une
session ; elle est simplement marquée comme telle.
"""

from __future__ import annotations

from dataclasses import dataclass

GIT = "git"
FICHIERS = "fichiers"
PREMIER_PLAN = "premier_plan"
MANUELLE = "manuelle"

KINDS = (GIT, FICHIERS, PREMIER_PLAN, MANUELLE)

LABELS = {
    GIT: "Commits git",
    FICHIERS: "Fichiers modifiés",
    PREMIER_PLAN: "Application au premier plan",
    MANUELLE: "Déclaration manuelle",
}

# Ce que chaque moyen exige d'être renseigné pour fonctionner réellement.
NEEDS_PATH = (GIT, FICHIERS)


@dataclass(frozen=True)
class Readiness:
    """Le moyen déclaré est-il réellement opérationnel ?"""

    kind: str
    ready: bool
    detail: str

    @property
    def label(self) -> str:
        return LABELS.get(self.kind, self.kind)


def normalise(value: str) -> str | None:
    """Lit un moyen écrit à la main. Rend ``None`` si le mot est inconnu."""
    candidate = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "commits": GIT,
        "commit": GIT,
        "depot": GIT,
        "fichier": FICHIERS,
        "mtime": FICHIERS,
        "foreground": PREMIER_PLAN,
        "activitywatch": PREMIER_PLAN,
        "aucune": MANUELLE,
        "manuel": MANUELLE,
    }
    candidate = aliases.get(candidate, candidate)
    return candidate if candidate in KINDS else None


def readiness(kind: str, *, has_path: bool) -> Readiness:
    """Dit si le moyen déclaré peut fonctionner, et sinon ce qui manque.

    Un projet qui annonce ``git`` sans dépôt déclaré n'est pas vérifié : il
    croit l'être, ce qui est pire. Le cas doit être visible immédiatement.
    """
    if kind in NEEDS_PATH and not has_path:
        return Readiness(
            kind=kind,
            ready=False,
            detail=(
                f"« {LABELS[kind]} » annoncé, mais aucun chemin déclaré. "
                "Tant qu'il manque, ce projet n'est pas vérifié."
            ),
        )
    if kind == PREMIER_PLAN:
        return Readiness(
            kind=kind,
            ready=True,
            detail="Dépend d'ActivityWatch : sans lui, la mesure est simplement absente.",
        )
    if kind == MANUELLE:
        return Readiness(kind=kind, ready=True, detail="Aucune preuve automatique, et c'est assumé.")
    return Readiness(kind=kind, ready=True, detail="")
