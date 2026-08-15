"""Saisons : identité, boss, modificateurs, fantôme.

Le moteur narratif du produit (SPEC §12). Une saison dure 4 semaines, porte un
nom et une couleur, un boss dont la vie descend avec le travail réel, un
modificateur qui change les règles, et un fantôme — la courbe d'une saison
passée — auquel se comparer jour après jour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

SEASON_DAYS = 28
SEASON_PAUSE_DAYS = 2

# Registres volontairement mélangés : métal, dark fantasy, sci-fi (SPEC §12.2).
SEASON_POOL: tuple[dict, ...] = (
    {"key": "hellfest", "name": "Hellfest", "accent": "#E0533D", "registre": "métal",
     "baseline": "Quatre semaines. Le feu ne demande pas la permission."},
    {"key": "heavens_paradise", "name": "Heaven's Paradise", "accent": "#F2E6C2", "registre": "métal céleste",
     "baseline": "On monte, ou on regarde monter."},
    {"key": "ragnarok", "name": "Ragnarök", "accent": "#8FA9C4", "registre": "nordique",
     "baseline": "Tout finit. La question est ce que tu auras bâti avant."},
    {"key": "purgatoire", "name": "Purgatoire", "accent": "#8A6FB0", "registre": "dark fantasy",
     "baseline": "Ni en haut, ni en bas. Vingt-huit jours pour trancher."},
    {"key": "faille_s", "name": "Faille S", "accent": "#43D9E0", "registre": "sci-fi",
     "baseline": "La faille est ouverte. Rang S ou rien."},
    {"key": "solstice_noir", "name": "Solstice Noir", "accent": "#B98A2E", "registre": "dark fantasy",
     "baseline": "La nuit la plus longue se travaille."},
    {"key": "wacken", "name": "Wacken", "accent": "#8FD14F", "registre": "métal",
     "baseline": "Le champ est boueux. On joue quand même."},
    {"key": "dernier_rempart", "name": "Dernier Rempart", "accent": "#C0574F", "registre": "siège",
     "baseline": "Ils passeront par toi."},
    {"key": "aube_rouge", "name": "Aube Rouge", "accent": "#D1403F", "registre": "épique",
     "baseline": "Vingt-huit levers. Compte-les."},
    {"key": "nadir", "name": "Nadir", "accent": "#3E6FA8", "registre": "sci-fi froid",
     "baseline": "Le point le plus bas est un point de départ comme un autre."},
    {"key": "inferno", "name": "Inferno", "accent": "#F07A20", "registre": "métal",
     "baseline": "Ça chauffe à partir de maintenant."},
    {"key": "vigie", "name": "Vigie", "accent": "#4FC4B4", "registre": "sobriété",
     "baseline": "Tenir le poste. Rien de plus, rien de moins."},
)

# Modificateurs façon roguelike : trois sont proposés, un seul est choisi.
MODIFIERS: tuple[dict, ...] = (
    {"key": "aube", "name": "Aube", "effet": "XP ×1,3 avant 20h, mais le gardien passe à 21h.",
     "params": {"early_multiplier": 1.3, "guardian_hour": 21}},
    {"key": "marathon", "name": "Marathon", "effet": "Sessions de 50 min ×1,5. Mode dégradé désactivé.",
     "params": {"long_multiplier": 1.5, "degraded_enabled": False}},
    {"key": "fragmentation", "name": "Fragmentation", "effet": "Quatre sessions comptent au lieu de trois.",
     "params": {"full_xp_sessions": 4}},
    {"key": "siege", "name": "Siège", "effet": "Le boss a 20 % de vie en plus, la mise est doublée.",
     "params": {"boss_hp_multiplier": 1.2, "stake_multiplier": 2}},
    {"key": "discipline", "name": "Discipline", "effet": "Aucun jour off, mais un bouclier de plus au départ.",
     "params": {"days_off_allowed": 0, "starting_shields": 3}},
    {"key": "deux_fronts", "name": "Deux fronts", "effet": "La piste Corps inflige des dégâts doubles au boss.",
     "params": {"body_damage_multiplier": 2}},
)

BOSSES: tuple[dict, ...] = (
    {"key": "procrastin", "name": "Procrastin, l'Ajourneur"},
    {"key": "scrollhydre", "name": "La Scroll-Hydre"},
    {"key": "veilleur", "name": "Le Veilleur de 23h"},
    {"key": "eparpilleur", "name": "L'Éparpilleur"},
    {"key": "jour_six", "name": "Jour Six"},
    {"key": "brouillard", "name": "Le Brouillard"},
)

# Dégâts infligés au boss, en points. Une minute travaillée = un point ; une
# étape de roadmap terminée pèse une heure ; un engagement tenu, trois quarts.
DAMAGE_PER_MINUTE = 1
DAMAGE_PER_STEP = 60
DAMAGE_PER_COMMITMENT = 45
BOSS_REGEN_ON_MISSED_DAY = 45     # sanction du palier 1 (SPEC §14)


@dataclass(frozen=True)
class SeasonPlan:
    index: int
    key: str
    name: str
    accent: str
    baseline: str
    boss_key: str
    boss_name: str
    boss_hp: int
    modifier_key: str
    starts_on: date
    ends_on: date

    @property
    def days_total(self) -> int:
        return (self.ends_on - self.starts_on).days + 1


def pick_identity(index: int, used_keys: set[str] | None = None) -> dict:
    """Choisit une identité de saison sans répéter les précédentes trop vite."""
    used = used_keys or set()
    available = [s for s in SEASON_POOL if s["key"] not in used] or list(SEASON_POOL)
    return available[index % len(available)]


def propose_modifiers(index: int, count: int = 3) -> list[dict]:
    """Trois modificateurs proposés à l'ouverture — un choix, pas une subissance."""
    start = (index * count) % len(MODIFIERS)
    doubled = list(MODIFIERS) * 2
    return doubled[start : start + count]


def boss_hp(previous_score: int | None, contract_sessions_per_week: int = 3) -> int:
    """Vie du boss : la saison précédente + 5 %, ou l'estimation du contrat."""
    if previous_score:
        return int(previous_score * 1.05)
    estimate = contract_sessions_per_week * 4 * 25 * DAMAGE_PER_MINUTE
    return max(1500, estimate)


def damage_of(minutes: int = 0, steps_done: int = 0, commitments_kept: int = 0) -> int:
    return (
        minutes * DAMAGE_PER_MINUTE
        + steps_done * DAMAGE_PER_STEP
        + commitments_kept * DAMAGE_PER_COMMITMENT
    )


def plan_season(
    index: int,
    starts_on: date,
    *,
    previous_score: int | None = None,
    used_keys: set[str] | None = None,
) -> SeasonPlan:
    identity = pick_identity(index, used_keys)
    boss = BOSSES[index % len(BOSSES)]
    return SeasonPlan(
        index=index,
        key=identity["key"],
        name=identity["name"],
        accent=identity["accent"],
        baseline=identity["baseline"],
        boss_key=boss["key"],
        boss_name=boss["name"],
        boss_hp=boss_hp(previous_score),
        modifier_key=propose_modifiers(index)[0]["key"],
        starts_on=starts_on,
        ends_on=starts_on + timedelta(days=SEASON_DAYS - 1),
    )


def next_season_start(ends_on: date) -> date:
    """Deux jours de pause explicite entre deux saisons (jours neutres)."""
    return ends_on + timedelta(days=SEASON_PAUSE_DAYS + 1)


def ghost_delta(day_index: int, mine: list[int], ghost: list[int]) -> int:
    """Écart au fantôme à un jour donné, en points cumulés (SPEC §12.7)."""
    def at(curve: list[int]) -> int:
        if not curve:
            return 0
        return curve[min(day_index, len(curve) - 1)]

    return at(mine) - at(ghost)


def title_for(score_ratio: float, season_name: str) -> str:
    """Titre décerné à la clôture. Le titre raté existe aussi, sans humiliation."""
    if score_ratio >= 1.0:
        return f"Vainqueur de {season_name}"
    if score_ratio >= 0.7:
        return f"Survivant de {season_name}"
    if score_ratio >= 0.3:
        return f"Vétéran de {season_name}"
    return f"Déserteur de {season_name}"
