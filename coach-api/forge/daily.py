"""Ce que le bilan quotidien lit en base (SPEC §13.1).

La logique est dans ``rules/daily``. Ici on ne fait que sortir quatre chiffres :
la fenêtre du soir, les minutes réellement travaillées, ce que les sondes ont vu
et le créneau prévu.

**Rien n'est stocké.** Le bilan se recalcule à la lecture, contrairement au
bilan hebdomadaire du §4.7 qui est figé parce qu'il part chez quelqu'un d'autre.
Celui-ci ne quitte pas la machine, et une sonde qui remonte ses minutes en
retard doit pouvoir corriger le tableau du matin plutôt que le laisser faux.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from .models import Profile, Session, Signal, TimeSlot
from .rules import daily
from .rules.calendar import evening_window


def du_jour(user, *, jour: date) -> daily.BilanDuJour:
    """Le bilan d'une journée du coach."""
    profile: Profile = user.profile
    fenetre = evening_window(jour, profile.windows_by_weekday(), profile.timezone_name)
    disponibles = int((fenetre.end - fenetre.start).total_seconds() // 60)

    travaillees = (
        Session.objects.filter(user=user, coach_day=jour, status=Session.DONE).aggregate(
            total=Sum("actual_minutes")
        )["total"]
        or 0
    )

    signaux = {
        row["category"]: row["minutes"] or 0
        for row in Signal.objects.filter(user=user, day=jour)
        .values("category")
        .annotate(minutes=Sum("minutes"))
    }

    creneau = TimeSlot.objects.filter(
        project__user=user, project__status="active", active=True, weekday=jour.weekday()
    ).exists()

    return daily.composer(
        disponibles=disponibles,
        travaillees=travaillees,
        signaux=signaux,
        creneau_prevu=creneau,
        creneau_tenu=creneau and travaillees > 0,
    )


def hier(user, *, now=None) -> tuple[date, daily.BilanDuJour]:
    """Le bilan de la journée qui vient de se terminer.

    « Hier » se compte en journées du coach : à 4h05 du matin, la journée qui
    vient de finir est celle de la veille au sens du §1, et c'est elle qu'on
    résume — pas les cinq minutes écoulées depuis la bascule.
    """
    from .rules.calendar import coach_day

    now = now or timezone.now()
    profile = user.profile
    jour = coach_day(now, profile.timezone_name, profile.day_rollover_hour) - timedelta(days=1)
    return jour, du_jour(user, jour=jour)
