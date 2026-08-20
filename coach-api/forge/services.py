"""Services du domaine : ce qui relie les modèles à la logique pure.

Rien ici ne réimplémente une règle : le streak, l'XP et la saison viennent de
``forge/rules``. Ce module se contente de rassembler les faits, d'appeler les
règles, et d'écrire le résultat.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, F, Max, Min, Sum, Value
from django.db.models.functions import Greatest
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import (
    Achievement,
    Ascendance,
    Commitment,
    DayOff,
    DiscardedResource,
    Garde,
    GardeDay,
    JournalEntry,
    Profile,
    Preuve,
    Project,
    ProjectBloc,
    ProjectHold,
    ProjectRepo,
    Quest,
    RelaxWindow,
    RoadmapStep,
    Routine,
    RoutineCheck,
    NotificationLog,
    Season,
    SeasonBoss,
    Session,
    Signal,
    TimeSlot,
    Track,
)
from . import achievements, filescan, gitscan, progression
from .rules import bossphases as bossphase_rules
from .rules import contract as contract_rules
from .rules import capacite as capacite_rules
from .rules import corps as corps_rules
from .rules import creneau as creneau_rules
from .rules import crit as crit_rules
from .rules import loot as loot_rules
from .rules import gardes as garde_rules
from .rules import ghost as ghost_rules
from .rules import sommeil as sommeil_rules
from .rules import modifiers as modifier_rules
from .rules import ranks as rank_rules
from .rules import roadmap_import
from .rules import routines as routine_rules
from .rules import sanctions as sanction_rules
from .rules import hiatus as hiatus_rules
from .rules import holds as hold_rules
from .rules import citations
from .rules import seasons as season_rules
from .rules import signals as signal_rules
from .rules import slots as slot_rules
from .rules import verification as verification_rules
from .rules import streak as streak_rules
from .rules import xp as xp_rules
from .rules import years as year_rules
from .rules.calendar import coach_day, day_bounds, evening_window, week_start

FLOOR_MINUTES = streak_rules.FLOOR_MINUTES
DEGRADED_MINUTES = 10

# Ce qu'un « +15 min » ajoute à l'objectif d'une séance en cours (§4.1).
EXTENSION_MINUTES = 15

# Le plafond dur d'une séance. Il n'est **pas** un jugement sur la durée : c'est
# le garde-fou du §8.7 pour le cas que la sonde ne couvre pas. Une session
# oubliée toute une nuit et clôturée au matin ne doit pas créditer huit heures
# de travail — le §17 interdit de récompenser du temps qui n'a pas été
# travaillé, et c'est la seule faute que ce module puisse commettre en silence.
# Quatre heures : au-delà, ce n'est plus une séance, c'est un oubli.
MAX_SESSION_MINUTES = 240


# --------------------------------------------------------------------------
# Journées et streak
# --------------------------------------------------------------------------

def resolve_days(user, track: Track, *, until: date, since: date | None = None) -> list[streak_rules.Day]:
    """Construit l'historique jour par jour, sans trou.

    Une journée est validée si elle porte assez de minutes, neutre si un jour
    off a été déclaré à temps ou si elle tombe dans une pause de saison, ratée
    sinon. La journée en cours n'est jamais comptée comme ratée : elle n'est
    pas finie.
    """
    first_session = (
        Session.objects.filter(user=user, project__track=track, status=Session.DONE)
        .order_by("coach_day")
        .values_list("coach_day", flat=True)
        .first()
    )
    start = since or first_session
    if not start:
        return []

    minutes_by_day: dict[date, int] = {
        row["coach_day"]: row["total"] or 0
        for row in Session.objects.filter(
            user=user, project__track=track, status=Session.DONE, coach_day__gte=start, coach_day__lte=until
        )
        .values("coach_day")
        .annotate(total=Sum("actual_minutes"))
    }
    days_off = set(DayOff.objects.filter(user=user, date__gte=start, date__lte=until).values_list("date", flat=True))
    pauses = _season_pause_days(user, start, until)
    # Le mode veille : une absence déclarée ne casse rien et ne construit rien.
    # Même contrat que le jour off du §11.5, sur une durée qui a du sens.
    pauses |= veille_days(user, start, until)

    result: list[streak_rules.Day] = []
    cursor = start
    while cursor <= until:
        if cursor in days_off or cursor in pauses:
            state = streak_rules.DayState.NEUTRE
        elif minutes_by_day.get(cursor, 0) >= DEGRADED_MINUTES:
            state = streak_rules.DayState.VALIDEE
        else:
            state = streak_rules.DayState.RATEE
        result.append(streak_rules.Day(cursor, state))
        cursor += timedelta(days=1)
    return result


def veille_days(user, start: date, until: date) -> set[date]:
    """Les journées couvertes par une veille déclarée (mode veille).

    Une veille interrompue ne couvre plus que jusqu'à son interruption : on en
    sort quand on veut, et les jours d'après redeviennent des jours normaux.
    """
    from .models import Hiatus

    couverts: set[date] = set()
    for veille in Hiatus.objects.filter(user=user, ends_on__gte=start, starts_on__lte=until):
        fin = veille.ends_on
        if veille.ended_early_at:
            fin = min(fin, veille.ended_early_at.date())
        couverts |= {
            jour
            for jour in hiatus_rules.jours(veille.starts_on, fin)
            if start <= jour <= until
        }
    return couverts


def veille_en_cours(user, *, today: date):
    """La veille qui couvre aujourd'hui, ou ``None``."""
    from .models import Hiatus

    for veille in Hiatus.objects.filter(
        user=user, starts_on__lte=today, ends_on__gte=today, ended_early_at__isnull=True
    ):
        return veille
    return None


@transaction.atomic
def synchroniser_veille(user, *, today: date) -> str:
    """Gèle ou dégèle la saison selon la veille en cours. Rend ce qui a changé.

    Appelée à chaque lecture de l'accueil et à chaque passage de l'ordonnanceur :
    la reprise ne doit dépendre d'aucun geste. Quelqu'un qui rouvre l'app après
    trois semaines d'absence n'a pas à cliquer sur « je suis rentré ».

    La saison reprend **où elle en était** : les jours gelés lui sont rendus. Une
    saison de 28 jours dont on a gelé 10 se termine 10 jours plus tard, sinon la
    veille coûterait un tiers de la saison — et une pause qui coûte n'est pas une
    pause.
    """
    from .models import Hiatus

    veille = veille_en_cours(user, today=today)
    saison = (
        Season.objects.filter(user=user, status__in=[Season.RUNNING, Season.PAUSED])
        .order_by("-index")
        .first()
    )
    if saison is None:
        return "rien"

    if veille and saison.status == Season.RUNNING:
        saison.status = Season.PAUSED
        saison.save(update_fields=["status"])
        return "gelee"

    if veille:
        return "gelee"

    # Plus de veille : on rend à la saison les jours qu'on lui a pris.
    rendus = 0
    for passee in Hiatus.objects.filter(user=user, starts_on__lte=today):
        fin = passee.ends_on
        if passee.ended_early_at:
            fin = min(fin, passee.ended_early_at.date())
        fin = min(fin, today)
        effectifs = max(0, (fin - passee.starts_on).days + 1)
        du = effectifs - passee.days_given_back
        if du <= 0:
            continue
        rendus += du
        passee.days_given_back = effectifs
        passee.save(update_fields=["days_given_back"])

    if saison.status == Season.PAUSED:
        saison.status = Season.RUNNING
    if rendus:
        saison.ends_on = saison.ends_on + timedelta(days=rendus)
    if rendus or saison.status == Season.RUNNING:
        saison.save(update_fields=["status", "ends_on"])
    return "reprise" if rendus else "rien"


@transaction.atomic
def declarer_veille(user, *, debut: date, fin: date, today: date, raison: str = ""):
    """Déclare une veille. Lève ``ValueError`` si les règles la refusent."""
    from .models import Hiatus

    verdict = hiatus_rules.verifier(debut=debut, fin=fin, aujourdhui=today)
    if not verdict.ok:
        raise ValueError(verdict.raison)
    if veille_en_cours(user, today=today):
        raise ValueError("Une veille est déjà en cours.")

    veille = Hiatus.objects.create(
        user=user, starts_on=debut, ends_on=fin, reason=raison.strip()[:120]
    )
    synchroniser_veille(user, today=today)
    return veille


@transaction.atomic
def terminer_veille(user, *, today: date, now: datetime | None = None):
    """Sort de la veille tout de suite. Rendre est immédiat, comme partout ici."""
    veille = veille_en_cours(user, today=today)
    if veille is None:
        return None
    veille.ended_early_at = now or timezone.now()
    veille.save(update_fields=["ended_early_at"])
    synchroniser_veille(user, today=today)
    return veille


def _season_pause_days(user, start: date, until: date) -> set[date]:
    """Les deux jours entre deux saisons sont neutres (SPEC §12.1)."""
    pauses: set[date] = set()
    closed = Season.objects.filter(user=user, status=Season.CLOSED).order_by("index")
    for season in closed:
        for offset in range(1, season_rules.SEASON_PAUSE_DAYS + 1):
            day = season.ends_on + timedelta(days=offset)
            if start <= day <= until:
                pauses.add(day)
    return pauses


# --------------------------------------------------------------------------
# L'ascendance : l'année accomplie, et ce qu'elle ouvre (§12.2 étendu)
# --------------------------------------------------------------------------

def ascendances(user) -> list:
    """Les années déjà accomplies, de la plus ancienne à la plus récente."""
    return list(Ascendance.objects.filter(user=user).order_by("year_index"))


def ascendance_effects(user) -> year_rules.Effets:
    """Ce que les voies prises changent, cumulé.

    Seules les ascendances dont la voie a été **choisie** comptent : une année
    close dont on n'a pas encore tranché la voie n'ouvre rien, et c'est ce qui
    rend le choix réel plutôt qu'une formalité à cliquer plus tard.
    """
    return year_rules.effets([a.voie for a in ascendances(user) if a.voie])


def xp_horizon(user) -> date | None:
    """Le jour depuis lequel l'XP courante se compte. ``None`` avant la première année.

    C'est tout le mécanisme du reset, et il tient en une date. **Aucune session
    n'est touchée** : l'XP cumulée de toujours reste lisible dans la trace
    longue, et seule l'échelle affichée repart. Le §17 interdit de faire
    disparaître du travail réel, pas de changer d'unité.
    """
    derniere = Ascendance.objects.filter(user=user).order_by("-year_index").first()
    return derniere.closed_on if derniere else None


def rank_horizon(user) -> date | None:
    """Le lundi depuis lequel les semaines tenues se comptent.

    Même mécanisme que pour l'XP, et pour la même raison : le rang repart de F
    à l'ascendance, mais **aucune semaine n'est effacée**. C'est la fenêtre de
    lecture qui avance, et le plus haut rang atteint reste lisible dans la
    trace longue.
    """
    derniere = Ascendance.objects.filter(user=user).order_by("-year_index").first()
    return week_start(derniere.closed_on) if derniere else None


def slots_graves(user) -> int:
    """Les slots rendus permanents par les ascendances passées.

    Le rang les reprendrait en repartant de F, et le §4.3 l'interdit : « les
    projets ne sont pas supprimés ». C'est la seule récompense de rang qui
    survive à une ascendance — les boucliers, les jours off et le plancher se
    regagnent.
    """
    derniere = Ascendance.objects.filter(user=user).order_by("-year_index").first()
    return derniere.slots_engraved if derniere else slot_rules.BASE_SLOTS


def current_xp(user, *, exclude_session=None) -> int:
    """L'XP de l'année en cours, c'est-à-dire depuis la dernière ascendance."""
    faites = Session.objects.filter(user=user, status=Session.DONE)
    horizon = xp_horizon(user)
    if horizon is not None:
        faites = faites.filter(coach_day__gt=horizon)
    if exclude_session is not None:
        faites = faites.exclude(pk=exclude_session.pk)
    return faites.aggregate(t=Sum("xp_awarded"))["t"] or 0


def floor_minutes(user, *, today: date) -> int:
    """Le plancher de la session normale, indexé sur le rang (§4.1, §4.4).

    L'ascendance peut le relever définitivement : c'est la contrepartie de la
    voie « Exigence », payée en Éclats — donc en monnaie cosmétique, la seule
    que le système puisse donner sans fausser sa propre mesure.
    """
    base = streak_rules.floor_for(rank_state(user, today=today)["code"])
    return base + ascendance_effects(user).plancher_bonus


def starting_shields(user, *, today: date, season: Season | None = None) -> int:
    """Le stock de boucliers de départ, toutes sources réunies.

    **Cette fonction manquait**, et son absence rendait inertes trois mécaniques
    qui s'affichaient pourtant à l'écran : le bouclier de rang du §4.4, la
    relique « Cœur increvable » du §12.8, et le modificateur « Discipline » du
    §12.5. Les trois étaient calculés, montrés, et jamais passés à l'évaluation
    du streak — un bonus qu'on voit sans le recevoir est pire que pas de bonus,
    parce qu'il fait douter de tout le reste.

    Le modificateur **remplace** au lieu de s'ajouter : « Discipline » donne
    trois boucliers au départ *et* interdit les jours off, c'est un échange, pas
    un cumul. Le plafond du §4.2 s'applique en dernier, à tout le monde.
    """
    effets = modifier_rules.resolve(season.modifier_key if season else "")
    if effets.starting_shields is not None:
        depart = effets.starting_shields
    else:
        depart = (
            streak_rules.DEFAULT_SHIELDS
            + rank_state(user, today=today)["extra_shields"]
            + progression.relic_bonuses(user).extra_shields
        )
    return min(depart, streak_rules.MAX_SHIELDS)


def days_off_allowed(user, *, today: date, season: Season | None = None) -> int:
    """Combien de jours off par semaine, toutes sources réunies (§11.5).

    Même défaut que pour les boucliers : le jour off de rang et la relique
    « Souffle du retour » étaient calculés et jamais appliqués. Ici encore le
    modificateur remplace — « Discipline » descend à zéro, et il n'y a pas de
    relique qui puisse le remonter, sinon le modificateur ne voudrait rien dire.
    """
    from django.conf import settings

    effets = modifier_rules.resolve(season.modifier_key if season else "")
    if effets.days_off_allowed is not None:
        return effets.days_off_allowed

    return (
        settings.COACH["MAX_DAYS_OFF_PER_WEEK"]
        + rank_state(user, today=today)["extra_days_off"]
        + progression.relic_bonuses(user).extra_days_off
    )


def streak_state(user, track: Track, *, today: date) -> streak_rules.StreakState:
    """État du streak, évalué côté serveur à chaque lecture.

    La journée en cours est exclue : tant qu'elle n'est pas finie, elle n'est
    pas ratée.
    """
    history = resolve_days(user, track, until=today - timedelta(days=1))
    return streak_rules.evaluate(
        history,
        floor_minutes=floor_minutes(user, today=today),
        starting_shields=starting_shields(
            user, today=today, season=current_season(user, today=today)
        ),
    )


# --------------------------------------------------------------------------
# Saison
# --------------------------------------------------------------------------

def _position_dans_la_voie(user, season: Season) -> int:
    """Combien de saisons de cette voie ont précédé celle-ci."""
    return Season.objects.filter(
        user=user, voie=season.voie or season_rules.VOIE_CIMES, index__lt=season.index
    ).count()


def prochaine_voie(user) -> tuple[str, int]:
    """La voie de la prochaine saison, et la position qu'elle y occupe (§12.2).

    La voie descend du **résultat de la dernière saison close** : tenue, on
    monte ; ratée, on descend aux braises. La position est le nombre de saisons
    déjà passées sur cette voie-là — chacune avance à son rythme, et c'est ce
    qui fait qu'une année en dents de scie raconte une suite au lieu d'un
    tirage.

    La saison d'essai est exclue des deux comptes : elle ne raconte rien et ne
    doit pas décider de ce qui vient (même règle qu'au boss).
    """
    closes = [
        s
        for s in Season.objects.filter(user=user, status=Season.CLOSED).order_by("index")
        if not season_rules.est_essai(s.index)
    ]
    derniere = closes[-1] if closes else None
    voie = season_rules.voie_apres(derniere.reussie if derniere else None)
    position = sum(1 for s in closes if s.voie == voie)
    return voie, position


def puissance_de_saison(user, season: Season) -> int:
    """Ce que la saison précédente pèse, pour dimensionner le boss suivant.

    **Les dégâts réellement infligés, pas les minutes seules** (corrigé le
    20 août 2026). Le §12.4 dimensionne le boss sur « la performance de la
    saison précédente × 1,05 », et cette performance était lue comme la somme
    des minutes. Or les dégâts viennent aussi des étapes de roadmap — soixante
    points chacune — et des engagements tenus. Un boss de 1800 abattu avec 600
    minutes de session produisait donc un boss suivant à **630 points**, soit
    dix heures là où le précédent en demandait trente. Et le suivant encore
    moins : la courbe s'effondrait d'une saison à l'autre, exactement à
    l'inverse de ce que le ×1,05 promet.

    Les dégâts sont plafonnés à la vie du boss : le dernier coup dépasse presque
    toujours, et compter le débordement ferait monter la barre d'un hasard.
    """
    minutes = (
        Session.objects.filter(user=user, season=season, status=Session.DONE).aggregate(
            total=Sum("actual_minutes")
        )["total"]
        or 0
    )
    boss = getattr(season, "boss", None)
    degats = min(boss.damage_taken, boss.max_hp) if boss else 0
    return max(minutes, degats)


def current_season(user, *, today: date) -> Season | None:
    return (
        Season.objects.filter(user=user, status=Season.RUNNING, starts_on__lte=today)
        .order_by("-index")
        .first()
    )


@transaction.atomic
def open_season(
    user,
    *,
    starts_on: date,
    stake: int = 0,
    modifier_key: str = "",
    phantom_choice: str = "",
    contract_sessions_per_week: int = 0,
    essai: bool = False,
    ends_on: date | None = None,
) -> Season:
    """Ouvre une saison. ``modifier_key`` et ``phantom_choice`` viennent des
    choix faits à l'écran d'ouverture (§12.5, §12.7) ; vides, le plan décide.

    ``essai`` ouvre une **saison d'essai** : index 0, mise à zéro, et exclue de
    toute comparaison ultérieure. Elle sert aux premiers jours, ceux où l'on
    règle ses créneaux et où l'on rate une soirée pour une mauvaise raison.
    Ces jours-là doivent exister — le travail fait y compte, l'XP est gardée —
    mais ils ne doivent **rien fixer** : le boss de la saison suivante se
    dimensionne sur le score précédent, et le fantôme se choisit parmi les
    saisons passées. Une période d'apprentissage rangée parmi les vraies
    resterait un adversaire trop faible pour toujours.

    ``ends_on`` raccourcit la saison. Réservé à l'essai : une vraie saison dure
    28 jours et cette durée est une règle (§12.1), pas un réglage.

    Les deux sont pris **avant** de créer le boss et la mise, parce que le
    modificateur les dimensionne tous les deux. Les appliquer après coup
    obligerait à défaire ce que le plan a calculé, et c'est le genre de calcul
    inverse qui finit par diverger.
    """
    previous = Season.objects.filter(user=user).order_by("-index").first()
    index = season_rules.ESSAI_INDEX if essai else ((previous.index + 1) if previous else 1)
    previous_score = None
    # Une saison d'essai ne dimensionne aucun boss. Sinon les quelques jours
    # passés à comprendre le système fixeraient la barre de la première vraie
    # saison, et la fixeraient trop bas — pour toujours, puisque chaque saison
    # se compare à la précédente.
    if previous and season_rules.est_essai(previous.index):
        previous = None
    if previous:
        previous_score = puissance_de_saison(user, previous) or None

    # Le contrat, s'il est signé, dimensionne le boss de la première saison :
    # sans score précédent, la seule estimation honnête du volume à venir est
    # celle que quelqu'un vient d'annoncer lui-même.
    contrat = 0
    if contract_sessions_per_week:
        verdict = contract_rules.verifier(contract_sessions_per_week)
        if not verdict.ok:
            raise ValueError(verdict.raison)
        contrat = contract_sessions_per_week

    voie, position = prochaine_voie(user)
    plan = season_rules.plan_season(
        index,
        starts_on,
        previous_score=previous_score,
        contract_sessions_per_week=contrat or 3,
        identite=season_rules.pick_identity(index, voie=voie, position=position),
    )
    retenu = modifier_key or plan.modifier_key
    effets = modifier_rules.resolve(retenu)

    projets = list(
        Project.objects.filter(user=user, status=Project.ACTIVE)
        .exclude(slot=None)
        .values_list("name", flat=True)
    )

    season = Season.objects.create(
        user=user,
        index=plan.index,
        key=plan.key,
        name=plan.name,
        accent=plan.accent,
        baseline=plan.baseline,
        # La voie est gravée avec la saison : elle sert à savoir où reprendre
        # cette ligne-là quand on y revient, deux saisons plus tard.
        voie=voie,
        modifier_key=retenu,
        starts_on=plan.starts_on,
        ends_on=ends_on if (essai and ends_on) else plan.ends_on,
        # « Siège » double la mise et gonfle le boss (§12.5). Appliqué ici, à
        # l'ouverture, et jamais recalculé ensuite : une saison dont l'enjeu
        # bougerait en cours de route ne serait plus un engagement.
        # Rien à engager sur une saison qui ne compte pas : une mise sur un
        # essai serait une perte possible sans gain possible.
        stake_shards=0 if essai else stake * effets.stake_multiplier,
        contract_sessions_per_week=contrat,
        contract_projects=projets if contrat else [],
        contract_signed_at=timezone.now() if contrat else None,
        **({"phantom_choice": phantom_choice} if phantom_choice else {}),
    )
    # Le boss est dimensionné pour 28 jours (§12.4). Sur une saison raccourcie,
    # il doit descendre d'autant : un boss de quatre semaines posé sur onze
    # jours est imbattable, et un adversaire imbattable dès le premier jour
    # n'apprend rien à personne — c'est exactement ce qu'une saison d'essai doit
    # éviter.
    jours = (season.ends_on - season.starts_on).days + 1
    echelle = min(1.0, jours / season_rules.SEASON_DAYS)
    SeasonBoss.objects.create(
        season=season,
        key=plan.boss_key,
        name=plan.boss_name,
        max_hp=round(plan.boss_hp * effets.boss_hp_multiplier * echelle),
    )
    return season


def season_contract(user, season: Season | None) -> dict | None:
    """Le contrat signé et où il en est. ``None`` si la saison n'a rien signé.

    L'avancement se **recalcule** depuis les sessions closes, comme tout le
    reste (§10) : un contrat dont le compteur divergerait serait cru sur parole,
    et c'est précisément ce qu'un contrat ne doit jamais demander.
    """
    if season is None or not season.signed:
        return None

    semaines = max(1, ((season.ends_on - season.starts_on).days + 1) // 7)
    contrat = contract_rules.Contrat(
        sessions_par_semaine=season.contract_sessions_per_week,
        projets=tuple(season.contract_projects or ()),
        semaines=semaines,
    )
    faites = Session.objects.filter(
        user=user, season=season, status=Session.DONE
    ).count()

    return {
        "sessions_per_week": contrat.sessions_par_semaine,
        "projects": list(contrat.projets),
        "weeks": contrat.semaines,
        "total": contrat.total,
        "done": faites,
        "signed_on": season.contract_signed_at.date().isoformat(),
        "terms": list(contrat.lignes),
        "line": contract_rules.bilan(signe=contrat.total, fait=faites),
    }


def boss_payload(season: Season | None, *, today: date | None = None) -> dict | None:
    """L'état du boss, plus sa mise en scène : phase courante et dernier round.

    Les deux sont calculés ici et pas côté client pour la raison habituelle : un
    seuil recopié dans le front finit par diverger du seuil réel, et un boss qui
    change de nom un cran trop tôt ne se rattrape plus.
    """
    if not season or not hasattr(season, "boss"):
        return None
    boss = season.boss
    phase = bossphase_rules.phase_for(boss.key, boss.name, boss.ratio)
    round_final = (
        season_rules.final_round(
            days_left=season.days_left(today),
            current_hp=boss.current_hp,
            is_dead=boss.is_dead,
        )
        if today
        else None
    )
    return {
        "name": boss.name,
        "max_hp": boss.max_hp,
        "current_hp": boss.current_hp,
        "ratio": boss.ratio,
        "is_dead": boss.is_dead,
        "phase": {
            "index": phase.index,
            "name": phase.name,
            "line": phase.line,
            "intensity": phase.intensity,
            "final": phase.final,
            "total": len(bossphase_rules.INTENSITES),
        },
        "final_round": (
            {
                "active": round_final.active,
                "days_left": round_final.days_left,
                "sessions_left": round_final.sessions_left,
                "session_minutes": round_final.session_minutes,
                "reachable": round_final.reachable,
                "line": round_final.line,
            }
            if round_final and round_final.active
            else None
        ),
    }


# --------------------------------------------------------------------------
# Le prix du décrochage (SPEC §14)
# --------------------------------------------------------------------------

def _sanctions(
    state: streak_rules.StreakState, *, validated_today: bool
) -> sanction_rules.Sanctions:
    return sanction_rules.evaluate(
        missed_run=state.missed_run,
        current_streak=state.current,
        broken_once=state.broken_at is not None,
        validated_today=validated_today,
        # La dette se mesure contre le plancher **du jour**, qui monte avec le
        # rang : la comparer à la constante ferait apparaître une dette de 10 min
        # permanente dès le rang B.
        debt_minutes=state.required_minutes - state.floor_minutes,
    )


def sanctions_for(user, *, today: date) -> sanction_rules.Sanctions:
    """Les sanctions actives, calculées seules — pour les gardes d'API.

    ``home_state`` ne passe pas par ici : il tient déjà l'historique et l'état
    de la journée, et relire les deux pour la même réponse ferait diverger deux
    lectures du même fait.
    """
    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    minutes = (
        Session.objects.filter(user=user, coach_day=today, status=Session.DONE).aggregate(
            t=Sum("actual_minutes")
        )["t"]
        or 0
    )
    return _sanctions(
        streak_state(user, atelier, today=today), validated_today=minutes >= DEGRADED_MINUTES
    )


def sync_boss_regen(season: Season | None, history: list[streak_rules.Day]) -> int:
    """Le boss récupère une session moyenne de vie par jour raté (§14, palier 1).

    **Recalculé depuis l'historique, jamais incrémenté au fil de l'eau.** Le
    streak l'est déjà, et deux mécaniques qui lisent la même journée doivent la
    lire de la même façon : un incrément posé par un déclencheur nocturne se
    doublerait au premier rejeu et disparaîtrait au premier cron manqué. Ici,
    rejouer la fonction cent fois donne cent fois le même boss.

    La valeur stockée est la dette brute ; le plafonnement aux dégâts encaissés
    vit dans ``SeasonBoss.current_hp``. C'est ce qui rend correct le cas où l'on
    rate un jour avant d'avoir touché le boss : la dette est notée, et elle se
    prélève dès que le boss a de la vie à rendre.

    Un boss déjà mort ne se relève pas. Sa mort a joué sa séquence et clos la
    saison (§12.4) ; le ressusciter le lendemain matin défairait un événement
    déjà vécu, ce que le §14 range parmi les sanctions rétroactives.
    """
    if season is None:
        return 0
    boss = getattr(season, "boss", None)
    if boss is None or boss.is_dead:
        return 0

    rates = sum(
        1
        for jour in history
        if jour.state is streak_rules.DayState.RATEE
        and season.starts_on <= jour.date <= season.ends_on
    )
    du = rates * season_rules.BOSS_REGEN_ON_MISSED_DAY
    if du != boss.regen:
        boss.regen = du
        boss.save(update_fields=["regen"])
    return min(boss.regen, boss.damage_taken)


def sync_stake_forfeit(user, season: Season | None, state: streak_rules.StreakState) -> int:
    """Chaque streak cassé pendant la saison entame la mise (§14, palier 2).

    C'est le **seul prélèvement irréversible** du produit, et le §12.6 le veut
    ainsi : un enjeu réel, sans conséquence matérielle. Il est donc écrit, pas
    dérivé — le solde d'Éclats a déjà bougé, et une valeur recalculée à chaque
    lecture finirait par prélever deux fois.

    Idempotent par différence : on compare le total dû au total déjà prélevé.
    La transaction n'entoure que l'écriture — l'accueil appelle cette fonction
    toutes les dix secondes, et le cas courant est de n'avoir rien à faire.
    """
    if season is None or not season.stake_shards:
        return 0

    cassures = sum(
        1
        for evenement in state.events
        if evenement.kind == "streak_casse"
        and season.starts_on <= evenement.date <= season.ends_on
    )
    du = sanction_rules.stake_forfeit(season.stake_shards, cassures)
    delta = du - season.stake_forfeited
    if delta <= 0:
        return season.stake_forfeited

    with transaction.atomic():
        Profile.objects.filter(user=user).update(shards=Greatest(F("shards") - delta, Value(0)))
        season.stake_forfeited = du
        season.save(update_fields=["stake_forfeited"])
    return du


def sanction_state(
    state: streak_rules.StreakState,
    *,
    validated_today: bool,
    open_slots: int,
    boss_regen_minutes: int,
    shards_forfeited: int,
) -> dict:
    """Ce que l'accueil affiche du §14. Le client n'en déduit rien de plus.

    Les libellés sont construits ici et pas côté client, pour la même raison
    que partout ailleurs : un texte de sanction réécrit dans un composant est
    un texte que le test du ton ne surveille plus.
    """
    sanctions = _sanctions(state, validated_today=validated_today)
    geles = max(0, open_slots - slot_rules.BASE_SLOTS) if sanctions.slots_frozen else 0

    return {
        "level": sanctions.level,
        "active": sanctions.active,
        "showcase_locked": sanctions.showcase_locked,
        "relax_revoked": sanctions.relax_revoked,
        "slots_frozen": sanctions.slots_frozen,
        "frozen_slots": geles,
        "early_block": sanctions.early_block,
        "title_reprieve": sanctions.title_reprieve,
        "comeback": sanctions.comeback,
        "season_exit_offered": sanctions.season_exit_offered,
        "debt_minutes": sanctions.debt_minutes,
        "day_validated": sanctions.day_validated,
        "boss_regen_minutes": boss_regen_minutes,
        "shards_forfeited": shards_forfeited,
        "lines": sanction_rules.lines(
            sanctions,
            boss_regen_minutes=boss_regen_minutes,
            shards_forfeited=shards_forfeited,
            frozen_slots=geles,
        ),
    }


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

@transaction.atomic
def start_session(
    user,
    project: Project,
    *,
    planned_minutes: int,
    now: datetime | None = None,
    energy_level: int | None = None,
    client_uuid=None,
    verified: bool = True,
) -> Session:
    now = now or timezone.now()
    profile = user.profile
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    running = Session.objects.filter(user=user, status=Session.RUNNING).first()
    if running:
        raise ValueError("Une session tourne déjà.")

    rank = Session.objects.filter(user=user, coach_day=today, status=Session.DONE).count() + 1
    mode = Session.DEGRADED if planned_minutes <= DEGRADED_MINUTES else Session.NORMAL

    # L'étape courante commence maintenant, si elle n'avait pas déjà commencé.
    # C'est le seul moment où le système sait qu'on travaille dessus, et le
    # §13.5 en a besoin pour repérer une étape figée depuis trois semaines.
    etape = project.current_step
    if etape and etape.doing_since is None:
        RoadmapStep.objects.filter(pk=etape.pk).update(doing_since=now)

    # Le plan est figé ici, sur la durée annoncée. Une séance prolongée déborde
    # sur les étapes suivantes du plan et pas au-delà : le temps en trop
    # profite au travail prévu, il n'ouvre pas une étape qu'on n'a pas vue.
    plan = creneau_rules.plan_pour(planned_minutes, list(project.steps.all()))

    return Session.objects.create(
        user=user,
        project=project,
        season=current_season(user, today=today),
        coach_day=today,
        started_at=now,
        planned_minutes=planned_minutes,
        mode=mode,
        rank_in_day=rank,
        client_uuid=client_uuid,
        verification=Session.SERVER if verified else Session.UNVERIFIED,
        plan=[
            {"step_id": p.etape.id, "minutes": p.minutes, "reste_avant": p.reste_avant}
            for p in plan.portions
        ],
    )


def extend_session(
    session: Session, *, minutes: int = EXTENSION_MINUTES, now: datetime | None = None
) -> dict:
    """Prolonge une séance en cours. L'objectif monte, le minuteur repart.

    Le glossaire promettait ce bouton depuis le début — « une fois lancé, un
    bouton te propose de prolonger de 15 minutes » — et il n'existait nulle
    part. Il compte maintenant que le dépassement est payé : sans lui, une
    séance qui déborde n'a plus de terme du tout, et l'anneau ne montre plus
    rien une fois le compte à rebours à zéro.

    Prolonger **rehausse la promesse** au lieu de l'effacer. C'est la différence
    avec le simple fait de continuer à travailler : on redit une durée, et la
    clôture dira encore si elle a été tenue.
    """
    if session.status != Session.RUNNING:
        raise ValueError("Cette séance n'est plus en cours.")

    minutes = max(1, int(minutes))
    now = now or timezone.now()
    ecoulees = int((now - session.started_at).total_seconds() // 60)

    # L'objectif repart de **maintenant** quand il est déjà dépassé. Ajouter
    # quinze minutes à un objectif de 25 franchi depuis une demi-heure rendrait
    # un anneau encore à zéro : le bouton n'aurait rien fait de visible, ce qui
    # est la pire réponse possible à un clic.
    base = max(session.planned_minutes, ecoulees)
    session.planned_minutes = min(MAX_SESSION_MINUTES, base + minutes)
    session.extensions += 1
    session.save(update_fields=["planned_minutes", "extensions"])

    return {
        "id": session.id,
        "planned_minutes": session.planned_minutes,
        "extensions": session.extensions,
        "elapsed_minutes": max(0, ecoulees),
    }


@transaction.atomic
def _crediter_le_plan(session: Session) -> None:
    """Reporte les minutes travaillées sur les étapes prévues au démarrage.

    Ne clôt rien et ne change aucun état : seul le compteur ``minutes_done``
    bouge. Une session antérieure au plan — il n'y en a plus, mais la base en
    garde — n'a pas de plan et ne crédite donc rien, ce qui est le bon repli.
    """
    portions = session.plan or []
    if not portions:
        return

    etapes = {
        e.id: e
        for e in RoadmapStep.objects.filter(
            id__in=[p.get("step_id") for p in portions if p.get("step_id")]
        )
    }

    restant = session.actual_minutes
    for portion in portions:
        if restant <= 0:
            break
        etape = etapes.get(portion.get("step_id"))
        if etape is None:
            continue
        part = min(int(portion.get("minutes") or 0), restant)
        if part <= 0:
            continue
        RoadmapStep.objects.filter(pk=etape.pk).update(
            minutes_done=F("minutes_done") + part
        )
        restant -= part


def end_session(
    session: Session,
    *,
    now: datetime | None = None,
    note: str = "",
    next_action: str = "",
    difficulty: int | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Clôture une session : minutes réelles, XP, dégâts au boss, hauts faits.

    ``difficulty`` est facultative et ne change **aucun** calcul : ni XP, ni
    dégâts, ni streak. Elle n'alimente qu'un constat — trois sessions d'affilée
    trop faciles disent qu'on a cessé d'apprendre. La faire entrer dans le
    barème donnerait une raison de mentir dessus, et l'information deviendrait
    inutilisable le jour où elle compte.
    """
    now = now or timezone.now()
    if difficulty in (capacite_rules.TROP_FACILE, capacite_rules.JUSTE, capacite_rules.TROP_DUR):
        session.difficulty = difficulty
    profile = session.user.profile

    # Les minutes **réellement écoulées**, et non l'objectif annoncé. Jusqu'au
    # 19 août 2026 elles étaient plafonnées à ``planned_minutes`` : travailler
    # quarante minutes sur un minuteur de vingt-cinq en perdait quinze, sans
    # que rien ne le dise. C'était le seul endroit du produit où du travail réel
    # disparaissait, et le §17 l'interdit dans les deux sens — on ne paie pas ce
    # qui n'a pas eu lieu, on ne raye pas ce qui a eu lieu.
    #
    # Le minuteur ne perd rien pour autant : il reste l'**objectif** de la
    # séance, celui qu'on annonce en démarrant, celui que le §8.7 utilise pour
    # repérer un fantôme, et celui que la clôture reprend en disant s'il a été
    # tenu. Une session se clôture donc à tout moment — avant le terme, après,
    # bien après — et compte ce qu'elle a duré.
    elapsed = int((now - session.started_at).total_seconds() // 60)
    session.actual_minutes = max(0, min(elapsed, MAX_SESSION_MINUTES))
    session.ended_at = now

    # Sous le plancher dégradé, il ne s'est rien passé : la session est
    # abandonnée, pas récompensée. Sinon démarrer puis arrêter aussitôt
    # rapporterait les bonus de première session — de l'XP sans travail réel,
    # ce que le SPEC §17 interdit explicitement.
    if session.actual_minutes < DEGRADED_MINUTES:
        session.status = Session.ABANDONED
        session.xp_awarded = 0
        session.xp_breakdown = {}
        session.save()
        return {
            "session_id": session.id,
            "aborted": True,
            "minutes": session.actual_minutes,
            "xp": 0,
            "breakdown": {},
            "boss_damage": 0,
            "achievements": [],
            "detail": f"Moins de {DEGRADED_MINUTES} minutes : la session ne compte pas.",
        }

    session.status = Session.DONE

    # Le temps réellement passé est crédité sur les étapes que la soirée devait
    # couvrir, dans l'ordre. C'est ce qui rend le remplissage partiel
    # utilisable : une étape de cinquante minutes entamée sur un créneau de
    # vingt-cinq reprend le lendemain là où elle s'est arrêtée, au lieu d'être à
    # refaire en entier.
    #
    # Rien n'est jamais **clos** ici. Le §6 est net : le critère de sortie
    # décide qu'une étape est finie, pas le chronomètre. Un compteur au plafond
    # dit « le temps prévu est écoulé », ce qui n'est pas la même chose que
    # « c'est fait » — et la différence est exactement ce qui distingue une
    # roadmap d'un minuteur.
    _crediter_le_plan(session)

    track = session.project.track
    history_before = resolve_days(
        session.user, track, until=session.coach_day - timedelta(days=1)
    )
    state_before = streak_rules.evaluate(history_before)

    week = week_start(session.coach_day)
    days_worked = (
        Session.objects.filter(
            user=session.user, status=Session.DONE, coach_day__gte=week, coach_day__lte=session.coach_day
        )
        .values("coach_day")
        .distinct()
        .count()
    ) or 1

    total_xp_before = current_xp(session.user, exclude_session=session)

    local_hour = session.started_at.astimezone(ZoneInfo(profile.timezone_name)).hour
    is_first = not Session.objects.filter(
        user=session.user, coach_day=session.coach_day, status=Session.DONE
    ).exclude(pk=session.pk).exists()

    # Le jeu du §12 entre ici, et seulement par ces deux valeurs : la chaleur
    # du §12.10 et les reliques du §12.8. Aucune autre mécanique de progression
    # ne touche au calcul — le §17 interdit qu'un cosmétique devienne du pouvoir.
    chaleur = progression.heat(session.user, today=session.coach_day)
    bonus = progression.relic_bonuses(session.user)
    effets = modifier_rules.resolve(session.season.modifier_key if session.season else "")

    breakdown = xp_rules.session_xp(
        minutes=session.actual_minutes,
        rank_in_day=session.rank_in_day,
        is_first_of_day=is_first,
        started_hour=local_hour,
        streak=state_before.current,
        days_worked_this_week=days_worked,
        momentum_multiplier=chaleur["multiplier"],
        ecart_au_creneau=ecart_au_creneau(session),
        punctuality_bonus_ratio=bonus.punctuality_bonus,
        duration_bonus_ratio=bonus.duration_bonus,
        modifier_multiplier=modifier_rules.session_multiplier(
            effets, minutes=session.actual_minutes, started_hour=local_hour
        ),
        full_xp_sessions=effets.full_xp_sessions,
    )
    # Le coup critique se tire **après** le barème et ne touche que l'XP : les
    # minutes et les dégâts au boss restent la mesure du travail, et le §12.7
    # compare des minutes. Gravé dans le détail plutôt que rejoué : une session
    # close deux fois ne retire pas les dés.
    critique = crit_rules.roll(
        xp=breakdown.total, draws_since_crit=_draws_since_crit(session)
    )
    session.xp_awarded = critique.xp_after
    session.xp_breakdown = {
        "base": breakdown.base,
        "first_of_day": breakdown.first_of_day,
        "punctual": breakdown.punctual,
        "streak_multiplier": breakdown.streak_multiplier,
        "momentum_multiplier": breakdown.momentum_multiplier,
        "modifier_multiplier": breakdown.modifier_multiplier,
        "degressivity": breakdown.degressivity,
        "base_total": breakdown.total,
        "crit": critique.hit,
        "crit_multiplier": critique.multiplier,
        "crit_forced": critique.forced,
        "crit_bonus": critique.bonus,
        "total": critique.xp_after,
        "notes": breakdown.notes + ([critique.line] if critique.hit else []),
    }
    session.save()

    if note or next_action:
        JournalEntry.objects.update_or_create(
            session=session, defaults={"raw_note": note, "next_action": next_action}
        )

    piste_corps = session.project.track.kind == Track.CORPS
    damage = round(
        season_rules.damage_of(minutes=session.actual_minutes)
        * (1 + bonus.boss_damage_bonus)
        * (effets.body_damage_multiplier if piste_corps else 1.0)
    )

    # Le boss tombe-t-il **maintenant** ? C'est le franchissement qui se met en
    # scène, pas l'état : sans cette comparaison avant/après, la séquence se
    # rejouerait à chaque session tant que la saison n'est pas close.
    boss_tue = None
    phase_franchie = None
    if session.season and hasattr(session.season, "boss"):
        boss = session.season.boss
        vivant_avant = not boss.is_dead
        ratio_avant = boss.ratio
        boss.damage_taken += damage
        boss.save(update_fields=["damage_taken"])
        boss.refresh_from_db()
        if vivant_avant and boss.is_dead:
            boss_tue = {
                "name": boss.name,
                "max_hp": boss.max_hp,
                "season": session.season.name,
                "days_left": session.season.days_left(session.coach_day),
            }
        # La phase ne se met en scène qu'au franchissement, et jamais en même
        # temps que la mort : deux cérémonies sur le même clic s'annulent.
        phase = bossphase_rules.crossed(
            boss.key, boss.name, before=ratio_avant, after=boss.ratio
        )
        if phase and not boss_tue:
            phase_franchie = {
                "index": phase.index,
                "name": phase.name,
                "line": phase.line,
                "intensity": phase.intensity,
                "final": phase.final,
                "previous_name": bossphase_rules.phase_for(
                    boss.key, boss.name, ratio_avant
                ).name,
            }

    _update_commitment(session)
    _update_quests(session)
    unlocked = achievements.synchroniser(session.user)

    # Les quatre séquences de juice du §7 ont besoin de savoir **ce qui vient
    # de changer**, pas de l'état courant : c'est le franchissement qui se met
    # en scène. Tout ce qui suit est donc un delta, calculé une fois ici.
    niveau_avant = xp_rules.level_for(total_xp_before)
    total_apres = total_xp_before + session.xp_awarded
    niveau_apres = xp_rules.level_for(total_apres)

    cartes = []
    reliques = progression.grant_relics_for(session.user, [a["key"] for a in unlocked])
    for _ in range(max(0, niveau_apres - niveau_avant)):
        cartes.append(progression.draw_card(session.user, reason=loot_rules.MONTEE_DE_NIVEAU))

    # La carte de séance longue (§12.6 étendu, tranché le 19 août 2026). Elle est
    # **probabiliste** là où celle d'une étape est garantie, et c'est la même
    # règle qu'ailleurs : ce qui est fréquent se tire, ce qui est rare se donne.
    # Une session par soir, garantie, inonderait la collection en un mois.
    des = rng or random.Random()
    if des.random() < loot_rules.chance_de_carte(session.actual_minutes):
        cartes.append(progression.draw_card(session.user, reason=loot_rules.SESSION_LONGUE))

    return {
        "session_id": session.id,
        "minutes": session.actual_minutes,
        # L'objectif annoncé au démarrage, et ce qu'il est devenu. C'est ce qui
        # empêche le minuteur de devenir décoratif maintenant que le dépassement
        # compte : on a annoncé une durée, la clôture dit si elle a été tenue.
        "objectif": session.planned_minutes,
        "objectif_tenu": session.actual_minutes >= session.planned_minutes,
        "depassement": max(0, session.actual_minutes - session.planned_minutes),
        "extensions": session.extensions,
        "xp": session.xp_awarded,
        "breakdown": session.xp_breakdown,
        "crit": (
            {
                "hit": True,
                "multiplier": critique.multiplier,
                "bonus": critique.bonus,
                "forced": critique.forced,
                "label": crit_rules.LABEL,
                "line": critique.line,
            }
            if critique.hit
            else None
        ),
        "boss_damage": damage,
        "achievements": unlocked,
        # -- de quoi jouer les séquences du §7 sans un second aller-retour
        "level_before": niveau_avant,
        "level_after": niveau_apres,
        "levelled_up": niveau_apres > niveau_avant,
        "total_xp": total_apres,
        "progression": xp_rules.progression(total_apres),
        "momentum": chaleur,
        "branch_tier": progression.branch_tier_crossed(session.user, session),
        "boss_killed": boss_tue,
        "boss_phase": phase_franchie,
        "cards": cartes,
        "relics": reliques,
    }


def complete_step(user, step: RoadmapStep, *, today: date) -> dict:
    """Termine une étape de roadmap, et lâche la carte qu'elle vaut.

    **Idempotent.** Une étape déjà terminée ne repaie rien : ni dégâts, ni
    carte. Avant, un second appel — un double-clic, un retour arrière, un
    rejeu de requête — infligeait une heure de dégâts au boss pour du travail
    qui n'avait pas eu lieu, ce que le §17 interdit précisément.

    La carte est **garantie** parce que le déclencheur l'est aussi : terminer
    une étape n'arrive pas trois fois par soirée, et la rareté du déclencheur
    est ce qui autorise la certitude du tirage. C'est l'inverse du loot de
    semaine, fréquent et donc probabiliste.
    """
    if step.state == RoadmapStep.DONE:
        return {
            "id": step.id,
            "state": step.state,
            "boss_damage": 0,
            "card": None,
            "boss_phase": None,
            "achievements": [],
            "relics": [],
            "already_done": True,
        }

    step.state = RoadmapStep.DONE
    step.done_at = timezone.now()
    step.save(update_fields=["state", "done_at"])

    season = current_season(user, today=today)
    damage = 0
    phase_franchie = None
    if season and hasattr(season, "boss"):
        boss = season.boss
        ratio_avant = boss.ratio
        damage = season_rules.damage_of(steps_done=1)
        boss.damage_taken += damage
        boss.save(update_fields=["damage_taken"])
        boss.refresh_from_db()
        phase = bossphase_rules.crossed(
            boss.key, boss.name, before=ratio_avant, after=boss.ratio
        )
        if phase:
            phase_franchie = {
                "index": phase.index,
                "name": phase.name,
                "line": phase.line,
                "intensity": phase.intensity,
                "final": phase.final,
            }

    # Ce qui a été posé sur cette étape incline le tirage vers le haut, sans
    # rien garantir (§12.6). Le déclencheur reste **terminer** — une étape
    # abandonnée à quatre heures ne rend rien — mais une étape qui a coûté cher
    # ne rend plus la même carte qu'une étape expédiée.
    posees = minutes_sur_etape(step)
    carte = progression.draw_card(
        user, reason=loot_rules.ETAPE_TERMINEE, faveur=loot_rules.faveur_pour(posees)
    )
    obtenus = achievements.synchroniser(user)
    reliques = progression.grant_relics_for(user, [a["key"] for a in obtenus])

    return {
        "id": step.id,
        "state": step.state,
        "boss_damage": damage,
        "card": carte,
        "boss_phase": phase_franchie,
        "achievements": obtenus,
        "relics": reliques,
        "minutes_posees": posees,
        "already_done": False,
    }


def creneau_du_jour(project: Project, *, today: date, now: datetime, tz: str) -> dict | None:
    """Le rendez-vous fixe de ce projet aujourd'hui, situé dans le temps.

    Partagé par la proposition déterministe et par le briefing du §5.1 : quand
    le modèle choisit un autre projet que le repli, c'est **son** créneau qu'il
    faut montrer, pas celui recopié du repli. Une heure juste attachée au mauvais
    projet est pire qu'une heure absente.
    """
    slot = (
        TimeSlot.objects.filter(project=project, active=True, weekday=today.weekday())
        .order_by("start_time")
        .first()
    )
    if slot is None:
        return None

    porteur = {
        "creneau": {
            "heure": slot.start_time.strftime("%Hh%M"),
            "minutes": slot.duration_minutes,
            "tolerance": xp_rules.TOLERANCE_MINUTES,
        }
    }
    _situer_le_creneau(porteur, today=today, now=now, tz=tz)
    return porteur["creneau"]


def _situer_le_creneau(proposition: dict | None, *, today: date, now: datetime, tz: str) -> None:
    """Ajoute à la proposition où l'on en est de son rendez-vous.

    Trois états, et c'est tout ce dont l'écran a besoin pour le dire d'une
    phrase : à venir, maintenant, passé. Calculé côté serveur parce que la
    journée du coach bascule à 4h — un client qui comparerait l'heure du créneau
    à ``new Date()`` se tromperait toutes les nuits entre minuit et 4h, en
    annonçant « dans 20 heures » un créneau qui vient d'être manqué.
    """
    if not proposition or not proposition.get("creneau"):
        return

    creneau = proposition["creneau"]
    zone = ZoneInfo(tz)
    heure, minute = (int(part) for part in creneau["heure"].replace("h", ":").split(":"))
    rendez_vous = datetime.combine(today, time(heure, minute), tzinfo=zone)
    ecart = int((now.astimezone(zone) - rendez_vous).total_seconds() // 60)

    creneau["ecart_minutes"] = ecart
    if abs(ecart) <= creneau["tolerance"]:
        creneau["statut"] = "maintenant"
    elif ecart < 0:
        creneau["statut"] = "a_venir"
    else:
        creneau["statut"] = "passe"


def ecart_au_creneau(session: Session) -> int | None:
    """Minutes entre le démarrage et le rendez-vous le plus proche du jour.

    ``None`` s'il n'y a aucun créneau déclaré ce jour-là sur ce projet : il n'y
    avait alors rien à tenir, et le barème n'a rien à primer.

    Lu en **heure locale**, comme tout ce qui touche à une horloge dans ce
    produit : un créneau est une heure de la vie de quelqu'un, pas un instant
    UTC. Et rapporté à la **journée du coach**, ce qui donne le bon résultat
    dans le seul cas tordu : une séance lancée à 00h20 appartient à la journée
    de la veille, son créneau de 20h30 est donc à quatre heures de là, et elle
    n'est pas ponctuelle — ce qui est exactement ce qu'on veut dire.
    """
    profile = session.user.profile
    creneaux = TimeSlot.objects.filter(
        project=session.project, active=True, weekday=session.coach_day.weekday()
    )
    if not creneaux:
        return None

    zone = ZoneInfo(profile.timezone_name)
    debut = session.started_at.astimezone(zone)
    ecarts = [
        abs((debut - datetime.combine(session.coach_day, c.start_time, tzinfo=zone)).total_seconds())
        // 60
        for c in creneaux
    ]
    return int(min(ecarts))


def minutes_sur_etape(step: RoadmapStep) -> int:
    """Les minutes travaillées sur le projet depuis que l'étape est commencée.

    C'est une **approximation assumée** : aucune session ne déclare l'étape sur
    laquelle elle porte, et lui demander de le faire ajouterait un champ à la
    clôture — le seul moment du produit où l'on ne peut rien demander de plus
    sans faire renoncer à clôturer. Le repère existant est ``doing_since``,
    posé au premier démarrage sur l'étape courante, et il est juste dans le cas
    normal : on travaille l'étape en cours.

    Sans ``doing_since``, la réponse est zéro et non une estimation. Une étape
    cochée sans avoir jamais été commencée n'a rien coûté ; l'inventer
    reviendrait à payer une faveur pour du travail qu'on n'a pas vu.
    """
    if not step.doing_since:
        return 0
    return (
        Session.objects.filter(
            user=step.project.user,
            project=step.project,
            status=Session.DONE,
            started_at__gte=step.doing_since,
        ).aggregate(total=Sum("actual_minutes"))["total"]
        or 0
    )


def _draws_since_crit(session: Session) -> int:
    """Combien de sessions payées depuis le dernier critique.

    Recalculé depuis les sessions closes, jamais stocké : c'est la même règle
    que la pitié du loot (§12.6), et pour la même raison — un compteur qui
    dérive dérègle la pitié.

    Les sessions à zéro XP sont exclues des deux côtés : elles n'ont pas tiré,
    donc elles ne rapprochent pas du tirage garanti.
    """
    payees = (
        Session.objects.filter(user=session.user, status=Session.DONE, xp_awarded__gt=0)
        .exclude(pk=session.pk)
        .order_by("-coach_day", "-id")
        .values_list("xp_breakdown", flat=True)[: crit_rules.PITY + 1]
    )
    for rang, detail in enumerate(payees):
        if (detail or {}).get("crit"):
            return rang
    return len(payees)


def _update_commitment(session: Session) -> None:
    week = week_start(session.coach_day)
    commitment, _ = Commitment.objects.get_or_create(
        project=session.project,
        week_start=week,
        defaults={"planned_sessions": session.project.weekly_commitment},
    )
    commitment.done_sessions = Session.objects.filter(
        project=session.project, status=Session.DONE, coach_day__gte=week, coach_day__lt=week + timedelta(days=7)
    ).count()
    commitment.save(update_fields=["done_sessions"])


def _update_quests(session: Session) -> None:
    for quest in Quest.objects.filter(user=session.user, date=session.coach_day, done_at__isnull=True):
        quest.progress += 1
        if quest.done:
            quest.done_at = timezone.now()
        quest.save(update_fields=["progress", "done_at"])


# --------------------------------------------------------------------------
# La piste Corps (SPEC §11.4)
# --------------------------------------------------------------------------

def corps_track(user) -> Track:
    piste, _ = Track.objects.get_or_create(user=user, kind=Track.CORPS)
    return piste


def corps_objectif(user) -> int:
    """L'objectif hebdomadaire de la piste, en séances.

    Somme des engagements des projets Corps actifs, plafonnée. Le §11.4 donne
    deux séances par défaut ; deux activités qui en visent une chacune font
    donc bien deux, et il n'y a pas de second réglage à tenir en cohérence avec
    le premier.
    """
    engagements = list(
        Project.objects.filter(
            user=user, status=Project.ACTIVE, track__kind=Track.CORPS
        ).values_list("weekly_commitment", flat=True)
    )
    if not engagements:
        return corps_rules.OBJECTIF_PAR_DEFAUT
    return min(sum(engagements), corps_rules.OBJECTIF_MAX)


def corps_state(user, *, today: date, semaines: int = 8) -> corps_rules.CorpsState:
    """L'état de la piste Corps : semaine en cours, streak de semaines tenues.

    Les séances sous le plancher du §11.4 ne comptent pas. Elles sont
    enregistrées — le travail a eu lieu — mais une séance de dix minutes n'est
    pas une séance, et l'objectif hebdomadaire perdrait tout son sens si elle
    l'était.
    """
    objectif = corps_objectif(user)
    lundi = week_start(today)
    debut = lundi - timedelta(days=7 * semaines)

    par_semaine: dict[date, int] = {}
    for jour in Session.objects.filter(
        user=user,
        status=Session.DONE,
        project__track__kind=Track.CORPS,
        coach_day__gte=debut,
        coach_day__lte=today,
        actual_minutes__gte=corps_rules.DEGRADE,
    ).values_list("coach_day", flat=True):
        par_semaine[week_start(jour)] = par_semaine.get(week_start(jour), 0) + 1

    passees = [
        corps_rules.Semaine(
            lundi=debut + timedelta(days=7 * i),
            seances=par_semaine.get(debut + timedelta(days=7 * i), 0),
            objectif=objectif,
        )
        for i in range(semaines)
    ]
    en_cours = corps_rules.Semaine(
        lundi=lundi, seances=par_semaine.get(lundi, 0), objectif=objectif
    )
    return corps_rules.evaluate(passees, en_cours=en_cours)


def corps_panel(user, *, today: date) -> dict | None:
    """Ce que l'accueil affiche de la piste Corps.

    ``None`` quand aucun projet Corps n'existe : afficher une piste vide à
    côté de la décision du soir ajouterait un panneau qui ne demande rien, et
    le §11.1 n'en veut pas.
    """
    projets = list(
        Project.objects.filter(user=user, status=Project.ACTIVE, track__kind=Track.CORPS)
    )
    if not projets:
        return None

    etat = corps_state(user, today=today)
    jours_restants = 7 - today.weekday()

    return {
        "objectif": etat.objectif,
        "faites": etat.faites,
        "restantes": etat.restantes,
        "tenue": etat.tenue,
        "ratio": etat.semaine_en_cours.ratio if etat.semaine_en_cours else 0.0,
        "streak": etat.current,
        "best": etat.best,
        "semaines_tenues": etat.semaines_tenues,
        "message": corps_rules.message_for(etat),
        "plancher": corps_rules.PLANCHER,
        "degrade": corps_rules.DEGRADE,
        "jours_restants": jours_restants,
        "priorite": corps_rules.priorite(etat, jours_restants=jours_restants),
        "projets": [
            {"id": p.id, "name": p.name, "color": p.color, "emblem": p.emblem}
            for p in projets
        ],
    }


# --------------------------------------------------------------------------
# La proposition unique de l'accueil (SPEC §11.1)
# --------------------------------------------------------------------------

# À partir de quelle urgence la piste Corps prend la décision du soir.
#
# 0,6 place la bascule au vendredi quand deux séances manquent : trois jours
# devant, deux à poser, il faut commencer. À 0,75 elle serait tombée le samedi
# — techniquement encore possible, mais une semaine qui ne tient plus qu'à deux
# soirées consécutives est une semaine déjà perdue si l'une des deux saute.
SEUIL_PRIORITE_CORPS = 0.6


def propose(
    user,
    *,
    today: date,
    comeback: bool = False,
    now: datetime | None = None,
    minutes: int | None = None,
) -> dict | None:
    """Choisit la piste, le projet, la durée et la tâche. L'utilisateur n'arbitre pas.

    ``minutes`` est le créneau que la personne vient de choisir à l'écran. Il
    change **la tâche**, pas seulement le chronomètre : on propose l'étape qui
    tient dans ce temps-là. Sans lui, la durée reste le plancher du rang et
    l'étape reste la première ouverte, comme avant.

    **La décision peut désormais être une séance de Corps.** Jusqu'ici elle ne
    regardait que l'Atelier : la piste Corps du §11.4 existait dans la base,
    donnait de l'XP et des dégâts au boss, et n'a jamais été proposée une seule
    fois. Une piste qu'on ne propose pas est une piste qu'on oublie.

    L'arbitrage est une règle, pas un choix rendu à l'utilisateur — le §11.1
    n'autorise qu'une seule décision à l'écran. Le Corps l'emporte quand sa
    semaine est sur le point d'être ratée : deux séances manquantes et deux
    jours restants, et c'est ce soir ou jamais. Le reste du temps l'Atelier
    passe devant, parce qu'il se compte en jours et que chaque soirée y compte.

    Une semaine de Corps déjà tenue ne réclame plus rien : le §17 interdit de
    pousser au-delà d'un objectif, qui est un objectif et pas un plancher.

    ``comeback`` est le palier 3 du §14 : après trois jours d'arrêt, la durée
    proposée tombe à dix minutes quoi qu'annonce le créneau. Proposer une
    séance de cinquante minutes à quelqu'un qui n'a rien fait depuis trois
    jours, c'est proposer de ne pas ouvrir l'app.
    """
    now = now or timezone.now()

    # Le Corps d'abord, s'il est en train de perdre sa semaine. Le comeback du
    # §14 en est exclu : quelqu'un qui revient après trois jours d'arrêt reprend
    # par dix minutes de son travail, pas par une séance de sport de trente.
    if not comeback:
        corps = _propose_corps(user, today=today)
        if corps is not None:
            _situer_le_creneau(corps, today=today, now=now, tz=user.profile.timezone_name)
            return corps

    # Le développement du coach reste accessible en un tap, mais n'est jamais
    # ce que l'app propose d'elle-même : proposer de coder le coach le soir,
    # c'est le piège du SPEC §11.6. Aucune restriction, juste aucune promotion.
    # Un projet en attente déclarée reste à sa place mais ne se propose plus :
    # le soir où il est bloqué par quelqu'un d'autre, le proposer quand même
    # ferait de la proposition unique du §11.1 une proposition impossible.
    en_attente = projects_on_hold(user, day=today)
    projects = [
        p
        for p in Project.objects.filter(
            user=user, status=Project.ACTIVE, track__kind=Track.ATELIER
        )
        .exclude(is_coach_project=True)
        .select_related("track")
        .prefetch_related("steps", "timeslots")
        if p.id not in en_attente
    ]
    if not projects:
        return None

    week = week_start(today)
    done_by_project = {
        row["project"]: row["n"]
        for row in Session.objects.filter(
            user=user, status=Session.DONE, coach_day__gte=week, coach_day__lte=today
        )
        .values("project")
        .annotate(n=Count("id"))
    }
    last_seen = {
        row["project"]: row["last"]
        for row in Session.objects.filter(user=user, status=Session.DONE)
        .values("project")
        .annotate(last=Max("coach_day"))
    }

    def score(project: Project) -> tuple:
        has_slot_today = any(ts.weekday == today.weekday() and ts.active for ts in project.timeslots.all())
        done = done_by_project.get(project.id, 0)
        remaining = max(0, project.weekly_commitment - done)
        last = last_seen.get(project.id)
        staleness = (today - last).days if last else 999
        # Le slot départage les ex æquo : la rotation reste stable d'un soir à
        # l'autre au lieu de dépendre de l'ordre de la base.
        return (has_slot_today, remaining, staleness, -(project.slot or 99))

    chosen = max(projects, key=score)
    plancher = floor_minutes(user, today=today)

    # Le créneau décide de ce qu'on fait. C'est tout le sujet du module
    # ``creneau`` : « Longue · 50 » sur une étape de trois sessions engageait
    # soixante-quinze minutes en en promettant cinquante, et personne ne le
    # voyait avant 22h. Le plan enchaîne plusieurs étapes si elles tiennent, et
    # coupe la dernière si elle déborde.
    duree = DEGRADED_MINUTES if comeback else (minutes or plancher)
    plan = creneau_rules.plan_pour(duree, list(chosen.steps.all()))
    premiere = plan.premiere
    step = premiere.etape if premiere else None
    slot = next(
        (ts for ts in chosen.timeslots.all() if ts.weekday == today.weekday() and ts.active), None
    )
    amorce = (
        JournalEntry.objects.filter(session__project=chosen)
        .exclude(next_action="")
        .order_by("-created_at")
        .values_list("next_action", flat=True)
        .first()
    )

    proposition = {
        "track": Track.ATELIER,
        "project": {
            "id": chosen.id,
            "name": chosen.name,
            "color": chosen.color,
            "emblem": chosen.emblem,
            "completion": chosen.completion,
        },
        # **La durée proposée est le plancher du rang, toujours** — jamais celle
        # déclarée sur le créneau (corrigé le 20 août 2026).
        #
        # Le créneau annonçait parfois cinquante minutes, et le gros bouton du
        # soir affichait « Démarrer · 50 min ». C'est exactement le contraire de
        # ce que le §4.1 cherche : le plancher est ridicule à dessein pour
        # survivre aux mauvais soirs, et un engagement de cinquante minutes
        # affiché à 21h30 un soir de fatigue est une raison de ne pas appuyer.
        #
        # Rien n'est perdu pour autant : depuis que le dépassement compte et que
        # « +15 minutes » existe, une séance **monte** — on part à vingt-cinq et
        # on prolonge tant que ça vient. Décider d'une heure entière avant
        # d'avoir commencé, c'est décider à froid ce qui se décide à chaud.
        # La durée du créneau reste ce qu'elle a toujours été : une intention,
        # que le rappel de créneau et le gardien continuent d'annoncer.
        "minutes": duree,
        # Le plan de la soirée : ce que le créneau couvre, étape par étape.
        # L'écran le montre avant de démarrer — enchaîner deux étapes ou n'en
        # faire que la moitié se décide à froid, pas à 22h quand on découvre
        # qu'on est au milieu de quelque chose.
        "plan": [
            {
                "step_id": p.etape.id,
                "label": p.etape.label,
                "minutes": p.minutes,
                "reste_avant": p.reste_avant,
                "pourcentage": p.pourcentage,
                "entiere": p.entiere,
                "a_clore": p.a_clore,
                "exit_criterion": p.etape.exit_criterion,
            }
            for p in plan.portions
        ],
        # Les deux faits que l'écran annonce en une phrase. Redondants avec le
        # plan, et c'est voulu : un composant qui doit recalculer « est-ce que ça
        # rentre » à partir d'une liste finit par le calculer autrement que le
        # serveur.
        "plan_coupe": plan.coupe,
        "plan_enchaine": plan.enchaine,
        # Le bloc suivant du parcours, quand la roadmap vient de se vider. C'est
        # le seul moment où la question se pose, et c'est aussi le moment où,
        # sans cette ligne, le produit s'arrêtait : quatorze blocs planifiés, la
        # roadmap épuisée en quelques semaines, et rien à l'écran pour en ouvrir
        # un de plus.
        "next_bloc": (
            {"id": suivant.id, "name": suivant.name, "resource": suivant.resource}
            if (suivant := bloc_a_ouvrir(chosen))
            else None
        ),
        # Le critère de sortie voyage avec l'étape jusqu'à la décision du soir.
        # C'est le seul endroit où il compte vraiment : savoir *quand on a fini*
        # avant de commencer est ce qui distingue une session d'une dérive, et
        # une étape ouverte sur le bureau ne le rappelle jamais toute seule.
        "step": (
            {
                "id": step.id,
                "label": step.label,
                "needs_split": step.needs_split,
                "exit_criterion": step.exit_criterion,
                "resource": step.resource,
                "url": step.url,
                "scope": step.scope,
            }
            if step
            else None
        ),
        "amorce": amorce or "",
        # Le rendez-vous du jour, s'il y en a un. Il voyage avec la proposition
        # parce que c'est là qu'il se décide : savoir *avant* de démarrer qu'on
        # est dans son créneau — ou qu'on l'a manqué de vingt minutes — est la
        # seule façon pour la prime de ponctualité d'être autre chose qu'une
        # surprise après coup. Une règle qu'on ne découvre qu'au décompte final
        # ne change aucun comportement.
        "creneau": (
            {
                "heure": slot.start_time.strftime("%Hh%M"),
                "minutes": slot.duration_minutes,
                "tolerance": xp_rules.TOLERANCE_MINUTES,
            }
            if slot
            else None
        ),
        "reason": (
            "Une tâche, dix minutes."
            if comeback
            else _proposal_reason(chosen, slot, done_by_project.get(chosen.id, 0))
        ),
    }
    # Où l'on en est du rendez-vous, ajouté ici plutôt que chez l'appelant :
    # le briefing du §5.1 recopie cette proposition telle quelle, et la ligne
    # disparaissait dès que le modèle répondait — un défaut invisible à la
    # lecture du code, visible seulement à l'écran, une seconde après le
    # chargement.
    _situer_le_creneau(proposition, today=today, now=now, tz=user.profile.timezone_name)
    return proposition


def _propose_corps(user, *, today: date) -> dict | None:
    """La séance de Corps, quand la semaine est sur le point d'être ratée.

    Rend ``None`` la plupart du temps, et c'est voulu : la piste Corps réclame
    la soirée deux fois par semaine, pas tous les soirs. Une piste qui prendrait
    la décision chaque jour ferait de l'Atelier la piste secondaire, ce que le
    §11.4 refuse dans les deux sens — « les deux pistes apparaissent côte à
    côte, jamais fusionnées ».
    """
    panneau = corps_panel(user, today=today)
    if panneau is None or panneau["priorite"] < SEUIL_PRIORITE_CORPS:
        return None

    # Celui qui a le moins servi cette semaine : deux activités qui se
    # partagent l'objectif tournent au lieu que l'une prenne tout.
    semaine = week_start(today)
    faites = {
        row["project"]: row["n"]
        for row in Session.objects.filter(
            user=user,
            status=Session.DONE,
            project__track__kind=Track.CORPS,
            coach_day__gte=semaine,
            coach_day__lte=today,
        )
        .values("project")
        .annotate(n=Count("id"))
    }
    projets = list(
        Project.objects.filter(user=user, status=Project.ACTIVE, track__kind=Track.CORPS)
        .prefetch_related("timeslots")
    )
    if not projets:
        return None

    choisi = min(
        projets,
        key=lambda p: (
            faites.get(p.id, 0),
            not any(ts.weekday == today.weekday() and ts.active for ts in p.timeslots.all()),
            p.slot or 99,
        ),
    )
    creneau = next(
        (ts for ts in choisi.timeslots.all() if ts.weekday == today.weekday() and ts.active),
        None,
    )

    return {
        "track": Track.CORPS,
        "project": {
            "id": choisi.id,
            "name": choisi.name,
            "color": choisi.color,
            "emblem": choisi.emblem,
            "completion": choisi.completion,
        },
        # Le plancher de la piste, jamais la durée du créneau : même raison
        # qu'à l'Atelier — ce qui s'affiche sur le bouton est ce qu'on s'engage
        # à faire *maintenant*, et ça se prolonge.
        "minutes": corps_rules.PLANCHER,
        "step": None,
        "amorce": "",
        # La piste Corps a des créneaux comme l'Atelier, et la même prime les
        # récompense : une séance de sport tenue à l'heure dite est exactement
        # ce que le §11.4 cherche à installer.
        "creneau": (
            {
                "heure": creneau.start_time.strftime("%Hh%M"),
                "minutes": creneau.duration_minutes,
                "tolerance": xp_rules.TOLERANCE_MINUTES,
            }
            if creneau
            else None
        ),
        # L'heure du rendez-vous d'abord quand il y en a un : c'est elle que la
        # ligne d'état sous la raison commente, et sans elle « passé de 46 min »
        # ne se rapporte à rien.
        "reason": (
            f"Créneau du jour, {creneau.start_time.strftime('%Hh%M')}."
            if creneau
            else (
                f"{panneau['restantes']} séance(s) pour tenir la semaine, "
                f"{panneau['jours_restants']} jour(s) devant."
            )
        ),
    }


def _proposal_reason(project: Project, slot, done: int) -> str:
    if slot:
        return f"Créneau du jour, {slot.start_time.strftime('%Hh%M')}."
    remaining = max(0, project.weekly_commitment - done)
    if remaining:
        return f"{remaining} session(s) restante(s) sur ton engagement de la semaine."
    return "Le projet le plus ancien de ta rotation."


# --------------------------------------------------------------------------
# L'état complet de l'accueil
# --------------------------------------------------------------------------

def home_state(user, *, now: datetime | None = None, minutes: int | None = None) -> dict:
    """L'écran d'accueil. ``minutes`` est le créneau choisi, s'il l'a été.

    Il ne sert qu'à la proposition, où il change la tâche autant que le
    chronomètre — voir ``propose`` et ``rules.creneau``.
    """
    now = now or timezone.now()
    profile: Profile = user.profile
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    # L'historique est lu **une fois** ici : le streak et les sanctions du §14
    # en descendent tous les deux, et deux lectures séparées finiraient par
    # afficher un palier qui ne correspond plus au streak affiché à côté.
    history = resolve_days(user, atelier, until=today - timedelta(days=1))
    rang = rank_state(user, today=today)
    state = streak_rules.evaluate(history, floor_minutes=streak_rules.floor_for(rang["code"]))
    season = current_season(user, today=today)

    window = evening_window(today, profile.windows_by_weekday(), profile.timezone_name)
    sessions_today = list(
        Session.objects.filter(user=user, coach_day=today).select_related("project").order_by("started_at")
    )
    minutes_today = sum(s.actual_minutes for s in sessions_today if s.status == Session.DONE)

    total_xp = current_xp(user)
    running = next((s for s in sessions_today if s.status == Session.RUNNING), None)

    # Les deux écritures du §14, posées à la lecture de l'accueil. Comme la
    # clôture de semaine du §12.6, elles sont idempotentes et n'ont donc pas
    # besoin qu'un déclencheur nocturne ait tourné pour être justes — c'est ce
    # qui les rend fiables sur un hébergement qui s'endort.
    regen = sync_boss_regen(season, history)
    forfeited = sync_stake_forfeit(user, season, state)
    sanctions = sanction_state(
        state,
        validated_today=minutes_today >= DEGRADED_MINUTES,
        open_slots=rang["slots"],
        boss_regen_minutes=regen,
        shards_forfeited=forfeited,
    )

    # La bande dessinée s'élargit à ce qui a réellement eu lieu. Depuis que le
    # travail compte à n'importe quelle heure (§4.1), une séance de 10h était
    # dessinée **collée à 18h** : le ratio était borné à la fenêtre, donc la
    # jauge affirmait une chose fausse — et c'est la seule chose qu'une jauge ne
    # doit jamais faire. La fenêtre du soir reste rendue à part : elle garde son
    # rôle, dire quand la soirée se ferme et quand le gardien parlera.
    posees = [s for s in sessions_today if s.status in (Session.DONE, Session.RUNNING)]
    debut_bande = min([window.start, *[s.started_at for s in posees]])
    fin_bande = max([window.end, *[s.ended_at or now for s in posees]])
    span = max(1, int((fin_bande - debut_bande).total_seconds() // 60))

    def _ratio(moment: datetime) -> float:
        minutes = (moment - debut_bande).total_seconds() / 60
        return round(min(1.0, max(0.0, minutes / span)), 4)

    blocks = [
        {
            "project": s.project.name,
            "color": s.project.color,
            "start_ratio": _ratio(s.started_at),
            "end_ratio": _ratio(s.ended_at or now),
            "minutes": s.actual_minutes,
            "running": s.status == Session.RUNNING,
        }
        for s in posees
    ]

    proposition = propose(
        user, today=today, comeback=sanctions["comeback"], now=now, minutes=minutes
    )

    return {
        "day": today.isoformat(),
        "now": now.isoformat(),
        # Les cosmétiques équipés, résolus en valeurs affichables. Ils partaient
        # nulle part : une carte s'équipait et l'écran ne changeait pas d'un
        # pixel (§12.6).
        "cosmetics": progression.cosmetics(user),
        "momentum": progression.heat(user, today=today),
        "skills": progression.skill_tree(user)["branches"],
        "phantom": progression.phantom_panel(user, today=today, now=now),
        "modifier": progression.season_modifier(season) if season else None,
        "validated_today": minutes_today >= DEGRADED_MINUTES,
        "required_minutes": state.required_minutes,
        "minutes_today": minutes_today,
        "streak": {
            "current": state.current,
            "best": state.best,
            "shields": state.shields,
            "to_next_shield": max(0, streak_rules.DAYS_PER_SHIELD - state.consecutive_for_shield),
            "sanction_level": state.sanction_level,
            "message": streak_rules.message_for(state),
        },
        "sanctions": sanctions,
        "progression": {**xp_rules.progression(total_xp), "rank": rang["code"]},
        "rank": rang,
        "season": (
            {
                "index": season.index,
                "key": season.key,   # sélectionne l'emblème dessiné côté client
                "name": season.name,
                # La palette entiere, pas la seule couleur d'accent : `accent2`
                # tient l'atmosphere du fond et `ambiance` nomme le traitement
                # que le client sait dessiner. Derivee de la cle, donc une
                # saison ancienne se repeint quand la trame evolue.
                **season_rules.palette_de(season.key, season.accent),
                "baseline": season.baseline,
                # Où l'on se tient dans la trame (§12.2). Une histoire que seul
                # le code connaît n'est pas une histoire : sans cette ligne, la
                # voie basse ne se distingue de la haute que par la couleur.
                "acte": season_rules.acte_de_voie(
                    season.voie or season_rules.VOIE_CIMES,
                    _position_dans_la_voie(user, season),
                ),
                # La ligne de la semaine (§12.2 etendu). Elle vient du serveur
                # comme tout texte affiche : le §11.10 fait du ton une regle
                # testee, et une phrase ecrite cote client y echapperait.
                "citation": citations.citation_de(season.key, season.day_index(today)),
                "semaine": citations.semaine_de(season.day_index(today)),
                "day_index": season.day_index(today) + 1,
                "days_total": season_rules.SEASON_DAYS,
                "days_left": season.days_left(today),
                "modifier": season.modifier_key,
                "stake": max(0, season.stake_shards - season.stake_forfeited),
                "stake_forfeited": season.stake_forfeited,
                "contract": season_contract(user, season),
                # L'année : douze saisons, et le compte à rebours qui va avec.
                # Sans lui, la douzième arrive sans prévenir, et une ascendance
                # qu'on n'a pas vue venir n'est pas un événement.
                "year": year_rules.annee_de(season.index),
                "rank_in_year": year_rules.rang_dans_l_annee(season.index),
                "seasons_per_year": year_rules.SAISONS_PAR_AN,
                "seasons_left_in_year": year_rules.saisons_restantes(season.index),
                "closes_the_year": year_rules.ferme_l_annee(season.index),
            }
            if season
            else None
        ),
        "boss": boss_payload(season, today=today),
        "evening": {
            # La bande dessinée, puis la fenêtre. Les deux coïncident tant que
            # rien n'a été travaillé en dehors, ce qui est le cas ordinaire.
            "start": debut_bande.isoformat(),
            "end": fin_bande.isoformat(),
            "window_start": window.start.isoformat(),
            "window_end": window.end.isoformat(),
            "widened": debut_bande < window.start or fin_bande > window.end,
            "total_minutes": window.total_minutes,
            "elapsed_ratio": window.ratio(now),
            "blocks": blocks,
        },
        "running_session": (
            {
                "id": running.id,
                "project": running.project.name,
                "color": running.project.color,
                "started_at": running.started_at.isoformat(),
                "planned_minutes": running.planned_minutes,
                "extensions": running.extensions,
            }
            if running
            else None
        ),
        "proposal": proposition,
        "quests": [
            {
                "kind": q.kind,
                "label": q.label,
                "progress": q.progress,
                "target": q.target,
                "done": q.done,
            }
            for q in Quest.objects.filter(user=user, date=today)
        ],
        # Côte à côte, jamais fusionnées en un score unique (§11.4).
        "corps": corps_panel(user, today=today),
        "entretien": routine_panel(user, today=today),
        "gardes": gardes_panel(user, today=today),
        "relax_used": RelaxWindow.objects.filter(user=user, coach_day=today).exists(),
    }


# --------------------------------------------------------------------------
# Création d'un projet depuis un markdown (SPEC §4.5)
# --------------------------------------------------------------------------

def preview_project(markdown: str) -> dict:
    """Ce que l'app a compris du markdown collé, avant toute écriture."""
    parsed = roadmap_import.parse(markdown)
    return {
        "valid": parsed.valid,
        "name": parsed.name,
        "branch": parsed.branch,
        "domain": parsed.domain,
        "domain_label": slot_rules.DOMAIN_LABELS.get(parsed.domain, parsed.domain),
        "verification": parsed.verification,
        "verification_label": verification_rules.LABELS.get(parsed.verification, parsed.verification),
        "repo_path": parsed.repo_path,
        "color": parsed.color,
        "emblem": parsed.emblem,
        "weekly_commitment": parsed.weekly_commitment,
        "objective": parsed.objective,
        "frame": parsed.frame,
        "open_steps": parsed.open_steps,
        "steps": [
            {
                "label": s.label,
                "state": s.state,
                "estimated_sessions": s.estimated_sessions,
                "needs_split": s.needs_split,
                "resource": s.resource,
                "url": s.url,
                "scope": s.scope,
                "load": s.load,
                "exit_criterion": s.exit_criterion,
            }
            for s in parsed.steps
        ],
        # L'aperçu montre tout ce qui sera écrit, y compris ce qui ne se voit
        # pas dans la liste d'étapes. Un aperçu qui cache une partie du document
        # laisse valider une roadmap dont on n'a pas vu la moitié.
        "parcours": [
            {
                "name": b.name,
                "outcome": b.outcome,
                "resource": b.resource,
                "url": b.url,
                "load": b.load,
                "cost": b.cost,
                "optional": b.optional,
                "exit_criterion": b.exit_criterion,
            }
            for b in parsed.parcours
        ],
        "ecartees": [{"name": e.name, "reason": e.reason} for e in parsed.ecartees],
        "warnings": parsed.warnings,
        # Ce que le parseur n'a pas su placer. L'écran s'en sert pour proposer
        # une relecture par le modèle : c'est le seul signal fiable disant que
        # le document contient plus que ce qui vient d'être lu.
        "ignored": parsed.ignorees,
    }


def rank_state(user, *, today: date) -> dict:
    """Le rang de l'utilisateur, calculé sur les engagements tenus (SPEC §4.4).

    Cumulatif et monotone : une mauvaise semaine n'en retire aucune. Le §17
    interdit tout retrait rétroactif de rang.
    """
    # Les semaines où un projet était en attente déclarée en sortent : ne pas
    # pouvoir travailler n'est pas manquer de fiabilité, et le rang mesure la
    # fiabilité. Sans ça, l'inaction d'un tiers faisait tomber le rang.
    attentes = list(
        ProjectHold.objects.filter(project__user=user).select_related("project")
    )
    # Les semaines antérieures à la dernière ascendance sortent du calcul : le
    # rang repart de F et se regravit. Elles ne sont pas supprimées pour autant,
    # et la trace longue continue de les compter.
    engagements = Commitment.objects.filter(
        project__user=user, week_start__lt=week_start(today)
    )
    horizon = rank_horizon(user)
    if horizon is not None:
        engagements = engagements.filter(week_start__gte=horizon)

    semaines = [
        (c.week_start, c.done_sessions >= c.planned_sessions)
        for c in engagements
        if not any(
            a.project_id == c.project_id
            and hold_rules.leve_la_semaine(a.starts_on, a.effective_end, lundi=c.week_start)
            for a in attentes
        )
    ]
    tenues = rank_rules.weeks_kept(semaines)
    code = rank_rules.rank_for(tenues)
    recompenses = rank_rules.rewards_for(code)
    suivant = rank_rules.next_rank(tenues)

    # La voie « Ampleur » ouvre un slot de plus, plafonné par le §4.3. Ce n'est
    # pas un avantage : le rang exige que *tous* les engagements d'une semaine
    # soient tenus, donc un projet de plus est une chance de plus de la rater.
    ouverts = min(
        max(recompenses.slots, slots_graves(user)) + ascendance_effects(user).slots_bonus,
        slot_rules.ABSOLUTE_MAX_SLOTS,
    )

    return {
        "code": code,
        "weeks_kept": tenues,
        "slots": ouverts,
        "extra_shields": recompenses.extra_shields,
        "extra_days_off": recompenses.extra_days_off,
        "next": {"code": suivant[0], "weeks_left": suivant[1]} if suivant else None,
        "next_unlock": rank_rules.unlock_label(code),
    }


# --------------------------------------------------------------------------
# Le projet en attente déclarée (ajout du 17 août 2026)
# --------------------------------------------------------------------------

def projects_on_hold(user, *, day: date) -> set[int]:
    """Les projets en attente à une date donnée."""
    return {
        a.project_id
        for a in ProjectHold.objects.filter(
            project__user=user, starts_on__lte=day, ends_on__gte=day
        )
        if a.covers(day)
    }


def hold_days_between(user, project_id: int, *, since: date, until: date) -> int:
    """Combien de jours d'attente séparent deux dates, pour ce projet.

    Sert à la détection « projet mort » : sans cette soustraction, un projet
    bloqué quatorze jours serait déclaré mort le lendemain de son déblocage,
    c'est-à-dire au seul moment où il redevient vivant.
    """
    return sum(
        hold_rules.jours_couverts(a.starts_on, a.effective_end, entre=since, et=until)
        for a in ProjectHold.objects.filter(project_id=project_id, project__user=user)
    )


def declare_hold(
    user, project: Project, *, starts_on: date, ends_on: date, reason: str, today: date
) -> ProjectHold:
    """Déclare une attente. Lève ``ValueError`` si les règles s'y opposent."""
    verdict = hold_rules.verifier(
        debut=starts_on, fin=ends_on, aujourdhui=today, raison=reason
    )
    if not verdict.ok:
        raise ValueError(verdict.raison)

    if projects_on_hold(user, day=starts_on) & {project.id}:
        raise ValueError("Ce projet est déjà en attente à cette date.")

    return ProjectHold.objects.create(
        project=project, starts_on=starts_on, ends_on=ends_on, reason=reason.strip()
    )


def end_hold(user, project: Project, *, today: date) -> bool:
    """Sort le projet de l'attente, immédiatement.

    Comme pour la veille : une attente dont on ne peut pas sortir est une raison
    de plus de ne pas la déclarer. Rend ``False`` s'il n'y en avait pas.
    """
    attente = (
        ProjectHold.objects.filter(
            project=project, project__user=user, starts_on__lte=today, ends_on__gte=today
        )
        .order_by("-starts_on")
        .first()
    )
    if attente is None or attente.ended_on is not None:
        return False

    attente.ended_on = today
    attente.save(update_fields=["ended_on"])
    return True


def hold_payload(user, project: Project, *, today: date) -> dict | None:
    """L'attente en cours d'un projet, prête à afficher. ``None`` s'il n'y en a pas."""
    attente = (
        ProjectHold.objects.filter(project=project, starts_on__lte=today, ends_on__gte=today)
        .order_by("-starts_on")
        .first()
    )
    if attente is None or not attente.covers(today):
        return None

    return {
        "starts_on": attente.starts_on.isoformat(),
        "ends_on": attente.effective_end.isoformat(),
        "reason": attente.reason,
        "days_left": max(0, (attente.effective_end - today).days),
        "line": hold_rules.message(project.name, attente.effective_end, attente.reason),
    }


def taken_slots(user) -> list[tuple[int, str]]:
    """Les ``(slot, domaine)`` actuellement occupés."""
    return list(
        Project.objects.filter(user=user, status=Project.ACTIVE)
        .exclude(slot=None)
        .values_list("slot", "domain")
    )


def free_slot(user, domain: str = slot_rules.CODE, *, today: date | None = None) -> int | None:
    """Le slot qu'un projet de ce domaine peut prendre, ou rien (SPEC §4.3).

    Trois limites s'appliquent : le nombre de slots ouverts — qui dépend du
    rang, donc des engagements tenus —, deux slots par domaine, et le **gel du
    palier 2** (§14).

    Le gel ne déloge personne : un quatrième projet déjà installé y reste, le
    §4.3 est formel — « les projets ne sont pas supprimés, le slot est gelé
    jusqu'à la reprise ». Ce qui est suspendu, c'est le droit d'en ouvrir un de
    plus pendant qu'on n'arrive plus à tenir ceux qu'on a.
    """
    today = today or timezone.now().date()
    ouverts = rank_state(user, today=today)["slots"]
    if sanctions_for(user, today=today).slots_frozen:
        ouverts = min(ouverts, slot_rules.BASE_SLOTS)
    return slot_rules.assign_slot(taken_slots(user), domain, total_slots=ouverts)


@transaction.atomic
def create_project_from_markdown(user, markdown: str) -> Project:
    """Crée un projet et sa roadmap depuis le markdown produit par un chat.

    Si les trois slots sont pris, le projet est créé **au frigo** plutôt que
    refusé : la limite du §4.3 ne se contourne pas, mais l'idée ne se perd pas
    non plus. L'échange de slot reste un geste du dimanche.
    """
    parsed = roadmap_import.parse(markdown)
    if not parsed.valid:
        raise ValueError("; ".join(parsed.warnings) or "Markdown illisible.")

    track, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    slot = free_slot(user, parsed.domain)

    project = Project.objects.create(
        user=user,
        track=track,
        name=parsed.name,
        status=Project.ACTIVE if slot else Project.FRIDGE,
        slot=slot,
        color=parsed.color,
        emblem=parsed.emblem,
        branch=parsed.branch,
        domain=parsed.domain,
        verification=parsed.verification,
        weekly_commitment=parsed.weekly_commitment,
        objective=parsed.objective,
        frame=parsed.frame,
    )
    if parsed.repo_path:
        # Déclaré à la création : la vérification marche dès la première
        # session, sans réglage supplémentaire.
        ProjectRepo.objects.get_or_create(project=project, path=parsed.repo_path)
    # Le parcours et les écartées ne servent à rien le soir même, et c'est
    # exactement pourquoi ils se perdaient : le parseur les lisait, la création
    # ne les recopiait pas, et l'entretien de projet passait vingt minutes à
    # produire une information que l'écriture en base jetait sans rien dire.
    blocs = [
        ProjectBloc.objects.create(
            project=project,
            order=order,
            name=bloc.name,
            outcome=bloc.outcome,
            resource=bloc.resource,
            url=bloc.url,
            load=bloc.load,
            cost=bloc.cost,
            optional=bloc.optional,
            exit_criterion=bloc.exit_criterion,
        )
        for order, bloc in enumerate(parsed.parcours)
    ]

    # Les étapes initiales sont le détail du **premier** bloc : c'est ce que
    # l'entretien produit, et le lien est ce qui permettra plus tard de savoir
    # quel bloc refermer quand la roadmap se videra.
    premier = blocs[0] if blocs else None

    for order, step in enumerate(parsed.steps):
        RoadmapStep.objects.create(
            project=project,
            bloc=premier,
            order=order,
            label=step.label,
            state=step.state,
            estimated_sessions=step.estimated_sessions,
            done_at=timezone.now() if step.state == RoadmapStep.DONE else None,
            resource=step.resource,
            url=step.url,
            scope=step.scope,
            load=step.load,
            exit_criterion=step.exit_criterion,
        )
    for order, ecartee in enumerate(parsed.ecartees):
        DiscardedResource.objects.create(
            project=project,
            order=order,
            name=ecartee.name,
            reason=ecartee.reason,
        )
    return project


def bloc_a_ouvrir(projet) -> "ProjectBloc | None":
    """Le prochain bloc du parcours, s'il y a lieu d'en ouvrir un.

    Rend ``None`` dans trois cas, tous normaux : le projet n'a pas de parcours
    (une roadmap collée à la main n'en a pas), il reste des étapes ouvertes, ou
    le parcours est terminé. La question n'est posée que lorsque la roadmap est
    vide — c'est le seul moment où le bloc courant est réellement fini.
    """
    if projet.steps.filter(state__in=["todo", "doing"]).exists():
        return None
    return projet.parcours.filter(done_at__isnull=True).order_by("order", "id").first()



@transaction.atomic
def ecrire_les_etapes_du_bloc(project: Project, bloc: ProjectBloc, etapes: list[dict]) -> dict:
    """Referme le bloc précédent, rattache les nouvelles étapes à celui-ci.

    Vit ici, à côté de ``create_project_from_markdown``, parce que les deux
    écrivent des ``RoadmapStep`` à partir des mêmes champs : les séparer les
    aurait fait diverger au premier attribut ajouté, et une étape créée par le
    découpage aurait perdu son périmètre sans que rien ne le signale.

    Les étapes déjà faites ne sont pas touchées. Elles restent dans la roadmap,
    rattachées à leur bloc : c'est l'historique du projet, et le §17 interdit
    d'effacer ce qui a eu lieu.
    """
    maintenant = timezone.now()

    # Les blocs qui précèdent celui-ci sont refermés — y compris ceux qu'on
    # aurait sautés. Un bloc laissé ouvert derrière soi ferait rouvrir un
    # parcours déjà dépassé au prochain passage.
    ProjectBloc.objects.filter(
        project=project, done_at__isnull=True, order__lt=bloc.order
    ).update(done_at=maintenant)

    depart = (project.steps.aggregate(m=Max("order"))["m"] or 0) + 1
    for decalage, etape in enumerate(etapes):
        RoadmapStep.objects.create(
            project=project,
            bloc=bloc,
            order=depart + decalage,
            label=etape["libelle"],
            state=etape.get("etat") or RoadmapStep.TODO,
            estimated_sessions=max(1, min(3, int(etape.get("sessions") or 2))),
            resource=etape.get("ressource", ""),
            url=etape.get("url", ""),
            scope=etape.get("perimetre", ""),
            load=etape.get("charge", ""),
            exit_criterion=etape.get("critere_sortie", ""),
        )

    return {
        "bloc": {"id": bloc.id, "name": bloc.name, "order": bloc.order},
        "created": len(etapes),
        "detail": f"« {bloc.name} » est ouvert : {len(etapes)} étapes à faire.",
    }


# --------------------------------------------------------------------------
# Les preuves de capacité — le troisième axe
# --------------------------------------------------------------------------

@transaction.atomic
def declarer_preuve(user, project: Project, *, critere: str, day: date, bloc=None) -> Preuve:
    """Constate une capacité, et la paie en Éclats.

    Jamais en XP : l'XP mesure un volume par construction (§4.4), et une
    capacité n'est pas un volume. Les Éclats, eux, se dépensent à la Forge —
    donc une preuve ouvre quelque chose, ce qui est le bon signal.

    Le critère est refusé s'il ne dit rien. « J'ai progressé » n'est pas
    constatable par quelqu'un d'autre, et une preuve qu'on s'accorde soi-même
    est de l'auto-évaluation — exactement ce que le §6 refuse partout ailleurs.
    """
    regle = capacite_rules.Preuve(projet=project.name, critere=critere)
    if not regle.valide:
        raise ValueError(
            "Écris ce qui a été constaté, et de façon vérifiable : "
            "« les 100 % de labs Apprentice validés », pas « j'ai progressé »."
        )

    shards = capacite_rules.shards_pour_preuve(
        Preuve.objects.filter(user=user, project=project).count()
    )
    preuve = Preuve.objects.create(
        user=user,
        project=project,
        bloc=bloc,
        critere=critere.strip(),
        obtained_on=day,
        shards_awarded=shards,
    )
    Profile.objects.filter(user=user).update(shards=F("shards") + shards)
    return preuve


def capacite_panel(user) -> dict:
    """Les preuves acquises, et les heures qu'elles ont coûtées.

    Les deux nombres restent côte à côte et ne fusionnent jamais : un score
    unique remonterait en ne faisant que des heures, donc il aurait exactement
    le défaut que cet axe corrige.
    """
    preuves = list(
        Preuve.objects.filter(user=user).select_related("project").order_by("-obtained_on", "-id")
    )
    minutes = (
        Session.objects.filter(user=user, status=Session.DONE).aggregate(t=Sum("actual_minutes"))["t"]
        or 0
    )
    etat = capacite_rules.etat(len(preuves), minutes)
    etat["liste"] = [
        {
            "id": p.id,
            "critere": p.critere,
            "projet": p.project.name,
            "couleur": p.project.color,
            "obtained_on": p.obtained_on.isoformat(),
        }
        for p in preuves[:12]
    ]
    return etat


def palier_de_difficulte(user, *, project: Project | None = None) -> dict | None:
    """Trois sessions d'affilée déclarées trop faciles (§ capacité).

    Le seul constat du système déclenché par une **bonne** nouvelle apparente.
    Il ne retire rien et n'impose rien : monter la barre peut vouloir dire
    changer de ressource, passer au bloc suivant, ou arrêter de refaire ce
    qu'on sait déjà — et le système ne sait pas lequel.
    """
    sessions = Session.objects.filter(user=user, status=Session.DONE, difficulty__isnull=False)
    if project is not None:
        sessions = sessions.filter(project=project)
    difficultes = list(sessions.order_by("-started_at").values_list("difficulty", flat=True)[:5])
    return capacite_rules.palier_trop_facile(difficultes)


# --------------------------------------------------------------------------
# L'agent local (SPEC §8)
# --------------------------------------------------------------------------

def _guardian_consign(user, profile: Profile, *, today: date, now: datetime) -> dict:
    """La consigne que l'agent rejouera si le serveur devient injoignable.

    Le gardien du §11.3 part du serveur, ce qui est le bon endroit — c'est lui
    qui sait si la journée est validée. Mais il a un défaut qui ne se voit
    qu'une fois : le soir où le serveur ne répond pas, il ne part pas, et
    personne ne le sait. Un gardien qui tombe le soir où il tombe n'est pas un
    gardien.

    Ce que l'agent reçoit est **exactement ce que la notification aurait
    affiché sur cette même machine** : l'heure, la tâche de dix minutes, le
    plancher. Aucune classe d'information nouvelle ne descend vers un jeton de
    sonde qui peut fuir (§8) — ni boucliers, ni streak, ni historique.
    """
    window = evening_window(today, profile.windows_by_weekday(), profile.timezone_name)
    declenche = window.end - timedelta(minutes=profile.guardian_minutes_before_end)

    minutes = (
        Session.objects.filter(user=user, coach_day=today, status=Session.DONE).aggregate(
            t=Sum("actual_minutes")
        )["t"]
        or 0
    )
    proposition = propose(user, today=today)

    return {
        "day": today.isoformat(),
        "at": declenche.isoformat(),
        "window_end": window.end.isoformat(),
        "floor_minutes": DEGRADED_MINUTES,
        "validated": minutes >= DEGRADED_MINUTES,
        "project": proposition["project"]["name"] if proposition else "",
        # L'amorce du §11.3, telle quelle. Pas de découpage par le modèle ici :
        # le repli local doit rester calculable hors ligne, et une consigne qui
        # dépendrait d'un appel au modèle serait vide le jour où il manque.
        "task": (proposition or {}).get("amorce", ""),
    }


def agent_state(user, *, now: datetime | None = None) -> dict:
    """Le strict nécessaire à l'agent : que lancer, et quoi afficher.

    Volontairement pauvre. L'agent s'authentifie avec un jeton de sonde, qui
    peut fuir d'une machine ; il ne reçoit donc ni historique, ni gardes, ni
    journal. Le nom du projet suffit à retrouver un profil de lancement dans
    **sa propre** liste blanche — le serveur n'envoie jamais de commande
    (SPEC §8, sécurité non négociable).
    """
    now = now or timezone.now()
    profile = user.profile
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    running = (
        Session.objects.filter(user=user, status=Session.RUNNING)
        .select_related("project")
        .first()
    )

    recentes = NotificationLog.objects.filter(
        user=user, created_at__gte=now - timedelta(minutes=30)
    ).order_by("-created_at")[:5]

    return {
        "now": now.isoformat(),
        "day": today.isoformat(),
        "block_scroll": _block_scroll(user, profile, today=today, now=now),
        "guardian": _guardian_consign(user, profile, today=today, now=now),
        "running_session": (
            {
                "id": running.pk,
                "project": running.project.name,
                "started_at": running.started_at.isoformat(),
                "planned_minutes": running.planned_minutes,
                "elapsed_minutes": int((now - running.started_at).total_seconds() // 60),
            }
            if running
            else None
        ),
        "notifications": [
            {
                "id": n.pk,
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "created_at": n.created_at.isoformat(),
            }
            for n in recentes
        ],
    }


def _block_scroll(user, profile: Profile, *, today: date, now: datetime) -> dict:
    """À partir de quand le scroll passif se bloque, et jusqu'à quoi (§8.5, §14).

    **Le serveur dit quand, l'agent décide comment.** C'est l'état « armé » qui
    manquait : sans lui, ni l'agent ni l'extension n'ont de quoi savoir s'ils
    doivent bloquer, et le blocage effectif du J5 n'aurait rien à interroger.

    Par défaut il s'arme à la fin du sas de détente s'il a été pris, sinon à
    l'heure du gardien — les deux moments que le §8.5 nomme. Le **palier 2** du
    §14 l'avance à l'ouverture de la fenêtre du soir.

    Il se lève à la validation de la journée, jamais à une heure fixe : « le
    retour est conditionné, pas puni ». Un blocage qui tomberait à minuit quoi
    qu'il arrive n'aurait rien demandé.

    **Un instant, un booléen, rien d'autre.** Le motif — sas, gardien, palier 2
    — reste ici : il dirait à qui lit le jeton de sonde qu'on a raté deux jours,
    et le §8 refuse à l'agent tout ce qui ressemble à de l'historique. L'heure
    seule suffit à décider quoi bloquer.
    """
    window = evening_window(today, profile.windows_by_weekday(), profile.timezone_name)
    minutes = (
        Session.objects.filter(user=user, coach_day=today, status=Session.DONE).aggregate(
            t=Sum("actual_minutes")
        )["t"]
        or 0
    )
    validee = minutes >= DEGRADED_MINUTES

    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    sanctions = _sanctions(streak_state(user, atelier, today=today), validated_today=validee)

    if sanctions.early_block:
        depuis = window.start
    else:
        sas = RelaxWindow.objects.filter(user=user, coach_day=today).first()
        depuis = (
            sas.ends_at
            if sas
            else window.end - timedelta(minutes=profile.guardian_minutes_before_end)
        )

    return {"armed_from": depuis.isoformat(), "armed": not validee and now >= depuis}


@transaction.atomic
def close_ghost_session(
    session: Session, *, last_active_at: datetime | None, now: datetime | None = None
) -> dict:
    """Clôture une session abandonnée, au dernier instant d'activité prouvé.

    La décision appartient au serveur, pas à l'agent : l'agent rapporte ce
    qu'il a mesuré, le serveur vérifie que les deux conditions du §8.7 sont
    réunies. Un agent bavard ou compromis ne peut donc pas fermer une session
    en cours.
    """
    now = now or timezone.now()
    verdict = ghost_rules.evaluate(
        started_at=session.started_at,
        planned_minutes=session.planned_minutes,
        now=now,
        last_active_at=last_active_at,
    )
    if not verdict.is_ghost:
        return {"closed": False, "reason": verdict.reason}

    resultat = end_session(
        session,
        now=verdict.close_at,
        note=(
            "Session clôturée automatiquement : la sonde n'a plus vu d'activité "
            f"après {verdict.close_at:%H:%M}."
        ),
        next_action="",
    )
    resultat.update({"closed": True, "reason": verdict.reason, "minutes": verdict.active_minutes})
    return resultat


# --------------------------------------------------------------------------
# Sondes et preuves automatiques (SPEC §8, §9, §11.10)
# --------------------------------------------------------------------------

@transaction.atomic
def ingest_signals(user, *, source: str, entries: list[dict], day: date) -> dict:
    """Enregistre les observations d'une sonde, puis marque ce qui doit l'être.

    Les entrées sont validées par la logique pure : une catégorie inconnue est
    refusée, et il n'existe aucun champ pour transporter une URL.
    """
    created = 0
    for entry in entries:
        checked = signal_rules.Signal(
            source=source,
            category=entry.get("category", ""),
            minutes=int(entry.get("minutes", 0)),
            day=day,
            started_at=parse_datetime(entry["started_at"]) if entry.get("started_at") else None,
            ended_at=parse_datetime(entry["ended_at"]) if entry.get("ended_at") else None,
        )
        if checked.minutes <= 0:
            continue
        Signal.objects.create(
            user=user,
            source=checked.source,
            category=checked.category,
            minutes=checked.minutes,
            day=day,
            started_at=checked.started_at,
            ended_at=checked.ended_at,
        )
        created += 1

    return {"stored": created, "marked": apply_signals_to_gardes(user, day=day)}


def apply_signals_to_gardes(user, *, day: date) -> list[dict]:
    """Marque les gardes dont la catégorie a été détectée ce jour-là.

    Deux règles, toutes deux issues du §11.10 :

    * une détection **marque** une journée, une absence de détection ne
      déclare jamais une journée tenue ;
    * une déclaration faite à la main n'est **jamais** écrasée par une sonde —
      l'utilisateur a le dernier mot, y compris contre la machine. La
      contradiction éventuelle est remontée par ``gardes_panel``, pas résolue
      en douce.
    """
    observed = [s.to_rule() for s in Signal.objects.filter(user=user, day=day)]
    marked = []

    for garde in Garde.objects.filter(user=user, active=True).exclude(auto_category=""):
        verdict = signal_rules.verdict_for(observed, garde.auto_category, day)
        if not verdict.marks:
            continue

        existing = GardeDay.objects.filter(garde=garde, day=day).first()
        if existing and existing.origin == GardeDay.MAIN:
            continue

        GardeDay.objects.update_or_create(
            garde=garde,
            day=day,
            defaults={
                "occurred": True,
                "origin": GardeDay.SONDE,
                "declared_at": timezone.now(),
            },
        )
        marked.append({"garde": garde.name, "minutes": verdict.minutes, "sources": list(verdict.sources)})

    return marked


def session_evidence(session: Session) -> dict:
    """Ce que la session laisse comme trace, selon le moyen déclaré par le projet.

    Le projet a choisi son moyen à sa création (§4.5) : on applique celui-là et
    pas un autre. Lire git sur un projet qui a déclaré ``fichiers`` produirait
    « aucune preuve » alors que le travail est bien là — et une preuve qui
    manque le travail réel est pire qu'une absence de preuve assumée.

    N'invalide jamais une session : le §6 est explicite là-dessus.
    """
    end = session.ended_at or timezone.now()
    kind = session.project.verification
    paths = list(ProjectRepo.objects.filter(project=session.project).values_list("path", flat=True))

    payload = {
        "verification": kind,
        "verification_label": verification_rules.LABELS.get(kind, kind),
        "paths": paths,
        "commits": [],
        "files": [],
        "files_total": 0,
        "unavailable": [],
        "suggested_note": "",
        "detail": "",
        "coverage": None,
    }

    if kind == verification_rules.MANUELLE:
        payload["detail"] = "Ce projet est en déclaration manuelle : aucune trace n'est cherchée."
        return payload

    if kind == verification_rules.PREMIER_PLAN:
        observed = [
            s.to_rule()
            for s in Signal.objects.filter(user=session.user, day=session.coach_day)
        ]
        coverage = signal_rules.session_coverage(
            observed,
            category=signal_rules.TRAVAIL_PROJET,
            start=session.started_at,
            end=end,
        )
        payload["coverage"] = {
            "percent": coverage.percent,
            "covered_minutes": coverage.covered_minutes,
            "session_minutes": coverage.session_minutes,
            "ignored_signals": coverage.ignored_signals,
        }
        payload["detail"] = coverage.label
        return payload

    if not paths:
        payload["detail"] = (
            f"« {payload['verification_label']} » est déclaré, mais aucun chemin ne l'est. "
            "Ce projet n'est pas vérifié tant qu'il manque."
        )
        return payload

    for path in paths:
        if kind == verification_rules.GIT:
            activity = gitscan.commits_between(path, session.started_at, end)
            if not activity.available:
                payload["unavailable"].append({"path": path, "detail": activity.detail})
                continue
            payload["commits"].extend(
                {"sha": c.sha, "subject": c.subject, "at": c.at.isoformat()} for c in activity.commits
            )
        else:
            activity = filescan.files_modified_between(path, session.started_at, end)
            if not activity.available:
                payload["unavailable"].append({"path": path, "detail": activity.detail})
                continue
            payload["files_total"] += activity.total
            payload["files"].extend(
                {"path": f.relative_path, "at": f.at.isoformat()} for f in activity.files
            )
            if activity.detail:
                payload["detail"] = activity.detail

        ProjectRepo.objects.filter(project=session.project, path=path).update(
            last_scanned_at=timezone.now()
        )

    payload["commits"].sort(key=lambda c: c["at"])
    payload["files"].sort(key=lambda f: f["at"])

    if kind == verification_rules.GIT:
        payload["suggested_note"] = "\n".join(f"- {c['subject']}" for c in payload["commits"])
    else:
        payload["suggested_note"] = "\n".join(f"- {f['path']}" for f in payload["files"])

    return payload


# --------------------------------------------------------------------------
# Les gardes (SPEC §11.10)
# --------------------------------------------------------------------------

def _garde_days(user) -> tuple[dict[str, list[date]], dict[str, list[date]]]:
    """Jours déclarés et jours marqués, indexés par garde."""
    declared: dict[str, list[date]] = {}
    marked: dict[str, list[date]] = {}
    rows = GardeDay.objects.filter(garde__user=user).values_list("garde_id", "day", "occurred")
    for garde_id, day, occurred in rows:
        key = str(garde_id)
        declared.setdefault(key, []).append(day)
        if occurred:
            marked.setdefault(key, []).append(day)
    return declared, marked


def gardes_panel(user, *, today: date) -> dict:
    """L'état des gardes du jour. Ne sort jamais de l'app (SPEC §11.10)."""
    gardes = list(Garde.objects.filter(user=user, active=True))
    declared, marked = _garde_days(user)

    payload = []
    for garde in gardes:
        rule = garde.to_rule()
        key = str(garde.pk)
        week = garde_rules.week_state(rule, marked.get(key, []), today)
        total = garde_rules.held_days(declared.get(key, []), marked.get(key, []))
        today_row = next((d for d in declared.get(key, []) if d == today), None)
        seen = signal_rules.verdict_for(
            [s.to_rule() for s in Signal.objects.filter(user=user, day=today)],
            garde.auto_category,
            today,
        ) if garde.auto_category else None
        payload.append(
            {
                "id": garde.pk,
                "name": garde.name,
                "budget": garde.weekly_budget,
                "declared_today": today_row is not None,
                "occurred_today": today in marked.get(key, []),
                "week_marked": week.marked,
                "week_label": week.label,
                "week_held": week.held,
                "week_left": week.left,
                "held_days": total,
                "held_weeks": garde_rules.held_weeks(rule, declared.get(key, []), marked.get(key, [])),
                "message": garde_rules.message_for(week, total),
                "auto": bool(garde.auto_category),
                "seen_minutes": seen.minutes if seen else 0,
                "seen_label": seen.label if seen else "",
                "conflict": bool(
                    seen
                    and seen.marks
                    and today_row is not None
                    and today not in marked.get(key, [])
                ),
            }
        )

    return {
        "day": today.isoformat(),
        "gardes": payload,
        "to_declare": sum(1 for g in payload if not g["declared_today"]),
    }


@transaction.atomic
def declare_garde(garde: Garde, *, day: date, occurred: bool) -> dict:
    """Déclare une journée. Redéclarer le même jour corrige, ça n'empile pas."""
    GardeDay.objects.update_or_create(
        garde=garde,
        day=day,
        defaults={"occurred": occurred, "declared_at": timezone.now()},
    )
    return gardes_panel(garde.user, today=day)


# --------------------------------------------------------------------------
# Piste Entretien (SPEC §11.9)
# --------------------------------------------------------------------------

def _checks_by_routine(user) -> dict[str, list[date]]:
    """Toutes les coches **valides** de l'utilisateur, indexées par routine.

    Les coches hors fenêtre en sont exclues : elles restent en base — le §17
    interdit d'effacer ce qui a eu lieu — mais elles ne comptent pas pour la
    semaine. Une habitude horaire dont la coche à 14h compterait comme un lever
    à 7h ne mesurerait rien du tout.
    """
    out: dict[str, list[date]] = {}
    for routine_id, day in (
        RoutineCheck.objects.filter(routine__user=user, on_time=True)
        .values_list("routine_id", "day")
    ):
        out.setdefault(str(routine_id), []).append(day)
    return out


def _local_time(user, moment=None):
    """L'heure locale de l'utilisateur — jamais l'heure du serveur.

    Le §1 est catégorique là-dessus : les timestamps viennent du serveur, mais
    ce qui se compare à une heure déclarée par quelqu'un est son heure à lui.
    Un lever « avant 7h30 » mesuré en UTC serait faux deux fois par an, et faux
    en permanence en voyage.
    """
    from zoneinfo import ZoneInfo

    moment = moment or timezone.now()
    return moment.astimezone(ZoneInfo(user.profile.timezone_name)).time()


def _bornes_d_activite(user, day: date) -> tuple[time | None, time | None]:
    """Première et dernière activité observée sur une journée du coach.

    Lues depuis les signaux des sondes, qui datent leurs fenêtres quand elles
    savent le faire. Les sondes qui n'en sont pas capables ne rendent rien ici,
    et c'est traité comme une absence de signal — jamais comme une nuit calme.
    """
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(user.profile.timezone_name)
    bornes = Signal.objects.filter(user=user, day=day).aggregate(
        debut=Min("started_at"), fin=Max("ended_at")
    )
    debut, fin = bornes["debut"], bornes["fin"]
    return (
        debut.astimezone(zone).time() if debut else None,
        fin.astimezone(zone).time() if fin else None,
    )


def corroboration_du_jour(user, routine: Routine, *, day: date) -> str:
    """Ce que les sondes disent de cette habitude horaire, aujourd'hui.

    Recalculée à chaque lecture et jamais stockée : un coucher ne peut être
    corroboré qu'une fois la nuit passée, et un état figé au moment du clic
    serait faux pour l'habitude la plus importante des deux.
    """
    if routine.deadline is None:
        return sommeil_rules.SANS_SIGNAL
    profile = user.profile
    premiere, derniere = _bornes_d_activite(user, day)
    return sommeil_rules.corroboration(
        routine.deadline,
        routine.direction,
        routine.anchor,
        premiere_activite=premiere,
        derniere_activite=derniere,
        journee_finie=day < coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour),
        rollover_hour=user.profile.day_rollover_hour,
    )


def routine_panel(user, *, today: date) -> dict:
    """Le panneau de quêtes d'entretien du jour, groupé par ancre.

    Ne renvoie que ce qui est dû aujourd'hui : une routine hors de son rythme
    n'apparaît pas, plutôt que d'apparaître grisée (SPEC §0.9).
    """
    routines = list(Routine.objects.filter(user=user, active=True))
    rules = [r.to_rule() for r in routines]
    checks = _checks_by_routine(user)
    entries = routine_rules.today_panel(rules, checks, today)
    # Les coches du jour posées hors fenêtre. Elles n'entrent pas dans le
    # compte, mais l'écran doit les montrer : sans ça, la ligne resterait
    # « à faire » alors que le bouton ne répond plus, et ça ressemblerait à un bug.
    en_retard = set(
        str(rid)
        for rid in RoutineCheck.objects.filter(
            routine__user=user, day=today, on_time=False
        ).values_list("routine_id", flat=True)
    )
    # Ce que les sondes disent des habitudes horaires. Calculé une fois pour le
    # panneau entier : les bornes d'activité sont les mêmes pour toutes.
    premiere, derniere = _bornes_d_activite(user, today)
    corroborations, corroboration_lignes = {}, {}
    for routine in routines:
        if routine.deadline is None:
            continue
        etat = sommeil_rules.corroboration(
            routine.deadline,
            routine.direction,
            routine.anchor,
            premiere_activite=premiere,
            derniere_activite=derniere,
            # Le panneau ne montre qu'aujourd'hui, donc une journée jamais
            # close : un coucher ne s'y juge pas, et c'est honnête.
            journee_finie=False,
            rollover_hour=user.profile.day_rollover_hour,
        )
        corroborations[str(routine.pk)] = etat
        corroboration_lignes[str(routine.pk)] = sommeil_rules.ligne(etat, routine.deadline)

    groups: list[dict] = []
    for entry in entries:
        anchor = entry.routine.anchor
        if not groups or groups[-1]["anchor"] != anchor:
            groups.append(
                {
                    "anchor": anchor,
                    "label": routine_rules.ANCHOR_LABELS.get(anchor, anchor),
                    "routines": [],
                }
            )
        groups[-1]["routines"].append(
            {
                "id": int(entry.routine.key),
                "name": entry.routine.name,
                "checked": entry.checked_today,
                "week_done": entry.week.done,
                "week_target": entry.week.target,
                "week_label": entry.week.label,
                "week_held": entry.week.held,
                "slack": entry.routine.slack,
                "shards_if_checked": entry.shards_if_checked,
                "window": routine_rules.window_label(entry.routine),
                "late_today": entry.routine.key in en_retard,
                "corroboration": corroborations.get(entry.routine.key, sommeil_rules.SANS_SIGNAL),
                "corroboration_line": corroboration_lignes.get(entry.routine.key, ""),
            }
        )

    return {
        "day": today.isoformat(),
        "held_weeks": routine_rules.piste_held_weeks(rules, checks),
        "week_held": routine_rules.piste_week_held(rules, checks, today),
        "due_today": len(entries),
        "done_today": sum(1 for e in entries if e.checked_today),
        "groups": groups,
    }


@transaction.atomic
def check_routine(
    routine: Routine, *, day: date, source: str = RoutineCheck.APP, at: date | None = None
) -> dict:
    """Coche une routine pour une journée du coach.

    Idempotent : recocher le même jour ne rapporte rien de plus. Les Éclats
    s'arrêtent à l'objectif hebdomadaire, et la semaine tenue paie son bonus une
    seule fois — celui de la coche qui atteint le seuil.

    Pour une routine à fenêtre horaire — se lever tôt, ne pas se coucher tard —
    l'heure de la coche décide. Hors fenêtre, le geste est **gardé** et ne compte
    pas : ni semaine, ni Éclats. Refuser le clic ferait croire à une panne, et
    l'accepter en silence ferait d'une habitude horaire un simple bouton.
    """
    rule = routine.to_rule()
    days = list(
        RoutineCheck.objects.filter(routine=routine, on_time=True).values_list("day", flat=True)
    )
    if RoutineCheck.objects.filter(routine=routine, day=day).exists():
        return {"created": False, "on_time": day in days, "shards": 0, "week": _week_payload(rule, days, day)}

    a_l_heure = routine_rules.within_window(
        rule, at or _local_time(routine.user), routine.user.profile.day_rollover_hour
    )
    if not a_l_heure:
        RoutineCheck.objects.create(
            routine=routine, day=day, source=source, shards_awarded=0, on_time=False
        )
        return {"created": True, "on_time": False, "shards": 0, "week": _week_payload(rule, days, day)}

    before = routine_rules.week_state(rule, days, day).done
    shards = routine_rules.shards_for_check(rule, checks_before_in_week=before)
    if before + 1 == rule.weekly_target:
        shards += routine_rules.WEEK_HELD_BONUS

    RoutineCheck.objects.create(routine=routine, day=day, source=source, shards_awarded=shards)
    if shards:
        Profile.objects.filter(user=routine.user).update(shards=F("shards") + shards)

    return {"created": True, "on_time": True, "shards": shards, "week": _week_payload(rule, days + [day], day)}


@transaction.atomic
def uncheck_routine(routine: Routine, *, day: date) -> dict:
    """Annule une coche du jour — correction d'un tap, pas une sanction.

    Les Éclats effectivement crédités par cette coche sont repris, ni plus ni
    moins. Rien d'autre n'est retiré (SPEC §17 : pas de sanction rétroactive).
    """
    check = RoutineCheck.objects.filter(routine=routine, day=day).first()
    if check is None:
        days = list(RoutineCheck.objects.filter(routine=routine).values_list("day", flat=True))
        return {"removed": False, "shards": 0, "week": _week_payload(routine.to_rule(), days, day)}

    shards = check.shards_awarded
    check.delete()
    if shards:
        Profile.objects.filter(user=routine.user).update(shards=F("shards") - shards)

    days = list(RoutineCheck.objects.filter(routine=routine).values_list("day", flat=True))
    return {"removed": True, "shards": -shards, "week": _week_payload(routine.to_rule(), days, day)}


def _week_payload(rule: routine_rules.Routine, days: list[date], day: date) -> dict:
    week = routine_rules.week_state(rule, days, day)
    return {
        "done": week.done,
        "target": week.target,
        "label": week.label,
        "held": week.held,
        "remaining": week.remaining,
    }


