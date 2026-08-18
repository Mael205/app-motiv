"""Le cycle d'une saison : clôture, offre, ouverture (SPEC §12.2, §12.6, §7.4).

Une saison qui se termine et une saison qui commence sont **le même moment**.
C'est la raison d'être de ce module : la clôture rend son score et son titre,
et dans la foulée elle propose la suivante avec ses trois modificateurs. Séparer
les deux laisserait un état où aucune saison n'est en cours — donc une app sans
boss, sans mise et sans horizon, exactement là où l'on avait le plus besoin de
relancer.

Trois règles y sont tenues :

1. **Le titre raté existe.** *Déserteur de Ragnarök* est décerné aussi
   franchement que *Vainqueur*. Le §12.3 le dit : une collection sans trous n'a
   aucune valeur, et un système qui n'enregistrerait que les réussites mentirait
   sur ce qui s'est passé.
2. **Le modificateur est choisi parmi trois** (§12.5) — un choix, pas une
   subissance. Idem pour le fantôme (§12.7) : contre quoi on court se décide à
   l'ouverture et se fige ensuite.
3. **La mise est résolue avant tout le reste.** Saison réussie, mise doublée ;
   ratée, mise perdue. C'est le seul endroit du système où quelque chose se
   perd, et le §12.6 le veut : un enjeu réel, sans conséquence matérielle.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Sum

from . import progression, seasonreport, services
from .models import Ascendance, Project, Season, Session
from .rules import contract as contract_rules
from .rules import loot as loot_rules
from .rules import modifiers as modifier_rules
from .rules import phantom as phantom_rules
from .rules import seasons as season_rules
from .rules import xp as xp_rules
from .rules import years as year_rules

# Une saison est « réussie » quand le boss est tombé. C'est le seuil le plus
# lisible : la barre de vie est visible en permanence (§12.4), donc chacun sait
# où il en est sans avoir à consulter un barème.
SEUIL_REUSSITE = 1.0


# --------------------------------------------------------------------------
# Clôture (§7, séquence 4)
# --------------------------------------------------------------------------

def season_score(user, season: Season) -> int:
    """Le score d'une saison, en minutes réellement travaillées.

    En minutes et non en XP, pour la même raison qu'au fantôme : l'XP porte des
    multiplicateurs de streak, de momentum et de modificateur qui changent d'une
    saison à l'autre. Un score en XP comparerait des règles ; un score en
    minutes compare du travail.
    """
    return (
        Session.objects.filter(user=user, season=season, status=Session.DONE).aggregate(
            total=Sum("actual_minutes")
        )["total"]
        or 0
    )


def is_over(season: Season, *, today: date) -> bool:
    """La saison est-elle finie ? Le boss mort la termine en avance (§12.4)."""
    boss = getattr(season, "boss", None)
    return today > season.ends_on or bool(boss and boss.is_dead)


@transaction.atomic
def close_season(user, season: Season, *, today: date, rng: random.Random | None = None) -> dict:
    """Clôt une saison et rend de quoi jouer la séquence du §7.4.

    Idempotent : une saison déjà close rend son bilan enregistré sans rien
    retirer ni rejouer. Cette fonction est appelée depuis l'ouverture de l'app
    **et** depuis un déclencheur, et une mise résolue deux fois doublerait ou
    effacerait des Éclats sans que personne ne comprenne pourquoi.
    """
    if season.status == Season.CLOSED:
        return _bilan(user, season, today=today, deja=True)

    boss = getattr(season, "boss", None)
    score = season_score(user, season)
    ratio = 1 - (boss.ratio if boss else 1.0)  # part de la vie du boss retirée

    season.final_score = score
    season.title_awarded = season_rules.title_for(ratio, season.name)
    season.status = Season.CLOSED
    season.save(update_fields=["final_score", "title_awarded", "status"])

    # La mise, résolue une seule fois — et sur ce qu'il en **reste**. Le palier 2
    # du §14 en prélève un quart à chaque streak cassé, déjà retiré du solde ;
    # rejouer la mise entière ici la ferait payer deux fois.
    profil = user.profile
    gagne = ratio >= SEUIL_REUSSITE
    engagee = max(0, season.stake_shards - season.stake_forfeited)
    delta = engagee if gagne else -engagee
    profil.shards = max(0, profil.shards + delta)
    profil.save(update_fields=["shards"])

    cartes = [progression.draw_card(user, reason=loot_rules.FIN_DE_SAISON, rng=rng)]
    if gagne:
        cartes.append(progression.draw_card(user, reason=loot_rules.FIN_DE_SAISON, rng=rng))

    bilan = _bilan(user, season, today=today, deja=False)
    bilan["cards"] = cartes
    bilan["stake_delta"] = delta

    # La douzième saison ferme l'année. L'ascendance est écrite ici, dans la
    # même transaction : une année close dont l'ascendance manquerait laisserait
    # la treizième saison s'ouvrir sur l'ancienne échelle d'XP.
    if year_rules.ferme_l_annee(season.index):
        bilan["annee"] = _clore_l_annee(user, season, today=today)

    return bilan


def _clore_l_annee(user, season: Season, *, today: date) -> dict:
    """Fige le bilan de l'année et ouvre le choix de la voie. Idempotent.

    Le bilan est **figé** plutôt que recalculé à la lecture : une session
    corrigée un mois plus tard, une saison rejouée, et l'année deux ne
    raconterait plus ce qu'on a lu le jour de l'ascendance.

    La voie, elle, reste vide. Elle se choisit après, en ayant lu le bilan —
    choisir avant de savoir ce qu'on a fait de l'année n'aurait aucun sens.
    """
    annee = year_rules.annee_de(season.index)
    existante = Ascendance.objects.filter(user=user, year_index=annee).first()
    if existante:
        return _payload_annee(user, existante)

    saisons = Season.objects.filter(
        user=user,
        index__gt=(annee - 1) * year_rules.SAISONS_PAR_AN,
        index__lte=annee * year_rules.SAISONS_PAR_AN,
    ).select_related("boss")

    abattus = sum(1 for s in saisons if hasattr(s, "boss") and s.boss.is_dead)
    minutes = sum(season_score(user, s) for s in saisons)
    xp = services.current_xp(user)
    rang = services.rank_state(user, today=today)

    ascendance = Ascendance.objects.create(
        user=user,
        year_index=annee,
        closed_on=today,
        seasons_closed=saisons.filter(status=Season.CLOSED).count(),
        bosses_killed=abattus,
        minutes=minutes,
        xp_at_reset=xp,
        level_at_reset=xp_rules.level_for(xp),
        rank_at_reset=rang["code"],
        # Gravés **avant** que le rang ne reparte : c'est la seule récompense de
        # rang qui survive, et il faut la lire pendant qu'elle existe encore.
        slots_engraved=rang["slots"],
        title_awarded=year_rules.titre_de_l_annee(annee, abattus),
    )
    return _payload_annee(user, ascendance)


def _payload_annee(user, ascendance) -> dict:
    """L'année accomplie, et les voies encore ouvertes."""
    prises = [a.voie for a in services.ascendances(user) if a.voie]
    ouvertes = year_rules.voies_disponibles(
        prises, slots_actuels=services.rank_state(user, today=ascendance.closed_on)["slots"]
    )

    return {
        "year": ascendance.year_index,
        "title": ascendance.title_awarded,
        "seasons": ascendance.seasons_closed,
        "bosses_killed": ascendance.bosses_killed,
        "hours": round(ascendance.minutes / 60, 1),
        "xp_at_reset": ascendance.xp_at_reset,
        "level_at_reset": ascendance.level_at_reset,
        "rank_at_reset": ascendance.rank_at_reset,
        "slots_engraved": ascendance.slots_engraved,
        "voie": ascendance.voie,
        "voies": [
            {
                "key": v.cle,
                "label": v.label,
                "promesse": v.promesse,
                "cout": v.cout,
            }
            for v in ouvertes
        ],
        # Dit en toutes lettres, parce que c'est la question qu'on se pose en
        # lisant l'écran, et qu'un doute là-dessus vaut plus cher que l'écran.
        "garde": (
            f"L'XP, le niveau et le rang repartent — tu redescends en F et tu "
            f"regravis. Tes {ascendance.slots_engraved} slots sont gravés : le "
            "rang ne peut pas les reprendre, sinon des projets en cours se "
            "retrouveraient gelés. L'arbre, les reliques, la collection et les "
            "hauts faits ne bougent pas, et la trace longue garde tout."
        ),
    }


def choisir_la_voie(user, cle: str) -> dict:
    """Grave la voie d'une ascendance. Une seule fois, jamais reprise.

    Le choix est définitif, et c'est ce qui en fait un choix. Une voie qu'on
    pourrait échanger le mois suivant serait un réglage — et le produit a déjà
    tranché ailleurs que les réglages qu'on modifie en passant ne se tiennent
    pas (§16 de la liste du 17 août, le contrat de saison).
    """
    ascendance = (
        Ascendance.objects.filter(user=user, voie="").order_by("year_index").first()
    )
    if ascendance is None:
        raise ValueError("Aucune année en attente de voie.")

    prises = [a.voie for a in services.ascendances(user) if a.voie]
    ouvertes = {
        v.cle
        for v in year_rules.voies_disponibles(
            prises, slots_actuels=services.rank_state(user, today=ascendance.closed_on)["slots"]
        )
    }
    if cle not in ouvertes:
        raise ValueError(
            f"« {cle} » n'est pas ouverte. Restent : {', '.join(sorted(ouvertes)) or 'aucune'}."
        )

    ascendance.voie = cle
    ascendance.save(update_fields=["voie"])
    return _payload_annee(user, ascendance)


def annee_en_attente(user) -> dict | None:
    """L'ascendance dont la voie n'a pas encore été choisie, s'il y en a une."""
    ascendance = (
        Ascendance.objects.filter(user=user, voie="").order_by("year_index").first()
    )
    return _payload_annee(user, ascendance) if ascendance else None


def _bilan(user, season: Season, *, today: date, deja: bool) -> dict:
    boss = getattr(season, "boss", None)
    ratio = 1 - (boss.ratio if boss else 1.0)
    jours = (season.ends_on - season.starts_on).days + 1

    # La comparaison au fantôme se fait au **dernier jour**, pas à aujourd'hui :
    # le bilan d'une saison finie ne bouge plus.
    passees = [
        progression._season_curve(user, s)
        for s in Season.objects.filter(user=user, index__lt=season.index).order_by("index")
    ]
    mienne = progression._season_curve(user, season)
    fantome = phantom_rules.pick(passees, season.phantom_choice)
    ecart = phantom_rules.compare(mienne, fantome, day_index=jours - 1)

    return {
        "season": {
            "index": season.index,
            "name": season.name,
            "accent": season.accent,
            "baseline": season.baseline,
            "days": jours,
        },
        "score": season.final_score,
        "hours": round(season.final_score / 60, 1),
        "title": season.title_awarded,
        "won": ratio >= SEUIL_REUSSITE,
        "boss": {
            "name": boss.name if boss else "",
            "ratio_killed": round(ratio, 3),
            "is_dead": bool(boss and boss.is_dead),
        },
        "stake": max(0, season.stake_shards - season.stake_forfeited),
        "stake_forfeited": season.stake_forfeited,
        "modifier": progression.season_modifier(season),
        "phantom": {
            "line": ecart.line,
            "available": ecart.available,
            "ahead": ecart.ahead,
            "delta": ecart.delta,
            "reference": ecart.reference,
            "series": phantom_rules.series(mienne, fantome, days=jours),
        },
        # Le contrat relu à la clôture : un écart, jamais une note (§17).
        "contract": services.season_contract(user, season),
        "already_closed": deja,
        "cards": [],
        "stake_delta": 0,
        # Le §13.4 : la comparaison à toutes les saisons passées, et la question
        # de fin de saison. C'est la passe de fin de saison de l'analyste (§5.5),
        # l'autre étant celle de chaque nuit.
        "comparaison": seasonreport.comparaison(user, season),
    }


# --------------------------------------------------------------------------
# Offre de la saison suivante (§12.2, §12.5, §12.7)
# --------------------------------------------------------------------------

def next_offer(user, *, today: date) -> dict:
    """Ce qu'on propose pour la saison suivante. N'écrit rien.

    Rien n'est écrit tant que le choix n'est pas fait : c'est ce qui permet de
    reculer, de fermer l'app, d'y revenir le lendemain. Une saison ouverte
    d'office par un appel de lecture serait un engagement pris à la place de
    quelqu'un.
    """
    precedente = Season.objects.filter(user=user).order_by("-index").first()
    index = (precedente.index + 1) if precedente else 1

    score_precedent = season_score(user, precedente) if precedente else None
    plan = season_rules.plan_season(
        index, _next_start(precedente, today=today), previous_score=score_precedent
    )

    # La voie « Écho » en propose cinq au lieu de trois. Un choix plus large,
    # pas un meilleur modificateur : ils sortent du même catalogue, et un seul
    # reste actif.
    combien = services.ascendance_effects(user).modificateurs_proposes
    propositions = []
    for entree in season_rules.propose_modifiers(index, combien):
        effets = modifier_rules.resolve(entree["key"])
        propositions.append(
            {
                "key": effets.key,
                "name": effets.name,
                "effet": effets.effet,
                # Ce que chaque choix coûte vraiment, dit d'avance. Un
                # modificateur dont on découvre le prix trois semaines plus tard
                # n'a pas été choisi.
                "boss_hp": round(plan.boss_hp * effets.boss_hp_multiplier),
                "stake_multiplier": effets.stake_multiplier,
                "hard": not effets.degraded_enabled or effets.days_off_allowed == 0,
            }
        )

    return {
        "index": plan.index,
        "name": plan.name,
        "accent": plan.accent,
        "baseline": plan.baseline,
        "starts_on": plan.starts_on.isoformat(),
        "ends_on": plan.ends_on.isoformat(),
        "boss": {"name": plan.boss_name, "hp": plan.boss_hp},
        "modifiers": propositions,
        "phantoms": _phantom_offer(user, index=index),
        "shards": user.profile.shards,
        "contract": _contract_offer(user, plan),
    }


def _contract_offer(user, plan) -> dict:
    """Ce qu'on propose de signer, et ce que ça engage en toutes lettres.

    Le nombre proposé est la somme des engagements hebdomadaires déjà pris sur
    les projets en slot : il ne sort pas de nulle part, et une proposition qui
    reprend ce qu'on fait déjà se signe sans négocier. Reste à la lire.
    """
    projets = list(
        Project.objects.filter(user=user, status=Project.ACTIVE)
        .exclude(slot=None)
        .values_list("name", "weekly_commitment")
    )
    propose = sum(engagement for _, engagement in projets) or 3
    propose = min(propose, contract_rules.MAXIMUM)
    semaines = max(1, plan.days_total // 7)
    contrat = contract_rules.Contrat(
        sessions_par_semaine=propose,
        projets=tuple(nom for nom, _ in projets),
        semaines=semaines,
    )

    return {
        "proposed": contrat.sessions_par_semaine,
        "minimum": contract_rules.MINIMUM,
        "maximum": contract_rules.MAXIMUM,
        "weeks": semaines,
        "total": contrat.total,
        "projects": list(contrat.projets),
        "terms": list(contrat.lignes),
    }


def _next_start(previous: Season | None, *, today: date) -> date:
    """Deux jours de pause explicite entre deux saisons (§12.4).

    Jamais dans le passé : rouvrir une saison sur une date écoulée créerait des
    jours déjà « manqués » avant même d'avoir commencé.
    """
    if previous is None:
        return today
    return max(today, season_rules.next_season_start(previous.ends_on))


def _phantom_offer(user, *, index: int) -> list[dict]:
    """Les adversaires possibles, avec leur total, pour choisir en connaissance.

    Afficher le total de chacun n'est pas un détail : choisir « ma meilleure
    saison » sans savoir qu'elle représente soixante heures revient à choisir au
    hasard, et le §12.7 veut un adversaire, pas une surprise.
    """
    courbes = [
        progression._season_curve(user, s)
        for s in Season.objects.filter(user=user, index__lt=index).order_by("index")
    ]
    offres = []
    for choix in phantom_rules.CHOIX:
        courbe = phantom_rules.pick(courbes, choix)
        offres.append(
            {
                "key": choix,
                "label": phantom_rules.CHOIX_LABELS[choix],
                "available": courbe is not None,
                "reference": courbe.label if courbe else "",
                "hours": round(courbe.total / 60, 1) if courbe else 0.0,
            }
        )
    return offres


@transaction.atomic
def open_next(
    user,
    *,
    today: date,
    modifier_key: str = "",
    phantom_choice: str = phantom_rules.MEILLEURE,
    stake: int = 0,
    contract_sessions_per_week: int = 0,
) -> Season:
    """Ouvre la saison suivante avec les choix faits à l'écran d'ouverture."""
    if phantom_choice not in phantom_rules.CHOIX:
        raise ValueError("Choix de fantôme inconnu.")

    disponibles = {m["key"] for m in next_offer(user, today=today)["modifiers"]}
    if modifier_key and modifier_key not in disponibles:
        # Le tirage est le sens de la mécanique : accepter n'importe quelle clé
        # laisserait choisir le modificateur le plus avantageux à chaque saison,
        # et la saison 5 redeviendrait la saison 1.
        raise ValueError("Ce modificateur n'est pas dans les trois proposés.")

    precedente = Season.objects.filter(user=user).order_by("-index").first()
    return services.open_season(
        user,
        starts_on=_next_start(precedente, today=today),
        stake=stake,
        modifier_key=modifier_key,
        phantom_choice=phantom_choice,
        contract_sessions_per_week=contract_sessions_per_week,
    )


def exit_offer(user, *, today: date) -> dict | None:
    """La porte de sortie du palier 3 (§14) : clore la saison en avance.

    Offerte au-delà de cinq jours d'arrêt, et **jamais prise d'office**. Le §14
    en donne la raison : la porte est proposée avant qu'elle soit inventée sous
    forme de désinstallation. La prendre à la place de quelqu'un reviendrait à
    décider de son abandon.

    Le prix est annoncé — c'est la règle tenue partout ailleurs pour les
    modificateurs (§12.5) : une saison close en avance reste une saison ratée,
    donc la mise qu'il en reste ne revient pas.
    """
    courante = services.current_season(user, today=today)
    if courante is None or is_over(courante, today=today):
        return None
    if not services.sanctions_for(user, today=today).season_exit_offered:
        return None

    return {
        "season": courante.name,
        "days_left": courante.days_left(today),
        "stake_at_risk": max(0, courante.stake_shards - courante.stake_forfeited),
    }


def pending_close(user, *, today: date) -> Season | None:
    """La saison en cours qui devrait être close, s'il y en a une.

    Interrogée à l'ouverture de l'app : une saison finie pendant qu'on ne
    regardait pas doit se conclure au moment où l'on revient, pas rester en
    suspens jusqu'à ce qu'un déclencheur passe.
    """
    courante = services.current_season(user, today=today)
    if courante and is_over(courante, today=today):
        return courante
    return None
