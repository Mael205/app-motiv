"""Les cartes donnent des buffs, et les hauts faits donnent l'apparence.

*(Inversé le 16 septembre 2026. Remplace la règle du §17 « le loot est de
l'apparence, jamais du pouvoir ».)*

**Ce qu'une carte donne** *(resserré le 16 septembre 2026)* : du **temps d'écran
rendu**, et rien d'autre. Ni XP, ni Éclats, ni dégâts au boss — un chiffre qui
monte plus vite ne se ressent pas, et c'est précisément ce qu'on reprochait à
l'ancienne collection de couleurs. Ce qu'une carte change, on le vit : vingt
minutes de plus, un second sas, une soirée sans notification.

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
   bornée, payante et prévue — et même la plus généreuse des cartes s'arrête au
   couvre-feu. Aucune carte ne peut acheter une soirée.

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
SAS_IMMEDIAT = "sas_immediat"      # le prochain sas s'ouvre sans les soixante secondes
SAS_DEMAIN = "sas_demain"          # un sas de plus, demain
SAS_JUSQU_AU_COUVRE_FEU = "sas_jusqu_au_couvre_feu"   # le sas court jusqu'à 23h
SILENCE = "silence"                # le coach ne notifie pas aujourd'hui

EFFETS = (
    SAS_PLUS,
    SAS_SECOND,
    SAS_GRATUIT,
    SAS_IMMEDIAT,
    SAS_DEMAIN,
    SAS_JUSQU_AU_COUVRE_FEU,
    SILENCE,
)

# Les effets qui touchent au sas — la seule brèche autorisée dans le cadre.
EFFETS_DE_SAS = (
    SAS_PLUS,
    SAS_SECOND,
    SAS_GRATUIT,
    SAS_IMMEDIAT,
    SAS_DEMAIN,
    SAS_JUSQU_AU_COUVRE_FEU,
)


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
        if self.effect == SAS_IMMEDIAT:
            return "Le prochain sas s'ouvre tout de suite, sans les soixante secondes."
        if self.effect == SAS_DEMAIN:
            return "Un sas de plus demain."
        if self.effect == SAS_JUSQU_AU_COUVRE_FEU:
            return "Le prochain sas court jusqu'au couvre-feu."
        return "Le coach ne t'envoie aucune notification aujourd'hui."


CATALOGUE: tuple[Buff, ...] = (
    # ---- Le souffle : du temps d'écran rendu, et rien d'autre ---------
    Buff("respiration", "Respiration", COMMUN, SAS_PLUS, 10,
         "Dix minutes de plus. Rien qui change une soirée, assez pour finir ce qu'on regardait."),
    Buff("bouffee_d_air", "Bouffée d'air", COMMUN, SAS_IMMEDIAT, 1,
         "Le sas s'ouvre à l'instant. L'attente existe pour laisser passer l'impulsion ; "
         "cette carte est la seule chose qui la saute, et elle se paie."),
    Buff("longue_respiration", "Longue respiration", RARE, SAS_PLUS, 20,
         "Le double du sas d'une saison douce, en une fois."),
    Buff("second_souffle", "Second souffle", RARE, SAS_SECOND, 1,
         "La soupape s'ouvre deux fois. Le couvre-feu, lui, ne bouge pas."),
    Buff("reserve", "Réserve", RARE, SAS_DEMAIN, 1,
         "Un sas mis de côté pour demain. C'est la seule carte qui prête à la journée suivante."),
    Buff("grand_large", "Grand large", EPIQUE, SAS_PLUS, 45,
         "Trois quarts d'heure. Une vraie soirée de rien, décidée d'avance."),
    Buff("blanc_seing", "Blanc-seing", EPIQUE, SAS_GRATUIT, 1,
         "Un sas qui ne s'inscrit nulle part. Le compteur de jours tenus ne bouge pas."),
    Buff("plein_ciel", "Plein ciel", LEGENDAIRE, SAS_JUSQU_AU_COUVRE_FEU, 1,
         "Le sas court jusqu'au couvre-feu. C'est la carte la plus généreuse du jeu, "
         "et elle s'arrête quand même à 23h — rien n'ouvre la nuit."),

    # ---- Le silence : le coach se tait -------------------------------
    Buff("silence", "Silence", COMMUN, SILENCE, 1,
         "Aucune notification aujourd'hui. Le blocage, lui, ne se tait pas : "
         "ce qui disparaît est le rappel, jamais le cadre."),
)

PAR_CLE = {b.key: b for b in CATALOGUE}

# La rotation : combien de cartes une saison rend tirables.
#
# Six sur neuf : assez pour que deux saisons ne se ressemblent pas, assez peu
# pour qu'un lot se complète. Un lot qu'on ne peut pas finir ne donne pas envie
# de le poursuivre — c'est le défaut des collections de trois cents pièces.
TAILLE_DU_LOT = 6


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
