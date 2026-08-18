"""Les phases du boss de saison (SPEC §12.4, ajout du 17 août 2026).

Le boss est la meilleure réponse du produit à « à quoi ça sert, ce soir » : sa
vie descend avec les minutes travaillées. Mais une barre qui descend
linéairement pendant vingt-huit jours s'aplatit — au jour 15 il ne se passe
plus rien de nouveau, et le combat devient un décompte.

Trois phases, deux franchissements. À la moitié de sa vie et au dernier quart,
le boss **change de nom et de comportement**.

**Aucune règle ne change**, et c'est la condition pour que ce soit acceptable.
Pas de dégâts modifiés, pas de vie qui remonte, pas de bonus de dernière phase :
le §17 interdit qu'un cosmétique devienne du pouvoir, et une phase qui doublerait
les dégâts transformerait la fin de saison en sur-régime récompensé — exactement
ce que le §0.2 cherche à empêcher. Ce module ne rend que des noms, des phrases
et une intensité d'affichage.

Les noms de phase sont écrits par boss plutôt que générés, parce qu'un suffixe
appliqué à tout le monde (« l'Ajourneur éveillé », « la Scroll-Hydre éveillée »)
se lit comme un gabarit dès la deuxième saison. Un boss inconnu retombe sur le
gabarit — c'est le cas dégradé, pas le cas normal.
"""

from __future__ import annotations

from dataclasses import dataclass

# Le seuil est le ratio de vie **en dessous duquel** la phase commence.
SEUILS = (0.5, 0.25)

PHASES: dict[str, tuple[tuple[str, str], ...]] = {
    "procrastin": (
        ("Procrastin, l'Ajourneur", "Il repousse. C'est tout ce qu'il sait faire."),
        ("Procrastin, le Pressé", "Il a arrêté de repousser : il négocie."),
        ("Procrastin, à découvert", "Plus rien à ajourner. Il n'a plus que ce soir."),
    ),
    "scrollhydre": (
        ("La Scroll-Hydre", "Une tête coupée, deux qui repoussent."),
        ("La Scroll-Hydre décapitée", "Les têtes repoussent moins vite qu'avant."),
        ("Le Moignon", "Il ne reste qu'un cou. Il mord encore."),
    ),
    "veilleur": (
        ("Le Veilleur de 23h", "Il attend que la soirée glisse."),
        ("Le Veilleur de 1h", "Il a reculé son heure. Il tient toujours."),
        ("Le Veilleur blanc", "Il ne dort plus du tout, et ça se voit."),
    ),
    "eparpilleur": (
        ("L'Éparpilleur", "Six choses commencées, zéro finie."),
        ("L'Éparpilleur rassemblé", "Il n'a plus assez de morceaux pour disperser."),
        ("Le Dernier Fragment", "Une seule chose reste ouverte. La sienne."),
    ),
    "jour_six": (
        ("Jour Six", "La semaine tient jusqu'à lui."),
        ("Jour Six et demi", "Il grignote le septième."),
        ("Jour Sept", "Il n'a plus de jour où se cacher."),
    ),
    "brouillard": (
        ("Le Brouillard", "On ne voit pas à trois jours."),
        ("La Brume", "Ça se dégage. Pas beaucoup."),
        ("La Rosée", "Il ne reste que ce qu'il a déposé au sol."),
    ),
}

# Gabarit pour un boss non décrit. Volontairement sobre : un gabarit qui essaie
# d'être spectaculaire trahit qu'il est un gabarit.
GABARIT = (
    ("{nom}", ""),
    ("{nom}, entamé", "Il a pris assez pour changer de façon de se battre."),
    ("{nom}, acculé", "Dernier quart. Il n'a plus de place derrière lui."),
)

# Intensité d'affichage, lue par la barre de vie. Pas une règle : un nombre que
# le front multiplie à ses propres animations.
INTENSITES = (1.0, 1.35, 1.8)


@dataclass(frozen=True)
class Phase:
    index: int            # 1, 2 ou 3
    name: str
    line: str
    intensity: float
    ratio_floor: float    # le ratio de vie où cette phase a commencé

    @property
    def final(self) -> bool:
        return self.index == len(INTENSITES)


def index_for(ratio: float) -> int:
    """La phase correspondant à un ratio de vie. 1 tant que rien n'est franchi."""
    borne = max(0.0, min(1.0, ratio))
    phase = 1
    for seuil in SEUILS:
        if borne < seuil:
            phase += 1
    return phase


def phase_for(boss_key: str, base_name: str, ratio: float) -> Phase:
    """L'état de scène du boss à un ratio de vie donné."""
    index = index_for(ratio)
    noms = PHASES.get(boss_key) or tuple(
        (nom.format(nom=base_name), ligne) for nom, ligne in GABARIT
    )
    nom, ligne = noms[index - 1]
    return Phase(
        index=index,
        name=nom,
        line=ligne,
        intensity=INTENSITES[index - 1],
        ratio_floor=(1.0, *SEUILS)[index - 1],
    )


def crossed(boss_key: str, base_name: str, *, before: float, after: float) -> Phase | None:
    """La phase franchie entre deux ratios, s'il y en a une.

    Le franchissement se met en scène, pas l'état : sans cette comparaison
    avant/après, la bascule se rejouerait à chaque session du reste de la
    saison. C'est la même règle que pour la mort du boss.

    Un boss qui remonte (la régénération des jours ratés, §14) ne **défranchit**
    rien : la phase perdue ne se rejoue pas à la baisse. Une saison où l'on
    perdrait des paliers en public serait une punition affichée, et le §17
    interdit que le système en ajoute une.
    """
    avant = index_for(before)
    apres = index_for(after)
    if apres <= avant:
        return None
    return phase_for(boss_key, base_name, after)
