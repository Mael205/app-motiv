"""Le fuseau horaire (ajout du 17 août 2026).

Tout le produit est indexé sur deux choses : la fenêtre du soir, et la bascule
de 4h du §1. Les deux se calculent dans le fuseau du profil, réglé une fois à
l'installation et jamais rouvert depuis.

Un voyage casse les deux **en silence**. À Montréal, la fenêtre « 20h–23h »
s'ouvre à 14h heure locale et se referme avant le dîner ; le gardien part au
milieu de l'après-midi, la journée bascule à 22h la veille, et rien dans l'app
ne dit pourquoi. Le pire n'est pas le décalage — c'est qu'il ne se voit pas :
on lit des chiffres faux en les croyant justes, et c'est exactement ce que le
§17 interdit au système de produire.

**Détecté, jamais appliqué.** L'app propose, l'utilisateur trancHe. Deux
raisons, et la seconde suffirait :

- une escale de trois heures n'est pas un déménagement, et déplacer la soirée
  de quelqu'un qui change d'avion serait pire que de ne rien faire ;
- le §11.1 n'autorise le système à décider que de ce qu'on fait maintenant. Le
  fuseau n'en fait pas partie.

L'écart se mesure sur le **décalage effectif**, pas sur le nom de la zone. Deux
noms différents au même décalage ne changent rien à ce soir ; proposer une
bascule dans ce cas serait du bruit, et le bruit apprend à ignorer les vraies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# En dessous, ce n'est pas un voyage. Aucun fuseau habité n'est à moins de
# quinze minutes d'un autre, mais la borne protège des arrondis.
ECART_MINIMAL = 15


@dataclass(frozen=True)
class Proposition:
    """Un écart constaté entre le fuseau du profil et celui de l'appareil."""

    actuel: str
    detecte: str
    ecart_minutes: int
    valide: bool
    raison: str = ""

    @property
    def line(self) -> str:
        if not self.valide:
            return self.raison

        sens = "en avance" if self.ecart_minutes > 0 else "en retard"
        heures, minutes = divmod(abs(self.ecart_minutes), 60)
        ecart = f"{heures}h{minutes:02d}" if minutes else f"{heures}h"
        return (
            f"Ton appareil est à {self.detecte}, {ecart} {sens} sur {self.actuel}. "
            "La fenêtre du soir et la bascule de 4h suivent le fuseau réglé, "
            "pas celui de l'appareil."
        )


def ecart(actuel: str, detecte: str, *, at: datetime) -> int:
    """Le décalage en minutes entre deux fuseaux, à un instant donné.

    À un instant donné, parce que l'heure d'été ne bascule pas partout le même
    jour : entre fin mars et début avril, Paris et New York sont à cinq heures
    une semaine et à quatre l'autre.
    """
    def offset(nom: str) -> int:
        decalage = at.astimezone(ZoneInfo(nom)).utcoffset()
        return int(decalage.total_seconds() // 60) if decalage else 0

    return offset(detecte) - offset(actuel)


def proposer(actuel: str, detecte: str, *, at: datetime) -> Proposition:
    """Faut-il proposer de basculer ? Ne bascule jamais rien lui-même."""
    if not detecte or detecte == actuel:
        return Proposition(actuel, detecte, 0, False, "Même fuseau : rien à changer.")

    try:
        minutes = ecart(actuel, detecte, at=at)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return Proposition(actuel, detecte, 0, False, "Fuseau inconnu.")

    if abs(minutes) < ECART_MINIMAL:
        return Proposition(
            actuel,
            detecte,
            minutes,
            False,
            "Même décalage qu'ici aujourd'hui : rien ne bouge ce soir.",
        )

    return Proposition(actuel, detecte, minutes, True)
