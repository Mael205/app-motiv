"""Le gardien de secours local (ajout du 17 août 2026).

Le gardien du soir (§11.3) part du serveur. C'est le bon endroit : c'est lui
qui sait si la journée est validée, combien de boucliers restent, et quelle est
la tâche de dix minutes. Mais il a un défaut qui ne se voit qu'une fois — le
soir où le serveur est injoignable, il ne part pas, et personne ne le sait.

Un gardien qui tombe le soir où il tombe n'est pas un gardien. Le §11.3 dit
qu'il doit exister dès J1 et ne jamais tomber ; ce module est ce « jamais ».

**Ce qu'il fait** : quand le serveur ne répond pas, l'agent lève lui-même la
notification, à l'heure que le serveur lui avait indiquée la dernière fois
qu'il répondait, avec la tâche qu'il lui avait donnée.

**Ce qu'il ne fait pas**, et c'est ce qui le rend acceptable au regard du §8 :

- il ne décide de rien. Il rejoue une notification que le serveur avait déjà
  calculée et datée. Aucun jugement local, aucun seuil local ;
- il ne peut pas se déclencher à tort sur une journée validée. Si le serveur
  est injoignable, aucune session n'a pu démarrer — l'app en a besoin — donc
  l'état « journée non validée » lu au dernier contact est encore vrai ;
- il ne survit pas à la journée. Un cache daté d'hier ne lève rien : mieux vaut
  un gardien manquant qu'un gardien qui parle du mauvais soir ;
- il ne double jamais celui du serveur. Le serveur a répondu ⇒ le local se tait,
  et il ne se lève qu'une fois par journée du coach.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CACHE_PATH = Path(__file__).with_name("gardien.local.json")


@dataclass(frozen=True)
class Consigne:
    """Ce que le serveur avait dit, la dernière fois qu'il parlait."""

    day: str
    at: datetime
    task: str
    project: str
    validated: bool
    floor_minutes: int

    def due(self, now: datetime) -> bool:
        return now >= self.at


def memoriser(etat: dict, *, chemin: Path = CACHE_PATH) -> Consigne | None:
    """Range la consigne du gardien reçue avec l'état de l'agent.

    Écrit à chaque contact réussi plutôt qu'une fois par soir : la consigne
    porte l'état de validation du jour, et c'est justement cet état qui doit
    être le plus frais possible au moment où le serveur disparaît.
    """
    consigne = _lire_etat(etat)
    if consigne is None:
        return None

    chemin.write_text(
        json.dumps(
            {
                "day": consigne.day,
                "at": consigne.at.isoformat(),
                "task": consigne.task,
                "project": consigne.project,
                "validated": consigne.validated,
                "floor_minutes": consigne.floor_minutes,
            }
        ),
        encoding="utf-8",
    )
    return consigne


def charger(*, chemin: Path = CACHE_PATH) -> Consigne | None:
    """Relit la dernière consigne connue. ``None`` si elle manque ou est illisible."""
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _lire_etat({"guardian": brut, "day": brut.get("day", "")})


def _lire_etat(etat: dict) -> Consigne | None:
    bloc = etat.get("guardian") or {}
    brut = bloc.get("at")
    if not brut:
        return None
    try:
        moment = datetime.fromisoformat(str(brut).replace("Z", "+00:00"))
    except ValueError:
        return None

    return Consigne(
        day=bloc.get("day") or etat.get("day", ""),
        at=moment,
        task=bloc.get("task", ""),
        project=bloc.get("project", ""),
        validated=bool(bloc.get("validated")),
        floor_minutes=int(bloc.get("floor_minutes") or 0),
    )


def a_lever(
    consigne: Consigne | None, *, now: datetime, jour_du_coach: str, deja_leve: str | None
) -> bool:
    """Faut-il lever le gardien local, maintenant ?

    ``jour_du_coach`` est la journée que la consigne annonçait. On la compare à
    elle-même plutôt que de la recalculer : l'agent ne connaît ni la bascule de
    4h ni le fuseau du profil, et deviner l'une ou l'autre serait exactement le
    genre de règle locale que le §8 lui interdit.
    """
    if consigne is None or consigne.validated:
        return False
    if consigne.day != jour_du_coach:
        return False                       # consigne d'hier : on se tait
    if deja_leve == consigne.day:
        return False                       # une fois par soir, comme le serveur
    return consigne.due(now)


def message(consigne: Consigne) -> tuple[str, str]:
    """Le texte affiché. Le même fond que le gardien du serveur, en plus court.

    Il dit qu'il est hors ligne. Ce n'est pas un détail technique lâché au
    passage : une notification qui ne ressemble pas tout à fait à celle qu'on
    connaît, sans expliquer pourquoi, se lit comme un bug — et une sanction
    qu'on prend pour un bug ne sanctionne rien.
    """
    corps = (
        f"10 min : {consigne.task}"
        if consigne.task
        else f"Le plancher est à {consigne.floor_minutes} minutes."
    )
    if consigne.project and consigne.task:
        corps += f"\nSur {consigne.project}."
    corps += "\nCoach injoignable — c'est l'agent qui te le dit."
    return "Rien de posé ce soir", corps
