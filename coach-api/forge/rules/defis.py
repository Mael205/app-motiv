"""Les défis : ce qui remplace le hasard sur les cartes marquantes (§12.6, §17).

Le tirage de fin de semaine convenait tant que la collection était un plaisir
d'appoint. Il ne convient plus pour les trente-six cartes épiques et
légendaires, et pour une raison simple : **on ne peut rien viser**. Une carte
qui tombe au hasard ne demande rien, ne se prépare pas, et ne se raconte pas
après coup. Elle décore une grille.

Chaque carte épique ou légendaire porte donc un défi, et un seul. Le défi
regarde un **compteur de discipline** déjà mesuré par les hauts faits — les
levers avant 20h, les séances tenues à l'heure, les semaines sans scroll, les
jours sans consommer de bouclier — et tombe à un seuil.

## Trois règles, et elles sont dures

1. **Une carte à défi ne tombe jamais au tirage.** Sinon le défi n'est pas une
   condition, c'est un raccourci parmi d'autres, et le premier tirage chanceux
   efface trois mois de travail. La même raison vaut pour la Forge : elle est
   fermée sur ces cartes, quel que soit le solde d'Éclats.

2. **Un défi ne mesure jamais un excès.** Les compteurs utilisés sont ceux du
   §12.3 : monotones, jamais repris, et aucun ne se gagne en une soirée de
   sur-régime. « Six sessions dans la même journée » n'existe pas ici, pour la
   raison que le module des hauts faits explique en long.

3. **Le défi ne donne aucun pouvoir.** Ce qu'il débloque reste une carte, donc
   de l'apparence — le §17 est intact. La discipline achète du style, jamais un
   avantage. C'est exactement la ligne que les reliques tiennent de l'autre
   côté : elles seules donnent un bonus, et elles se gagnent par un haut fait.

## Pourquoi les seuils par paire

Une épique et une légendaire de la même voie forment un palier et son horizon :
vingt-cinq séances à l'heure, puis cent vingt. La seconde ne s'atteint pas en
poussant, elle s'atteint en durant — et c'est le seul comportement que ce
produit cherche à installer.
"""

from __future__ import annotations

from dataclasses import dataclass

# Comment se dit un compteur, au singulier de la phrase « il te faut … ».
# Le texte vit ici et pas dans le client : c'est le §11.10, le ton est une
# règle testée, et « sessions_avant_20h: 50 » à l'écran ne dit rien à personne.
PHRASES = {
    "sessions_terminees": "{n} sessions terminées",
    "heures_totales": "{n} heures de travail cumulées",
    "jours_travailles": "{n} journées travaillées",
    "plus_longue_serie": "{n} jours d'affilée avec du travail posé",
    "jours_sans_bouclier": "{n} jours sans consommer de bouclier",
    "etapes_finies": "{n} étapes de roadmap terminées",
    "etapes_dans_une_saison": "{n} étapes terminées dans une même saison",
    "projets_termines": "{n} projet(s) mené(s) jusqu'à la dernière étape",
    "sessions_avant_20h": "{n} séances démarrées avant 20h",
    "sessions_a_l_heure": "{n} séances démarrées à l'heure dite",
    "sessions_longues": "{n} sessions de cinquante minutes",
    "semaines_sans_scroll": "{n} semaine(s) entière(s) sans une minute de scroll passif",
    "branches_dans_une_semaine": "{n} branches de l'arbre nourries dans la même semaine",
    "saisons_closes": "{n} saison(s) menée(s) jusqu'à leur clôture",
    "boss_abattus": "{n} boss de saison abattu(s)",
    "semaines_tenues": "{n} semaines où tous les engagements ont été tenus",
    "jours_off_declares": "{n} jours off déclarés la veille ou plus tôt",
    "retours_apres_arret": "{n} reprise(s) après au moins trois jours d'arrêt",
}


@dataclass(frozen=True)
class Defi:
    carte: str      # la clé de la carte que le défi débloque
    voie: str       # le nom de la discipline travaillée, pour le regroupement
    fait: str       # le compteur regardé, parmi ceux des hauts faits
    seuil: int

    @property
    def condition(self) -> str:
        return PHRASES[self.fait].format(n=self.seuil)


# Les trente-six cartes épiques et légendaires, chacune derrière sa voie.
#
# Les voies sont volontairement peu nombreuses et répétées : ce sont les six ou
# sept comportements que le produit cherche à installer, pas une liste de
# curiosités. Voir chaque paire épique/légendaire comme un palier et son
# horizon.
CATALOGUE: tuple[Defi, ...] = (
    # ---- Lève-tôt : la soirée commence avant qu'elle ne soit perdue -------
    Defi("cadre_aurore", "Lève-tôt", "sessions_avant_20h", 100),
    Defi("theme_aurore_boreale", "Lève-tôt", "sessions_avant_20h", 150),
    Defi("theme_pourpre", "Parole tenue", "sessions_a_l_heure", 25),
    Defi("emb_soleil_noir", "Parole tenue", "sessions_a_l_heure", 120),

    # ---- Longue haleine : la séance qui dure -----------------------------
    Defi("theme_orage", "Longue haleine", "sessions_longues", 25),
    Defi("titre_sans_excuse", "Longue haleine", "sessions_longues", 60),
    Defi("theme_or_noir", "Longue haleine", "heures_totales", 50),
    Defi("theme_amethyste", "Longue haleine", "heures_totales", 120),
    Defi("theme_eclipse", "Longue haleine", "heures_totales", 250),
    Defi("theme_or_blanc", "Longue haleine", "heures_totales", 400),

    # ---- Constance : revenir demain --------------------------------------
    Defi("titre_sans_repit", "Constance", "plus_longue_serie", 21),
    Defi("titre_monarque", "Constance", "plus_longue_serie", 60),
    Defi("titre_intraitable", "Constance", "plus_longue_serie", 90),
    Defi("titre_increvable", "Constance", "jours_sans_bouclier", 21),
    Defi("cadre_obsidienne", "Constance", "jours_sans_bouclier", 14),
    Defi("theme_fer_blanc", "Constance", "jours_sans_bouclier", 56),
    Defi("emb_tour", "Constance", "jours_travailles", 60),
    Defi("fin_aurore", "Constance", "jours_travailles", 200),
    Defi("emb_spirale", "Constance", "sessions_terminees", 100),
    Defi("fin_enclume", "Constance", "sessions_terminees", 200),

    # ---- Parole tenue : l'engagement de la semaine -----------------------
    Defi("theme_jade", "Parole tenue", "semaines_tenues", 6),
    Defi("cadre_givre", "Parole tenue", "semaines_tenues", 10),
    Defi("cadre_eclipse", "Parole tenue", "semaines_tenues", 24),

    # ---- Ermite : la soirée qui ne part pas en scroll ---------------------
    Defi("titre_dernier_debout", "Ermite", "semaines_sans_scroll", 2),
    Defi("titre_sans_ombre", "Ermite", "semaines_sans_scroll", 6),
    Defi("theme_vert_de_gris", "Franchise", "jours_off_declares", 5),
    Defi("emb_phenix", "Franchise", "retours_apres_arret", 3),

    # ---- Bâtisseur : ce qui reste quand la saison est finie ---------------
    Defi("emb_sceau", "Bâtisseur", "etapes_finies", 15),
    Defi("cadre_meteore", "Bâtisseur", "etapes_finies", 60),
    Defi("cadre_vitrail", "Bâtisseur", "etapes_dans_une_saison", 8),
    Defi("fin_sceau", "Bâtisseur", "projets_termines", 1),
    Defi("emb_couronne", "Bâtisseur", "projets_termines", 2),
    Defi("emb_trident", "Polyvalence", "branches_dans_une_semaine", 3),

    # ---- Saison : ce qui se compte en mois --------------------------------
    Defi("fin_fracture", "Saison", "boss_abattus", 1),
    Defi("fin_eclipse", "Saison", "boss_abattus", 4),
    Defi("fin_ascension", "Saison", "saisons_closes", 3),
)

PAR_CARTE = {d.carte: d for d in CATALOGUE}

# Les cartes que le tirage et la Forge doivent ignorer. Calculé une fois : la
# question se pose à chaque tirage, et parcourir le catalogue à chaque fois
# pour une réponse constante serait du travail refait quatre-vingts fois par an.
CARTES_A_DEFI = frozenset(PAR_CARTE)


def pour(carte_key: str) -> Defi | None:
    return PAR_CARTE.get(carte_key)


def atteints(mesures: dict[str, int]) -> list[str]:
    """Les cartes dont le défi est rempli, d'après les compteurs.

    Ne regarde pas ce qui est déjà possédé : l'appelant le sait, et une règle
    qui interrogerait la base cesserait d'être testable sans elle.
    """
    return [d.carte for d in CATALOGUE if mesures.get(d.fait, 0) >= d.seuil]
