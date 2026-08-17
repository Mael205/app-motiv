"""Ce que le rapport de fuite lit en base (SPEC §13.2).

Les sondes remontent des fenêtres — « scroll passif, 14 minutes, entre 19h05 et
19h35 ». On les étale sur des tranches de trente minutes, on cherche la
charnière, on convertit le total en sessions et en points de vie du boss.

**Ces données ne sortent jamais d'ici.** Le §13.2 le dit et le §4.7 le répète :
jamais dans le bilan de l'ami, jamais dans un export, jamais dans une
notification lisible sur écran verrouillé. Une fuite de temps envoyée à un tiers
est du bruit transformé en jugement social.

Une fenêtre sans horodatage — une sonde qui ne sait donner qu'un total du jour —
compte dans le coût mais pas dans l'histogramme : on ne sait pas *quand*, et
l'inventer déplacerait la charnière, c'est-à-dire la seule information utile.
"""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import Session, Signal
from .rules import leak
from .rules.seasons import DAMAGE_PER_MINUTE
from .rules.signals import AGENT, EXTENSION, MOBILE, SCROLL_PASSIF

# Le §13.2 : quatre semaines glissantes. Assez pour lisser les semaines
# atypiques, assez peu pour qu'un changement d'habitude s'y voie.
JOURS_OBSERVES = 28

# Ce qu'une session de 25 minutes retire au boss, pour la conversion du coût.
DEGATS_PAR_SESSION = 25 * DAMAGE_PER_MINUTE


def rapport(user, *, today: date | None = None) -> dict:
    """Le rapport complet. Local à l'utilisateur, et il le reste."""
    today = today or timezone.now().date()
    debut = today - timedelta(days=JOURS_OBSERVES - 1)
    zone = ZoneInfo(user.profile.timezone_name)

    signaux = list(
        Signal.objects.filter(
            user=user, category=SCROLL_PASSIF, day__gte=debut, day__lte=today
        )
    )

    fenetres = []
    for signal in signaux:
        if not (signal.started_at and signal.ended_at):
            continue
        debut_local = signal.started_at.astimezone(zone)
        fin_local = signal.ended_at.astimezone(zone)
        depart = debut_local.hour * 60 + debut_local.minute
        arrivee = fin_local.hour * 60 + fin_local.minute
        if arrivee <= depart:
            # Fenêtre à cheval sur minuit : on garde la part d'avant minuit. La
            # part d'après appartient à la journée du coach suivante et sera
            # remontée par une autre fenêtre.
            arrivee = 24 * 60
        fenetres.append((depart, arrivee, signal.minutes))

    tranches = leak.repartir(fenetres)
    pivot = leak.charniere(tranches)

    total = sum(s.minutes for s in signaux)
    semaine = sum(s.minutes for s in signaux if s.day > today - timedelta(days=7))

    return {
        "depuis": debut.isoformat(),
        "tranches": [{"debut": t.debut, "libelle": t.libelle, "minutes": t.minutes} for t in tranches],
        "charniere": (
            {"libelle": pivot.libelle, "minutes": pivot.minutes} if pivot else None
        ),
        "cout_semaine": _cout(user, semaine, today=today),
        "cout_total": _cout(user, total, today=today),
        "par_surface": _par_surface(signaux, today=today),
        "declencheurs": [
            {"quoi": d.quoi, "occurrences": d.occurrences, "part": d.part}
            for d in leak.declencheurs(_precedents(user, signaux, zone=zone))
        ],
        "sans_horodatage": sum(
            s.minutes for s in signaux if not (s.started_at and s.ended_at)
        ),
    }


def _cout(user, minutes: int, *, today: date) -> dict:
    from . import services

    saison = services.current_season(user, today=today)
    pv = saison.boss.max_hp if saison and hasattr(saison, "boss") else 0
    valeur = leak.cout(minutes, degats_par_session=DEGATS_PAR_SESSION, pv_du_boss=pv)
    return {
        "minutes": valeur.minutes,
        "sessions": valeur.sessions,
        "part_du_boss": valeur.part_du_boss,
        "phrase": valeur.phrase,
    }


def _par_surface(signaux: list[Signal], *, today: date) -> dict:
    """PC contre téléphone, sur deux semaines comparées.

    Le §13.2 veut cette comparaison visible : le scroll qui migre du PC vers le
    téléphone quand le blocage est armé est le contournement le plus probable,
    et sans elle le blocage se croit efficace à tort.
    """
    bascule = today - timedelta(days=7)

    def somme(sources: tuple[str, ...], *, recent: bool) -> int:
        return sum(
            s.minutes
            for s in signaux
            if s.source in sources and ((s.day > bascule) is recent)
        )

    pc = (AGENT, EXTENSION)
    return {
        "pc": {"semaine": somme(pc, recent=True), "avant": somme(pc, recent=False)},
        "mobile": {
            "semaine": somme((MOBILE,), recent=True),
            "avant": somme((MOBILE,), recent=False),
        },
    }


def _precedents(user, signaux: list[Signal], *, zone) -> list[str]:
    """Ce qui précède chaque décrochage du soir, en trois catégories seulement.

    Trois, parce que ce sont les trois que le système observe réellement (§13.2 :
    fin de session, retour à la maison, blocage déclaré). Le reste demanderait de
    savoir ce qui s'est passé hors de l'écran, et le §17 interdit d'aller le
    chercher.
    """
    sessions = list(
        Session.objects.filter(user=user, status=Session.DONE, ended_at__isnull=False)
    )
    fins = {}
    for session in sessions:
        fin = session.ended_at.astimezone(zone)
        fins.setdefault(session.coach_day, []).append(fin.hour * 60 + fin.minute)

    precedents = []
    for signal in signaux:
        if not signal.started_at:
            continue
        debut = signal.started_at.astimezone(zone)
        minute = debut.hour * 60 + debut.minute

        du_jour = fins.get(signal.day, [])
        juste_avant = [f for f in du_jour if 0 <= minute - f <= 30]

        if juste_avant:
            precedents.append("juste après une session")
        elif du_jour:
            precedents.append("après avoir déjà travaillé")
        else:
            precedents.append("avant toute session de la journée")

    return precedents
