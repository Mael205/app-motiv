"""XP, niveaux, rangs et plafond de régime.

Le plafond est la mécanique qui répond au diagnostic §0.2 : le problème n'est
pas la motivation mais l'absence de plafond. À partir de la 4ᵉ session du jour
la récompense s'éteint progressivement — la session reste enregistrée, les
heures comptent, la roadmap avance, seule l'XP disparaît.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FIRST_SESSION_BONUS = 20

# --------------------------------------------------------------------------
# La prime de ponctualité (tranchée le 20 août 2026)
# --------------------------------------------------------------------------
#
# Elle remplace le forfait « démarrée avant 20h », et le remplacement est le
# sujet — ce n'est pas une règle de plus.
#
# Le §11.2 fait des rendez-vous fixes le cœur du dispositif : « mardi 20h30 se
# tient, "ce soir" se rate ». Mais depuis que n'importe quelle heure vaut une
# journée validée, l'heure annoncée ne pesait plus rien : la tenir ne rapportait
# pas, la manquer ne coûtait rien le soir même, et le seul forfait horaire du
# barème récompensait *l'horloge* — 19h58 payait, 20h02 non, et un créneau
# déclaré à 21h ne pouvait jamais y toucher. Une app qui dit « 20h30 » et qui
# paie « avant 20h » se contredit à voix haute.
#
# La prime va donc au **rendez-vous qu'on s'est fixé**, quelle que soit l'heure
# qu'il porte. Tenir un créneau de 22h vaut exactement autant qu'un de 18h.
#
# **Et rien n'est retiré à qui travaille hors créneau.** Le §17 interdit au
# système d'ajouter une sanction : une séance hors rendez-vous ne perd rien,
# elle ne gagne pas. C'est aussi ce qui empêche la prime de devenir une raison
# de ne pas s'y mettre le soir où l'on a raté son heure.
PONCTUALITE_BONUS = 10

# La demi-heure autour du rendez-vous. Symétrique, et volontairement pas
# « avant l'heure ou dans la demi-heure qui suit » : une prime accordée à qui
# démarre trois heures plus tôt redeviendrait une prime « avant l'heure », donc
# la règle qu'on vient de retirer.
TOLERANCE_MINUTES = 30
STREAK_STEP = 0.05
STREAK_CAP = 10                 # multiplicateur de streak plafonné à ×1.5
MOMENTUM_STEP = 0.05
MOMENTUM_CAP = 1.25

# Dégressivité par rang de session dans la journée : les trois premières
# comptent plein, la quatrième à moitié, les suivantes plus du tout.
DEGRESSIVITY = (1.0, 1.0, 1.0, 0.5)

# --------------------------------------------------------------------------
# La prime de durée (tranchée le 19 août 2026)
# --------------------------------------------------------------------------
#
# Jusqu'ici une minute valait une minute, donc deux sessions de 25 minutes
# valaient exactement une de 50. C'était défendable — le §0.2 se méfie du
# sur-régime, et le point dur est le démarrage — mais ça rate ce qui se passe
# **à l'intérieur** d'une séance : les vingt premières minutes servent à
# retrouver où l'on en était, et le travail qui compte commence après. Deux
# démarrages à froid ne produisent pas ce que produit une plongée continue.
#
# D'où une prime **par paliers sur les minutes tardives**, jamais un
# multiplicateur sur le total : le début d'une session ne change pas de valeur
# parce qu'elle a fini par durer. Une session de 50 minutes rapporte donc plus
# que deux de 25, et le plafond de régime du §0.2 reste intact — il compte des
# sessions, et prolonger n'en ajoute pas une.
#
# **Le calibrage n'est pas décoratif, et il a un critère.** Une session porte
# deux bonus forfaitaires — première du jour, démarrée avant 20h — que *couper
# la soirée en deux paie deux fois*. Avec une prime trop faible, deux séances de
# vingt-cinq minutes rapportent donc plus qu'une d'une heure, et la mécanique
# dit exactement le contraire de ce qu'elle prétend dire. Les taux ci-dessous
# sont choisis pour que la prime dépasse ce que le fractionnement duplique : à
# 50 minutes elle vaut 14 XP, là où couper en deux rapporte 10 XP de bonus
# matinal en plus. Un test tient cette propriété, parce qu'elle se casserait au
# premier changement de barème.
#
# La prime s'arrête à 45 minutes et ne monte plus : au-delà, récompenser la
# durée reviendrait à récompenser la veillée, ce que le §14 sanctionne par
# ailleurs. Une prime sans plafond finirait par payer le 2h du dimanche soir.
PALIER_LONG = 25
PALIER_TRES_LONG = 45
PRIME_LONG = 0.5
PRIME_TRES_LONG = 0.75


def prime_de_duree(minutes: int) -> int:
    """Les minutes **en plus** que vaut une session longue. 0 sous 25 minutes.

    Le calcul est par tranche, comme un barème d'impôt : les 25 premières
    minutes valent leur valeur, celles entre 25 et 45 valent une fois et demie,
    celles au-delà une fois trois quarts. Une tranche ne requalifie jamais les précédentes — sinon
    franchir 45 minutes d'une seconde ferait bondir toute la session, et
    l'affichage du détail deviendrait incompréhensible.
    """
    minutes = max(0, int(minutes))
    longues = max(0, min(minutes, PALIER_TRES_LONG) - PALIER_LONG)
    tres_longues = max(0, minutes - PALIER_TRES_LONG)
    return round(longues * PRIME_LONG + tres_longues * PRIME_TRES_LONG)

# Le rang ne vit plus ici : il mesure la fiabilité, pas le volume, et se calcule
# dans ``forge/rules/ranks.py`` sur les semaines d'engagements tenus (SPEC §4.4).
# L'XP garde les niveaux, le loot, les dégâts au boss et le score de saison.


@dataclass
class XpBreakdown:
    """Le détail du calcul, pour que l'interface puisse l'afficher ligne à ligne."""

    base: int = 0
    duration_premium: int = 0
    first_of_day: int = 0
    punctual: int = 0
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
    ecart_au_creneau: int | None = None,
    punctuality_bonus_ratio: float = 0.0,
    duration_bonus_ratio: float = 0.0,
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

    ``ecart_au_creneau`` est le nombre de minutes entre le démarrage et le
    rendez-vous le plus proche déclaré ce jour-là sur ce projet. ``None`` quand
    il n'y en a aucun : il n'y a alors **rien à tenir**, donc rien à primer, et
    ce n'est pas une punition — c'est l'absence de promesse.

    ``started_hour`` ne sert plus au barème depuis le 20 août ; il reste pour le
    modificateur de saison (§12.5), qui lui parle bien de l'horloge — « Aube »
    paie le matin, et c'est son sujet.

    ``punctuality_bonus_ratio`` et ``duration_bonus_ratio`` sont les primes des
    reliques du §12.8. Chacune ne s'applique **qu'à sa propre ligne**, jamais au
    total : une relique reste modérée, et une prime sur le total serait un
    multiplicateur déguisé.

    ``modifier_multiplier`` et ``full_xp_sessions`` viennent du modificateur de
    saison (§12.5). Ils valent 1.0 et 3 par défaut, donc une saison sans
    modificateur calcule exactement comme avant — c'est ce qui permet d'ajouter
    la mécanique sans changer les parties déjà jouées.
    """
    b = XpBreakdown()
    b.base = max(0, int(minutes))
    b.duration_premium = round(
        prime_de_duree(b.base) * (1 + max(0.0, duration_bonus_ratio))
    )

    if is_first_of_day:
        b.first_of_day = FIRST_SESSION_BONUS
    if a_l_heure(ecart_au_creneau):
        b.punctual = round(PONCTUALITE_BONUS * (1 + max(0.0, punctuality_bonus_ratio)))

    b.streak_multiplier = 1 + min(max(streak, 0), STREAK_CAP) * STREAK_STEP
    b.momentum_multiplier = (
        momentum_multiplier if momentum_multiplier is not None
        else momentum(days_worked_this_week)
    )
    b.degressivity = degressivity_for(rank_in_day, full_xp_sessions)
    b.modifier_multiplier = max(0.0, modifier_multiplier)

    raw = (b.base + b.duration_premium + b.first_of_day + b.punctual)
    b.total = round(
        raw
        * b.streak_multiplier
        * b.momentum_multiplier
        * b.modifier_multiplier
        * b.degressivity
    )

    if b.duration_premium:
        notee = "au-delà de 45 min" if b.base > PALIER_TRES_LONG else "au-delà de 25 min"
        b.notes.append(f"Prime de durée : +{b.duration_premium} XP {notee}.")

    if b.degressivity == 0.0:
        b.notes.append(
            f"{rank_in_day}ᵉ session du jour : au-delà de 3, l'XP ne compte plus."
        )
    elif b.degressivity < 1.0:
        b.notes.append(f"{rank_in_day}ᵉ session du jour : XP à moitié.")

    return b


def a_l_heure(ecart_au_creneau: int | None, tolerance: int = TOLERANCE_MINUTES) -> bool:
    """Le démarrage tombe-t-il dans la demi-heure autour du rendez-vous ?

    ``None`` — aucun créneau déclaré ce jour-là — rend ``False`` sans que ce
    soit un échec : il n'y avait rien à tenir.
    """
    return ecart_au_creneau is not None and abs(int(ecart_au_creneau)) <= tolerance


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
