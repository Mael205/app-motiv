"""XP, niveaux, rangs et plafond de régime.

Le plafond est la mécanique qui répond au diagnostic §0.2 : le problème n'est
pas la motivation mais l'absence de plafond. À partir de la 4ᵉ session du jour
la récompense s'éteint progressivement — la session reste enregistrée, les
heures comptent, la roadmap avance, seule l'XP disparaît.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FIRST_SESSION_BONUS = 20
EARLY_BONUS = 10
EARLY_HOUR = 20                 # « démarrée avant 20h »
STREAK_STEP = 0.05
STREAK_CAP = 10                 # multiplicateur de streak plafonné à ×1.5
MOMENTUM_STEP = 0.05
MOMENTUM_CAP = 1.25

# Dégressivité par rang de session dans la journée : les trois premières
# comptent plein, la quatrième à moitié, les suivantes plus du tout.
DEGRESSIVITY = (1.0, 1.0, 1.0, 0.5)

# Le rang ne vit plus ici : il mesure la fiabilité, pas le volume, et se calcule
# dans ``forge/rules/ranks.py`` sur les semaines d'engagements tenus (SPEC §4.4).
# L'XP garde les niveaux, le loot, les dégâts au boss et le score de saison.


@dataclass
class XpBreakdown:
    """Le détail du calcul, pour que l'interface puisse l'afficher ligne à ligne."""

    base: int = 0
    first_of_day: int = 0
    early: int = 0
    streak_multiplier: float = 1.0
    momentum_multiplier: float = 1.0
    modifier_multiplier: float = 1.0
    degressivity: float = 1.0
    total: int = 0
    notes: list[str] = field(default_factory=list)


def session_xp(
    *,
    minutes: int,
    rank_in_day: int,
    is_first_of_day: bool,
    started_hour: int,
    streak: int,
    days_worked_this_week: int = 1,
    momentum_multiplier: float | None = None,
    early_bonus_ratio: float = 0.0,
    modifier_multiplier: float = 1.0,
    full_xp_sessions: int = 3,
) -> XpBreakdown:
    """XP d'une session terminée.

    ``rank_in_day`` commence à 1. Le mode dégradé garde son bonus de première
    session : le point dur est le démarrage, pas la durée (SPEC §4.1).

    ``momentum_multiplier`` permet de passer la vraie jauge de chaleur du §12.10,
    qui décroît progressivement et se calcule sur sept jours glissants — le
    repli sur ``days_worked_this_week`` ne connaît que la semaine en cours et
    retomberait à zéro tous les lundis.

    ``early_bonus_ratio`` est la prime de la relique « Lampe de l'aube » (§12.8).
    Elle ne s'applique **qu'au bonus matinal**, jamais au total : une relique
    reste modérée, et une prime sur le total serait un multiplicateur déguisé.

    ``modifier_multiplier`` et ``full_xp_sessions`` viennent du modificateur de
    saison (§12.5). Ils valent 1.0 et 3 par défaut, donc une saison sans
    modificateur calcule exactement comme avant — c'est ce qui permet d'ajouter
    la mécanique sans changer les parties déjà jouées.
    """
    b = XpBreakdown()
    b.base = max(0, int(minutes))

    if is_first_of_day:
        b.first_of_day = FIRST_SESSION_BONUS
    if started_hour < EARLY_HOUR:
        b.early = round(EARLY_BONUS * (1 + max(0.0, early_bonus_ratio)))

    b.streak_multiplier = 1 + min(max(streak, 0), STREAK_CAP) * STREAK_STEP
    b.momentum_multiplier = (
        momentum_multiplier if momentum_multiplier is not None
        else momentum(days_worked_this_week)
    )
    b.degressivity = degressivity_for(rank_in_day, full_xp_sessions)
    b.modifier_multiplier = max(0.0, modifier_multiplier)

    raw = (b.base + b.first_of_day + b.early)
    b.total = round(
        raw
        * b.streak_multiplier
        * b.momentum_multiplier
        * b.modifier_multiplier
        * b.degressivity
    )

    if b.degressivity == 0.0:
        b.notes.append(
            f"{rank_in_day}ᵉ session du jour : au-delà de 3, l'XP ne compte plus."
        )
    elif b.degressivity < 1.0:
        b.notes.append(f"{rank_in_day}ᵉ session du jour : XP à moitié.")

    return b


def degressivity_for(rank_in_day: int, full_sessions: int = 3) -> float:
    """Le plafond de régime (§0.2). ``full_sessions`` vient du modificateur.

    Le modificateur « Fragmentation » ouvre une quatrième session à plein tarif
    (§12.5). Le plafond ne disparaît pas pour autant : il se décale d'un cran,
    et la session suivante tombe à moitié comme avant. Un modificateur qui
    supprimerait le plafond supprimerait la réponse au diagnostic du §0.2.
    """
    if rank_in_day < 1:
        raise ValueError("rank_in_day commence à 1")

    pleines = max(1, full_sessions)
    if rank_in_day <= pleines:
        return 1.0
    if rank_in_day == pleines + 1:
        return 0.5
    return 0.0


def momentum(days_worked_this_week: int) -> float:
    """Jauge de chaleur : monte avec les jours travaillés, plafonnée (SPEC §12.10)."""
    value = 1.0 + MOMENTUM_STEP * max(0, days_worked_this_week - 1)
    return min(value, MOMENTUM_CAP)


def xp_threshold(level: int) -> int:
    """XP cumulée nécessaire pour atteindre ``level``. Courbe croissante."""
    if level <= 1:
        return 0
    n = level - 1
    return 50 * n * n + 50 * n


def level_for(total_xp: int) -> int:
    level = 1
    while xp_threshold(level + 1) <= total_xp:
        level += 1
    return level



def progression(total_xp: int) -> dict:
    """Tout ce dont la barre d'XP a besoin, calculé une seule fois côté serveur."""
    level = level_for(total_xp)
    floor_xp = xp_threshold(level)
    next_xp = xp_threshold(level + 1)
    span = max(1, next_xp - floor_xp)
    return {
        "total_xp": total_xp,
        "level": level,
        "level_floor_xp": floor_xp,
        "next_level_xp": next_xp,
        "into_level": total_xp - floor_xp,
        "ratio": round((total_xp - floor_xp) / span, 4),
    }
