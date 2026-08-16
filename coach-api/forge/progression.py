"""Le jeu autour du travail : arbre, loot, reliques, momentum (SPEC §12, J2).

Ce module est le seul endroit où le coach distribue quelque chose. Il obéit à
une règle unique, posée au §17 et répétée au §12.6 :

> Le loot est de l'apparence, jamais du pouvoir.

Elle a une conséquence architecturale, et pas seulement morale : **rien ici ne
peut modifier une journée, un streak, un rang ou une garde**. Ce module lit les
faits produits par ``services`` et écrit du cosmétique. Le sens inverse n'existe
pas, et c'est ce qui rend l'ensemble sûr — on peut ajouter autant de paillettes
qu'on veut sans jamais risquer de rendre une journée « tenue » sans travail.

Les reliques (§12.8) sont l'exception assumée, et bornée à trois effets
modérés qui n'ajoutent que de la marge : un bouclier, un jour off, une petite
prime. Elles se gagnent par un haut fait, donc par du travail, jamais par un
tirage.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from django.db.models import Count, F, Q, Sum

from .models import (
    Achievement,
    Commitment,
    LootCard,
    LootDraw,
    OwnedRelic,
    Profile,
    Session,
)
from .rules import loot as loot_rules
from .rules import modifiers as modifier_rules
from .rules import momentum as momentum_rules
from .rules import phantom as phantom_rules
from .rules import relics as relic_rules
from .rules import skills as skill_rules
from .rules.calendar import week_start

# Les emplacements cosmétiques. Un seul équipé par emplacement : deux thèmes en
# même temps n'auraient aucun sens, et laisser l'ambiguïté au client garantit
# qu'elle finira par diverger d'un appareil à l'autre.
EMPLACEMENTS = ("theme", "emblem", "frame", "title", "finisher")


# --------------------------------------------------------------------------
# Arbre de compétences (§12.9)
# --------------------------------------------------------------------------

def branch_minutes(user) -> dict[str, int]:
    """Les minutes travaillées par branche, tous projets confondus.

    C'est l'agrégation qui donne son sens au §12.9 : deux projets UE5
    nourrissent la même branche, et un projet archivé continue de compter — les
    heures ont été faites.
    """
    lignes = (
        Session.objects.filter(user=user, status=Session.DONE)
        .exclude(project__branch="")
        .values("project__branch")
        .annotate(total=Sum("actual_minutes"))
    )
    return {l["project__branch"]: l["total"] or 0 for l in lignes}


def skill_tree(user) -> dict:
    """L'arbre complet, plus sa forme pour la revue de saison."""
    etats = skill_rules.tree(branch_minutes(user))
    return {
        "branches": [
            {
                "key": b.key,
                "label": b.label,
                "color": b.color,
                "minutes": b.minutes,
                "hours": b.hours,
                "tier": b.tier,
                "title": b.title,
                "emblem": b.emblem,
                "next_hours": b.next_hours,
                "progress": b.progress,
                "maxed": b.maxed,
            }
            for b in etats
        ],
        "shape": skill_rules.shape(etats),
        "tiers": list(skill_rules.TIER_HOURS),
    }


def branch_tier_crossed(user, session: Session) -> dict | None:
    """Le palier franchi par cette session, s'il y en a un.

    Se calcule **après** la clôture, en retirant la session pour retrouver
    l'avant : c'est plus sûr que de mémoriser un total avant l'écriture, qui se
    désynchroniserait à la première correction manuelle.
    """
    branche = session.project.branch
    if not branche:
        return None

    apres = branch_minutes(user).get(branche, 0)
    avant = apres - session.actual_minutes

    palier = skill_rules.newly_reached(avant, apres)
    if palier is None:
        return None

    etat = skill_rules.branch_state(branche, apres)
    return {
        "branch": branche,
        "label": etat.label,
        "color": etat.color,
        "tier": palier,
        "title": etat.title,
        "emblem": etat.emblem,
        "hours": skill_rules.TIER_HOURS[palier - 1],
    }


# --------------------------------------------------------------------------
# Momentum (§12.10)
# --------------------------------------------------------------------------

def heat(user, *, today: date) -> dict:
    """La jauge de chaleur, recalculée depuis les jours réellement travaillés."""
    depuis = today - timedelta(days=momentum_rules.FENETRE - 1)
    travailles = set(
        Session.objects.filter(
            user=user, status=Session.DONE, coach_day__gte=depuis, coach_day__lte=today
        ).values_list("coach_day", flat=True)
    )
    jours = [
        (depuis + timedelta(days=i)) in travailles for i in range(momentum_rules.FENETRE)
    ]

    etat = momentum_rules.evaluate(jours)
    return {
        "level": etat.level,
        "percent": etat.percent,
        "multiplier": etat.multiplier,
        "label": etat.label,
        "detail": etat.detail,
        "days_worked": etat.days_worked,
        "cooling": etat.cooling,
        "days": jours,
    }


# --------------------------------------------------------------------------
# Loot (§12.6)
# --------------------------------------------------------------------------

def _pity(user) -> tuple[int, int]:
    """Les compteurs de pitié, recalculés depuis le journal des tirages.

    Recalculés et non stockés : un compteur qui dérive dérègle la pitié, donc
    produit exactement la sensation de triche qu'elle devait empêcher.
    """
    recents = list(
        LootDraw.objects.filter(user=user).order_by("-created_at").values_list("rarity", flat=True)[:60]
    )

    depuis_rare = next(
        (i for i, r in enumerate(recents) if r != loot_rules.COMMUN), len(recents)
    )
    depuis_epique = next(
        (i for i, r in enumerate(recents) if r in (loot_rules.EPIQUE, loot_rules.LEGENDAIRE)),
        len(recents),
    )
    return depuis_rare, depuis_epique


def draw_card(user, *, reason: str, rng: random.Random | None = None) -> dict:
    """Tire une carte, la range, et rend de quoi jouer l'animation d'ouverture."""
    possedees = set(LootCard.objects.filter(user=user).values_list("key", flat=True))
    depuis_rare, depuis_epique = _pity(user)

    carte, doublon = loot_rules.draw(
        owned=possedees,
        draws_since_rare=depuis_rare,
        draws_since_epic=depuis_epique,
        rng=rng,
    )
    eclats = loot_rules.shards_for(carte, duplicate=doublon)

    if doublon:
        LootCard.objects.filter(user=user, key=carte.key).update(copies=F("copies") + 1)
    else:
        LootCard.objects.create(
            user=user,
            key=carte.key,
            rarity=carte.rarity,
            kind=carte.kind,
            reason=reason,
        )

    if eclats:
        profil = user.profile
        bonus = relic_bonuses(user).shard_bonus
        gagnes = round(eclats * (1 + bonus))
        profil.shards += gagnes
        profil.save(update_fields=["shards"])
        eclats = gagnes

    LootDraw.objects.create(
        user=user,
        key=carte.key,
        rarity=carte.rarity,
        duplicate=doublon,
        shards=eclats,
        reason=reason,
    )

    return {
        "key": carte.key,
        "label": carte.label,
        "rarity": carte.rarity,
        "rarity_label": loot_rules.RARETE_LABELS[carte.rarity],
        "color": carte.color,
        "kind": carte.kind,
        "payload": carte.payload,
        "duplicate": doublon,
        "shards": eclats,
        "reason": reason,
        "reason_label": loot_rules.RAISONS.get(reason, ""),
    }


def collection(user) -> dict:
    """L'inventaire, groupé par emplacement, avec ce qui manque encore.

    Les cartes non possédées sont rendues **en creux** : une collection qui ne
    montre que ce qu'on a ne donne aucune raison de continuer, et le §12.6 fait
    du loot un moteur d'envie, pas un coffre.
    """
    possedees = {c.key: c for c in LootCard.objects.filter(user=user)}
    equipes = (user.profile.cosmetics or {})

    par_emplacement: dict[str, list[dict]] = {e: [] for e in EMPLACEMENTS}
    for carte in loot_rules.CATALOGUE:
        avoir = possedees.get(carte.key)
        par_emplacement.setdefault(carte.kind, []).append(
            {
                "key": carte.key,
                "label": carte.label,
                "rarity": carte.rarity,
                "rarity_label": loot_rules.RARETE_LABELS[carte.rarity],
                "color": carte.color,
                "kind": carte.kind,
                "payload": carte.payload,
                "owned": avoir is not None,
                "copies": avoir.copies if avoir else 0,
                "equipped": equipes.get(carte.kind) == carte.key,
            }
        )

    return {
        "slots": par_emplacement,
        "owned": len(possedees),
        "total": len(loot_rules.CATALOGUE),
        "shards": user.profile.shards,
        "equipped": equipes,
    }


def equip_card(user, key: str) -> dict:
    """Équipe une carte dans son emplacement. Rien n'est cumulable.

    Un ré-équipement de la carte déjà en place la retire : c'est le
    comportement attendu d'une bascule, et il évite un second bouton « retirer »
    dont l'absence ne manque à personne.
    """
    carte = loot_rules.PAR_CLE.get(key)
    if carte is None:
        raise ValueError("Carte inconnue.")
    if not LootCard.objects.filter(user=user, key=key).exists():
        raise ValueError("Tu ne possèdes pas cette carte.")

    profil: Profile = user.profile
    equipes = dict(profil.cosmetics or {})
    equipes[carte.kind] = "" if equipes.get(carte.kind) == key else key
    profil.cosmetics = {k: v for k, v in equipes.items() if v}
    profil.save(update_fields=["cosmetics"])

    return profil.cosmetics


# --------------------------------------------------------------------------
# Reliques (§12.8)
# --------------------------------------------------------------------------

def relic_bonuses(user) -> relic_rules.Bonuses:
    """Les bonus actifs. Passe toujours par ``rules.relics`` pour le plafond."""
    equipees = OwnedRelic.objects.filter(user=user, equipped=True).values_list("key", flat=True)
    return relic_rules.bonuses(list(equipees))


def grant_relics_for(user, achievement_keys) -> list[dict]:
    """Débloque les reliques associées à des hauts faits fraîchement obtenus.

    Non équipées d'office : le §12.8 plafonne à trois, donc le choix appartient
    à l'utilisateur. Équiper automatiquement remplirait les emplacements dans
    l'ordre d'obtention, c'est-à-dire au hasard.
    """
    obtenues = []
    for cle in achievement_keys:
        relique = relic_rules.unlocked_by(cle)
        if relique is None:
            continue
        _, cree = OwnedRelic.objects.get_or_create(user=user, key=relique.key)
        if cree:
            obtenues.append(
                {
                    "key": relique.key,
                    "label": relique.label,
                    "lore": relique.lore,
                    "emblem": relique.emblem,
                    "effect": relique.effect,
                    "value": relique.value,
                }
            )
    return obtenues


def relic_panel(user) -> dict:
    possedees = {r.key: r for r in OwnedRelic.objects.filter(user=user)}
    equipees = [k for k, r in possedees.items() if r.equipped]

    return {
        "max": relic_rules.MAX_EQUIPEES,
        "equipped_count": len(equipees),
        "relics": [
            {
                "key": r.key,
                "label": r.label,
                "lore": r.lore,
                "emblem": r.emblem,
                "effect": r.effect,
                "value": r.value,
                "owned": r.key in possedees,
                "equipped": r.key in equipees,
                "achievement": r.achievement,
            }
            for r in relic_rules.CATALOGUE
        ],
        "bonuses": {
            "extra_shields": relic_bonuses(user).extra_shields,
            "extra_days_off": relic_bonuses(user).extra_days_off,
            "early_xp_bonus": relic_bonuses(user).early_xp_bonus,
            "shard_bonus": relic_bonuses(user).shard_bonus,
            "boss_damage_bonus": relic_bonuses(user).boss_damage_bonus,
        },
    }


def toggle_relic(user, key: str) -> dict:
    """Équipe ou retire une relique, plafond compris."""
    avoir = OwnedRelic.objects.filter(user=user, key=key).first()
    if avoir is None:
        raise ValueError("Tu ne possèdes pas cette relique.")

    if avoir.equipped:
        avoir.equipped = False
        avoir.save(update_fields=["equipped"])
        return relic_panel(user)

    equipees = list(
        OwnedRelic.objects.filter(user=user, equipped=True).values_list("key", flat=True)
    )
    permis, motif = relic_rules.can_equip(equipees, key)
    if not permis:
        raise ValueError(motif)

    avoir.equipped = True
    avoir.save(update_fields=["equipped"])
    return relic_panel(user)


# --------------------------------------------------------------------------
# Clôture de semaine (§12.6)
# --------------------------------------------------------------------------

def close_week(user, *, week: date, rng: random.Random | None = None) -> dict:
    """Tire les cartes de la semaine écoulée. Idempotent par semaine.

    L'idempotence n'est pas du confort : cette fonction sera appelée par un
    déclencheur nocturne **et** à l'ouverture de l'app, et deux tirages pour une
    même semaine transformeraient un rythme en loterie.
    """
    marque = f"semaine:{week.isoformat()}"
    if LootDraw.objects.filter(user=user, reason=marque).exists():
        return {"drawn": [], "already": True}

    jours = (
        Session.objects.filter(
            user=user,
            status=Session.DONE,
            coach_day__gte=week,
            coach_day__lt=week + timedelta(days=7),
        )
        .values("coach_day")
        .distinct()
        .count()
    )

    engagements = Commitment.objects.filter(project__user=user, week_start=week).aggregate(
        total=Count("id"), tenus=Count("id", filter=Q(done_sessions__gte=1))
    )
    tous_tenus = bool(engagements["total"]) and _all_kept(user, week)

    combien = loot_rules.draws_for_week(days_kept=jours, commitments_kept=tous_tenus)
    tirees = [draw_card(user, reason=marque, rng=rng) for _ in range(combien)]

    return {"drawn": tirees, "already": False, "days_kept": jours, "all_kept": tous_tenus}


def _all_kept(user, week: date) -> bool:
    engagements = Commitment.objects.filter(project__user=user, week_start=week)
    return bool(engagements) and all(c.kept for c in engagements)


# --------------------------------------------------------------------------
# Le fantôme de saison (§12.7)
# --------------------------------------------------------------------------

def _season_curve(user, season) -> phantom_rules.Curve:
    """La courbe cumulée d'une saison, en minutes travaillées par jour.

    En minutes et non en XP : l'XP porte des multiplicateurs de streak, de
    momentum et de modificateur qui diffèrent d'une saison à l'autre. Comparer
    des XP reviendrait à comparer des règles plutôt que du travail, et le
    fantôme doit rester un adversaire, pas un barème.
    """
    jours = (season.ends_on - season.starts_on).days + 1
    par_jour = {
        ligne["coach_day"]: ligne["total"] or 0
        for ligne in Session.objects.filter(
            user=user,
            status=Session.DONE,
            coach_day__gte=season.starts_on,
            coach_day__lte=season.ends_on,
        )
        .values("coach_day")
        .annotate(total=Sum("actual_minutes"))
    }

    return phantom_rules.Curve(
        label=season.name,
        points=phantom_rules.cumulative(
            [par_jour.get(season.starts_on + timedelta(days=i), 0) for i in range(jours)]
        ),
    )


def phantom_panel(user, *, today: date) -> dict | None:
    """La comparaison au fantôme, prête à afficher. ``None`` hors saison."""
    from .models import Season

    courante = Season.objects.filter(
        user=user, status=Season.RUNNING, starts_on__lte=today, ends_on__gte=today
    ).first()
    if courante is None:
        return None

    passees = [
        _season_curve(user, s)
        for s in Season.objects.filter(user=user, index__lt=courante.index).order_by("index")
    ]
    mienne = _season_curve(user, courante)
    fantome = phantom_rules.pick(passees, courante.phantom_choice)

    jour = courante.day_index(today)
    ecart = phantom_rules.compare(mienne, fantome, day_index=jour)
    jours = (courante.ends_on - courante.starts_on).days + 1

    # La courbe personnelle s'arrête **aujourd'hui**. Sans cette coupe elle
    # continuait à plat jusqu'au dernier jour de la saison, ce qui se lit
    # « je n'ai rien fait ces dix-huit jours-là » alors que ces jours ne sont
    # pas encore arrivés. Le fantôme, lui, va jusqu'au bout : c'est ce qui fait
    # lire le graphique comme une course.
    tracee = phantom_rules.Curve(mienne.label, mienne.points[: jour + 1])

    return {
        "line": ecart.line,
        "available": ecart.available,
        "ahead": ecart.ahead,
        "delta": ecart.delta,
        "mine": ecart.mine,
        "theirs": ecart.theirs,
        "reference": ecart.reference,
        "choice": courante.phantom_choice,
        "choice_label": phantom_rules.CHOIX_LABELS.get(courante.phantom_choice, ""),
        "series": phantom_rules.series(tracee, fantome, days=jours),
        "day_index": jour,
        "days_total": jours,
    }


def season_modifier(season) -> dict:
    """Le modificateur en clair, affiché en permanence pendant la saison.

    En permanence et pas seulement à l'ouverture : un modificateur choisi il y a
    trois semaines et oublié produit des chiffres inexplicables, et un chiffre
    inexplicable détruit la confiance plus vite qu'une règle dure.
    """
    effets = modifier_rules.resolve(getattr(season, "modifier_key", ""))
    return {
        "key": effets.key,
        "name": effets.name,
        "effet": effets.effet,
        "line": modifier_rules.describe(effets),
        "active": effets.active,
    }
