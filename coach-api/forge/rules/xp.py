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
) -> XpBreakdown:
    """XP d'une session terminée.

    ``rank_in_day`` commence à 1. Le mode dégradé garde son bonus de première
    session : le point dur est le démarrage, pas la durée (SPEC §4.1).
    """
    b = XpBreakdown()
    b.base = max(0, int(minutes))

    if is_first_of_day:
        b.first_of_day = FIRST_SESSION_BONUS
    if started_hour < EARLY_HOUR:
        b.early = EARLY_BONUS

    b.streak_multiplier = 1 + min(max(streak, 0), STREAK_CAP) * STREAK_STEP
    b.momentum_multiplier = momentum(days_worked_this_week)
    b.degressivity = degressivity_for(rank_in_day)

    raw = (b.base + b.first_of_day + b.early)
    b.total = round(raw * b.streak_multiplier * b.momentum_multiplier * b.degressivity)

    if b.degressivity == 0.0:
        b.notes.append(
            f"{rank_in_day}ᵉ session du jour : au-delà de 3, l'XP ne compte plus."
        )
    elif b.degressivity < 1.0:
        b.notes.append(f"{rank_in_day}ᵉ session du jour : XP à moitié.")

    return b


def degressivity_for(rank_in_day: int) -> float:
    if rank_in_day < 1:
        raise ValueError("rank_in_day commence à 1")
    if rank_in_day <= len(DEGRESSIVITY):
        return DEGRESSIVITY[rank_in_day - 1]
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
