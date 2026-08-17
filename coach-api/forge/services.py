"""Services du domaine : ce qui relie les modèles à la logique pure.

Rien ici ne réimplémente une règle : le streak, l'XP et la saison viennent de
``forge/rules``. Ce module se contente de rassembler les faits, d'appeler les
règles, et d'écrire le résultat.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, F, Max, Sum, Value
from django.db.models.functions import Greatest
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import (
    Achievement,
    Commitment,
    DayOff,
    Garde,
    GardeDay,
    JournalEntry,
    Profile,
    Project,
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
    Track,
)
from . import filescan, gitscan, progression
from .rules import loot as loot_rules
from .rules import gardes as garde_rules
from .rules import ghost as ghost_rules
from .rules import modifiers as modifier_rules
from .rules import ranks as rank_rules
from .rules import roadmap_import
from .rules import routines as routine_rules
from .rules import sanctions as sanction_rules
from .rules import hiatus as hiatus_rules
from .rules import seasons as season_rules
from .rules import signals as signal_rules
from .rules import slots as slot_rules
from .rules import verification as verification_rules
from .rules import streak as streak_rules
from .rules import xp as xp_rules
from .rules.calendar import coach_day, day_bounds, evening_window, week_start

FLOOR_MINUTES = streak_rules.FLOOR_MINUTES
DEGRADED_MINUTES = 10


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


def floor_minutes(user, *, today: date) -> int:
    """Le plancher de la session normale, indexé sur le rang (§4.1, §4.4)."""
    return streak_rules.floor_for(rank_state(user, today=today)["code"])


def streak_state(user, track: Track, *, today: date) -> streak_rules.StreakState:
    """État du streak, évalué côté serveur à chaque lecture.

    La journée en cours est exclue : tant qu'elle n'est pas finie, elle n'est
    pas ratée.
    """
    history = resolve_days(user, track, until=today - timedelta(days=1))
    return streak_rules.evaluate(history, floor_minutes=floor_minutes(user, today=today))


# --------------------------------------------------------------------------
# Saison
# --------------------------------------------------------------------------

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
) -> Season:
    """Ouvre une saison. ``modifier_key`` et ``phantom_choice`` viennent des
    choix faits à l'écran d'ouverture (§12.5, §12.7) ; vides, le plan décide.

    Les deux sont pris **avant** de créer le boss et la mise, parce que le
    modificateur les dimensionne tous les deux. Les appliquer après coup
    obligerait à défaire ce que le plan a calculé, et c'est le genre de calcul
    inverse qui finit par diverger.
    """
    previous = Season.objects.filter(user=user).order_by("-index").first()
    index = (previous.index + 1) if previous else 1
    used = set(Season.objects.filter(user=user).values_list("key", flat=True))
    previous_score = None
    if previous:
        previous_score = (
            Session.objects.filter(user=user, season=previous, status=Session.DONE).aggregate(
                total=Sum("actual_minutes")
            )["total"]
            or None
        )

    plan = season_rules.plan_season(index, starts_on, previous_score=previous_score, used_keys=used)
    retenu = modifier_key or plan.modifier_key
    effets = modifier_rules.resolve(retenu)

    season = Season.objects.create(
        user=user,
        index=plan.index,
        key=plan.key,
        name=plan.name,
        accent=plan.accent,
        baseline=plan.baseline,
        modifier_key=retenu,
        starts_on=plan.starts_on,
        ends_on=plan.ends_on,
        # « Siège » double la mise et gonfle le boss (§12.5). Appliqué ici, à
        # l'ouverture, et jamais recalculé ensuite : une saison dont l'enjeu
        # bougerait en cours de route ne serait plus un engagement.
        stake_shards=stake * effets.stake_multiplier,
        **({"phantom_choice": phantom_choice} if phantom_choice else {}),
    )
    SeasonBoss.objects.create(
        season=season,
        key=plan.boss_key,
        name=plan.boss_name,
        max_hp=round(plan.boss_hp * effets.boss_hp_multiplier),
    )
    return season


def boss_payload(season: Season | None) -> dict | None:
    if not season or not hasattr(season, "boss"):
        return None
    boss = season.boss
    return {
        "name": boss.name,
        "max_hp": boss.max_hp,
        "current_hp": boss.current_hp,
        "ratio": boss.ratio,
        "is_dead": boss.is_dead,
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
    )


@transaction.atomic
def end_session(session: Session, *, now: datetime | None = None, note: str = "", next_action: str = "") -> dict:
    """Clôture une session : minutes réelles, XP, dégâts au boss, hauts faits."""
    now = now or timezone.now()
    profile = session.user.profile

    elapsed = int((now - session.started_at).total_seconds() // 60)
    session.actual_minutes = max(0, min(elapsed, session.planned_minutes))
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

    total_xp_before = (
        Session.objects.filter(user=session.user, status=Session.DONE)
        .exclude(pk=session.pk)
        .aggregate(t=Sum("xp_awarded"))["t"]
        or 0
    )

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
        early_bonus_ratio=bonus.early_xp_bonus,
        modifier_multiplier=modifier_rules.session_multiplier(
            effets, minutes=session.actual_minutes, started_hour=local_hour
        ),
        full_xp_sessions=effets.full_xp_sessions,
    )
    session.xp_awarded = breakdown.total
    session.xp_breakdown = {
        "base": breakdown.base,
        "first_of_day": breakdown.first_of_day,
        "early": breakdown.early,
        "streak_multiplier": breakdown.streak_multiplier,
        "momentum_multiplier": breakdown.momentum_multiplier,
        "modifier_multiplier": breakdown.modifier_multiplier,
        "degressivity": breakdown.degressivity,
        "total": breakdown.total,
        "notes": breakdown.notes,
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
    if session.season and hasattr(session.season, "boss"):
        boss = session.season.boss
        vivant_avant = not boss.is_dead
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

    _update_commitment(session)
    _update_quests(session)
    unlocked = _check_achievements(session.user, session)

    # Les quatre séquences de juice du §7 ont besoin de savoir **ce qui vient
    # de changer**, pas de l'état courant : c'est le franchissement qui se met
    # en scène. Tout ce qui suit est donc un delta, calculé une fois ici.
    niveau_avant = xp_rules.level_for(total_xp_before)
    total_apres = total_xp_before + breakdown.total
    niveau_apres = xp_rules.level_for(total_apres)

    cartes = []
    reliques = progression.grant_relics_for(session.user, [a["key"] for a in unlocked])
    for _ in range(max(0, niveau_apres - niveau_avant)):
        cartes.append(progression.draw_card(session.user, reason=loot_rules.MONTEE_DE_NIVEAU))

    return {
        "session_id": session.id,
        "minutes": session.actual_minutes,
        "xp": breakdown.total,
        "breakdown": session.xp_breakdown,
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
        "cards": cartes,
        "relics": reliques,
    }


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


ACHIEVEMENTS = {
    "premier_sang": ("Premier sang", "Ta première session enregistrée."),
    "retour_du_neant": ("Retour du néant", "Reprendre après au moins trois jours d'arrêt."),
    "increvable": ("Increvable", "Vingt-huit jours sans consommer de bouclier."),
    "chirurgien": ("Chirurgien", "Dix étapes de roadmap terminées dans une saison."),
}


def _check_achievements(user, session: Session) -> list[dict]:
    unlocked: list[dict] = []

    def grant(key: str) -> None:
        label, description = ACHIEVEMENTS[key]
        obj, created = Achievement.objects.get_or_create(
            user=user, key=key, defaults={"label": label, "description": description}
        )
        if created:
            unlocked.append({"key": key, "label": label, "description": description})

    if Session.objects.filter(user=user, status=Session.DONE).count() == 1:
        grant("premier_sang")

    history = resolve_days(user, session.project.track, until=session.coach_day - timedelta(days=1))
    state = streak_rules.evaluate(history)
    if state.missed_run >= streak_rules.COMEBACK_MISSED_THRESHOLD:
        grant("retour_du_neant")

    return unlocked


# --------------------------------------------------------------------------
# La proposition unique de l'accueil (SPEC §11.1)
# --------------------------------------------------------------------------

def propose(user, *, today: date, comeback: bool = False) -> dict | None:
    """Choisit le projet, la durée et la tâche. L'utilisateur n'arbitre pas.

    Priorité : le créneau du jour, puis le retard sur l'engagement hebdo, puis
    l'ancienneté du dernier passage.

    ``comeback`` est le palier 3 du §14 : après trois jours d'arrêt, la durée
    proposée tombe à dix minutes quoi qu'annonce le créneau. Proposer une
    séance de cinquante minutes à quelqu'un qui n'a rien fait depuis trois
    jours, c'est proposer de ne pas ouvrir l'app.
    """
    # Le développement du coach reste accessible en un tap, mais n'est jamais
    # ce que l'app propose d'elle-même : proposer de coder le coach le soir,
    # c'est le piège du SPEC §11.6. Aucune restriction, juste aucune promotion.
    projects = list(
        Project.objects.filter(user=user, status=Project.ACTIVE, track__kind=Track.ATELIER)
        .exclude(is_coach_project=True)
        .select_related("track")
        .prefetch_related("steps", "timeslots")
    )
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
    step = chosen.current_step
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

    return {
        "project": {
            "id": chosen.id,
            "name": chosen.name,
            "color": chosen.color,
            "emblem": chosen.emblem,
            "completion": chosen.completion,
        },
        # Sans créneau déclaré, la durée proposée **est** le plancher du rang :
        # c'est le seul endroit où la progression du §4.1 devient visible sans
        # qu'on aille lire un chiffre.
        "minutes": DEGRADED_MINUTES if comeback else (slot.duration_minutes if slot else plancher),
        "step": {"id": step.id, "label": step.label, "needs_split": step.needs_split} if step else None,
        "amorce": amorce or "",
        "reason": (
            "Une tâche, dix minutes."
            if comeback
            else _proposal_reason(chosen, slot, done_by_project.get(chosen.id, 0))
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

def home_state(user, *, now: datetime | None = None) -> dict:
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

    total_xp = Session.objects.filter(user=user, status=Session.DONE).aggregate(t=Sum("xp_awarded"))["t"] or 0
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

    blocks = [
        {
            "project": s.project.name,
            "color": s.project.color,
            "start_ratio": _ratio_in_window(window, s.started_at),
            "end_ratio": _ratio_in_window(window, s.ended_at or now),
            "minutes": s.actual_minutes,
            "running": s.status == Session.RUNNING,
        }
        for s in sessions_today
        if s.status in (Session.DONE, Session.RUNNING)
    ]

    return {
        "day": today.isoformat(),
        "now": now.isoformat(),
        "momentum": progression.heat(user, today=today),
        "skills": progression.skill_tree(user)["branches"],
        "phantom": progression.phantom_panel(user, today=today),
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
                "accent": season.accent,
                "baseline": season.baseline,
                "day_index": season.day_index(today) + 1,
                "days_total": season_rules.SEASON_DAYS,
                "days_left": season.days_left(today),
                "modifier": season.modifier_key,
                "stake": max(0, season.stake_shards - season.stake_forfeited),
                "stake_forfeited": season.stake_forfeited,
            }
            if season
            else None
        ),
        "boss": boss_payload(season),
        "evening": {
            "start": window.start.isoformat(),
            "end": window.end.isoformat(),
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
            }
            if running
            else None
        ),
        "proposal": propose(user, today=today, comeback=sanctions["comeback"]),
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
        "open_steps": parsed.open_steps,
        "steps": [
            {
                "label": s.label,
                "state": s.state,
                "estimated_sessions": s.estimated_sessions,
                "needs_split": s.needs_split,
            }
            for s in parsed.steps
        ],
        "warnings": parsed.warnings,
    }


def rank_state(user, *, today: date) -> dict:
    """Le rang de l'utilisateur, calculé sur les engagements tenus (SPEC §4.4).

    Cumulatif et monotone : une mauvaise semaine n'en retire aucune. Le §17
    interdit tout retrait rétroactif de rang.
    """
    semaines = [
        (c.week_start, c.done_sessions >= c.planned_sessions)
        for c in Commitment.objects.filter(project__user=user, week_start__lt=week_start(today))
    ]
    tenues = rank_rules.weeks_kept(semaines)
    code = rank_rules.rank_for(tenues)
    recompenses = rank_rules.rewards_for(code)
    suivant = rank_rules.next_rank(tenues)

    return {
        "code": code,
        "weeks_kept": tenues,
        "slots": recompenses.slots,
        "extra_shields": recompenses.extra_shields,
        "extra_days_off": recompenses.extra_days_off,
        "next": {"code": suivant[0], "weeks_left": suivant[1]} if suivant else None,
        "next_unlock": rank_rules.unlock_label(code),
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
    )
    if parsed.repo_path:
        # Déclaré à la création : la vérification marche dès la première
        # session, sans réglage supplémentaire.
        ProjectRepo.objects.get_or_create(project=project, path=parsed.repo_path)
    for order, step in enumerate(parsed.steps):
        RoadmapStep.objects.create(
            project=project,
            order=order,
            label=step.label,
            state=step.state,
            estimated_sessions=step.estimated_sessions,
            done_at=timezone.now() if step.state == RoadmapStep.DONE else None,
        )
    return project


# --------------------------------------------------------------------------
# L'agent local (SPEC §8)
# --------------------------------------------------------------------------

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
    """Toutes les coches de l'utilisateur, indexées par routine."""
    out: dict[str, list[date]] = {}
    for routine_id, day in RoutineCheck.objects.filter(routine__user=user).values_list("routine_id", "day"):
        out.setdefault(str(routine_id), []).append(day)
    return out


def routine_panel(user, *, today: date) -> dict:
    """Le panneau de quêtes d'entretien du jour, groupé par ancre.

    Ne renvoie que ce qui est dû aujourd'hui : une routine hors de son rythme
    n'apparaît pas, plutôt que d'apparaître grisée (SPEC §0.9).
    """
    routines = list(Routine.objects.filter(user=user, active=True))
    rules = [r.to_rule() for r in routines]
    checks = _checks_by_routine(user)
    entries = routine_rules.today_panel(rules, checks, today)

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
def check_routine(routine: Routine, *, day: date, source: str = RoutineCheck.APP) -> dict:
    """Coche une routine pour une journée du coach.

    Idempotent : recocher le même jour ne rapporte rien de plus. Les Éclats
    s'arrêtent à l'objectif hebdomadaire, et la semaine tenue paie son bonus une
    seule fois — celui de la coche qui atteint le seuil.
    """
    rule = routine.to_rule()
    days = list(RoutineCheck.objects.filter(routine=routine).values_list("day", flat=True))
    if day in days:
        return {"created": False, "shards": 0, "week": _week_payload(rule, days, day)}

    before = routine_rules.week_state(rule, days, day).done
    shards = routine_rules.shards_for_check(rule, checks_before_in_week=before)
    if before + 1 == rule.weekly_target:
        shards += routine_rules.WEEK_HELD_BONUS

    RoutineCheck.objects.create(routine=routine, day=day, source=source, shards_awarded=shards)
    if shards:
        Profile.objects.filter(user=routine.user).update(shards=F("shards") + shards)

    return {"created": True, "shards": shards, "week": _week_payload(rule, days + [day], day)}


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


def _ratio_in_window(window, moment: datetime) -> float:
    total = max(1, window.total_minutes)
    minutes = (moment - window.start).total_seconds() / 60
    return round(min(1.0, max(0.0, minutes / total)), 4)
