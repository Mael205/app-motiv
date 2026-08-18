"""Reliques : les seuls bonus passifs du système (SPEC §12.8).

C'est l'exception à la règle du §17 — *le loot est de l'apparence, jamais du
pouvoir* — et elle est bornée avec soin :

> Quelques hauts faits rares donnent un bonus passif permanent et **modéré**.
> Plafonnées à **3 reliques équipées**, pour que la progression reste sensible
> sans devenir absurde.

Trois garde-fous découlent de là, et ils sont appliqués ici :

1. **Une relique se gagne par un haut fait, jamais par un tirage.** Elle
   récompense donc du travail réel et non de la chance, ce qui est exactement la
   ligne que le §17 défend.
2. **Aucune relique ne touche au streak, aux rangs ou aux gardes.** Elle ajoute
   une marge — un bouclier, un jour off — ou une petite prime d'XP. Une relique
   qui rendrait une journée « tenue » sans travail transformerait le cœur du
   système en objet cosmétique.
3. **Trois équipées au maximum**, et le choix est réversible. Le plafond crée
   un arbitrage : gagner une quatrième relique oblige à décider ce qui compte,
   ce qui vaut mieux qu'un empilement où plus rien ne se ressent.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_EQUIPEES = 3

# Les effets possibles. La liste est fermée à dessein : un effet ne s'invente
# pas au fil de l'eau, sinon la promesse « modéré » se dissout en une saison.
BOUCLIER_SUPP = "bouclier_supp"
JOUR_OFF_SUPP = "jour_off_supp"
XP_MATINAL = "xp_matinal"
ECLATS_BONUS = "eclats_bonus"
DEGATS_BOSS = "degats_boss"


@dataclass(frozen=True)
class Relic:
    key: str
    label: str
    lore: str
    effect: str
    value: float
    achievement: str   # le haut fait qui la débloque
    emblem: str


CATALOGUE: tuple[Relic, ...] = (
    Relic(
        key="coeur_increvable",
        label="Cœur increvable",
        lore="Vingt-huit jours sans céder un bouclier. Le corps se souvient.",
        effect=BOUCLIER_SUPP,
        value=1,
        achievement="increvable",
        emblem="◈",
    ),
    Relic(
        key="souffle_du_retour",
        label="Souffle du retour",
        lore="Revenir après une série cassée est plus dur que ne jamais la casser.",
        effect=JOUR_OFF_SUPP,
        value=1,
        achievement="retour_du_neant",
        emblem="⟲",
    ),
    Relic(
        key="lampe_de_l_aube",
        label="Lampe de l'aube",
        lore="Ce qui est fait avant vingt heures n'est pris à personne.",
        effect=XP_MATINAL,
        value=0.05,
        achievement="leve_tot",
        emblem="☼",
    ),
    Relic(
        key="bourse_du_veilleur",
        label="Bourse du veilleur",
        lore="Une semaine entière sans une minute de scroll passif.",
        effect=ECLATS_BONUS,
        value=0.15,
        achievement="ermite",
        emblem="◍",
    ),
    Relic(
        key="lame_polyvalente",
        label="Lame polyvalente",
        lore="Trois branches qui poussent la même semaine. Rien n'est à l'arrêt.",
        effect=DEGATS_BOSS,
        value=0.10,
        achievement="polyvalent",
        emblem="✧",
    ),

    # ---- Deuxième vague -------------------------------------------------
    # Les valeurs restent dans la même fourchette que les cinq premières : rien
    # au-dessus de 15 %, rien au-dessus d'un bouclier ou d'un jour off. Le §12.8
    # dit « modéré », et le plafond de trois équipées ne protège de rien si
    # chaque relique prise séparément est déjà forte.
    Relic(
        key="marteau_du_chirurgien",
        label="Marteau du chirurgien",
        lore="Dix étapes closes dans une seule saison. Ce sont les étapes qui font "
             "avancer un projet, pas les heures.",
        effect=DEGATS_BOSS,
        value=0.10,
        achievement="chirurgien",
        emblem="⚒",
    ),
    Relic(
        key="pierre_de_fondation",
        label="Pierre de fondation",
        lore="Un projet mené jusqu'à sa dernière étape. Il y en a peu.",
        effect=ECLATS_BONUS,
        value=0.15,
        achievement="artisan",
        emblem="◧",
    ),
    Relic(
        key="serment_tenu",
        label="Serment tenu",
        lore="Douze semaines où tous les engagements ont été tenus. Le rang mesure "
             "ça et rien d'autre.",
        effect=BOUCLIER_SUPP,
        value=1,
        achievement="fidele",
        emblem="◫",
    ),
    Relic(
        key="souffle_long",
        label="Souffle long",
        lore="Cinquante sessions de cinquante minutes. Le corps finit par savoir "
             "s'asseoir.",
        effect=XP_MATINAL,
        value=0.05,
        achievement="longue_haleine",
        emblem="≋",
    ),
    Relic(
        key="pas_de_cote",
        label="Pas de côté",
        lore="Dix jours off déclarés la veille, jamais après coup. Prévenir n'est "
             "pas renoncer.",
        effect=JOUR_OFF_SUPP,
        value=1,
        achievement="honnete",
        emblem="⌇",
    ),
    Relic(
        key="tete_de_chasse",
        label="Tête de chasse",
        lore="Six boss abattus. Ils reviennent chaque saison, sous un autre nom.",
        effect=DEGATS_BOSS,
        value=0.10,
        achievement="grand_chasseur",
        emblem="☗",
    ),
    Relic(
        key="anneau_des_douze",
        label="Anneau des douze",
        lore="Une année entière. Douze saisons, douze boss, douze noms.",
        effect=ECLATS_BONUS,
        value=0.15,
        achievement="annaliste",
        emblem="◯",
    ),
)

PAR_CLE = {r.key: r for r in CATALOGUE}
PAR_HAUT_FAIT = {r.achievement: r for r in CATALOGUE}


@dataclass(frozen=True)
class Bonuses:
    """Le cumul des reliques équipées. Tout est additif, rien n'est multiplicatif.

    L'additivité n'est pas un détail d'implémentation : deux bonus qui se
    multiplient produisent une combinaison que personne n'a calculée, et c'est
    ainsi qu'un système « modéré » devient absurde sans que personne ne l'ait
    décidé.
    """

    extra_shields: int = 0
    extra_days_off: int = 0
    early_xp_bonus: float = 0.0
    shard_bonus: float = 0.0
    boss_damage_bonus: float = 0.0

    @property
    def any(self) -> bool:
        return bool(
            self.extra_shields
            or self.extra_days_off
            or self.early_xp_bonus
            or self.shard_bonus
            or self.boss_damage_bonus
        )


def unlocked_by(achievement_key: str) -> Relic | None:
    """La relique que débloque un haut fait, s'il en débloque une."""
    return PAR_HAUT_FAIT.get(achievement_key)


def bonuses(equipped_keys) -> Bonuses:
    """Le cumul des reliques équipées, plafond compris.

    Le plafond est appliqué **ici** et pas seulement à l'équipement : c'est le
    seul endroit par lequel passent tous les calculs, donc le seul où la règle
    ne peut pas être contournée par une écriture directe en base.
    """
    retenues = [PAR_CLE[k] for k in list(equipped_keys)[:MAX_EQUIPEES] if k in PAR_CLE]

    return Bonuses(
        extra_shields=sum(int(r.value) for r in retenues if r.effect == BOUCLIER_SUPP),
        extra_days_off=sum(int(r.value) for r in retenues if r.effect == JOUR_OFF_SUPP),
        early_xp_bonus=sum(r.value for r in retenues if r.effect == XP_MATINAL),
        shard_bonus=sum(r.value for r in retenues if r.effect == ECLATS_BONUS),
        boss_damage_bonus=sum(r.value for r in retenues if r.effect == DEGATS_BOSS),
    )


def can_equip(equipped_keys, key: str) -> tuple[bool, str]:
    """Peut-on équiper cette relique ? Rend la réponse **et** son motif.

    Un refus muet dans une interface de jeu se lit comme un bug. Le motif est
    donc rendu pour être affiché tel quel.
    """
    equipees = list(equipped_keys)
    if key in equipees:
        return False, "Cette relique est déjà équipée."
    if key not in PAR_CLE:
        return False, "Relique inconnue."
    if len(equipees) >= MAX_EQUIPEES:
        return False, (
            f"{MAX_EQUIPEES} reliques équipées au maximum. Retires-en une : "
            "le plafond existe pour que le choix se sente."
        )
    return True, ""
