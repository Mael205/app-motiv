"""Le mode veille — la pause déclarée qui n'est pas un abandon.

Le §11.5 plafonne les jours off à deux par semaine et six par saison, ce qui est
juste : au-delà, ce ne sont plus des jours off, c'est un rythme. Mais rien ne
couvrait ce qui dure — des vacances, une grippe, une semaine de partiels, un
déménagement. Le système n'avait alors que deux réponses, et les deux sont
mauvaises : encaisser une semaine de jours ratés, ou désinstaller.

La veille est la troisième. Elle gèle tout : les jours sont neutres, aucun
déclencheur ne part, la saison s'arrête et reprendra où elle en était. Rien
n'est perdu, rien n'est gagné non plus — c'est exactement le contrat du jour
neutre du §4.2, étendu à une durée qui a du sens.

**Ce qu'elle ne doit surtout pas être**, et c'est ce qui décide de ses règles :

- *rétroactive*. Comme le jour off du §11.5, elle se déclare avant, sinon elle
  devient l'excuse qu'on écrit le lendemain matin ;
- *un raccourci*. Trois jours minimum : en dessous, ce sont des jours off, et il
  y en a déjà ;
- *un piège*. On en sort quand on veut, immédiatement. Une pause dont on ne peut
  pas sortir est une raison de plus de ne pas la prendre.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# En dessous, les jours off du §11.5 font le travail — et eux ne gèlent pas la
# saison, ce qui est mieux pour deux jours d'absence.
DUREE_MINIMALE = 3

# Au-delà, ce n'est plus une pause, c'est un arrêt. Quatre semaines valent une
# saison entière : la bonne réponse devient alors de clore la saison en cours et
# d'en ouvrir une neuve au retour (§14, palier 3).
DUREE_MAXIMALE = 28


@dataclass(frozen=True)
class Verdict:
    ok: bool
    raison: str = ""


def verifier(*, debut: date, fin: date, aujourdhui: date) -> Verdict:
    """Une veille est-elle déclarable ainsi ?"""
    if debut < aujourdhui:
        return Verdict(
            False,
            "Une veille se déclare avant, jamais après coup — sinon c'est l'excuse "
            "qu'on écrit le lendemain matin.",
        )
    if fin < debut:
        return Verdict(False, "La fin est avant le début.")

    jours = (fin - debut).days + 1
    if jours < DUREE_MINIMALE:
        return Verdict(
            False,
            f"{jours} jour(s) : prends un jour off, ils sont faits pour ça. La veille "
            f"commence à {DUREE_MINIMALE} jours.",
        )
    if jours > DUREE_MAXIMALE:
        return Verdict(
            False,
            f"{jours} jours, maximum {DUREE_MAXIMALE}. Au-delà, ferme la saison et "
            "ouvres-en une neuve au retour : ce sera plus honnête qu'une saison gelée "
            "un mois.",
        )
    return Verdict(True)


def jours(debut: date, fin: date) -> set[date]:
    """Toutes les journées couvertes, bornes comprises."""
    return {debut + timedelta(days=i) for i in range((fin - debut).days + 1)}


def couvre(debut: date, fin: date, jour: date) -> bool:
    return debut <= jour <= fin


def message(debut: date, fin: date) -> str:
    """Ce que l'app affiche pendant la veille. Aucun décompte anxiogène."""
    return (
        f"En veille jusqu'au {fin.strftime('%d/%m')}. Rien ne casse, rien ne compte. "
        "Tu peux reprendre quand tu veux."
    )
