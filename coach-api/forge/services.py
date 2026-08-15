"""Services du domaine : ce qui relie les modèles à la logique pure.

Rien ici ne réimplémente une règle : le streak, l'XP et la saison viennent de
``forge/rules``. Ce module se contente de rassembler les faits, d'appeler les
règles, et d'écrire le résultat.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count, Max, Sum
from django.utils import timezone

from .models import (
    Achievement,
    Commitment,
    DayOff,
    JournalEntry,
    Profile,
    Project,
    Quest,
    RelaxWindow,
    Season,
    SeasonBoss,
    Session,
    Track,
)
from .rules import seasons as season_rules
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


def streak_state(user, track: Track, *, today: date) -> streak_rules.StreakState:
    """État du streak, évalué côté serveur à chaque lecture.

    La journée en cours est exclue : tant qu'elle n'est pas finie, elle n'est
    pas ratée.
    """
    history = resolve_days(user, track, until=today - timedelta(days=1))
    return streak_rules.evaluate(history)


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
def open_season(user, *, starts_on: date, stake: int = 0) -> Season:
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
    season = Season.objects.create(
        user=user,
        index=plan.index,
        key=plan.key,
        name=plan.name,
        accent=plan.accent,
        baseline=plan.baseline,
        modifier_key=plan.modifier_key,
        starts_on=plan.starts_on,
        ends_on=plan.ends_on,
        stake_shards=stake,
    )
    SeasonBoss.objects.create(
        season=season, key=plan.boss_key, name=plan.boss_name, max_hp=plan.boss_hp
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

    local_hour = session.started_at.astimezone(ZoneInfo(profile.timezone_name)).hour
    is_first = not Session.objects.filter(
        user=session.user, coach_day=session.coach_day, status=Session.DONE
    ).exclude(pk=session.pk).exists()

    breakdown = xp_rules.session_xp(
        minutes=session.actual_minutes,
        rank_in_day=session.rank_in_day,
        is_first_of_day=is_first,
        started_hour=local_hour,
        streak=state_before.current,
        days_worked_this_week=days_worked,
    )
    session.xp_awarded = breakdown.total
    session.xp_breakdown = {
        "base": breakdown.base,
        "first_of_day": breakdown.first_of_day,
        "early": breakdown.early,
        "streak_multiplier": breakdown.streak_multiplier,
        "momentum_multiplier": breakdown.momentum_multiplier,
        "degressivity": breakdown.degressivity,
        "total": breakdown.total,
        "notes": breakdown.notes,
    }
    session.save()

    if note or next_action:
        JournalEntry.objects.update_or_create(
            session=session, defaults={"raw_note": note, "next_action": next_action}
        )

    damage = season_rules.damage_of(minutes=session.actual_minutes)
    if session.season and hasattr(session.season, "boss"):
        boss = session.season.boss
        boss.damage_taken += damage
        boss.save(update_fields=["damage_taken"])

    _update_commitment(session)
    _update_quests(session)
    unlocked = _check_achievements(session.user, session)

    return {
        "session_id": session.id,
        "minutes": session.actual_minutes,
        "xp": breakdown.total,
        "breakdown": session.xp_breakdown,
        "boss_damage": damage,
        "achievements": unlocked,
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

def propose(user, *, today: date) -> dict | None:
    """Choisit le projet, la durée et la tâche. L'utilisateur n'arbitre pas.

    Priorité : le créneau du jour, puis le retard sur l'engagement hebdo, puis
    l'ancienneté du dernier passage.
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
        "minutes": slot.duration_minutes if slot else 25,
        "step": {"id": step.id, "label": step.label, "needs_split": step.needs_split} if step else None,
        "amorce": amorce or "",
        "reason": _proposal_reason(chosen, slot, done_by_project.get(chosen.id, 0)),
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
    state = streak_state(user, atelier, today=today)
    season = current_season(user, today=today)

    window = evening_window(today, profile.windows_by_weekday(), profile.timezone_name)
    sessions_today = list(
        Session.objects.filter(user=user, coach_day=today).select_related("project").order_by("started_at")
    )
    minutes_today = sum(s.actual_minutes for s in sessions_today if s.status == Session.DONE)

    total_xp = Session.objects.filter(user=user, status=Session.DONE).aggregate(t=Sum("xp_awarded"))["t"] or 0
    running = next((s for s in sessions_today if s.status == Session.RUNNING), None)

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
        "progression": xp_rules.progression(total_xp),
        "season": (
            {
                "index": season.index,
                "name": season.name,
                "accent": season.accent,
                "baseline": season.baseline,
                "day_index": season.day_index(today) + 1,
                "days_total": season_rules.SEASON_DAYS,
                "days_left": season.days_left(today),
                "modifier": season.modifier_key,
                "stake": season.stake_shards,
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
        "proposal": propose(user, today=today),
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
        "relax_used": RelaxWindow.objects.filter(user=user, coach_day=today).exists(),
    }


def _ratio_in_window(window, moment: datetime) -> float:
    total = max(1, window.total_minutes)
    minutes = (moment - window.start).total_seconds() / 60
    return round(min(1.0, max(0.0, minutes / total)), 4)
