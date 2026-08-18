"""La revue du dimanche (SPEC §5.3, §13.3).

Trois gestes, dans cet ordre : **ouvrir** avec les questions, **répondre** au fil
de la soirée ou pas du tout, **clore** avec le compte-rendu en trois blocs et le
contrat de la semaine suivante.

Ce qui rend la revue tenable est ce qu'elle ne demande pas. Elle arrive avec ses
constats (§13.5) et ses questions déjà écrites, quatre ou cinq, portant sur des
faits datés. Deux phrases suffisent à chacune. Et si le dialogue est esquivé,
elle se génère quand même **en le notant** — une revue qui attendrait les
réponses pour exister ne serait faite qu'une fois.

Le contrat proposé n'est jamais appliqué tout seul. Le §17 interdit qu'un
système baisse un engagement de lui-même, et le §11.1 ne l'autorise à décider
que de ce qu'on fait maintenant.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from . import detections, weekly
from .llm import LLMUnavailable, QualityGateFailed, Task, gate, get_provider
from .llm import prompts
from .models import Commitment, Project, Session, TimeSlot, WeeklyReview
from .rules import review as rules_review
from .rules.calendar import week_start

logger = logging.getLogger(__name__)

# Combien de semaines de recul pour proposer un engagement. Trois : assez pour
# lisser une semaine exceptionnelle, assez peu pour suivre un changement réel.
SEMAINES_OBSERVEES = 3


def ouvrir(user, *, semaine: date | None = None, now=None) -> WeeklyReview:
    """Crée la revue de la semaine et ses questions. Idempotent."""
    now = now or timezone.now()
    semaine = semaine or week_start(now.astimezone().date())

    existante = WeeklyReview.objects.filter(user=user, week_start=semaine).first()
    if existante:
        return existante

    constats = detections.toutes(user, today=semaine + timedelta(days=6))
    questions = rules_review.questions(
        creneaux_manques=_creneaux_manques(user, semaine=semaine),
        constats=[(d.constat, d.proposition) for d in constats],
        projets_avances=_minutes_par_projet(user, semaine=semaine),
    )

    return WeeklyReview.objects.create(
        user=user,
        week_start=semaine,
        questions=[{"fait": q.fait, "question": q.question, "reponse": ""} for q in questions],
        contract=[
            {
                "projet": ligne.projet,
                "actuel": ligne.actuel,
                "propose": ligne.propose,
                "raison": ligne.raison,
            }
            for ligne in rules_review.contrat(_lignes_de_contrat(user, semaine=semaine))
        ],
    )


def repondre(revue: WeeklyReview, *, index: int, texte: str) -> WeeklyReview:
    """Enregistre une réponse. Les questions restent modifiables tant que la revue est ouverte."""
    if revue.closed_at:
        raise ValueError("Cette revue est close.")
    if not 0 <= index < len(revue.questions):
        raise ValueError("Question inconnue.")

    revue.questions[index]["reponse"] = (texte or "").strip()[:2000]
    revue.save(update_fields=["questions"])
    return revue


def clore(revue: WeeklyReview) -> WeeklyReview:
    """Écrit le compte-rendu. Fonctionne avec ou sans réponses (§13.3)."""
    if revue.closed_at:
        return revue

    faits = weekly.collecter(revue.user, semaine=revue.week_start)
    constats = detections.toutes(revue.user, today=revue.week_start + timedelta(days=6))
    dialogue = revue.answered > 0

    blocs = _rediger(faits=faits, constats=constats, echanges=revue.questions)
    revue.report = rules_review.compte_rendu(dialogue=dialogue, **blocs)
    revue.closed_at = timezone.now()
    revue.save(update_fields=["report", "closed_at"])
    return revue


def appliquer_contrat(revue: WeeklyReview) -> list[dict]:
    """Applique le contrat proposé, sur un geste de l'utilisateur et jamais sans.

    Rend ce qui a changé. Les projets absents du contrat ne sont pas touchés :
    une revue ne range pas ce qu'elle n'a pas regardé.
    """
    changes = []
    for ligne in revue.contract:
        projet = Project.objects.filter(
            user=revue.user, name=ligne["projet"], status=Project.ACTIVE
        ).first()
        if not projet or projet.weekly_commitment == ligne["propose"]:
            continue
        avant = projet.weekly_commitment
        projet.weekly_commitment = ligne["propose"]
        projet.save(update_fields=["weekly_commitment"])
        changes.append({"projet": projet.name, "avant": avant, "apres": ligne["propose"]})

    revue.contract_applied_at = timezone.now()
    revue.save(update_fields=["contract_applied_at"])
    return changes


# --------------------------------------------------------------------------
# Le texte
# --------------------------------------------------------------------------

def _rediger(*, faits: dict, constats: list, echanges: list[dict]) -> dict:
    """Les trois blocs. Le modèle d'abord, le déterministe s'il manque ou dérape."""
    try:
        reponse = get_provider().structured(
            task=Task.REVUE_HEBDO,
            system=prompts.SYSTEM_REVUE,
            prompt=prompts.revue_prompt(
                faits=faits, constats=[d.constat for d in constats], echanges=echanges
            ),
            schema=prompts.SCHEMA_REVUE,
        )
    except LLMUnavailable as erreur:
        logger.info("revue sans IA : %s", erreur)
        return _blocs_deterministes(faits, constats)

    if reponse.refused:
        return _blocs_deterministes(faits, constats)

    payload = reponse.content if isinstance(reponse.content, dict) else {}
    try:
        return gate(Task.REVUE_HEBDO, payload)
    except QualityGateFailed as erreur:
        logger.warning("revue refusée par la porte : %s", erreur.reason)
        return _blocs_deterministes(faits, constats)


def _blocs_deterministes(faits: dict, constats: list) -> dict:
    """Une revue sans modèle : moins fine, et elle a lieu.

    Elle ne cherche pas de cause — elle n'en a pas les moyens, et en inventer
    une serait pire que de s'en passer. Elle dit les chiffres, le premier
    constat, et reprend sa proposition comme seule chose à changer : c'est déjà
    un geste précis, puisque le §13.5 les écrit chiffrés.
    """
    projets = faits["projets"]
    if projets:
        meilleur = max(projets, key=lambda p: p["minutes"])
        a_marche = (
            f"{meilleur['nom']} a avancé de {meilleur['minutes']} minutes "
            f"en {meilleur['sessions']} session(s)."
        )
    else:
        a_marche = "Aucune session cette semaine."

    manques = [e for e in faits["engagements"] if not e["ok"]]
    n_a_pas_marche = (
        " ".join(f"{e['nom']} : {e['tenus']} sur {e['pris']}." for e in manques)
        or "Tous les engagements de la semaine sont tenus."
    )

    seule = constats[0].proposition if constats else "Garder le même contrat une semaine de plus."

    return {"a_marche": a_marche, "n_a_pas_marche": n_a_pas_marche, "seule_chose": seule}


# --------------------------------------------------------------------------
# Les chiffres
# --------------------------------------------------------------------------

# Quatre semaines : assez loin pour avoir oublié, assez près pour que le projet
# existe encore. À trois mois, on relit quelqu'un d'autre.
RECUL_RAPPEL = 28


def il_y_a_quatre_semaines(user, *, semaine: date) -> dict | None:
    """Une entrée de journal d'il y a un mois, ressortie dans la revue.

    C'est le seul endroit du produit qui regarde en arrière **sans compter**.
    Les bilans mesurent, les détections comparent, la trace additionne : tout
    cela dit combien. Une note écrite il y a quatre semaines dit *ce qu'on
    faisait*, et c'est la seule chose qui rende visible qu'un projet a avancé —
    une roadmap à 60 % ne se souvient pas d'avoir été à 20 %.

    Elle sort telle quelle, sans commentaire. Le §17 interdit au système de
    juger, et « regarde le chemin parcouru » est un jugement, même flatteur.

    L'entrée la plus proche du jour visé est choisie dans une fenêtre de trois
    jours : la note d'il y a exactement 28 jours n'existe pas toujours, et
    renoncer pour trois jours d'écart reviendrait à n'afficher ce bloc qu'une
    semaine sur deux.
    """
    from .models import JournalEntry

    vise = semaine - timedelta(days=RECUL_RAPPEL)
    entrees = list(
        JournalEntry.objects.filter(
            session__user=user,
            session__coach_day__gte=vise - timedelta(days=3),
            session__coach_day__lte=vise + timedelta(days=3),
        )
        .exclude(raw_note="")
        .select_related("session", "session__project")
    )
    if not entrees:
        return None

    entree = min(entrees, key=lambda e: abs((e.session.coach_day - vise).days))
    return {
        "day": entree.session.coach_day.isoformat(),
        "project": entree.session.project.name,
        "color": entree.session.project.color,
        "note": entree.raw_note,
        "next_action": entree.next_action,
    }


def _creneaux_manques(user, *, semaine: date) -> list[tuple[int, str]]:
    """Les rendez-vous fixes de la semaine sans session ce jour-là.

    Les meilleures questions de la revue : un créneau manqué est un fait daté,
    et on s'en souvient. « Comment s'est passée ta semaine » n'obtient rien ;
    « mardi 20h30, rien » obtient une vraie réponse.
    """
    jours_avec_session = {
        (row["coach_day"], row["project__name"])
        for row in Session.objects.filter(
            user=user,
            status=Session.DONE,
            coach_day__gte=semaine,
            coach_day__lte=semaine + timedelta(days=6),
        ).values("coach_day", "project__name")
    }

    manques = []
    for slot in TimeSlot.objects.filter(
        project__user=user, project__status=Project.ACTIVE, active=True
    ).select_related("project"):
        jour = semaine + timedelta(days=slot.weekday)
        if (jour, slot.project.name) not in jours_avec_session:
            manques.append((slot.weekday, slot.project.name))
    return manques


def _minutes_par_projet(user, *, semaine: date) -> list[tuple[str, int]]:
    return [
        (row["project__name"], row["minutes"] or 0)
        for row in Session.objects.filter(
            user=user,
            status=Session.DONE,
            coach_day__gte=semaine,
            coach_day__lte=semaine + timedelta(days=6),
        )
        .values("project__name")
        .annotate(minutes=Sum("actual_minutes"), n=Count("id"))
    ]


def _lignes_de_contrat(user, *, semaine: date) -> list[tuple[str, int, list[int]]]:
    lignes = []
    for projet in Project.objects.filter(user=user, status=Project.ACTIVE):
        faites = [
            c.done_sessions
            for c in Commitment.objects.filter(project=projet, week_start__lte=semaine)[
                :SEMAINES_OBSERVEES
            ]
        ]
        lignes.append((projet.name, projet.weekly_commitment, faites))
    return lignes
