"""Le bilan de saison comparé, côté règles (SPEC §13.4, §5.5).

À la clôture des quatre semaines, la saison est comparée à **toutes** les
précédentes. Pas seulement à la dernière : une bonne saison suivie d'une
mauvaise ne dit rien, trois saisons dont la deuxième décroche disent quelque
chose.

Deux partis pris, et ils viennent tous les deux du §17.

**Les régressions sont dites.** Un bilan qui n'annoncerait que les progressions
serait une brochure, et personne ne se corrige sur une brochure. Ce qui est
interdit n'est pas la mauvaise nouvelle, c'est le jugement : « 4h de moins qu'à
la saison 2 » est un fait, « tu as relâché » est un reproche.

**La question de fin de saison est toujours la même** : qu'est-ce qui a cassé, et
à quelle date. Le système **connaît la date** — il la calcule ici. Ce qu'il vient
chercher est la cause, et c'est la seule chose qu'il ne peut pas déduire.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# En dessous, un écart n'est pas une évolution : c'est du bruit de mesure ou une
# semaine décalée d'un jour. L'annoncer ferait dire au bilan plus que ce que les
# chiffres portent.
SEUIL_RELATIF = 0.10

# Le §13.4 en demande trois. Trois causes se retiennent ; sept se lisent comme
# une liste de reproches et ne se retiennent pas.
MAX_CAUSES = 3


@dataclass(frozen=True)
class Chiffres:
    """Ce qu'une saison a produit. Comparable d'une saison à l'autre."""

    index: int
    nom: str
    heures: float
    sessions: int
    jours_tenus: int
    jours: int
    etapes: int
    engagements_tenus: int
    engagements_pris: int
    fuite_minutes: int

    @property
    def regularite(self) -> float:
        return round(self.jours_tenus / self.jours, 3) if self.jours else 0.0


@dataclass(frozen=True)
class Evolution:
    mesure: str
    valeur: float
    reference: float
    sens: str                     # "progression" | "regression" | "stable"
    phrase: str


# Nom lisible, extracteur, et **sens** : pour la fuite de temps, moins est mieux.
# Sans ce dernier champ, une baisse du scroll serait annoncée comme une
# régression, ce qui serait exactement l'inverse de la vérité.
MESURES = (
    ("Heures", lambda c: c.heures, True),
    ("Sessions", lambda c: float(c.sessions), True),
    ("Régularité", lambda c: c.regularite, True),
    ("Étapes terminées", lambda c: float(c.etapes), True),
    ("Engagements tenus", lambda c: float(c.engagements_tenus), True),
    ("Scroll passif", lambda c: float(c.fuite_minutes), False),
)


def comparer(courante: Chiffres, passees: list[Chiffres]) -> list[Evolution]:
    """Compare la saison à la moyenne de toutes les précédentes.

    La moyenne plutôt que la dernière : comparer deux points fait passer une
    oscillation normale pour une tendance, et le §13.4 demande une comparaison
    avec toutes les saisons passées, pas avec la précédente.
    """
    if not passees:
        return []

    evolutions = []
    for nom, lire, monter_est_mieux in MESURES:
        valeur = lire(courante)
        reference = sum(lire(p) for p in passees) / len(passees)

        if reference == 0 and valeur == 0:
            continue

        ecart = valeur - reference
        relatif = abs(ecart) / reference if reference else 1.0

        if relatif < SEUIL_RELATIF:
            sens = "stable"
        elif (ecart > 0) == monter_est_mieux:
            sens = "progression"
        else:
            sens = "regression"

        evolutions.append(
            Evolution(
                mesure=nom,
                valeur=round(valeur, 2),
                reference=round(reference, 2),
                sens=sens,
                phrase=_phrase(nom, valeur, reference, sens),
            )
        )

    ordre = {"regression": 0, "progression": 1, "stable": 2}
    return sorted(evolutions, key=lambda e: ordre[e.sens])


def _phrase(mesure: str, valeur: float, reference: float, sens: str) -> str:
    """Un fait, une comparaison, aucun adjectif."""
    if sens == "stable":
        return f"{mesure} : {_nombre(valeur)}, comme d'habitude."
    mot = "au-dessus" if valeur > reference else "en dessous"
    return f"{mesure} : {_nombre(valeur)}, {mot} de la moyenne ({_nombre(reference)})."


def _nombre(valeur: float) -> str:
    return f"{valeur:.1f}".rstrip("0").rstrip(".") if valeur % 1 else str(int(valeur))


def rupture(jours: list[tuple[date, bool]]) -> tuple[date, int] | None:
    """La date où ça a cassé, et combien de jours ça a duré.

    Le début de la plus longue série de jours non tenus. Pas le premier jour
    raté de la saison — un jour isolé n'est pas une rupture, c'est une soirée —
    mais le début de la série qui a réellement coupé l'élan.

    C'est la seule chose que le système apporte à la question de fin de saison,
    et elle compte : on se souvient rarement de la date, et on se souvient très
    bien de ce qui s'est passé ce jour-là quand on l'entend.
    """
    debut, longueur = None, 0
    meilleur_debut, meilleure_longueur = None, 0

    for jour, tenu in sorted(jours):
        if tenu:
            debut, longueur = None, 0
            continue
        if debut is None:
            debut = jour
        longueur += 1
        if longueur > meilleure_longueur:
            meilleur_debut, meilleure_longueur = debut, longueur

    if meilleure_longueur < 2:
        return None
    return meilleur_debut, meilleure_longueur


def question(coupure: tuple[date, int] | None) -> str:
    """La question de fin de saison. Toujours la même (§13.4)."""
    if not coupure:
        return "Rien n'a cassé cette saison. Qu'est-ce qui a tenu, exactement ?"

    jour, jours = coupure
    return (
        f"Ça a cassé le {jour.strftime('%d/%m')}, et c'est resté cassé {jours} jours. "
        "Qu'est-ce qui s'est passé ce jour-là ?"
    )


def causes(revues: list[dict]) -> list[str]:
    """Les trois causes les plus probables, tirées des revues de la saison.

    Elles ne sont pas devinées : ce sont les « seule chose à changer » écrites
    chaque dimanche, pendant que la semaine était encore fraîche. Les faire
    re-déduire par un modèle à la fin du mois remplacerait ce que la personne a
    constaté sur le moment par ce qu'un modèle suppose après coup — et le §13.4
    demande précisément des causes « identifiées à partir des revues hebdo ».

    Les doublons sont écartés : la même chose écrite trois dimanches de suite est
    **une** cause, et c'est même la plus solide du lot.
    """
    vues, sortie = set(), []
    for revue in revues:
        texte = (revue.get("seule_chose") or "").strip()
        cle = texte.lower()
        if not texte or cle in vues:
            continue
        vues.add(cle)
        sortie.append(texte)
    return sortie[:MAX_CAUSES]
