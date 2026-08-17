"""Le briefing, le debrief et l'entretien de projet (SPEC §5.1, §5.2, §4.5).

Les seuls endroits où un modèle parle à l'utilisateur. Le briefing et le debrief
partagent une architecture, et elle tient en une phrase :

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

**L'entretien de projet est la seule exception à l'architecture ci-dessus**, et
il faut le dire franchement : il n'a pas de repli. Aucun algorithme ne sait
interroger quelqu'un sur son projet, et prétendre le contraire produirait un
questionnaire à cases qui donne exactement les roadmaps floues que le §4.5
traite comme des défauts. Quand le modèle manque, l'utilisateur est renvoyé vers
le collage de markdown — qui, lui, marche sans IA et produit le même résultat
par le même parseur.
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
from .models import JournalEntry, Profile, Project, ProjectInterview, Session, Track
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
# Gardien du soir (§5.4)
# --------------------------------------------------------------------------

def tache_du_gardien(proposition: dict, *, minutes_restantes: int) -> dict:
    """Le geste de dix minutes annoncé par le gardien du soir.

    Prend la proposition déjà calculée par ``services.propose`` — le choix du
    projet reste déterministe, et le modèle n'a pas à le rejuger — et cherche à
    en tirer un morceau qui tienne vraiment en dix minutes.

    C'est le défaut connu du gardien déterministe : il reprend l'amorce ou le
    libellé de l'étape, qui sont dimensionnés pour une à trois séances de
    vingt-cinq minutes. Annoncer dix minutes pour un travail qui en demande
    quatre-vingts est une promesse fausse, et le soir où elle est lue, elle sert
    de raison de ne pas commencer.

    Rend toujours un dictionnaire : ``texte`` est la tâche à afficher, ``source``
    dit qui l'a écrite, ``ai_note`` pourquoi le modèle n'a pas servi. L'appelant
    n'a aucun cas d'échec à traiter — un gardien qui ne part pas est un gardien
    qui n'existe pas (§5.4). ``texte`` peut être vide quand le projet n'a ni
    étape ouverte ni amorce et que le modèle manque : il n'y a alors rien à dire
    de plus précis que le nom du projet, et l'inventer serait pire.
    """
    projet = proposition["project"]["name"]
    etape = proposition["step"]["label"] if proposition.get("step") else ""
    amorce = proposition.get("amorce") or ""
    repli = amorce or etape

    # Le §5.2 veut qu'un blocage soit réinjecté au démarrage suivant. Le gardien
    # est ce démarrage-là les soirs où il n'y en a pas eu d'autre : buter deux
    # fois sur la même chose à 21h30 est le meilleur moyen de refermer l'app.
    derniere = (
        JournalEntry.objects.filter(session__project_id=proposition["project"]["id"])
        .exclude(blockers=[])
        .order_by("-created_at")
        .values_list("blockers", flat=True)
        .first()
    )
    blocages = [b for b in (derniere or []) if isinstance(b, str)]

    secours = {"texte": repli, "source": SOURCE_DETERMINISTE, "ai_note": ""}

    try:
        reponse = get_provider().structured(
            task=Task.GARDIEN,
            system=prompts.SYSTEM_GARDIEN,
            prompt=prompts.gardien_prompt(
                {
                    "projet": projet,
                    "etape": etape,
                    "amorce": amorce,
                    "blocages": blocages,
                    "minutes_restantes": minutes_restantes,
                    "repli": repli,
                }
            ),
            schema=prompts.SCHEMA_GARDIEN,
        )
    except LLMUnavailable as error:
        logger.info("gardien sans IA : %s", error)
        return {**secours, "ai_note": str(error)}

    if reponse.refused:
        return {**secours, "ai_note": "le modèle a décliné la demande"}

    payload = reponse.content if isinstance(reponse.content, dict) else {}

    try:
        valide = gate(Task.GARDIEN, payload)
    except QualityGateFailed as error:
        logger.warning("gardien refusé par la porte : %s", error.reason)
        return {**secours, "ai_note": f"réponse du modèle refusée : {error.reason}"}

    return {"texte": valide["tache"], "source": SOURCE_MODELE, "ai_note": ""}


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


# --------------------------------------------------------------------------
# Entretien de projet (§4.5)
# --------------------------------------------------------------------------

# Au-delà, on arrête d'interroger. Le prompt vise trois à sept questions ; cette
# borne n'est pas la consigne, c'est le garde-fou du cas où le modèle tourne en
# rond. Un entretien qui dure plus longtemps que la session qu'il devait lancer
# a échoué, même s'il finit par produire une bonne roadmap.
MAX_QUESTIONS = 10

# Un refus de la porte vaut une reprise, motif à l'appui. Trois essais, et pas
# deux : un essai réel sur une roadmap trop longue a montré une convergence
# progressive — 34 étapes, puis 17 — là où deux tours s'arrêtaient juste avant
# d'aboutir. Au-delà de trois en revanche, on fait attendre quelqu'un devant un
# écran pour un modèle qui ne corrigera plus.
MAX_ESSAIS = 3


class InterviewUnavailable(Exception):
    """L'entretien ne peut pas avoir lieu — pas de modèle joignable.

    Distincte de ``LLMUnavailable`` pour une raison de produit : ici il n'y a
    **pas de repli déterministe**. Un briefing raté retombe sur un calcul ; un
    entretien raté ne retombe sur rien, parce qu'aucun algorithme ne sait
    interroger quelqu'un sur son projet. L'appelant doit donc renvoyer
    l'utilisateur vers le collage de markdown, qui lui marche sans IA.
    """


def _projets_existants(user) -> list[str]:
    return [
        f"{p.name} ({p.get_domain_display()})"
        for p in Project.objects.filter(user=user).exclude(status=Project.ARCHIVED)
    ]


def _tour(interview, *, reproche: str = "", essai: int = 1) -> dict:
    """Un tour d'entretien : rejoue l'échange, valide, et range le résultat.

    **Un refus de la porte donne droit à une seconde tentative**, et le motif
    est renvoyé au modèle. C'est la différence importante avec le briefing : là
    -bas un refus retombe sur un calcul déterministe, ici il ne retombe sur
    rien, et abandonner la création d'un projet parce qu'une question était mal
    tournée serait absurde. Dire au modèle ce qu'on lui reproche coûte un aller
    -retour et corrige la plupart des écarts du premier coup.

    Une seule reprise, cependant. Un modèle qui échoue deux fois de suite sur le
    même reproche ne le corrigera pas au troisième essai, et l'utilisateur
    attend devant un écran.
    """
    prompt = prompts.entretien_prompt(
        interview.messages, projets_existants=_projets_existants(interview.user)
    )
    if reproche:
        prompt += (
            f"\n\nTa réponse précédente a été refusée : {reproche}. "
            "Corrige exactement ce point et réponds à nouveau."
        )

    try:
        reponse = get_provider().structured(
            task=Task.ENTRETIEN_PROJET,
            system=prompts.SYSTEM_ENTRETIEN,
            prompt=prompt,
            schema=prompts.SCHEMA_ENTRETIEN,
        )
    except LLMUnavailable as error:
        raise InterviewUnavailable(str(error)) from error

    if reponse.refused:
        raise InterviewUnavailable("le modèle a décliné la demande")

    payload = reponse.content if isinstance(reponse.content, dict) else {}
    try:
        valide = gate(Task.ENTRETIEN_PROJET, payload)
    except QualityGateFailed as error:
        logger.warning("entretien refusé par la porte (essai %s) : %s", essai, error.reason)
        if essai < MAX_ESSAIS:
            return _tour(interview, reproche=error.reason, essai=essai + 1)
        # Contrairement au briefing, on ne masque pas : sans repli, taire le
        # motif laisserait l'utilisateur devant un écran figé sans rien à faire.
        raise InterviewUnavailable(f"réponse du modèle refusée : {error.reason}") from error

    if valide["fini"]:
        interview.markdown = valide["markdown"]
        interview.status = interview.PROPOSE
    else:
        interview.messages = [
            *interview.messages,
            {"role": "assistant", "content": valide["question"]},
        ]

    interview.save()
    return _payload(interview)


def _payload(interview) -> dict:
    """Ce que le client affiche. Le markdown n'est rendu qu'une fois proposé."""
    return {
        "id": interview.id,
        "status": interview.status,
        "messages": interview.messages,
        "markdown": interview.markdown,
        "questions_posees": interview.questions_posees,
        "max_questions": MAX_QUESTIONS,
    }


def interview_start(user) -> dict:
    """Ouvre un entretien et pose la première question."""
    interview = ProjectInterview.objects.create(user=user)
    return _tour(interview)


def interview_reply(interview, *, answer: str) -> dict:
    """Enregistre une réponse et rend le tour suivant.

    La réponse de l'utilisateur est écrite **avant** l'appel au modèle : si le
    modèle échoue, ce qu'on vient de taper n'est pas perdu, et réessayer reprend
    l'entretien là où il en était plutôt qu'au début.
    """
    answer = (answer or "").strip()
    if not answer:
        raise ValueError("Une réponse vide ne fait pas avancer l'entretien.")
    if interview.status != interview.EN_COURS:
        raise ValueError("Cet entretien est terminé.")

    interview.messages = [*interview.messages, {"role": "user", "content": answer}]
    interview.save(update_fields=["messages", "updated_at"])

    if interview.questions_posees >= MAX_QUESTIONS:
        # On force la conclusion plutôt que d'abandonner : le modèle a de quoi
        # écrire quelque chose, et une roadmap perfectible se corrige à l'écran
        # de confirmation, alors qu'un entretien abandonné se refait en entier.
        interview.messages = [
            *interview.messages,
            {
                "role": "user",
                "content": (
                    "Assez de questions. Rends maintenant la roadmap au format "
                    "demandé, avec ce que tu sais."
                ),
            },
        ]
        interview.save(update_fields=["messages", "updated_at"])

    return _tour(interview)


def interview_import(interview) -> "Project":
    """Crée le projet depuis la roadmap proposée, et lie l'entretien.

    Passe par ``create_project_from_markdown``, donc par le même parseur, les
    mêmes règles de slot et les mêmes avertissements que le collage manuel. Le
    chemin de l'IA n'a aucun privilège sur celui qu'on emprunte sans elle.
    """
    if interview.status != interview.PROPOSE:
        raise ValueError("Aucune roadmap à importer pour cet entretien.")

    projet = services.create_project_from_markdown(interview.user, interview.markdown)
    interview.project = projet
    interview.status = interview.IMPORTE
    interview.save(update_fields=["project", "status", "updated_at"])
    return projet
