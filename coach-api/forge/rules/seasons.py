"""Saisons : identité, boss, modificateurs, fantôme.

Le moteur narratif du produit (SPEC §12). Une saison dure 4 semaines, porte un
nom et une couleur, un boss dont la vie descend avec le travail réel, un
modificateur qui change les règles, et un fantôme — la courbe d'une saison
passée — auquel se comparer jour après jour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import years

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

# Modificateurs façon roguelike : trois sont proposés, un seul est choisi — cinq
# après la voie « Écho » de l'ascendance. Douze entrées pour que deux saisons
# consécutives ne se ressemblent pas : avec six, le tirage de trois recouvrait la
# moitié du catalogue à chaque fois.
#
# **Aucun ne rend le jeu plus facile sans contrepartie.** Chacun déplace une
# contrainte : ce qu'il donne d'un côté, il le reprend de l'autre. Un
# modificateur purement favorable serait celui qu'on choisirait toujours, et le
# choix du §12.5 n'existerait plus.
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
    {"key": "veille_haute", "name": "Veille haute", "effet": "Le gardien passe à 22h, mais le boss a 15 % de vie en plus.",
     "params": {"guardian_hour": 22, "boss_hp_multiplier": 1.15}},
    {"key": "premiere_lumiere", "name": "Première lumière", "effet": "XP ×1,5 avant 18h. Après 22h, plus rien ne compte.",
     "params": {"early_multiplier": 1.5, "guardian_hour": 20}},
    {"key": "austerite", "name": "Austérité", "effet": "Une seule session compte plein par jour, mais la mise est triplée.",
     "params": {"full_xp_sessions": 1, "stake_multiplier": 3}},
    {"key": "forge", "name": "Forge", "effet": "Sessions de 50 min ×1,3 et boss à 130 % de vie.",
     "params": {"long_multiplier": 1.3, "boss_hp_multiplier": 1.3}},
    {"key": "corde_raide", "name": "Corde raide", "effet": "Aucun bouclier au départ, mais le boss n'a que 80 % de vie.",
     "params": {"starting_shields": 0, "boss_hp_multiplier": 0.8}},
    {"key": "clemence", "name": "Clémence", "effet": "Trois jours off par semaine, et le mode dégradé disparaît.",
     "params": {"days_off_allowed": 3, "degraded_enabled": False}},
)

# Douze boss pour douze saisons : chaque saison de l'année a le sien, et on ne
# revoit pas le même adversaire deux fois en un an. Six suffisaient tant qu'une
# année n'existait pas ; avec elle, ils seraient revenus tous les six mois.
#
# Chacun nomme une façon précise de ne pas travailler. C'est le point : un boss
# qui s'appellerait « la Paresse » ne dirait rien, alors que « le Veilleur de
# 23h » se reconnaît le soir même où on le rencontre.
BOSSES: tuple[dict, ...] = (
    {"key": "procrastin", "name": "Procrastin, l'Ajourneur"},
    {"key": "scrollhydre", "name": "La Scroll-Hydre"},
    {"key": "veilleur", "name": "Le Veilleur de 23h"},
    {"key": "eparpilleur", "name": "L'Éparpilleur"},
    {"key": "jour_six", "name": "Jour Six"},
    {"key": "brouillard", "name": "Le Brouillard"},
    {"key": "presque_pret", "name": "Presque Prêt"},
    {"key": "grand_refacteur", "name": "Le Grand Refacteur"},
    {"key": "onglet_trente", "name": "L'Onglet Trente"},
    {"key": "demain_matin", "name": "Demain Matin"},
    {"key": "collectionneur", "name": "Le Collectionneur de Débuts"},
    {"key": "juste_un_episode", "name": "Juste Un Épisode"},
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

    @property
    def year(self) -> int:
        return years.annee_de(self.index)

    @property
    def rank_in_year(self) -> int:
        return years.rang_dans_l_annee(self.index)

    @property
    def closes_the_year(self) -> bool:
        return years.ferme_l_annee(self.index)


def pick_identity(index: int) -> dict:
    """L'identité d'une saison, décidée par sa place dans l'année.

    Chaque identité sort **exactement une fois par an** : arrivé à la neuvième,
    il en reste trois, et on les a toutes vues à la fin. La version précédente
    écartait simplement les clés déjà utilisées, ce qui marchait tant qu'une
    année n'existait pas — mais ne donnait aucun compte à rebours, et retombait
    sur le catalogue entier une fois les douze épuisées.

    L'ordre change d'une année à l'autre sans que rien ne soit stocké : il se
    déduit du numéro d'année.
    """
    annee = years.annee_de(index)
    ordre = years.ordre_des_identites(annee, len(SEASON_POOL))
    return SEASON_POOL[ordre[years.rang_dans_l_annee(index) - 1]]


def pick_boss(index: int) -> dict:
    """Le boss d'une saison. Un par saison de l'année, jamais deux fois.

    La permutation est décalée d'une année par rapport aux identités : sans ce
    décalage, « Hellfest » affronterait Procrastin chaque année, et les deux
    catalogues n'en formeraient plus qu'un.
    """
    annee = years.annee_de(index)
    ordre = years.ordre_des_identites(annee + 1, len(BOSSES))
    return BOSSES[ordre[years.rang_dans_l_annee(index) - 1]]


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
    contract_sessions_per_week: int = 3,
) -> SeasonPlan:
    """Le plan d'une saison. ``contract_sessions_per_week`` ne sert qu'à la
    première : sans score précédent, la seule estimation honnête du volume à
    venir est celle que quelqu'un vient d'annoncer en signant son contrat."""
    identity = pick_identity(index)
    boss = pick_boss(index)
    return SeasonPlan(
        index=index,
        key=identity["key"],
        name=identity["name"],
        accent=identity["accent"],
        baseline=identity["baseline"],
        boss_key=boss["key"],
        boss_name=boss["name"],
        boss_hp=boss_hp(previous_score, contract_sessions_per_week),
        modifier_key=propose_modifiers(index)[0]["key"],
        starts_on=starts_on,
        ends_on=starts_on + timedelta(days=SEASON_DAYS - 1),
    )


def next_season_start(ends_on: date) -> date:
    """Deux jours de pause explicite entre deux saisons (jours neutres)."""
    return ends_on + timedelta(days=SEASON_PAUSE_DAYS + 1)


# --------------------------------------------------------------------------
# Le dernier round (ajout du 17 août 2026)
# --------------------------------------------------------------------------

FINAL_ROUND_DAYS = 3
FINAL_ROUND_SESSION_MINUTES = 25


@dataclass(frozen=True)
class FinalRound:
    """La vie du boss traduite en sessions, les trois derniers jours.

    **Informatif seulement, et c'est la décision qui fait tout le reste.** Un
    bonus de fin de saison — dégâts doublés, XP majorée, mise récupérable —
    encouragerait trois soirées de rattrapage à quatre sessions, c'est-à-dire
    exactement le sur-régime du §0.2, et il le ferait au pire moment : celui où
    la saison suivante s'ouvre le lendemain. Ce module ne rend donc **aucun
    multiplicateur**. Il change une unité, rien d'autre.

    Le changement d'unité est tout ce qu'on peut honnêtement offrir. « 2 340
    points de vie » ne se compare à rien ; « quatre sessions » se compare à une
    soirée, et la comparaison se fait toute seule — on sait si on peut ou non,
    et personne n'a eu besoin de le dire.
    """

    active: bool
    days_left: int
    sessions_left: int
    minutes_left: int
    session_minutes: int
    reachable: bool
    line: str


def final_round(
    *,
    days_left: int,
    current_hp: int,
    is_dead: bool = False,
    session_minutes: int = FINAL_ROUND_SESSION_MINUTES,
    sessions_per_day: int = 3,
) -> FinalRound:
    """Traduit la vie restante en sessions, dans les trois derniers jours.

    ``reachable`` compare le nombre de sessions nécessaires au plafond de régime
    (§0.2) sur les jours qui restent : au-delà, le boss ne tombera pas, et le
    dire est plus honnête que de laisser espérer. Ce n'est pas un reproche —
    c'est la même information, avec sa borne.
    """
    par_session = max(1, session_minutes * DAMAGE_PER_MINUTE)
    restantes = 0 if is_dead else -(-max(0, current_hp) // par_session)
    possible = max(0, days_left) * max(1, sessions_per_day)

    if is_dead:
        ligne = "Dernier round — il est déjà tombé. Ce qui suit est du rab."
    elif restantes <= possible:
        pluriel = "s" if restantes > 1 else ""
        ligne = (
            f"Dernier round — {restantes} session{pluriel} de {session_minutes} min "
            f"pour l'abattre, {days_left} jour{'s' if days_left > 1 else ''} devant."
        )
    else:
        ligne = (
            f"Dernier round — il faudrait {restantes} sessions en {days_left} "
            f"jour{'s' if days_left > 1 else ''}. Il tiendra jusqu'au bout."
        )

    return FinalRound(
        active=0 <= days_left <= FINAL_ROUND_DAYS,
        days_left=max(0, days_left),
        sessions_left=restantes,
        minutes_left=0 if is_dead else max(0, current_hp) // max(1, DAMAGE_PER_MINUTE),
        session_minutes=session_minutes,
        reachable=is_dead or restantes <= possible,
        line=ligne,
    )


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
