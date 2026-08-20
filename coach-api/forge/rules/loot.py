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
# Le catalogue a doublé avec l'année de douze saisons. La raison n'est pas
# décorative : à deux tirages par semaine, une collection de vingt-neuf cartes
# se complète en six mois, et une collection complète cesse d'être un moteur —
# chaque tirage devient alors un doublon, c'est-à-dire une conversion en Éclats,
# c'est-à-dire une transaction. Soixante cartes tiennent une année pleine.
#
# La répartition par rareté est volontairement inégale entre emplacements. Un
# thème d'accent se voit en permanence, un effet de fin de session dure deux
# secondes : il y a donc plus de thèmes, et les légendaires y sont plus
# nombreuses.
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

    # ================= Deuxième vague =================================
    # -- Thèmes
    Card("theme_ardoise", "Ardoise", COMMUN, "theme", "#7C8BA1"),
    Card("theme_rouille", "Rouille", COMMUN, "theme", "#B4633A"),
    Card("theme_lichen", "Lichen", COMMUN, "theme", "#8FA36B"),
    Card("theme_prune", "Prune", COMMUN, "theme", "#8A5A78"),
    Card("theme_sable", "Sable", COMMUN, "theme", "#C4A87C"),
    Card("theme_cuivre", "Cuivre", RARE, "theme", "#C87D4A"),
    Card("theme_abysse", "Abysse", RARE, "theme", "#3A6E8F"),
    Card("theme_soufre", "Soufre", RARE, "theme", "#D9C22E"),
    Card("theme_cendre", "Cendre", RARE, "theme", "#8E8A93"),
    Card("theme_pourpre", "Pourpre", EPIQUE, "theme", "#9B2F52"),
    Card("theme_jade", "Jade impérial", EPIQUE, "theme", "#2FA37A"),
    Card("theme_orage", "Orage", EPIQUE, "theme", "#6A5ACD"),
    Card("theme_aurore_boreale", "Aurore boréale", LEGENDAIRE, "theme", "#4FE0B0"),
    Card("theme_fer_blanc", "Fer blanc", LEGENDAIRE, "theme", "#DCE4EC"),

    # -- Emblèmes
    Card("emb_triangle", "Triangle", COMMUN, "emblem", "▲"),
    Card("emb_anneau", "Anneau", COMMUN, "emblem", "◎"),
    Card("emb_clef", "Clef", COMMUN, "emblem", "⚿"),
    Card("emb_ancre", "Ancre", COMMUN, "emblem", "⚓"),
    Card("emb_eclair", "Éclair", RARE, "emblem", "⚡"),
    Card("emb_enclume", "Enclume", RARE, "emblem", "⛭"),
    Card("emb_faucille", "Faucille", RARE, "emblem", "☾"),
    Card("emb_tour", "Tour", EPIQUE, "emblem", "♜"),
    Card("emb_trident", "Trident", EPIQUE, "emblem", "♆"),
    Card("emb_phenix", "Phénix", LEGENDAIRE, "emblem", "🜂"),

    # -- Cadres
    Card("cadre_cuir", "Cadre de cuir", COMMUN, "frame", "leather"),
    Card("cadre_ardoise", "Cadre d'ardoise", COMMUN, "frame", "slate"),
    Card("cadre_argent", "Cadre d'argent", RARE, "frame", "silver"),
    Card("cadre_bois_brule", "Cadre de bois brûlé", RARE, "frame", "burnt"),
    Card("cadre_vitrail", "Cadre de vitrail", EPIQUE, "frame", "stained"),
    Card("cadre_meteore", "Cadre de météore", LEGENDAIRE, "frame", "meteor"),

    # -- Titres. Ils se lisent comme un grade, jamais comme un compliment (§0.2).
    Card("titre_matinal", "Matinal", COMMUN, "title", "Matinal"),
    Card("titre_regulier", "Le Régulier", COMMUN, "title", "Le Régulier"),
    Card("titre_tenace", "Tenace", RARE, "title", "Tenace"),
    Card("titre_gardien", "Gardien du seuil", RARE, "title", "Gardien du seuil"),
    Card("titre_increvable", "Increvable", EPIQUE, "title", "Increvable"),
    Card("titre_dernier_debout", "Dernier debout", EPIQUE, "title", "Dernier debout"),
    Card("titre_sans_ombre", "Sans ombre", LEGENDAIRE, "title", "Sans ombre"),

    # -- Effets de fin de session
    Card("fin_poussiere", "Poussière", COMMUN, "finisher", "dust"),
    Card("fin_braise", "Braise", COMMUN, "finisher", "ember"),
    Card("fin_givre", "Givre", RARE, "finisher", "frost"),
    Card("fin_lame", "Coup de lame", RARE, "finisher", "slash"),
    Card("fin_sceau", "Sceau apposé", EPIQUE, "finisher", "seal"),
    Card("fin_eclipse", "Éclipse", LEGENDAIRE, "finisher", "eclipse"),

    # ================= Troisième vague (J6, §16) =======================
    # Le confort du dernier jalon, au sens propre : rien ici ne débloque quoi
    # que ce soit. La raison d'ajouter est arithmétique — soixante-neuf cartes à
    # deux ou trois tirages par semaine se complètent en une année, et une
    # collection complète cesse d'être un moteur : chaque tirage devient un
    # doublon, c'est-à-dire une conversion en Éclats, c'est-à-dire une
    # transaction. La séance longue du 19 août ajoute en plus un tirage
    # hebdomadaire, ce qui rapproche encore l'échéance.
    #
    # Les emplacements gardent leur répartition : plus de thèmes, parce qu'un
    # accent se voit en permanence ; peu de cadres, parce qu'un cadre se voit
    # sur un seul écran.

    # -- Thèmes
    Card("theme_bitume", "Bitume", COMMUN, "theme", "#5F6672"),
    Card("theme_argile", "Argile", COMMUN, "theme", "#B07A5A"),
    Card("theme_menthe", "Menthe givrée", COMMUN, "theme", "#7FD8C0"),
    Card("theme_brique", "Brique", COMMUN, "theme", "#A5503F"),
    Card("theme_indigo", "Indigo", RARE, "theme", "#4B57B8"),
    Card("theme_safran", "Safran", RARE, "theme", "#E0952B"),
    Card("theme_ardente", "Terre ardente", RARE, "theme", "#C4562B"),
    Card("theme_vert_de_gris", "Vert-de-gris", EPIQUE, "theme", "#4E8C7A"),
    Card("theme_amethyste", "Améthyste", EPIQUE, "theme", "#7B4FBF"),
    Card("theme_or_blanc", "Or blanc", LEGENDAIRE, "theme", "#F0E2B6"),

    # -- Emblèmes
    Card("emb_sablier", "Sablier", COMMUN, "emblem", "⧗"),
    Card("emb_bougie", "Bougie", COMMUN, "emblem", "⚱"),
    Card("emb_compas", "Compas", COMMUN, "emblem", "⌖"),
    Card("emb_marteau", "Marteau", RARE, "emblem", "⚒"),
    Card("emb_alambic", "Alambic", RARE, "emblem", "⚗"),
    Card("emb_spirale", "Spirale", EPIQUE, "emblem", "◈"),
    Card("emb_soleil_noir", "Soleil noir", LEGENDAIRE, "emblem", "☉"),

    # -- Cadres
    Card("cadre_os", "Cadre d'os", COMMUN, "frame", "bone"),
    Card("cadre_bronze", "Cadre de bronze", RARE, "frame", "bronze"),
    Card("cadre_givre", "Cadre de givre", EPIQUE, "frame", "rime"),
    Card("cadre_eclipse", "Cadre d'éclipse", LEGENDAIRE, "frame", "eclipsed"),

    # -- Titres
    Card("titre_artisan", "Artisan", COMMUN, "title", "Artisan"),
    Card("titre_du_soir", "Homme du soir", COMMUN, "title", "Du soir"),
    Card("titre_patient", "Le Patient", RARE, "title", "Le Patient"),
    Card("titre_forgeron", "Forgeron", RARE, "title", "Forgeron"),
    Card("titre_sans_excuse", "Sans excuse", EPIQUE, "title", "Sans excuse"),
    Card("titre_intraitable", "Intraitable", LEGENDAIRE, "title", "Intraitable"),

    # -- Effets de fin de session
    Card("fin_limaille", "Limaille", COMMUN, "finisher", "filings"),
    Card("fin_souffle", "Souffle", RARE, "finisher", "breath"),
    Card("fin_enclume", "Coup d'enclume", EPIQUE, "finisher", "anvil"),
    Card("fin_aurore", "Aurore", LEGENDAIRE, "finisher", "dawn"),
)

PAR_CLE = {c.key: c for c in CATALOGUE}
PAR_RARETE: dict[str, list[Card]] = {
    r: [c for c in CATALOGUE if c.rarity == r] for r in RARETES
}


# Ce que l'effort déplace au maximum dans les poids, sur 1000. Volontairement
# modeste : la faveur incline le tirage, elle ne le décide pas. Une faveur qui
# garantirait l'épique ferait du travail une monnaie d'achat de cartes, et le
# §12.6 tient à ce que le loot reste une surprise et non un barème.
FAVEUR_VERS_RARE = 220
FAVEUR_VERS_EPIQUE = 90


def rarity_weights(
    *, draws_since_rare: int, draws_since_epic: int, faveur: float = 0.0
) -> dict[str, int]:
    """Les poids courants, pitié comprise.

    La montée est progressive et non un palier sec : une pitié qui bascule d'un
    coup se remarque et donne l'impression d'un système qui triche. Une pitié
    qui monte doucement se vit comme de la chance.

    ``faveur`` va de 0 à 1 et vient de l'**effort** que le tirage récompense —
    les heures posées sur une étape avant de la terminer. Elle transfère du
    commun vers le rare, et du rare vers l'épique. Elle s'ajoute à la pitié au
    lieu de la remplacer : la pitié corrige la malchance, la faveur reconnaît le
    travail, et les deux n'ont aucune raison de s'exclure.
    """
    poids = dict(POIDS)

    faveur = min(1.0, max(0.0, faveur))
    if faveur:
        vers_rare = min(poids[COMMUN], round(FAVEUR_VERS_RARE * faveur))
        poids[COMMUN] -= vers_rare
        poids[RARE] += vers_rare
        vers_epique = min(poids[RARE], round(FAVEUR_VERS_EPIQUE * faveur))
        poids[RARE] -= vers_epique
        poids[EPIQUE] += vers_epique

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
    faveur: float = 0.0,
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

    poids = rarity_weights(
        draws_since_rare=draws_since_rare, draws_since_epic=draws_since_epic, faveur=faveur
    )
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
# La Forge : dépenser des Éclats pour fabriquer une carte précise
# --------------------------------------------------------------------------

# Ouverte par la voie « Forge » de l'ascendance. Elle répond à un défaut qui ne
# se voit qu'au bout de plusieurs mois : les Éclats ne se dépensaient **nulle
# part**. Ils entraient par les doublons, les routines et les quêtes, et rien ne
# les faisait sortir — la mise de saison n'est pas une dépense, c'est un pari
# qu'on récupère doublé ou qu'on perd. Une monnaie qui ne descend jamais n'est
# pas une monnaie, c'est un compteur.
#
# Le prix est **très au-dessus** de ce qu'un doublon rapporte : six fois, pour
# être précis. Fabriquer reste donc le dernier recours — celui de la carte qu'on
# veut vraiment et qui ne tombe pas — et pas une façon de contourner le tirage.
# Si forger devenait rentable, l'ouverture d'une carte perdrait tout son sens et
# le §12.6 avec, qui fait du loot un moteur d'envie et non un catalogue à
# remplir.
PRIX_FORGE = {
    COMMUN: 30,
    RARE: 90,
    EPIQUE: 240,
    LEGENDAIRE: 720,
}


def prix_de_forge(card: Card) -> int:
    return PRIX_FORGE[card.rarity]


def peut_forger(card: Card, *, eclats: int, possedee: bool) -> tuple[bool, str]:
    """Peut-on forger cette carte ? Rend la réponse **et** son motif.

    Une carte déjà possédée est refusée : la forger ne donnerait qu'un doublon,
    c'est-à-dire une conversion en Éclats à perte. Le refus vaut mieux qu'une
    transaction que personne n'aurait voulue en connaissance de cause.
    """
    if possedee:
        return False, "Tu l'as déjà. La forger ne rendrait qu'un doublon, à perte."

    prix = prix_de_forge(card)
    if eclats < prix:
        return False, f"{prix} Éclats demandés, tu en as {eclats}."
    return True, ""


# --------------------------------------------------------------------------
# Ce qui déclenche un tirage
# --------------------------------------------------------------------------

MONTEE_DE_NIVEAU = "niveau"
CLOTURE_DE_SEMAINE = "semaine"
FIN_DE_SAISON = "saison"
# Terminer une étape de roadmap est l'action la plus structurante du système —
# c'est elle qui fait avancer un projet, pas les minutes — et c'était la moins
# fêtée : elle rendait 60 points de dégâts et rien d'autre. Une carte garantie
# la met au niveau du passage de niveau, qui lui ne demande que du volume.
ETAPE_TERMINEE = "etape"
# Une session longue peut faire tomber une carte, avec une probabilité qui monte
# avec les minutes réellement travaillées. C'est le seul tirage **probabiliste**
# lié à une session, et c'est voulu : garanti, il ferait de chaque soirée une
# distribution et viderait l'ouverture de son sens.
SESSION_LONGUE = "session"
# Fabriquée à la Forge, pas tirée. Distinguée dans le journal parce que ce n'est
# pas de la chance : c'est une dépense, et les deux ne se relisent pas pareil.
FORGEE = "forgee"

RAISONS = {
    MONTEE_DE_NIVEAU: "Passage de niveau",
    CLOTURE_DE_SEMAINE: "Semaine tenue",
    FIN_DE_SAISON: "Fin de saison",
    ETAPE_TERMINEE: "Étape terminée",
    SESSION_LONGUE: "Session longue",
    FORGEE: "Forgée",
}


# --------------------------------------------------------------------------
# Ce que la durée d'une session, et l'effort posé sur une étape, valent au tirage
# --------------------------------------------------------------------------
#
# Tranché le 19 août 2026, sur la question laissée ouverte dans `docs/a-faire` :
# *une étape longue vaut-elle la même carte qu'une étape courte ?* Non. Le
# déclencheur reste **terminer** — rien ne tombe pour avoir peiné sans finir —
# mais ce qui tombe tient compte de ce qui a été posé avant.
#
# Les deux courbes ci-dessous sont volontairement plates au début. Une carte qui
# arriverait dès dix minutes ferait du mode dégradé une machine à loot, alors
# qu'il existe pour les soirs où l'on ne peut rien faire d'autre : le §14 en fait
# une issue de secours, et une issue de secours ne se récompense pas.

SESSION_SEUIL = 25          # sous le plancher normal, aucun tirage
SESSION_PLAFOND = 60        # au-delà, la chance ne monte plus
SESSION_CHANCE_MAX = 0.25

ETAPE_PLAFOND_MINUTES = 300  # cinq heures posées sur une étape : faveur pleine


def chance_de_carte(minutes: int) -> float:
    """Probabilité qu'une session fasse tomber une carte, entre 0 et 0,25.

    Nulle sous 25 minutes, puis linéaire jusqu'à 60. Le plafond est bas exprès :
    à raison d'une session longue par soir, il tombe environ une carte par
    semaine, ce qui reste inférieur au rythme des étapes et des niveaux. Le loot
    doit rester lié à ce qui **avance**, et une session est du temps, pas de
    l'avancement.
    """
    minutes = max(0, int(minutes))
    if minutes < SESSION_SEUIL:
        return 0.0
    portee = SESSION_PLAFOND - SESSION_SEUIL
    ratio = min(1.0, (minutes - SESSION_SEUIL) / portee)
    return round(SESSION_CHANCE_MAX * ratio, 4)


def faveur_pour(minutes_posees: int) -> float:
    """La faveur d'un tirage d'étape, d'après les minutes posées sur elle.

    Zéro pour une étape expédiée, 1 au bout de cinq heures. La courbe est
    linéaire et plafonnée : au-delà, une étape n'est plus longue, elle est
    bloquée — et le §13.5 a déjà un constat pour ça. Récompenser encore
    récompenserait l'enlisement.
    """
    return min(1.0, max(0, int(minutes_posees)) / ETAPE_PLAFOND_MINUTES)


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
