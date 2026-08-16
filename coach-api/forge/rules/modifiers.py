"""Les modificateurs de saison, **appliqués** (SPEC §12.5).

Le §12.5 les décrit et ``seasons.MODIFIERS`` les catalogue, mais leurs
paramètres ne changeaient rien : la saison 5 était identique à la saison 1,
c'est-à-dire exactement ce que le modificateur existe pour empêcher.

Ce module résout une clé en un jeu d'effets typés, et c'est **le seul endroit**
où un modificateur se lit. Les appelants demandent « quel est le multiplicateur
matinal », jamais « est-ce que la saison est Aube » : un `if` sur une clé de
saison éparpillé dans le code rend le sixième modificateur impossible à ajouter
sans relire tout le reste.

**Ce qu'un modificateur n'a pas le droit de toucher.** Ni le streak, ni les
rangs, ni les gardes, ni le plancher de survie du §4.1. Il change ce qui
*rapporte* et ce qui *coûte* pendant quatre semaines — pas ce qui définit une
journée tenue. « Marathon » désactive le mode dégradé, ce qui est la seule
exception, et elle est assumée : c'est le modificateur difficile, il est annoncé
comme tel à l'ouverture, et il a été choisi parmi trois.
"""

from __future__ import annotations

from dataclasses import dataclass

from .seasons import MODIFIERS

PAR_CLE = {m["key"]: m for m in MODIFIERS}


@dataclass(frozen=True)
class Effects:
    """Les effets résolus d'un modificateur. Neutres par défaut.

    Les valeurs neutres ne sont pas un détail : une saison sans modificateur,
    une clé inconnue et un modificateur qui ne touche pas à un axe donné
    doivent produire **exactement** le même résultat que le code d'origine.
    Sans ça, ajouter cette mécanique changerait silencieusement les parties
    déjà jouées.
    """

    key: str = ""
    name: str = ""
    effet: str = ""

    early_multiplier: float = 1.0      # XP des sessions démarrées avant 20h
    long_multiplier: float = 1.0       # XP des sessions de 50 minutes
    degraded_enabled: bool = True      # le mode dégradé du §4.1 reste-t-il ouvert
    full_xp_sessions: int = 3          # combien de sessions comptent plein (§4.4)
    boss_hp_multiplier: float = 1.0
    stake_multiplier: int = 1
    days_off_allowed: int | None = None  # None = la règle normale du §11.5
    starting_shields: int | None = None
    body_damage_multiplier: float = 1.0
    guardian_hour: int | None = None

    @property
    def active(self) -> bool:
        return bool(self.key)


NEUTRE = Effects()


def resolve(key: str | None) -> Effects:
    """Les effets d'une clé de modificateur. Une clé inconnue est neutre.

    Neutre et non une erreur : une saison ouverte avec un modificateur retiré
    du catalogue plus tard doit continuer de se jouer. Refuser ici casserait
    l'app pour une raison purement historique.
    """
    entree = PAR_CLE.get(key or "")
    if entree is None:
        return NEUTRE

    p = entree.get("params", {})
    return Effects(
        key=entree["key"],
        name=entree["name"],
        effet=entree["effet"],
        early_multiplier=p.get("early_multiplier", 1.0),
        long_multiplier=p.get("long_multiplier", 1.0),
        degraded_enabled=p.get("degraded_enabled", True),
        full_xp_sessions=p.get("full_xp_sessions", 3),
        boss_hp_multiplier=p.get("boss_hp_multiplier", 1.0),
        stake_multiplier=p.get("stake_multiplier", 1),
        days_off_allowed=p.get("days_off_allowed"),
        starting_shields=p.get("starting_shields"),
        body_damage_multiplier=p.get("body_damage_multiplier", 1.0),
        guardian_hour=p.get("guardian_hour"),
    )


def session_multiplier(effects: Effects, *, minutes: int, started_hour: int) -> float:
    """Le multiplicateur d'XP dû au modificateur, pour une session donnée.

    Les deux primes **se cumulent** quand les deux conditions sont réunies : une
    session de cinquante minutes commencée à dix-huit heures sous « Aube » et
    « Marathon » n'existe pas — un seul modificateur est actif à la fois — mais
    la fonction reste écrite pour que ce soit vrai si ça arrivait un jour.
    """
    facteur = 1.0
    if started_hour < 20:
        facteur *= effects.early_multiplier
    if minutes >= 50:
        facteur *= effects.long_multiplier
    return facteur


def describe(effects: Effects) -> str:
    """Une ligne à afficher en permanence pendant la saison.

    Affichée en permanence et pas seulement à l'ouverture : un modificateur
    qu'on a choisi il y a trois semaines et qu'on a oublié produit des chiffres
    inexplicables, et un chiffre inexplicable détruit la confiance dans le
    système bien plus vite qu'une règle dure.
    """
    return f"{effects.name} — {effects.effet}" if effects.active else ""
