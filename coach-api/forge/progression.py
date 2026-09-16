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
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from .models import (
    Achievement,
    Commitment,
    LootCard,
    LootDraw,
    OwnedRelic,
    Profile,
    Season,
    Session,
)
from .rules import defis as defis_rules
from .rules import loot as loot_rules
from .rules import modifiers as modifier_rules
from .rules import momentum as momentum_rules
from .rules import phantom as phantom_rules
from .rules import achievements as achievement_rules
from .rules import buffs as buff_rules
from .rules import relics as relic_rules
from .rules import seasons as season_rules
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
    # Les cartes **forgées** en sont exclues : un achat n'est pas un tirage, et
    # l'y compter reviendrait à pouvoir acheter sa chance — payer une épique
    # pour rapprocher la pitié de la suivante.
    recents = list(
        LootDraw.objects.filter(user=user)
        .exclude(reason=loot_rules.FORGEE)
        .order_by("-created_at")
        .values_list("rarity", flat=True)[:60]
    )

    depuis_rare = next(
        (i for i, r in enumerate(recents) if r != loot_rules.COMMUN), len(recents)
    )
    depuis_epique = next(
        (i for i, r in enumerate(recents) if r in (loot_rules.EPIQUE, loot_rules.LEGENDAIRE)),
        len(recents),
    )
    return depuis_rare, depuis_epique


def draw_card(
    user, *, reason: str, faveur: float = 0.0, rng: random.Random | None = None, day=None
) -> dict:
    """Tire une carte de **buff** dans le lot de la saison, et range la charge.

    *(Inversé le 16 septembre 2026 : les cartes donnent des buffs, les hauts
    faits donnent l'apparence.)*

    ``faveur`` incline le tirage vers le haut sans rien garantir. Elle vient de
    l'effort posé avant le déclencheur — les heures d'une étape terminée — et
    vaut zéro partout ailleurs.

    **Un doublon n'est plus une déception.** Il ajoute une charge de la même
    carte au lieu de se convertir en Éclats : une charge se dépense, donc la
    deuxième copie sert autant que la première.
    """
    from . import services

    saison = services.current_season(user, today=day) if day else None
    if saison is None:
        saison = Season.objects.filter(user=user).order_by("-index").first()
    lot = buff_rules.lot_de_saison(saison.index if saison else 1)

    depuis_rare, depuis_epique = _pity(user)
    if day is not None:
        # La carte « Main chanceuse » : le tirage part d'un cran plus haut. Elle
        # incline, elle ne garantit rien — comme la faveur de l'effort.
        chance = buff_arme(user, buff_rules.TIRAGE_CHANCEUX, day=day)
        if chance is not None:
            faveur = min(1.0, faveur + consommer_buff(chance))

    carte = _tirer_dans_le_lot(
        lot,
        draws_since_rare=depuis_rare,
        draws_since_epic=depuis_epique,
        faveur=faveur,
        rng=rng,
    )
    possedee = LootCard.objects.filter(user=user, key=carte.key).first()
    doublon = possedee is not None
    eclats = 0

    if possedee is not None:
        LootCard.objects.filter(pk=possedee.pk).update(copies=F("copies") + 1)
    else:
        LootCard.objects.create(
            user=user,
            key=carte.key,
            rarity=carte.rarity,
            kind="buff",
            reason=reason,
        )

    if eclats:
        profil = user.profile
        # Les deux primes s'additionnent : la relique du §12.8 et la voie
        # « Exigence » de l'ascendance, qui paie en Éclats un plancher plus haut.
        # Additives et non multiplicatives, comme partout ailleurs — deux bonus
        # qui se multiplient produisent une combinaison que personne n'a calculée.
        bonus = relic_bonuses(user).shard_bonus + services.ascendance_effects(user).eclats_bonus
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
        "color": loot_rules.RARETE_COLORS[carte.rarity],
        "kind": "buff",
        "payload": carte.ligne,
        "lore": carte.lore,
        "duplicate": doublon,
        "shards": eclats,
        "reason": reason,
        "reason_label": loot_rules.RAISONS.get(reason, ""),
    }


def _tirer_dans_le_lot(
    lot, *, draws_since_rare: int, draws_since_epic: int, faveur: float, rng=None
):
    """Tire une carte du lot de la saison, avec la pitié et la faveur du §12.6.

    La rareté se tire d'abord, comme avant. Si le lot n'a rien à cette rareté —
    huit cartes sur treize, ça arrive —, on redescend d'un cran plutôt que de
    retirer : remonter donnerait une légendaire à qui vise un commun.
    """
    rng = rng or random.Random()
    poids = loot_rules.rarity_weights(
        draws_since_rare=draws_since_rare, draws_since_epic=draws_since_epic, faveur=faveur
    )
    table = buff_rules.par_rarete(tuple(lot))
    rarete = rng.choices(
        loot_rules.RARETES, weights=[poids[r] for r in loot_rules.RARETES], k=1
    )[0]

    rangs = list(loot_rules.RARETES)
    for cran in range(rangs.index(rarete), -1, -1):
        if table.get(rangs[cran]):
            return rng.choice(table[rangs[cran]])
    return rng.choice(list(lot))


def forger(user, key: str) -> dict:
    """Fabrique une carte précise contre des Éclats (voie « Forge »).

    Le seul endroit du produit où des Éclats **sortent**. Jusqu'ici ils
    n'entraient que : doublons, routines tenues, quêtes — et la mise de saison
    n'est pas une dépense mais un pari qu'on récupère ou qu'on perd.

    La carte forgée est marquée comme telle dans le journal des tirages, et
    **n'entre pas dans la pitié** : la pitié existe pour que les tirages ne
    partent pas en séries de communs, et un achat n'est pas un tirage. L'y
    compter reviendrait à pouvoir acheter sa chance.
    """
    from . import services

    # Depuis l'inversion du 16 septembre 2026, la Forge fabrique une **charge de
    # buff** et non une apparence : les apparences se gagnent par un haut fait,
    # et pouvoir les acheter en Éclats viderait ce qu'elles racontent.
    carte = buff_rules.PAR_CLE.get(key)
    if carte is None:
        raise ValueError("Carte inconnue.")
    if not services.ascendance_effects(user).forge_ouverte:
        raise ValueError(
            "La Forge n'est pas ouverte. Elle se débloque à une ascendance, "
            "à la fin d'une année de douze saisons."
        )

    profil = user.profile
    # Une charge se rachète, contrairement à une apparence : « déjà possédée »
    # n'a plus de sens ici, seul le prix compte.
    ok, motif = loot_rules.peut_forger(carte, eclats=profil.shards, possedee=False)
    if not ok:
        raise ValueError(motif)

    prix = loot_rules.prix_de_forge(carte)
    profil.shards -= prix
    profil.save(update_fields=["shards"])

    ligne = LootCard.objects.filter(user=user, key=carte.key, kind="buff").first()
    if ligne is not None:
        LootCard.objects.filter(pk=ligne.pk).update(copies=F("copies") + 1)
    else:
        LootCard.objects.create(
            user=user, key=carte.key, rarity=carte.rarity, kind="buff", reason=loot_rules.FORGEE
        )
    # ``shards`` compte ce qu'un tirage **rend**, et une forge ne rend rien :
    # elle dépense. Le prix n'est pas perdu pour autant — il se retrouve depuis
    # la rareté, qui est stockée, et ``prix_de_forge`` est une fonction pure.
    LootDraw.objects.create(
        user=user,
        key=carte.key,
        rarity=carte.rarity,
        duplicate=False,
        shards=0,
        reason=loot_rules.FORGEE,
    )

    return {
        "key": carte.key,
        "label": carte.label,
        "rarity": carte.rarity,
        "rarity_label": loot_rules.RARETE_LABELS[carte.rarity],
        "color": loot_rules.RARETE_COLORS[carte.rarity],
        "kind": "buff",
        "payload": carte.ligne,
        "duplicate": False,
        "shards": -prix,
        "reason": loot_rules.FORGEE,
        "reason_label": loot_rules.RAISONS[loot_rules.FORGEE],
    }


def collection(user) -> dict:
    """L'inventaire, groupé par emplacement, avec ce qui manque encore.

    Les cartes non possédées sont rendues **en creux** : une collection qui ne
    montre que ce qu'on a ne donne aucune raison de continuer, et le §12.6 fait
    du loot un moteur d'envie, pas un coffre.
    """
    from . import achievements as achievement_service

    possedees = {c.key: c for c in LootCard.objects.filter(user=user)}
    equipes = (user.profile.cosmetics or {})

    # Lus une fois pour toute la grille : cent cartes qui interrogeraient chacune
    # les compteurs feraient cent fois le travail pour le même chiffre.
    mesures = achievement_service.faits(user)

    def defi_de(carte) -> dict | None:
        """Le défi d'une carte, et où l'on en est. ``None`` si elle se tire."""
        d = defis_rules.pour(carte.key)
        if d is None:
            return None
        valeur = mesures.get(d.fait, 0)
        return {
            "voie": d.voie,
            "condition": d.condition,
            "valeur": min(valeur, d.seuil),
            "seuil": d.seuil,
        }

    par_emplacement: dict[str, list[dict]] = {e: [] for e in EMPLACEMENTS}
    for carte in loot_rules.CATALOGUE:
        avoir = possedees.get(carte.key)
        par_emplacement.setdefault(carte.kind, []).append(
            {
                # Ce qu'elle fait une fois équipée, et comment on l'obtient. Les
                # deux manquaient : la grille montrait une rareté et un point
                # d'interrogation, ce qui ne donne aucune raison d'en viser une.
                "utilite": loot_rules.utilite(carte),
                "defi": defi_de(carte),
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

    from . import services

    forge = services.ascendance_effects(user).forge_ouverte
    if forge:
        for cartes in par_emplacement.values():
            for entree in cartes:
                # Une carte à défi ne s'achète pas, quel que soit le solde : le
                # bouton n'apparaît donc pas plutôt que de refuser après le clic.
                if entree["defi"] is None:
                    entree["forge_price"] = loot_rules.PRIX_FORGE[entree["rarity"]]

    return {
        "slots": par_emplacement,
        "owned": len(possedees),
        "total": len(loot_rules.CATALOGUE),
        "shards": user.profile.shards,
        "equipped": equipes,
        "forge_open": forge,
    }


def cosmetics(user) -> dict:
    """Ce qui est équipé, **résolu en valeurs affichables** (§12.6).

    Sans cette fonction, les cartes ne servaient à rien. Elles se tiraient, se
    rangeaient dans la collection, s'équipaient — et l'application restait
    strictement identique : ``profile.cosmetics`` ne quittait jamais le serveur,
    et rien côté client n'allait le chercher. Un emplacement « équipé » qui ne
    change rien à l'écran est la définition d'une récompense creuse.

    Les valeurs sont résolues ici plutôt que rendues sous forme de clés : le
    client n'a pas le catalogue, et le lui envoyer pour qu'il en retrouve les
    charges reviendrait à dupliquer le contenu de chaque côté. Il reçoit une
    couleur, un glyphe, un mot.

    **Rien de tout cela n'entre dans un calcul.** Le §17 est formel — le loot
    est de l'apparence, jamais du pouvoir. Ces valeurs partent vers le thème,
    l'avatar et la séquence de fin, et nulle part ailleurs.
    """
    equipes = user.profile.cosmetics or {}
    resolu: dict[str, dict] = {}

    for emplacement, cle in equipes.items():
        carte = loot_rules.PAR_CLE.get(cle)
        if carte is None:
            continue
        resolu[emplacement] = {
            "key": carte.key,
            "label": carte.label,
            "value": carte.payload,
            "rarity": carte.rarity,
        }
    return resolu


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


def grant_skins_for(user, achievement_keys) -> list[dict]:
    """Chaque haut fait donne une apparence (§12.6, inversé le 16 septembre 2026).

    C'est l'autre moitié de l'inversion : ce qui se **gagne par du travail nommé**
    donne ce qui se **montre**, et ce qui se tire donne ce qui se joue. Une
    apparence obtenue par un haut fait raconte quelque chose — « vingt-huit jours
    sans céder un bouclier » —, là où la même couleur tirée au sort ne racontait
    que d'avoir cliqué.

    L'attribution est **déterministe** : le rang du haut fait dans son catalogue
    désigne l'apparence dans le sien. Un tirage ici rendrait deux comptes
    différents pour la même vie, et rendrait le catalogue impossible à relire.
    """
    catalogue = loot_rules.CATALOGUE
    if not catalogue:
        return []

    obtenues = []
    for cle in achievement_keys:
        if cle not in achievement_rules.CLES:
            continue
        carte = catalogue[achievement_rules.CLES.index(cle) % len(catalogue)]
        if LootCard.objects.filter(user=user, key=carte.key).exists():
            continue
        LootCard.objects.create(
            user=user,
            key=carte.key,
            rarity=carte.rarity,
            kind=carte.kind,
            reason="haut_fait",
        )
        obtenues.append(
            {
                "key": carte.key,
                "label": carte.label,
                "rarity": carte.rarity,
                "rarity_label": loot_rules.RARETE_LABELS[carte.rarity],
                "kind": carte.kind,
                "payload": carte.payload,
                "color": carte.color,
            }
        )
    return obtenues


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


def grant_defis(user) -> list[dict]:
    """Donne les cartes dont le défi vient d'être rempli (§12.6, 21 août 2026).

    Appelée aux mêmes moments que la synchronisation des hauts faits, et pour
    la même raison : les compteurs ne bougent qu'à la fin d'une session ou
    d'une étape, et un défi rempli qui n'apparaîtrait qu'au prochain
    rafraîchissement de l'écran se lirait comme une récompense en retard.

    Idempotente : ``get_or_create`` sur la carte, donc rejouer la fonction ne
    donne rien deux fois. C'est ce qui permet de l'appeler sans se demander si
    elle a déjà tourné aujourd'hui.

    Les cartes ainsi obtenues **ne comptent pas comme un tirage** : elles ne
    touchent ni la pitié ni le compteur de tirages. Un défi rempli ne doit pas
    éloigner la prochaine carte rare.
    """
    from . import achievements as achievement_service

    mesures = achievement_service.faits(user)
    possedees = set(LootCard.objects.filter(user=user).values_list("key", flat=True))

    obtenues = []
    for cle in defis_rules.atteints(mesures):
        if cle in possedees:
            continue
        carte = loot_rules.PAR_CLE.get(cle)
        if carte is None:
            continue
        _, cree = LootCard.objects.get_or_create(
            user=user,
            key=carte.key,
            defaults={"rarity": carte.rarity, "kind": carte.kind, "copies": 1},
        )
        if not cree:
            continue
        defi = defis_rules.pour(carte.key)
        obtenues.append(
            {
                "key": carte.key,
                "label": carte.label,
                "rarity": carte.rarity,
                "rarity_label": loot_rules.RARETE_LABELS[carte.rarity],
                "color": carte.color,
                "kind": carte.kind,
                "payload": carte.payload,
                "duplicate": False,
                "shards": 0,
                "reason": loot_rules.DEFI,
                "reason_label": loot_rules.RAISONS.get(loot_rules.DEFI, ""),
                # De quoi écrire « défi rempli » et non « carte trouvée » : ce
                # n'est pas le même événement, et le dire pareil effacerait la
                # seule différence qui compte.
                "defi": {"voie": defi.voie, "condition": defi.condition} if defi else None,
            }
        )
    return obtenues


def relic_panel(user) -> dict:
    """Les reliques, avec **comment on les gagne** et **ce qu'elles font**.

    L'écran n'en disait ni l'un ni l'autre : une relique scellée s'annonçait
    « se débloque avec le haut fait *increvable* » — la clé de base de données,
    pas la condition —, et une relique possédée affichait son effet sous forme
    de nom de variable. Une récompense dont on ignore le prix et l'usage ne
    tire aucun comportement : elle décore un écran.

    Trois ajouts, tous calculés ici parce que le client n'a ni le catalogue des
    hauts faits ni les compteurs : la **condition** en français, la
    **progression** vers elle, et l'**effet** en une phrase.
    """
    from . import achievements as achievement_service
    from .rules import achievements as achievement_rules

    possedees = {r.key: r for r in OwnedRelic.objects.filter(user=user)}
    equipees = [k for k, r in possedees.items() if r.equipped]

    # Les compteurs ne sont lus qu'une fois pour tout le panneau : `faits()`
    # touche une dizaine de tables, et le faire par relique multiplierait ça
    # par quinze pour afficher le même chiffre.
    mesures = achievement_service.faits(user)

    def defi(relique) -> dict | None:
        """Ce qu'il faut faire pour cette relique, et où l'on en est."""
        haut_fait = achievement_rules.PAR_CLE.get(relique.achievement)
        if haut_fait is None:
            return None
        valeur = mesures.get(haut_fait.fait, 0)
        return {
            "achievement": haut_fait.key,
            "titre": haut_fait.label,
            "condition": haut_fait.description,
            "valeur": min(valeur, haut_fait.seuil),
            "seuil": haut_fait.seuil,
            "registre": haut_fait.registre,
        }

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
                # Ce que la relique fait, dit comme on le dirait à voix haute.
                "effet": relic_rules.phrase_effet(r),
                # Ce qu'il faut faire pour l'avoir, et où l'on en est.
                "defi": defi(r),
            }
            for r in relic_rules.CATALOGUE
        ],
        "bonuses": {
            "extra_shields": relic_bonuses(user).extra_shields,
            "extra_days_off": relic_bonuses(user).extra_days_off,
            "punctuality_bonus": relic_bonuses(user).punctuality_bonus,
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


def _minutes_by_hour(user) -> dict[int, int]:
    """Les minutes travaillées par heure locale, toutes saisons confondues.

    Chaque session est **étalée** sur les heures qu'elle traverse plutôt que
    versée en bloc à son heure de début : une session de 50 minutes lancée à
    21h50 a travaillé dix minutes à 21h et quarante à 22h, et l'attribuer
    entièrement à 21h décalerait la courbe d'une demi-heure vers l'avant.
    """
    zone = ZoneInfo(user.profile.timezone_name)
    par_heure: dict[int, int] = {}

    for debut, minutes in Session.objects.filter(
        user=user, status=Session.DONE
    ).values_list("started_at", "actual_minutes"):
        if not minutes:
            continue
        local = debut.astimezone(zone)
        heure, position = local.hour, local.minute
        restant = minutes
        while restant > 0:
            part = min(restant, 60 - position)
            par_heure[heure] = par_heure.get(heure, 0) + part
            restant -= part
            heure, position = (heure + 1) % 24, 0

    return par_heure


def phantom_panel(user, *, today: date, now: datetime | None = None) -> dict | None:
    """La comparaison au fantôme, prête à afficher. ``None`` hors saison."""
    from .models import Season

    courante = Season.objects.filter(
        user=user, status=Season.RUNNING, starts_on__lte=today, ends_on__gte=today
    ).first()
    if courante is None:
        return None

    # La saison d'essai sort du réservoir de fantômes : elle n'a pas été jouée
    # dans les mêmes conditions, et un adversaire tiré de jours d'apprentissage
    # est un adversaire qu'on bat sans rien apprendre (§12.7).
    passees = [
        _season_curve(user, s)
        for s in Season.objects.filter(user=user, index__lt=courante.index)
        .exclude(index=season_rules.ESSAI_INDEX)
        .order_by("index")
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

    # Le fantôme en direct : sa position à cette heure-ci, et non en fin de
    # journée. C'est ce qui rend l'écart actionnable — la soirée est encore là.
    instant = (now or timezone.now()).astimezone(ZoneInfo(user.profile.timezone_name))
    repartition = phantom_rules.hourly_shares(
        _minutes_by_hour(user), rollover_hour=user.profile.day_rollover_hour
    )
    part = phantom_rules.share_at(
        repartition,
        hour=instant.hour,
        minute=instant.minute,
        rollover_hour=user.profile.day_rollover_hour,
    )
    veille = mienne.at(jour - 1) if jour > 0 else 0
    direct = phantom_rules.live(
        mine_now=mienne.at(jour),
        mine_today=mienne.at(jour) - veille,
        phantom=fantome,
        day_index=jour,
        share=part,
        hour_label=f"{instant.hour}h{instant.minute:02d}",
    )

    return {
        "line": ecart.line,
        "available": ecart.available,
        "live": {
            "available": direct.available,
            "line": direct.line,
            "ahead": direct.ahead,
            "delta": direct.delta,
            "mine": direct.mine,
            "theirs": direct.theirs,
            "mine_today": direct.mine_today,
            "theirs_today": direct.theirs_today,
            "delta_today": direct.delta_today,
            "share": direct.share,
            "measured": repartition is not None,
        },
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


# --------------------------------------------------------------------------
# Les buffs de carte (SPEC §12.6, inversé le 16 septembre 2026)
# --------------------------------------------------------------------------

def inventaire_de_buffs(user, *, today) -> dict:
    """Les charges possédées, et ce qui est armé aujourd'hui.

    Les cartes de buff se rangent dans la même table que les apparences : une
    ligne par clé, ``copies`` compte les charges. Un doublon n'est donc plus une
    déception convertie en Éclats, c'est une charge de plus.
    """
    from .models import BuffActif, LootCard

    cartes = []
    for ligne in LootCard.objects.filter(user=user, kind="buff", copies__gt=0):
        buff = buff_rules.PAR_CLE.get(ligne.key)
        if buff is None:
            continue
        cartes.append(
            {
                "key": buff.key,
                "label": buff.label,
                "rarity": buff.rarity,
                "charges": ligne.copies,
                "ligne": buff.ligne,
                "lore": buff.lore,
                "touche_au_cadre": buff_rules.touche_au_cadre(buff.effect),
            }
        )

    armes = [
        {
            "key": b.key,
            "effect": b.effect,
            "value": b.value,
            "ligne": buff_rules.PAR_CLE[b.key].ligne if b.key in buff_rules.PAR_CLE else "",
        }
        for b in BuffActif.objects.filter(user=user, day=today, used_at__isnull=True)
    ]
    return {"cartes": sorted(cartes, key=lambda c: c["label"]), "armes": armes}


def armer_buff(user, key: str, *, today):
    """Dépense une charge et arme l'effet pour la journée. Lève ``ValueError``.

    Deux refus, et ils disent la même chose : on ne dépense que ce qu'on a, et
    on n'empile pas deux fois le même effet. Sans le second, deux « ×2 » sur la
    même séance donneraient un ×4 que personne n'a calibré.
    """
    from .models import BuffActif, LootCard

    buff = buff_rules.PAR_CLE.get(key)
    if buff is None:
        raise ValueError("Cette carte n'existe pas.")

    ligne = LootCard.objects.filter(user=user, key=key, kind="buff", copies__gt=0).first()
    if ligne is None:
        raise ValueError(f"Aucune charge de « {buff.label} » en réserve.")

    if BuffActif.objects.filter(
        user=user, day=today, effect=buff.effect, used_at__isnull=True
    ).exists():
        raise ValueError(f"« {buff.label} » ferait doublon : un effet du même genre est déjà armé.")

    ligne.copies -= 1
    ligne.save(update_fields=["copies"])
    return BuffActif.objects.create(
        user=user, key=buff.key, effect=buff.effect, value=buff.value, day=today
    )


def buff_arme(user, effect: str, *, day):
    """Le buff de cet effet armé aujourd'hui, ou ``None``."""
    from .models import BuffActif

    return BuffActif.objects.filter(
        user=user, day=day, effect=effect, used_at__isnull=True
    ).first()


def consommer_buff(buff) -> float:
    """Marque le buff comme consommé et rend sa valeur. ``1.0`` si rien n'était armé."""
    from django.utils import timezone as dj

    if buff is None:
        return 1.0
    buff.used_at = dj.now()
    buff.save(update_fields=["used_at"])
    return buff.value
