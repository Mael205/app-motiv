"""Le briefing et le debrief (SPEC §5.1, §5.2).

Ces deux services sont les seuls endroits où un modèle parle à l'utilisateur.
Ils partagent une architecture, et elle tient en une phrase :

    **Le déterministe décide d'abord ; le modèle n'a le droit que d'améliorer.**

Le serveur calcule sa proposition sans IA, exactement comme avant. Puis il
demande au modèle s'il ferait mieux. Si le modèle est injoignable, lent, ou
rend une réponse que la porte refuse, l'utilisateur voit la proposition
déterministe et ne sait même pas qu'il y a eu une tentative. Le §0.9 est
respecté dans tous les cas, parce que dans tous les cas il y a **une** action
déjà décidée à l'écran.

C'est l'inverse de l'architecture habituelle, où l'IA est le chemin principal et
le repli une dégradation. Ici l'IA est un supplément, et c'est voulu : un soir
de fatigue, une app qui affiche « le service est indisponible » est une app
qu'on referme. Le prix de ce choix est que l'IA apporte moins ; le bénéfice est
qu'elle ne peut rien casser.

**Ce que le modèle n'a pas le droit de faire, quoi qu'il réponde.** Il ne choisit
jamais un identifiant : il nomme un projet, et le serveur retrouve l'objet par
ce nom parmi les projets réellement actifs. Un nom inconnu est une hallucination
et fait tomber le briefing sur le repli. Aucune réponse de modèle ne devient
une écriture en base sans passer par un geste de l'utilisateur.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.db.models import Count, Max
from django.utils import timezone

from . import services
from .llm import LLMUnavailable, QualityGateFailed, Task, gate, get_provider
from .llm import prompts
from .models import JournalEntry, Profile, Project, Session, Track
from .rules.calendar import coach_day, evening_window, week_start

logger = logging.getLogger(__name__)

# Origine d'un briefing. Affichée à l'utilisateur : savoir qui a décidé fait
# partie de la confiance qu'on peut accorder à l'écran.
SOURCE_MODELE = "modele"
SOURCE_DETERMINISTE = "deterministe"


# --------------------------------------------------------------------------
# Le contexte du soir
# --------------------------------------------------------------------------

def _projects_context(user, *, today: date) -> list[dict]:
    """Les faits sur chaque projet actif de l'Atelier, tels quels.

    Aucun jugement n'est porté ici : le modèle reçoit les mêmes chiffres que
    ceux qui ont servi au calcul déterministe, pour qu'un désaccord entre les
    deux soit un désaccord d'appréciation et non d'information.
    """
    projets = list(
        Project.objects.filter(user=user, status=Project.ACTIVE, track__kind=Track.ATELIER)
        .exclude(is_coach_project=True)
        .select_related("track")
        .prefetch_related("steps", "timeslots")
    )
    if not projets:
        return []

    semaine = week_start(today)
    faites = {
        row["project"]: row["n"]
        for row in Session.objects.filter(
            user=user, status=Session.DONE, coach_day__gte=semaine, coach_day__lte=today
        )
        .values("project")
        .annotate(n=Count("id"))
    }
    vues = {
        row["project"]: row["last"]
        for row in Session.objects.filter(user=user, status=Session.DONE)
        .values("project")
        .annotate(last=Max("coach_day"))
    }
    amorces = {
        row["session__project"]: row["next_action"]
        for row in JournalEntry.objects.filter(session__project__in=projets)
        .exclude(next_action="")
        .order_by("session__project", "-created_at")
        .values("session__project", "next_action")
    }

    contexte = []
    for projet in projets:
        creneau = next(
            (ts for ts in projet.timeslots.all() if ts.weekday == today.weekday() and ts.active),
            None,
        )
        etape = projet.current_step
        derniere = vues.get(projet.id)
        contexte.append(
            {
                "nom": projet.name,
                "domaine": projet.domain,
                "faites": faites.get(projet.id, 0),
                "engagement": projet.weekly_commitment,
                "derniere": (
                    f"il y a {(today - derniere).days} jour(s)" if derniere else "jamais"
                ),
                "creneau": (
                    f"{creneau.start_time.strftime('%Hh%M')}, {creneau.duration_minutes} min"
                    if creneau
                    else ""
                ),
                "etape": etape.label if etape else "",
                "amorce": amorces.get(projet.id, ""),
            }
        )
    return contexte


def _evening_context(user, *, now: datetime, today: date) -> dict:
    profile: Profile = user.profile
    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    etat = services.streak_state(user, atelier, today=today)
    saison = services.current_season(user, today=today)
    fenetre = evening_window(today, profile.windows_by_weekday(), profile.timezone_name)

    boss = ""
    if saison and hasattr(saison, "boss"):
        b = saison.boss
        boss = f"{b.name}, {b.current_hp} points de vie restants sur {b.max_hp}"

    return {
        "heure": now.astimezone(ZoneInfo(profile.timezone_name)).strftime("%Hh%M"),
        "jour": today.isoformat(),
        "streak": etat.current,
        "sessions_aujourdhui": Session.objects.filter(
            user=user, coach_day=today, status=Session.DONE
        ).count(),
        "fenetre": f"{fenetre.start.strftime('%Hh%M')} – {fenetre.end.strftime('%Hh%M')}",
        "boss": boss,
    }


# --------------------------------------------------------------------------
# Briefing (§5.1)
# --------------------------------------------------------------------------

def briefing(user, *, now: datetime | None = None) -> dict | None:
    """Ce qu'on fait maintenant. Rend ``None`` s'il n'y a aucun projet à proposer.

    Le résultat a toujours la forme de la proposition déterministe, enrichie de
    ``source`` et, quand le modèle n'a pas servi, de ``ai_note`` qui dit
    pourquoi. Le client affiche la même chose dans les deux cas.
    """
    now = now or timezone.now()
    profile: Profile = user.profile
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    repli = services.propose(user, today=today)
    if repli is None:
        # Aucun projet actif : il n'y a rien à décider, et surtout rien qu'un
        # modèle puisse inventer pour combler le vide.
        return None

    repli = {**repli, "source": SOURCE_DETERMINISTE, "ai_note": ""}

    projets = _projects_context(user, today=today)
    if not projets:
        return repli

    contexte = {
        **_evening_context(user, now=now, today=today),
        "projets": projets,
        "repli": f"{repli['project']['name']} — {repli['minutes']} min — {repli['reason']}",
    }

    try:
        reponse = get_provider().structured(
            task=Task.BRIEFING,
            system=prompts.SYSTEM_BRIEFING,
            prompt=prompts.briefing_prompt(contexte),
            schema=prompts.SCHEMA_BRIEFING,
        )
    except LLMUnavailable as error:
        logger.info("briefing sans IA : %s", error)
        return {**repli, "ai_note": str(error)}

    if reponse.refused:
        return {**repli, "ai_note": "le modèle a décliné la demande"}

    payload = reponse.content if isinstance(reponse.content, dict) else {}
    connus = {p["nom"] for p in projets}

    try:
        valide = gate(Task.BRIEFING, payload, projets_connus=connus)
    except QualityGateFailed as error:
        # Journalisé au niveau warning, à dessein : une porte qui refuse souvent
        # est un prompt à corriger, et ça ne se voit que dans les journaux.
        logger.warning("briefing refusé par la porte : %s", error.reason)
        return {**repli, "ai_note": f"réponse du modèle refusée : {error.reason}"}

    projet = next(
        (p for p in Project.objects.filter(user=user, status=Project.ACTIVE) if p.name == valide["projet"]),
        None,
    )
    if projet is None:  # pragma: no cover - la porte l'a déjà vérifié
        return {**repli, "ai_note": "projet du modèle introuvable en base"}

    etape = projet.current_step
    return {
        "project": {
            "id": projet.id,
            "name": projet.name,
            "color": projet.color,
            "emblem": projet.emblem,
            "completion": projet.completion,
        },
        "minutes": valide["minutes"],
        "step": (
            {"id": etape.id, "label": etape.label, "needs_split": etape.needs_split}
            if etape
            else None
        ),
        "amorce": valide["tache"],
        "reason": valide["pourquoi"] or repli["reason"],
        "definition_de_fini": valide["definition_de_fini"],
        "source": SOURCE_MODELE,
        "model": reponse.model,
        "ai_note": "",
        "usage": {
            "input_tokens": reponse.usage.input_tokens,
            "output_tokens": reponse.usage.output_tokens,
            "cache_read_tokens": reponse.usage.cache_read_tokens,
        },
    }


# --------------------------------------------------------------------------
# Debrief (§5.2)
# --------------------------------------------------------------------------

def debrief(session: Session, *, note: str) -> dict:
    """Structure des notes brutes en résumé, amorce et blocages.

    **Ne clôture rien et n'écrit rien.** C'est une suggestion, que le client
    pré-remplit dans le champ d'amorce et que l'utilisateur valide ou corrige.
    Le §11.3 veut que l'amorce soit payée pendant que le contexte est chaud :
    la faire écrire par un modèle sans relecture viderait l'exercice de son
    sens, et laisserait passer une amorce que personne n'a comprise.
    """
    note = (note or "").strip()
    if not note:
        return {
            "resume": "",
            "amorce": "",
            "blocages": [],
            "source": SOURCE_DETERMINISTE,
            "ai_note": "aucune note à structurer",
        }

    etape = session.project.current_step

    try:
        reponse = get_provider().structured(
            task=Task.DEBRIEF,
            system=prompts.SYSTEM_DEBRIEF,
            prompt=prompts.debrief_prompt(
                projet=session.project.name,
                etape=etape.label if etape else "",
                minutes=session.actual_minutes,
                note=note,
            ),
            schema=prompts.SCHEMA_DEBRIEF,
        )
    except LLMUnavailable as error:
        logger.info("debrief sans IA : %s", error)
        return _debrief_brut(note, str(error))

    if reponse.refused:
        return _debrief_brut(note, "le modèle a décliné la demande")

    payload = reponse.content if isinstance(reponse.content, dict) else {}
    try:
        valide = gate(Task.DEBRIEF, payload)
    except QualityGateFailed as error:
        logger.warning("debrief refusé par la porte : %s", error.reason)
        return _debrief_brut(note, f"réponse du modèle refusée : {error.reason}")

    return {
        **valide,
        "source": SOURCE_MODELE,
        "model": reponse.model,
        "ai_note": "",
    }


def _debrief_brut(note: str, raison: str) -> dict:
    """Le repli : on rend la note telle quelle, et surtout **pas d'amorce**.

    Inventer une amorce sans modèle serait pire que de n'en pas donner : elle
    serait fausse, l'utilisateur la validerait par réflexe, et la prochaine
    session démarrerait sur une consigne que personne n'a écrite. Le champ reste
    vide, et le §11.3 continue d'exiger que l'utilisateur le remplisse.
    """
    return {
        "resume": note,
        "amorce": "",
        "blocages": [],
        "source": SOURCE_DETERMINISTE,
        "ai_note": raison,
    }
