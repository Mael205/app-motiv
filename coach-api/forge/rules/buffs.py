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

# Les quatre cartes qui sortent du sas (16 septembre 2026). Aucune ne supprime
# le travail dû — sauf la dernière, et c'est pour ça qu'elle est légendaire.
CARTE_BLANCHE = "carte_blanche"    # ce soir, n'importe quel projet tient le rendez-vous
REPORT = "report"                  # le rendez-vous du jour passe à demain
PETIT_PAS = "petit_pas"            # ce soir, quinze minutes suffisent
JOUR_OFF = "jour_off"              # une journée neutre, hors quota

EFFETS = (
    SAS_PLUS,
    SAS_SECOND,
    SAS_GRATUIT,
    SAS_IMMEDIAT,
    SAS_DEMAIN,
    SAS_JUSQU_AU_COUVRE_FEU,
    SILENCE,
    CARTE_BLANCHE,
    REPORT,
    PETIT_PAS,
    JOUR_OFF,
)

# Les effets qui durent une journée entière et ne se consomment donc pas sur un
# événement : ils valent du lever au coucher, et se relisent tels quels.
EFFETS_DU_JOUR = (SILENCE, CARTE_BLANCHE, PETIT_PAS, REPORT, JOUR_OFF)

# Le plancher qu'une carte peut descendre — jamais plus bas. « Petit pas »
# abaisse la barre d'un soir ; il ne supprime pas le démarrage, qui est le vrai
# coût (§4.1).
PETIT_PAS_MINUTES = 15

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
        if self.effect == CARTE_BLANCHE:
            return "Ce soir, n'importe quel projet tient le rendez-vous."
        if self.effect == REPORT:
            return "Le rendez-vous d'aujourd'hui passe à demain — qui en portera deux."
        if self.effect == PETIT_PAS:
            return f"Ce soir, {PETIT_PAS_MINUTES} minutes suffisent au lieu de 25."
        if self.effect == JOUR_OFF:
            return "Une journée neutre, hors quota : ni tenue, ni ratée."
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

    # ---- La soirée : ce qui se déplace, et ce qui s'allège ------------
    #
    # Aucune de ces cartes n'efface le travail, sauf la dernière. « Carte
    # blanche » change le projet, « Report » change le jour, « Petit pas »
    # change la barre — les trois laissent l'obligation de s'y mettre, qui est
    # le vrai coût (§4.1).
    Buff("carte_blanche", "Carte blanche", COMMUN, CARTE_BLANCHE, 1,
         "Le rendez-vous tient avec le projet que tu veux. Tu poses tes minutes quand même : "
         "ce n'est pas la soirée qui est rendue, c'est le choix."),
    Buff("petit_pas", "Petit pas", RARE, PETIT_PAS, 1,
         "Quinze minutes au lieu de vingt-cinq. Le démarrage reste dû, et c'est lui "
         "qui coûte le plus cher."),
    Buff("report", "Report", EPIQUE, REPORT, 1,
         "La séance de ce soir est due demain, en plus de celle de demain. Rien n'est effacé, "
         "tout est déplacé — et la dette se paie."),
    Buff("treve", "Trêve", LEGENDAIRE, JOUR_OFF, 1,
         "Une journée neutre, hors quota. La seule carte du jeu qui rende une soirée entière, "
         "et la seule à être légendaire pour cette raison."),
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
    """Vrai si l'effet touche à la soirée elle-même, et pas seulement au sas.

    Existe pour être appelée par un test : la frontière se perd au premier effet
    ajouté à la va-vite, et c'est exactement ce que l'ancienne interdiction du
    §17 empêchait.
    """
    return effect in (CARTE_BLANCHE, REPORT, PETIT_PAS, JOUR_OFF)


def efface_une_soiree(effect: str) -> bool:
    """La seule carte qui rende une soirée entière. Il n'y en a qu'une, exprès.

    Les autres déplacent le travail ou l'allègent ; celle-ci le supprime. C'est
    la limite haute de tout le système : au-delà, une carte remplacerait une
    séance, et le §17 redeviendrait nécessaire.
    """
    return effect == JOUR_OFF
