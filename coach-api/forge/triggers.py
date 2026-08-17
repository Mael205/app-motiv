"""Les déclencheurs.

Le diagnostic est explicite (SPEC §11.2) : « j'oublie de le faire » n'est pas un
problème de mémoire, c'est une absence de déclencheur. Ce module contient donc
les trois seuls mécanismes qui font que l'app se manifeste toute seule.

1. Le rappel de créneau, 10 minutes avant un rendez-vous fixe.
2. Le gardien du soir, quand la fenêtre se referme sans session validée.
3. La fin du sas de détente.

Aucun n'a besoin d'IA : la proposition est construite depuis la roadmap. C'est
volontaire — le gardien doit exister dès J1 et ne jamais tomber, même quand
l'API du modèle est en panne (SPEC §5.4).

Le gardien **demande** en plus au modèle de découper sa tâche en un geste de dix
minutes, parce que reprendre une étape dimensionnée pour trois séances et
écrire « 10 min » devant est une promesse fausse. Mais il part quoi qu'il
arrive : ``coaching.tache_du_gardien`` rend le texte de repli quand le modèle
manque, décline ou dérape.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import NotificationLog, Profile, RelaxWindow, Session, Track
from .notifications import Notification, notify
from .rules.calendar import coach_day, evening_window
from .services import DEGRADED_MINUTES, propose, streak_state

GUARDIAN = "gardien"
SLOT_REMINDER = "creneau"
RELAX_OVER = "sas_fini"
BILAN = "bilan"
DAILY = "bilan_du_jour"
BILAN_NON_LU = "bilan_non_lu"

# Dimanche 20h. Assez tôt pour que la semaine décrite soit encore la semaine
# qu'on a en tête, assez tard pour que le dimanche compte dedans.
HEURE_BILAN = 20


def run_all(now: datetime | None = None) -> list[dict]:
    """Point d'entrée unique, appelé chaque minute par l'ordonnanceur."""
    now = now or timezone.now()
    fired: list[dict] = []

    for profile in Profile.objects.select_related("user").all():
        fired += check_slot_reminder(profile, now)
        fired += check_relax_end(profile, now)
        fired += check_guardian(profile, now)
        fired += check_daily_report(profile, now)
        fired += check_weekly_report(profile, now)

    return fired


# --------------------------------------------------------------------------
# 1. Le rappel de créneau
# --------------------------------------------------------------------------

def check_slot_reminder(profile: Profile, now: datetime) -> list[dict]:
    """« Mardi 20h30, bot STS2 » se tient ; « je bosserai ce soir » se rate."""
    user = profile.user
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)
    local = now.astimezone(_zone(profile))

    from .models import TimeSlot

    slots = TimeSlot.objects.filter(
        project__user=user, project__status="active", active=True, weekday=today.weekday()
    ).select_related("project")

    fired = []
    for slot in slots:
        start = local.replace(
            hour=slot.start_time.hour, minute=slot.start_time.minute, second=0, microsecond=0
        )
        delta = (start - local).total_seconds() / 60
        if not (0 <= delta <= 10):
            continue

        sent = _deliver(
            user,
            f"{SLOT_REMINDER}:{slot.id}",
            today,
            Notification(
                title=f"Créneau dans {int(delta)} min",
                body=f"{slot.project.name} — {slot.duration_minutes} minutes prévues à "
                f"{slot.start_time.strftime('%Hh%M')}.",
                kind="creneau",
            ),
        )
        if sent:
            fired.append({"kind": SLOT_REMINDER, "project": slot.project.name})

    return fired


# --------------------------------------------------------------------------
# 2. Le gardien du soir
# --------------------------------------------------------------------------

def check_guardian(profile: Profile, now: datetime) -> list[dict]:
    """Déclenché quand la fenêtre se referme sans qu'une session ait validé le jour.

    Le message ne fait pas la morale : il donne le plancher, les boucliers
    restants, et **une tâche précise de 10 minutes** tirée de la roadmap. Pas
    « tu devrais bosser », mais « 10 min : écrire le test de collision ».
    """
    user = profile.user
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)
    window = evening_window(today, profile.windows_by_weekday(), profile.timezone_name)

    trigger_at = window.end - timedelta(minutes=profile.guardian_minutes_before_end)
    if not (trigger_at <= now < trigger_at + timedelta(minutes=5)):
        return []

    minutes = _minutes_today(user, today)
    if minutes >= DEGRADED_MINUTES:
        return []                                  # journée déjà validée
    if Session.objects.filter(user=user, status=Session.RUNNING).exists():
        return []                                  # une session tourne, il est dessus

    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    state = streak_state(user, atelier, today=today)
    proposal = propose(user, today=today)

    left = int((window.end - now).total_seconds() // 60)
    if proposal:
        # Le découpage est la seule chose confiée au modèle ici, et il ne peut
        # rien casser : ``tache_du_gardien`` rend toujours un texte, celui du
        # repli si l'IA manque, refuse ou dérape.
        from .coaching import tache_du_gardien

        tache = tache_du_gardien(proposal, minutes_restantes=left)
        body = (
            f"10 min : {tache['texte']}"
            if tache["texte"]
            else f"10 min sur {proposal['project']['name']}"
        )
        body += f"\n{left} min avant la fin de la fenêtre."
    else:
        body = f"Le plancher est à {DEGRADED_MINUTES} minutes. {left} min avant la fin de la fenêtre."

    if state.shields:
        body += f"\nBoucliers : {state.shields}."
    else:
        body += "\nPlus aucun bouclier : un jour raté remet le streak à zéro."

    sent = _deliver(
        user,
        GUARDIAN,
        today,
        Notification(title="Rien de posé ce soir", body=body, kind="gardien"),
    )
    return [{"kind": GUARDIAN, "delivered": sent}] if sent else []


# --------------------------------------------------------------------------
# 3. La fin du sas de détente
# --------------------------------------------------------------------------

def check_relax_end(profile: Profile, now: datetime) -> list[dict]:
    """Le sas est un droit, pas un piège. Sa fin est nette."""
    user = profile.user
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    window = RelaxWindow.objects.filter(user=user, coach_day=today).first()
    if not window or not (window.ends_at <= now < window.ends_at + timedelta(minutes=5)):
        return []
    if _minutes_today(user, today) >= DEGRADED_MINUTES:
        return []

    sent = _deliver(
        user,
        RELAX_OVER,
        today,
        Notification(
            title="Sas terminé",
            body="Trente minutes, c'était le marché. Le plancher est à 25 minutes — "
            "ou 10 si la soirée est mauvaise.",
            kind="gardien",
        ),
    )
    return [{"kind": RELAX_OVER}] if sent else []


# --------------------------------------------------------------------------
# 4. Le bilan de la nuit
# --------------------------------------------------------------------------

def check_daily_report(profile: Profile, now: datetime) -> list[dict]:
    """Pousse le bilan de la journée écoulée, après la bascule (SPEC §13.1).

    Envoyé la nuit et lu au réveil : une notification qui ne demande rien et
    qu'on peut ignorer sans conséquence. C'est le seul message du produit qui
    n'attend aucun geste — et le §13.1 y tient, « aucune interaction demandée,
    rien à remplir ».

    Silencieux les jours où il n'y a rien à dire. Un bilan quotidien qui
    annonce tous les matins zéro minute travaillée devient un compteur de
    reproches, ce que le §17 refuse.
    """
    local = now.astimezone(_zone(profile))
    if local.hour != profile.day_rollover_hour or local.minute >= 5:
        return []

    from . import daily as daily_service

    jour, bilan = daily_service.hier(profile.user, now=now)
    if bilan.travaillees == 0 and not bilan.repartition:
        return []

    sent = _deliver(
        profile.user,
        DAILY,
        jour,
        Notification(title="Hier", body=bilan.phrase, kind="info"),
    )
    return [{"kind": DAILY, "day": jour.isoformat()}] if sent else []


# --------------------------------------------------------------------------
# 5. Le bilan du dimanche soir
# --------------------------------------------------------------------------

def check_weekly_report(profile: Profile, now: datetime) -> list[dict]:
    """Envoie le bilan à l'ami, le dimanche soir (SPEC §4.7).

    À heure fixe et non en fin de fenêtre : la fenêtre du dimanche peut être
    ouverte tard, et un bilan qui part à 23h est un bilan lu le lundi — quand
    la semaine qu'il décrit est déjà commencée.

    Aucun rattrapage si le serveur était éteint à cette minute-là : l'envoi
    suivant portera sa propre semaine, et un bilan en retard d'une semaine ne
    contrôle plus rien.
    """
    local = now.astimezone(_zone(profile))
    if local.weekday() != 6:                       # dimanche
        return []
    if not (HEURE_BILAN <= local.hour < HEURE_BILAN + 1 and local.minute < 5):
        return []

    from . import review, weekly

    # La revue s'ouvre avant que le bilan parte : ses questions sont calculées
    # sur la semaine qui vient de finir, et c'est le moment où elle est encore
    # en tête. Elle n'attend aucune réponse pour exister (§13.3).
    review.ouvrir(profile.user, now=now)

    rapport = weekly.envoyer(profile.user, now=now)
    if rapport is None:
        return []

    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)
    if rapport.sent_at:
        _deliver(
            profile.user,
            BILAN,
            today,
            Notification(
                title="Bilan envoyé",
                body="La semaine est partie. Tu peux le relire dans le journal.",
                kind="bilan",
            ),
        )

    # Le §4.7 : un contrôleur qui ne regarde pas ne contrôle rien.
    if weekly.non_lus(profile.user) >= weekly.SEUIL_NON_LUS:
        _deliver(
            profile.user,
            BILAN_NON_LU,
            today,
            Notification(
                title="Trois bilans sans lecture",
                body="Ton destinataire n'a rien ouvert depuis trois semaines. "
                "Le point d'appui n'en est plus un : change de destinataire.",
                kind="bilan",
            ),
        )

    return [{"kind": BILAN, "sent": bool(rapport.sent_at)}]


# --------------------------------------------------------------------------

def _deliver(user, kind: str, day: date, notification: Notification) -> bool:
    """Envoie une fois et une seule. L'unicité en base est la garantie.

    Le `create` est isolé dans son propre point de sauvegarde : sans ça, la
    violation d'unicité — qui est le cas *nominal* d'un second passage — casse
    la transaction englobante et rend inutilisable tout ce qui suit.
    """
    try:
        with transaction.atomic():
            log = NotificationLog.objects.create(
                user=user, kind=kind, coach_day=day, title=notification.title, body=notification.body
            )
    except IntegrityError:
        return False                               # déjà envoyé aujourd'hui

    log.channels = notify(user, notification)
    log.save(update_fields=["channels"])
    return True


def _minutes_today(user, day: date) -> int:
    from django.db.models import Sum

    return (
        Session.objects.filter(user=user, coach_day=day, status=Session.DONE).aggregate(
            total=Sum("actual_minutes")
        )["total"]
        or 0
    )


def _zone(profile: Profile):
    from zoneinfo import ZoneInfo

    return ZoneInfo(profile.timezone_name)
