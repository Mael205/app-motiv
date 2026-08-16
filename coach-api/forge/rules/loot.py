"""Cartes de loot et Éclats (SPEC §12.6).

Une contrainte domine tout ce module, et elle est répétée deux fois dans la
spec :

> Aucune carte ne donne d'XP ni ne modifie une règle. (§12.6)
> Le loot est de l'apparence, jamais du pouvoir — sinon le système récompense la
> chance et plus le travail. (§17)

Le loot est donc **entièrement cosmétique**, et c'est ce qui le rend sûr : on
peut tirer au sort sans risque, parce qu'un mauvais tirage ne coûte aucun droit
et qu'un bon tirage n'en donne aucun. C'est aussi ce qui le rend désirable sans
être pervers — l'ouverture d'une carte est un plaisir, pas un avantage.

Le tirage est **pseudo-aléatoire à pitié** : plus on enchaîne les tirages sans
rien de rare, plus la chance monte. Un aléa pur produit des séries de dix
communs qui donnent l'impression que le système est cassé, et c'est justement
l'impression qu'un système de discipline ne peut pas se permettre.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

COMMUN, RARE, EPIQUE, LEGENDAIRE = "commun", "rare", "epique", "legendaire"
RARETES = (COMMUN, RARE, EPIQUE, LEGENDAIRE)

RARETE_LABELS = {
    COMMUN: "Commun",
    RARE: "Rare",
    EPIQUE: "Épique",
    LEGENDAIRE: "Légendaire",
}

# Couleurs de rareté. Volontairement dans la palette du §7 plutôt que dans le
# gris-bleu-violet-orange habituel des jeux : la rareté doit se lire, sans
# importer une autre identité visuelle que celle du coach.
RARETE_COLORS = {
    COMMUN: "#9A8CAE",
    RARE: "#5FA8DE",
    EPIQUE: "#8B6FE8",
    LEGENDAIRE: "#E8A33D",
}

# Poids de base, sur 1000. La légendaire est rare sans être décorative : à deux
# tirages par semaine environ, elle tombe quelques fois par an.
POIDS = {COMMUN: 620, RARE: 280, EPIQUE: 85, LEGENDAIRE: 15}

# Éclats rendus par une carte. Le loot en double n'est pas perdu — il se
# convertit, pour qu'un tirage ne soit jamais nul.
ECLATS_PAR_RARETE = {COMMUN: 5, RARE: 15, EPIQUE: 40, LEGENDAIRE: 120}

# Pitié : au bout de tant de tirages sans rare ou mieux, on force. Le seuil est
# bas parce que les tirages sont peu fréquents — attendre vingt cartes, à deux
# par semaine, c'est attendre deux mois.
PITIE_RARE = 6
PITIE_EPIQUE = 20


@dataclass(frozen=True)
class Card:
    """Une carte. ``kind`` dit sur quoi elle agit, toujours cosmétiquement."""

    key: str
    label: str
    rarity: str
    kind: str          # theme | emblem | frame | title | finisher
    payload: str = ""  # la valeur cosmétique : un hex, un glyphe, un mot

    @property
    def color(self) -> str:
        return RARETE_COLORS[self.rarity]


# Le catalogue. Chaque entrée est du cosmétique pur : un thème d'accent, un
# emblème de projet, un cadre d'avatar, un titre, ou un effet de fin de session.
CATALOGUE: tuple[Card, ...] = (
    # -- Thèmes d'accent (§12.2 : la saison surcharge l'accent, jamais le fond)
    Card("theme_braise", "Braise", COMMUN, "theme", "#E8843D"),
    Card("theme_glacier", "Glacier", COMMUN, "theme", "#5FA8DE"),
    Card("theme_mousse", "Mousse", COMMUN, "theme", "#7ED08C"),
    Card("theme_encre", "Encre", RARE, "theme", "#6F7EE8"),
    Card("theme_venin", "Venin", RARE, "theme", "#9FE85F"),
    Card("theme_or_noir", "Or noir", EPIQUE, "theme", "#C9A227"),
    Card("theme_eclipse", "Éclipse", LEGENDAIRE, "theme", "#E85F9F"),
    # -- Emblèmes de projet
    Card("emb_losange", "Losange", COMMUN, "emblem", "◆"),
    Card("emb_etoile", "Étoile", COMMUN, "emblem", "✦"),
    Card("emb_croix", "Croix du sud", COMMUN, "emblem", "✜"),
    Card("emb_rune", "Rune", RARE, "emblem", "ᚦ"),
    Card("emb_oeil", "Œil", RARE, "emblem", "◉"),
    Card("emb_sceau", "Sceau", EPIQUE, "emblem", "❖"),
    Card("emb_couronne", "Couronne", LEGENDAIRE, "emblem", "♛"),
    # -- Cadres d'avatar
    Card("cadre_fer", "Cadre de fer", COMMUN, "frame", "iron"),
    Card("cadre_laiton", "Cadre de laiton", RARE, "frame", "brass"),
    Card("cadre_obsidienne", "Cadre d'obsidienne", EPIQUE, "frame", "obsidian"),
    Card("cadre_aurore", "Cadre d'aurore", LEGENDAIRE, "frame", "aurora"),
    # -- Titres
    Card("titre_veilleur", "Veilleur", COMMUN, "title", "Veilleur"),
    Card("titre_obstine", "L'Obstiné", RARE, "title", "L'Obstiné"),
    Card("titre_sans_repit", "Sans répit", EPIQUE, "title", "Sans répit"),
    Card("titre_monarque", "Monarque de l'ombre", LEGENDAIRE, "title", "Monarque de l'ombre"),
    # -- Effets de fin de session (§12.6 : « effets de la séquence de fin »)
    Card("fin_etincelles", "Étincelles", COMMUN, "finisher", "sparks"),
    Card("fin_onde", "Onde de choc", RARE, "finisher", "shockwave"),
    Card("fin_fracture", "Fracture", EPIQUE, "finisher", "fracture"),
    Card("fin_ascension", "Ascension", LEGENDAIRE, "finisher", "ascension"),
)

PAR_CLE = {c.key: c for c in CATALOGUE}
PAR_RARETE: dict[str, list[Card]] = {
    r: [c for c in CATALOGUE if c.rarity == r] for r in RARETES
}


def rarity_weights(*, draws_since_rare: int, draws_since_epic: int) -> dict[str, int]:
    """Les poids courants, pitié comprise.

    La montée est progressive et non un palier sec : une pitié qui bascule d'un
    coup se remarque et donne l'impression d'un système qui triche. Une pitié
    qui monte doucement se vit comme de la chance.
    """
    poids = dict(POIDS)

    if draws_since_rare >= PITIE_RARE:
        # Le commun s'effondre au profit du rare, jusqu'à devenir impossible.
        exces = draws_since_rare - PITIE_RARE + 1
        transfert = min(poids[COMMUN], exces * 200)
        poids[COMMUN] -= transfert
        poids[RARE] += transfert

    if draws_since_epic >= PITIE_EPIQUE:
        exces = draws_since_epic - PITIE_EPIQUE + 1
        transfert = min(poids[RARE], exces * 120)
        poids[RARE] -= transfert
        poids[EPIQUE] += transfert

    return poids


def draw(
    *,
    owned: set[str] | None = None,
    draws_since_rare: int = 0,
    draws_since_epic: int = 0,
    rng: random.Random | None = None,
) -> tuple[Card, bool]:
    """Tire une carte. Rend la carte et si elle est un doublon.

    ``owned`` ne restreint pas le tirage : un doublon est possible et se
    convertit en Éclats. Retirer les cartes possédées assècherait le catalogue
    et transformerait les derniers tirages en distribution certaine, ce qui
    supprime précisément ce qui rend l'ouverture agréable.
    """
    rng = rng or random.Random()
    owned = owned or set()

    poids = rarity_weights(draws_since_rare=draws_since_rare, draws_since_epic=draws_since_epic)
    rarete = rng.choices(RARETES, weights=[poids[r] for r in RARETES], k=1)[0]
    carte = rng.choice(PAR_RARETE[rarete])
    return carte, carte.key in owned


def shards_for(card: Card, *, duplicate: bool) -> int:
    """Les Éclats rendus. Un doublon vaut sa conversion, une nouveauté rien.

    Une nouvelle carte est déjà la récompense ; y ajouter des Éclats ferait du
    doublon une déception nette, et le but est l'inverse — qu'aucun tirage ne
    soit vide.
    """
    return ECLATS_PAR_RARETE[card.rarity] if duplicate else 0


# --------------------------------------------------------------------------
# Ce qui déclenche un tirage
# --------------------------------------------------------------------------

MONTEE_DE_NIVEAU = "niveau"
CLOTURE_DE_SEMAINE = "semaine"
FIN_DE_SAISON = "saison"

RAISONS = {
    MONTEE_DE_NIVEAU: "Passage de niveau",
    CLOTURE_DE_SEMAINE: "Semaine tenue",
    FIN_DE_SAISON: "Fin de saison",
}


def draws_for_week(*, days_kept: int, commitments_kept: bool) -> int:
    """Combien de cartes à la clôture d'une semaine (§12.6).

    Une seule carte de base, une seconde si tous les engagements ont été tenus.
    Le second tirage est indexé sur la **fiabilité**, pas sur le volume — c'est
    la même séparation qu'au §4.4, et la seule qui ne récompense pas le
    sur-régime.
    """
    if days_kept <= 0:
        return 0
    return 2 if commitments_kept else 1
