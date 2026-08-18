"""Le projet en attente déclarée (ajout du 17 août 2026).

Le cas est banal et rien ne le couvrait : un projet bloqué par quelqu'un
d'autre. Une réponse qu'on attend, une pièce qui n'est pas arrivée, un accès
qu'on ne t'a pas encore donné, une machine en réparation. Le travail n'est pas
possible, et l'absence de travail n'a rien à voir avec toi.

Sans rien pour le dire, le système lisait ça comme un abandon : au dixième jour
la détection du §13.5 proposait de mettre le projet au frigo, et l'engagement
manqué faisait tomber la semaine entière — donc le rang, qui mesure la
fiabilité. Se faire sanctionner pour l'inaction de quelqu'un d'autre est la
façon la plus sûre de faire perdre confiance à un système de discipline.

**Ce que l'attente fait, et rien de plus** : la détection se tait, l'engagement
de la semaine est levé, le projet cesse d'être proposé le soir. **Ce qu'elle ne
fait pas** : elle ne libère pas le slot. C'est le point qui la distingue du
frigo. Un projet en attente reste ton projet, il occupe sa place, et il la
reprend intacte au retour — sans quoi déclarer une attente coûterait une
renégociation de slots à chaque fois, et personne ne la déclarerait.

Trois bornes, une par façon de la détourner :

- **jamais rétroactive**, comme le jour off et la veille : sinon c'est l'excuse
  qu'on écrit le lendemain ;
- **une raison nommée**, parce qu'un blocage extérieur se nomme toujours en
  cinq mots. « Pas envie » ne s'écrit pas dans cette case, et devoir écrire
  quelque chose suffit à trier ;
- **deux semaines au maximum**. Au-delà, ce n'est plus une attente, c'est un
  projet qui a changé de nature — et la bonne réponse redevient le frigo, qui
  lui, rend le slot à quelque chose de vivant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# En dessous, il n'y a rien à déclarer : deux jours sans toucher un projet est
# le régime normal d'un projet à trois sessions par semaine.
DUREE_MINIMALE = 3

# Deux semaines. C'est aussi la borne de la détection « projet mort », qui
# regarde dix jours : au-delà de quatorze, l'attente couvrirait en permanence
# une détection qu'elle est censée seulement suspendre.
DUREE_MAXIMALE = 14

# Une raison plus courte que ça n'est pas une raison, c'est un accusé de
# réception. Quatre caractères laissent passer « SAV » ou « bac » à une lettre
# près ; huit forcent une phrase minuscule, et une phrase minuscule se relit.
RAISON_MINIMALE = 8

# Une semaine dont la moitié ou plus est couverte par l'attente ne compte pas
# comme un engagement manqué. En dessous, il reste une majorité de semaine
# ouvrable, et l'engagement se tient encore.
JOURS_POUR_LEVER_LA_SEMAINE = 4


@dataclass(frozen=True)
class Verdict:
    ok: bool
    raison: str = ""


def verifier(*, debut: date, fin: date, aujourdhui: date, raison: str) -> Verdict:
    """Une attente est-elle déclarable ainsi ?"""
    if debut < aujourdhui:
        return Verdict(
            False,
            "Une attente se déclare avant, jamais après coup — sinon c'est l'excuse "
            "qu'on écrit le lendemain matin.",
        )
    if fin < debut:
        return Verdict(False, "La fin est avant le début.")

    if len(raison.strip()) < RAISON_MINIMALE:
        return Verdict(
            False,
            "Dis ce qui bloque, en cinq mots. Un blocage extérieur se nomme "
            "toujours ; s'il ne se nomme pas, ce n'est pas un blocage extérieur.",
        )

    jours = (fin - debut).days + 1
    if jours < DUREE_MINIMALE:
        return Verdict(
            False,
            f"{jours} jour(s) : deux jours sans toucher un projet, c'est un rythme "
            f"normal. L'attente commence à {DUREE_MINIMALE} jours.",
        )
    if jours > DUREE_MAXIMALE:
        return Verdict(
            False,
            f"{jours} jours, maximum {DUREE_MAXIMALE}. Au-delà, ce n'est plus une "
            "attente : mets-le au frigo, son slot ira à quelque chose de vivant.",
        )
    return Verdict(True)


def couvre(debut: date, fin: date, jour: date) -> bool:
    return debut <= jour <= fin


def jours_couverts(debut: date, fin: date, *, entre: date, et: date) -> int:
    """Combien de jours d'attente tombent dans une fenêtre donnée."""
    haut = min(fin, et)
    bas = max(debut, entre)
    return max(0, (haut - bas).days + 1)


def leve_la_semaine(debut: date, fin: date, *, lundi: date) -> bool:
    """L'engagement de cette semaine est-il levé par l'attente ?

    Levé et non « manqué » : la nuance est tout le sujet. Un engagement manqué
    fait tomber la semaine et le rang mesure la fiabilité (§4.4) ; or ne pas
    pouvoir travailler n'est pas manquer de fiabilité. La semaine sort du calcul
    au lieu d'y entrer du mauvais côté.
    """
    return (
        jours_couverts(debut, fin, entre=lundi, et=lundi + timedelta(days=6))
        >= JOURS_POUR_LEVER_LA_SEMAINE
    )


def message(nom: str, fin: date, raison: str) -> str:
    """Ce que l'app affiche à côté du projet. Factuel, et la raison est relue.

    La raison est réaffichée telle qu'elle a été écrite : c'est ce qui permet
    de constater soi-même, au bout de dix jours, qu'on attend une réponse qui
    ne viendra pas. Le système ne le dira pas à ta place — le §17 lui interdit
    de trancher — mais il remet la phrase sous les yeux.
    """
    return f"{nom} en attente jusqu'au {fin.strftime('%d/%m')} — {raison.strip()}. Le slot reste pris."
