"""Session fantôme : partie sans clôturer (SPEC §8.7).

Le cas réel est banal. Une session de 25 minutes est lancée, le téléphone
sonne, la soirée part ailleurs, et le minuteur tourne encore à minuit. Sans
garde-fou, cette session compte pour sa durée planifiée — donc récompense du
temps qui n'a pas été travaillé, ce que le §17 interdit — ou reste ouverte et
bloque le démarrage de la suivante.

Deux conditions, et il faut les deux :

1. la session **dépasse** sa durée prévue d'une marge de grâce ;
2. la sonde n'a **rien vu** depuis un moment.

La marge existe parce que dépasser un peu est normal : on finit sa phrase, on
relit son test. Ce n'est pas de l'inactivité, c'est du travail qui déborde.

**Une sonde muette ne prouve rien**, et c'est la même asymétrie qu'au §11.10 :
si l'agent ne sait pas quand l'activité a cessé, il ne conclut pas. Fermer une
session sur une absence de données reviendrait à effacer du travail réel — la
faute la plus coûteuse que ce module puisse commettre, puisqu'elle est
invisible et qu'elle porte sur ce que le système existe pour compter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

GRACE_MINUTES = 15
IDLE_MINUTES = 15


@dataclass(frozen=True)
class GhostVerdict:
    """Ce qu'on peut conclure, et de quoi clôturer si on conclut."""

    is_ghost: bool
    reason: str
    close_at: datetime | None = None
    active_minutes: int = 0


def evaluate(
    *,
    started_at: datetime,
    planned_minutes: int,
    now: datetime,
    last_active_at: datetime | None,
    grace_minutes: int = GRACE_MINUTES,
    idle_minutes: int = IDLE_MINUTES,
) -> GhostVerdict:
    """La session est-elle un fantôme, et à quel instant faut-il la clôturer ?"""
    limite = started_at + timedelta(minutes=planned_minutes + grace_minutes)
    if now < limite:
        return GhostVerdict(False, "la session n'a pas encore dépassé sa durée et sa marge")

    if last_active_at is None:
        return GhostVerdict(
            False,
            "aucune mesure d'activité : on ne clôture pas sur une absence de données",
        )

    if last_active_at < started_at:
        return GhostVerdict(
            False,
            "la dernière activité connue précède le démarrage : mesure inutilisable",
        )

    inactif_depuis = (now - last_active_at).total_seconds() / 60
    if inactif_depuis < idle_minutes:
        return GhostVerdict(
            False, f"activité il y a {int(inactif_depuis)} min : la session tourne encore"
        )

    # On clôture au dernier instant prouvé, jamais à l'instant courant : le
    # temps entre les deux n'a pas été travaillé.
    minutes = int((last_active_at - started_at).total_seconds() // 60)
    return GhostVerdict(
        True,
        f"dépassement de {int((now - limite).total_seconds() // 60)} min "
        f"et aucune activité depuis {int(inactif_depuis)} min",
        close_at=last_active_at,
        active_minutes=max(0, minutes),
    )
