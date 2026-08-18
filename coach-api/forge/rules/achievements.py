"""Les hauts faits, et ce qui les déclenche (SPEC §12.3, §12.8).

Ce module existait en creux : quatre hauts faits étaient déclarés dans un
dictionnaire de ``services``, deux seulement étaient décernés, et les reliques
du §12.8 en réclamaient trois qui n'avaient aucun code pour les accorder.
Quatre reliques sur cinq étaient donc **inatteignables** — pas cachées, pas
difficiles : impossibles.

## Ce qu'un haut fait a le droit de récompenser

Une seule chose : **du travail réel, ou un comportement honnête**. Jamais de la
chance, jamais du volume brut poussé à bout.

La nuance entre les deux compte. « Cent heures cumulées » récompense du travail.
« Six sessions dans la même journée » récompenserait le sur-régime du §0.2 — le
diagnostic dit que le problème n'est pas la motivation mais l'absence de
plafond, et un haut fait qui applaudit le dépassement travaille contre le
produit. On n'en trouvera donc aucun ici qui se gagne en une soirée d'excès.

Le troisième registre est celui des hauts faits de **franchise** : déclarer un
jour off à l'avance, sortir d'une veille et travailler le jour même. Ils ne
mesurent aucune performance. Ils reconnaissent qu'on a utilisé le système comme
il demande à l'être, plutôt que de le subir puis de s'excuser.

## Pourquoi les conditions sont des données

Chaque haut fait dit quel **fait** il regarde et à partir de quel seuil il
tombe. Rien d'autre. L'évaluation n'a donc aucune logique par cas, ce qui
supprime la classe de bugs qui a produit la situation d'origine : un haut fait
déclaré ici sans être branché nulle part. Ajouter une entrée à ce tuple suffit
à le rendre atteignable, et un test vérifie que chaque fait cité existe
réellement.
"""

from __future__ import annotations

from dataclasses import dataclass

# Les faits mesurables. Tous sont des compteurs **monotones** ou des maxima :
# un haut fait ne se reprend jamais (§17), donc il ne peut s'appuyer que sur
# des grandeurs qui ne redescendent pas.
FAITS = (
    "sessions_terminees",
    "heures_totales",
    "jours_travailles",
    "plus_longue_serie",
    "jours_sans_bouclier",
    "etapes_finies",
    "etapes_dans_une_saison",
    "projets_termines",
    "sessions_avant_20h",
    "sessions_longues",
    "semaines_sans_scroll",
    "branches_dans_une_semaine",
    "saisons_closes",
    "boss_abattus",
    "semaines_tenues",
    "jours_off_declares",
    "retours_apres_arret",
    "retours_de_veille",
    "cartes_possedees",
    "annees_accomplies",
)


@dataclass(frozen=True)
class Achievement:
    key: str
    label: str
    description: str
    fait: str
    seuil: int
    # Ce que le haut fait raconte. Sert au classement à l'écran, et à rien
    # d'autre — un haut fait ne donne aucun droit par lui-même.
    registre: str = "travail"   # travail | franchise | saison | collection


CATALOGUE: tuple[Achievement, ...] = (
    # ---- Les premières fois -------------------------------------------
    Achievement(
        "premier_sang", "Premier sang",
        "Ta première session enregistrée.",
        "sessions_terminees", 1,
    ),
    Achievement(
        "premiere_etape", "Première pierre",
        "Une étape de roadmap terminée. C'est ce qui fait avancer un projet, pas les minutes.",
        "etapes_finies", 1,
    ),
    # ---- Le volume, sur la durée --------------------------------------
    Achievement(
        "centurion", "Centurion",
        "Cent heures de travail cumulées.",
        "heures_totales", 100,
    ),
    Achievement(
        "quintal", "Cinq cents",
        "Cinq cents heures. Il n'y a pas de raccourci vers ce chiffre.",
        "heures_totales", 500,
    ),
    Achievement(
        "mille", "Millier",
        "Mille heures cumulées.",
        "heures_totales", 1000,
    ),
    Achievement(
        "assidu", "Assidu",
        "Cent journées travaillées, quelle qu'en ait été la durée.",
        "jours_travailles", 100,
    ),
    # ---- La régularité -------------------------------------------------
    Achievement(
        "constance", "Constance",
        "Trente jours d'affilée avec du travail posé.",
        "plus_longue_serie", 30,
    ),
    Achievement(
        "increvable", "Increvable",
        "Vingt-huit jours sans consommer de bouclier.",
        "jours_sans_bouclier", 28,
    ),
    Achievement(
        "fidele", "Parole tenue",
        "Douze semaines où tous les engagements ont été tenus.",
        "semaines_tenues", 12,
    ),
    Achievement(
        "leve_tot", "Lève-tôt",
        "Cinquante sessions démarrées avant vingt heures.",
        "sessions_avant_20h", 50,
    ),
    Achievement(
        "longue_haleine", "Longue haleine",
        "Cinquante sessions de cinquante minutes.",
        "sessions_longues", 50,
    ),
    # ---- Ce qui se construit -------------------------------------------
    Achievement(
        "chirurgien", "Chirurgien",
        "Dix étapes de roadmap terminées dans une même saison.",
        "etapes_dans_une_saison", 10,
    ),
    Achievement(
        "artisan", "Artisan",
        "Un projet mené jusqu'à sa dernière étape.",
        "projets_termines", 1,
    ),
    Achievement(
        "maitre_d_oeuvre", "Maître d'œuvre",
        "Trois projets menés jusqu'au bout.",
        "projets_termines", 3,
    ),
    Achievement(
        "polyvalent", "Polyvalent",
        "Trois branches de l'arbre nourries dans la même semaine.",
        "branches_dans_une_semaine", 3,
    ),
    # ---- Les gardes et le scroll ---------------------------------------
    Achievement(
        "ermite", "Ermite",
        "Une semaine entière sans une minute de scroll passif.",
        "semaines_sans_scroll", 1,
        registre="franchise",
    ),
    # ---- La franchise ---------------------------------------------------
    Achievement(
        "retour_du_neant", "Retour du néant",
        "Reprendre après au moins trois jours d'arrêt.",
        "retours_apres_arret", 1,
        registre="franchise",
    ),
    Achievement(
        "honnete", "Dit à l'avance",
        "Dix jours off déclarés la veille ou plus tôt, jamais après coup.",
        "jours_off_declares", 10,
        registre="franchise",
    ),
    Achievement(
        "au_retour", "Au retour",
        "Sortir d'une veille et travailler le jour même.",
        "retours_de_veille", 1,
        registre="franchise",
    ),
    # ---- Les saisons -----------------------------------------------------
    Achievement(
        "premier_hiver", "Première saison",
        "Une saison menée jusqu'à sa clôture.",
        "saisons_closes", 1,
        registre="saison",
    ),
    Achievement(
        "chasseur", "Chasseur",
        "Un boss de saison abattu.",
        "boss_abattus", 1,
        registre="saison",
    ),
    Achievement(
        "grand_chasseur", "Grand chasseur",
        "Six boss abattus.",
        "boss_abattus", 6,
        registre="saison",
    ),
    Achievement(
        "annaliste", "Annaliste",
        "Une année entière — douze saisons closes.",
        "annees_accomplies", 1,
        registre="saison",
    ),
    # ---- La collection ---------------------------------------------------
    Achievement(
        "collectionneur", "Collectionneur",
        "Vingt cartes différentes trouvées.",
        "cartes_possedees", 20,
        registre="collection",
    ),
    Achievement(
        "conservateur", "Conservateur",
        "Quarante cartes différentes trouvées.",
        "cartes_possedees", 40,
        registre="collection",
    ),
)

PAR_CLE = {a.key: a for a in CATALOGUE}
CLES = tuple(a.key for a in CATALOGUE)


def atteints(faits: dict[str, int]) -> list[Achievement]:
    """Les hauts faits dont le seuil est franchi, dans l'ordre du catalogue.

    Rend **tout** ce qui est atteint, pas seulement le nouveau : l'appelant
    connaît déjà ce qui est acquis et n'a qu'à faire la différence. Une fonction
    qui rendrait « le nouveau » aurait besoin de savoir l'ancien, donc de la
    base, donc ne serait plus pure.
    """
    return [a for a in CATALOGUE if faits.get(a.fait, 0) >= a.seuil]


def prochain(faits: dict[str, int], *, acquis: set[str], combien: int = 3) -> list[dict]:
    """Ce qui est le plus proche de tomber, pour l'afficher.

    Trié par la part déjà parcourue et non par la distance restante : « 9 sur
    10 » est plus proche que « 90 sur 1000 », alors que la distance brute dit
    l'inverse. C'est la part qui donne envie de finir.
    """
    restants = [a for a in CATALOGUE if a.key not in acquis]
    avec_part = [
        (a, min(1.0, faits.get(a.fait, 0) / a.seuil) if a.seuil else 0.0) for a in restants
    ]
    avec_part.sort(key=lambda couple: couple[1], reverse=True)

    return [
        {
            "key": a.key,
            "label": a.label,
            "description": a.description,
            "registre": a.registre,
            "valeur": faits.get(a.fait, 0),
            "seuil": a.seuil,
            "part": round(part, 3),
        }
        for a, part in avec_part[:combien]
        if part > 0
    ]
