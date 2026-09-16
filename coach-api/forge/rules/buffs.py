"""Les cartes donnent des buffs, et les hauts faits donnent l'apparence.

*(Inversé le 16 septembre 2026. Remplace la règle du §17 « le loot est de
l'apparence, jamais du pouvoir ».)*

**Ce que l'ancienne règle protégeait, et comment on le garde.** Une carte se
tire : lui donner du pouvoir, c'est récompenser la chance. Trois garde-fous
remplacent l'interdiction, et ils sont la moitié de ce module :

1. **le tirage est déjà payé par du travail.** Rien ne tombe sans avoir terminé
   une étape ou posé une longue séance (§12.6). C'est le *contenu* du tirage qui
   est aléatoire, jamais le droit d'y avoir accès ;
2. **une charge, pas un passif.** Une carte donne une charge qu'on dépense quand
   on veut. La malchance coûte donc une occasion, jamais une puissance qui
   manquerait tous les jours — c'est ce qui la distingue d'une relique (§12.8),
   qui elle est permanente et vient d'un haut fait, donc d'un travail nommé ;
3. **le cadre reste hors d'atteinte.** Aucune carte ne touche au blocage, au
   couvre-feu, au streak, aux boucliers, au rang, aux slots ni aux gardes. La
   seule brèche autorisée est le **sas** (§4.6), qui est déjà une soupape
   bornée, payante et prévue. Aucune carte ne peut acheter une soirée.

**La rotation.** Chaque saison ouvre son propre lot de cartes tirables. Ce qui a
été tiré reste acquis et utilisable pour toujours — seule la *pêche* change.
Sans rotation, la centième carte d'un catalogue fixe est une ligne de plus dans
une liste ; avec elle, une saison a quelque chose à elle qu'on ne reverra pas
avant longtemps.
"""

from __future__ import annotations

from dataclasses import dataclass

from .loot import COMMUN, EPIQUE, LEGENDAIRE, RARE

# Les effets, et eux seuls. Une énumération fermée, comme pour les reliques :
# un effet ne s'invente pas au fil de l'eau, sinon la promesse « le cadre est
# hors d'atteinte » se dissout en une saison.
SAS_PLUS = "sas_plus"              # le prochain sas dure plus longtemps
SAS_SECOND = "sas_second"          # un sas de plus aujourd'hui
SAS_GRATUIT = "sas_gratuit"        # le prochain sas ne coûte pas sa journée de réseaux
XP_SEANCE = "xp_seance"            # la prochaine séance rapporte plus d'XP
BOSS_SEANCE = "boss_seance"        # la prochaine séance frappe plus fort
ECLATS_JOUR = "eclats_jour"        # les Éclats du jour sont majorés
TIRAGE_CHANCEUX = "tirage_chanceux"  # le prochain tirage part d'un cran plus haut

EFFETS = (
    SAS_PLUS,
    SAS_SECOND,
    SAS_GRATUIT,
    XP_SEANCE,
    BOSS_SEANCE,
    ECLATS_JOUR,
    TIRAGE_CHANCEUX,
)

# Les effets qui touchent au sas — la seule brèche autorisée dans le cadre.
EFFETS_DE_SAS = (SAS_PLUS, SAS_SECOND, SAS_GRATUIT)


@dataclass(frozen=True)
class Buff:
    """Une carte de buff. ``value`` se lit selon l'effet — minutes, ou facteur."""

    key: str
    label: str
    rarity: str
    effect: str
    value: float
    lore: str

    @property
    def ligne(self) -> str:
        """Ce que la carte promet, en une phrase. Affichée telle quelle."""
        if self.effect == SAS_PLUS:
            return f"Le prochain sas dure {int(self.value)} minutes de plus."
        if self.effect == SAS_SECOND:
            return "Un second sas aujourd'hui."
        if self.effect == SAS_GRATUIT:
            return "Le prochain sas ne compte pas dans ton budget réseaux."
        if self.effect == XP_SEANCE:
            return f"La prochaine séance rapporte ×{self.value:g} d'XP."
        if self.effect == BOSS_SEANCE:
            return f"La prochaine séance inflige ×{self.value:g} de dégâts au boss."
        if self.effect == ECLATS_JOUR:
            return f"Les Éclats gagnés aujourd'hui sont majorés de {int(self.value * 100)} %."
        return "Le prochain tirage part d'un cran plus haut."


CATALOGUE: tuple[Buff, ...] = (
    # ---- Le souffle : la brèche du sas, bornée ------------------------
    Buff("respiration", "Respiration", COMMUN, SAS_PLUS, 10,
         "Dix minutes de plus. Rien qui change une soirée, assez pour finir ce qu'on regardait."),
    Buff("longue_respiration", "Longue respiration", RARE, SAS_PLUS, 20,
         "Le double du sas d'une saison douce, en une fois."),
    Buff("second_souffle", "Second souffle", RARE, SAS_SECOND, 1,
         "La soupape s'ouvre deux fois. Le couvre-feu, lui, ne bouge pas."),
    Buff("blanc_seing", "Blanc-seing", EPIQUE, SAS_GRATUIT, 1,
         "Un sas qui ne s'inscrit nulle part. Le compteur de jours tenus ne bouge pas."),

    # ---- Le travail : ce qu'une séance rapporte -----------------------
    Buff("etincelle", "Étincelle", COMMUN, XP_SEANCE, 1.25,
         "Un quart d'XP en plus sur la prochaine. À dépenser sur une séance qu'on sait longue."),
    Buff("braise_ardente", "Braise ardente", RARE, XP_SEANCE, 1.5,
         "La moitié en plus. Le soir où l'on s'y met vraiment."),
    Buff("forge_blanche", "Forge blanche", LEGENDAIRE, XP_SEANCE, 2.0,
         "Le double. Une fois, et on s'en souvient."),

    # ---- Le boss : ce qu'une séance abat ------------------------------
    Buff("lame_ebrechee", "Lame ébréchée", COMMUN, BOSS_SEANCE, 1.5,
         "Le boss encaisse une fois et demie ce que la séance vaut."),
    Buff("coup_franc", "Coup franc", RARE, BOSS_SEANCE, 2.0,
         "Deux fois les dégâts. Le compte des minutes, lui, ne bouge pas."),
    Buff("estocade", "Estocade", EPIQUE, BOSS_SEANCE, 3.0,
         "Trois fois. Gardée pour le dernier jour d'une saison qui se joue de peu."),

    # ---- Les Éclats et la chance --------------------------------------
    Buff("butin", "Butin", COMMUN, ECLATS_JOUR, 0.5,
         "La moitié en plus sur tout ce que la journée rapporte en Éclats."),
    Buff("filon", "Filon", RARE, ECLATS_JOUR, 1.0,
         "Le double, sur une journée entière."),
    Buff("main_chanceuse", "Main chanceuse", EPIQUE, TIRAGE_CHANCEUX, 1,
         "Le prochain tirage monte d'un cran. Rien n'est garanti, tout est incliné."),
)

PAR_CLE = {b.key: b for b in CATALOGUE}

# La rotation : combien de cartes une saison rend tirables.
#
# Huit sur treize : assez pour que deux saisons ne se ressemblent pas, assez peu
# pour qu'un lot se complète. Un lot qu'on ne peut pas finir ne donne pas envie
# de le poursuivre — c'est le défaut des collections de trois cents pièces.
TAILLE_DU_LOT = 8


def lot_de_saison(index: int) -> tuple[Buff, ...]:
    """Les cartes tirables d'une saison, dans l'ordre du catalogue.

    Déterministe : la même saison rend toujours le même lot, aujourd'hui comme
    dans six mois. Un lot tiré au sort à chaque lecture ferait apparaître et
    disparaître des cartes au fil des rechargements.

    La fenêtre glisse d'une carte par saison plutôt que de repartir d'un tirage
    neuf : deux saisons voisines partagent donc une partie de leur lot, et une
    carte manquée revient — plus tard, pas jamais.
    """
    if not CATALOGUE:
        return ()
    depart = max(0, index - 1) % len(CATALOGUE)
    lot = [CATALOGUE[(depart + i) % len(CATALOGUE)] for i in range(min(TAILLE_DU_LOT, len(CATALOGUE)))]
    return tuple(sorted(lot, key=lambda b: CATALOGUE.index(b)))


def par_rarete(lot: tuple[Buff, ...]) -> dict[str, list[Buff]]:
    """Le lot rangé par rareté. Une rareté absente du lot rend une liste vide."""
    table: dict[str, list[Buff]] = {}
    for buff in lot:
        table.setdefault(buff.rarity, []).append(buff)
    return table


def touche_au_cadre(effect: str) -> bool:
    """Vrai si l'effet sort de la couche jeu. Seul le sas a le droit (§4.6).

    Existe pour être appelée par un test : la frontière se perd au premier effet
    ajouté à la va-vite, et c'est exactement ce que l'ancienne interdiction du
    §17 empêchait.
    """
    return effect in EFFETS_DE_SAS
