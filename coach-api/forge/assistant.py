"""L'assistant qui agit sur l'app (§5 étendu, ajout du 18 août 2026).

Un fil de discussion où l'on demande des choses en français — « fusionne mes
deux routines du matin », « découpe l'étape de collision en trois », « passe
Bestiaire à deux sessions par semaine » — et où l'assistant répond par des
**actions proposées**, chacune avec son avant/après et son bouton.

## Le tour, de bout en bout

1. la demande est écrite en base **avant** l'appel au modèle. Si le modèle
   échoue, ce qu'on vient de taper n'est pas perdu ;
2. le serveur assemble l'état réel de l'app — projets, étapes, routines,
   créneaux, saison, réglages — et le catalogue des actions ;
3. le modèle rend un texte court et une liste d'actions, contraintes par une
   énumération dans le schéma : il ne peut pas nommer un verbe inexistant ;
4. la porte refuse le faux accompli, le ton, et toute clé hors catalogue ;
5. chaque action est **résolue** contre l'état réel : les noms deviennent des
   objets, les règles métier s'appliquent, l'aperçu se calcule. Une action qui
   ne passe pas est rangée refusée, avec sa phrase — pas supprimée, parce que
   savoir ce que l'assistant a *voulu* faire vaut mieux qu'un silence ;
6. rien n'est écrit. L'écriture attend ``appliquer``.

## Pourquoi il n'y a pas d'outils au sens API

Le protocole des fournisseurs prévoit ``converse`` avec des outils, et ce
serait le chemin habituel. Deux raisons de ne pas le prendre.

Le backend par défaut — le CLI, celui qui consomme l'abonnement déjà payé —
refuse de prêter des outils au modèle, et c'est un choix de sécurité (§8) qu'il
ne faut pas contourner par la bande. Un assistant qui ne marcherait que sur le
backend facturé à la clé serait un assistant qu'on n'utilise pas.

Et surtout : un outil, ça s'exécute. Un schéma structuré, ça se propose. La
forme technique dit la même chose que le produit, ce qui est la meilleure
garantie qu'elles ne divergeront pas.
"""

from __future__ import annotations

import logging
from datetime import date

from django.db import transaction
from django.utils import timezone

from . import actions as executeurs
from . import services
from .llm import LLMUnavailable, QualityGateFailed, Task, gate, get_provider
from .llm import prompts
from .models import (
    Conversation,
    ConversationTurn,
    ProposedAction,
    Project,
    RoadmapStep,
    Routine,
)
from .rules import actions as catalogue
from .rules import routines as routine_rules

logger = logging.getLogger(__name__)

# Combien de tours de conversation sont renvoyés au modèle. Au-delà, le contexte
# coûte plus qu'il n'apporte : une demande d'il y a vingt messages ne décrit
# plus l'app telle qu'elle est, et l'état joint à chaque tour, lui, est frais.
MEMOIRE = 12


class AssistantIndisponible(Exception):
    """Le modèle manque ou a rendu une réponse inutilisable.

    Il n'y a pas de repli déterministe ici, et c'est assumé — comme pour
    l'entretien de projet (§4.5). Aucun algorithme ne comprend « fusionne mes
    deux routines du matin ». Sans modèle, l'écran le dit et renvoie vers les
    écrans qui, eux, marchent sans IA.
    """


# --------------------------------------------------------------------------
# L'état envoyé au modèle
# --------------------------------------------------------------------------

def etat_pour_le_modele(user, *, today: date) -> str:
    """Tout ce sur quoi l'assistant a le droit d'agir, en texte lisible.

    En texte et non en JSON : le modèle lit mieux des phrases, et surtout un
    texte se relit à l'œil quand une réponse surprend. Le JSON serait plus
    compact et strictement moins utile — ce n'est pas une API, c'est un
    briefing.

    **Aucune donnée qui ne serve pas une action.** Pas de journal, pas de notes
    de session, pas d'historique de streak : l'assistant n'a rien à en faire, et
    tout ce qui entre ici part chez un fournisseur.
    """
    lignes: list[str] = []

    lignes.append(f"Aujourd'hui : {today:%A %d %B %Y} (journée du coach).")

    saison = services.current_season(user, today=today)
    if saison:
        contrat = services.season_contract(user, saison)
        lignes.append(
            f"Saison {saison.index} « {saison.name} », jour {saison.day_index(today) + 1}, "
            f"{saison.days_left(today)} jours restants. "
            + (
                f"Contrat signé : {contrat['sessions_per_week']}/semaine."
                if contrat
                else "Contrat non signé."
            )
        )
    else:
        lignes.append("Aucune saison en cours.")

    veille = services.veille_en_cours(user, today=today)
    if veille:
        lignes.append(f"En veille jusqu'au {veille.ends_on:%d/%m}.")

    en_attente = services.projects_on_hold(user, day=today)
    lignes.append("\nPROJETS")
    projets = (
        Project.objects.filter(user=user)
        .exclude(status=Project.ARCHIVED)
        .prefetch_related("steps", "timeslots")
    )
    if not projets:
        lignes.append("  aucun.")
    for projet in projets:
        etat = "frigo" if projet.status == Project.FRIDGE else f"slot {projet.slot or '—'}"
        if projet.id in en_attente:
            etat += ", en attente déclarée"
        lignes.append(
            f"  {projet.name} — {etat}, domaine {projet.domain}, "
            f"branche {projet.branch or '—'}, preuve {projet.verification}, "
            f"{projet.weekly_commitment} sessions/semaine, {projet.emblem} {projet.color}"
        )
        ouvertes = [e for e in projet.steps.all() if e.state != RoadmapStep.DONE]
        for etape in ouvertes:
            marque = "en cours" if etape.state == RoadmapStep.DOING else "à faire"
            lignes.append(
                f"      étape « {etape.label} » — {marque}, "
                f"{etape.estimated_sessions} session(s) estimée(s)"
            )
        if not ouvertes:
            lignes.append("      aucune étape ouverte")
        for creneau in projet.timeslots.all():
            if creneau.active:
                lignes.append(
                    f"      créneau {executeurs.JOURS[creneau.weekday]} "
                    f"{creneau.start_time:%H:%M} — {creneau.duration_minutes} min"
                )

    lignes.append("\nENTRETIEN (routines)")
    routines = Routine.objects.filter(user=user, active=True)
    if not routines:
        lignes.append("  aucune.")
    for routine in routines:
        ancrage = routine_rules.ANCHOR_LABELS.get(routine.anchor, routine.anchor)
        lignes.append(
            f"  {routine.name} — {ancrage}, "
            f"{executeurs.dire_jours(list(routine.weekdays or []))}, "
            f"{routine.weekly_target}×/semaine"
        )

    profil = user.profile
    fenetres = ", ".join(
        f"{executeurs.JOURS[f.weekday][:3]} {f.start_time:%H:%M}–{f.end_time:%H:%M}"
        for f in profil.windows.all().order_by("weekday")
    )
    lignes.append("\nRÉGLAGES")
    lignes.append(f"  fenêtre du soir : {fenetres or 'aucune'}")
    lignes.append(f"  fuseau : {profil.timezone_name}, bascule à {profil.day_rollover_hour}h")
    lignes.append(
        f"  gardien : {profil.guardian_minutes_before_end} min avant la fin de la fenêtre"
    )
    lignes.append(
        "  rappel du matin : "
        + (f"{profil.morning_hour}h" if profil.morning_hour is not None else "coupé")
    )

    return "\n".join(lignes)


def catalogue_pour_le_modele() -> str:
    """Le catalogue, groupé par domaine, avec les paramètres de chaque verbe."""
    lignes: list[str] = []
    for domaine, label in catalogue.DOMAINE_LABELS.items():
        verbes = [a for a in catalogue.CATALOGUE if a.domaine == domaine]
        if not verbes:
            continue
        lignes.append(f"\n{label.upper()}")
        for action in verbes:
            params = ", ".join(
                f"{p.nom}{'' if p.requis else '?'} ({p.type})" for p in action.params
            )
            lignes.append(f"  {action.cle} — {action.quoi}")
            if params:
                lignes.append(f"      paramètres : {params}")
            for param in action.params:
                if param.description:
                    lignes.append(f"        {param.nom} : {param.description}")
    return "\n".join(lignes).strip()


# --------------------------------------------------------------------------
# Le fil
# --------------------------------------------------------------------------

def fil_ouvert(user) -> Conversation:
    """Le fil en cours, ou un neuf. Un seul à la fois (voir le modèle)."""
    fil = Conversation.objects.filter(user=user, closed_at__isnull=True).first()
    return fil or Conversation.objects.create(user=user)


def fermer(user) -> Conversation:
    """Clôt le fil courant. Les actions encore en attente deviennent caduques.

    Une proposition qui survivrait à sa conversation serait un bouton sans
    contexte : on ne saurait plus à quelle demande elle répondait, et
    l'appliquer serait un pari.
    """
    fil = Conversation.objects.filter(user=user, closed_at__isnull=True).first()
    if fil is None:
        return Conversation.objects.create(user=user)

    ProposedAction.objects.filter(
        turn__conversation=fil, state=ProposedAction.EN_ATTENTE
    ).update(state=ProposedAction.PERIMEE, detail="Le fil a été fermé.")
    fil.closed_at = timezone.now()
    fil.save(update_fields=["closed_at"])
    return Conversation.objects.create(user=user)


def parler(user, texte: str, *, today: date) -> dict:
    """Un tour complet. Rien n'est appliqué ici, quoi que dise le modèle.

    **Volontairement pas dans une seule transaction.** La demande est validée
    et écrite d'abord, seule ; le tour de l'assistant et ses actions sont
    écrits ensuite, ensemble. Tout envelopper aurait annulé la demande le jour
    où le modèle tombe — c'est-à-dire exactement le jour où l'on tient à ne pas
    retaper sa phrase.
    """
    texte = (texte or "").strip()
    if not texte:
        raise ValueError("Dis quelque chose.")

    fil = fil_ouvert(user)
    # Écrite et commise avant l'appel : si le modèle tombe, elle reste à l'écran.
    demande_ecrite = ConversationTurn.objects.create(
        conversation=fil, role=ConversationTurn.UTILISATEUR, text=texte
    )

    # Les **derniers** tours, pas les premiers : une conversation longue garde
    # sa fin, qui est la seule partie encore pertinente. Le tour qu'on vient
    # d'écrire est exclu — il part comme demande, pas comme historique.
    recents = list(
        fil.turns.exclude(text="")
        .exclude(pk=demande_ecrite.pk)
        .order_by("-created_at", "-id")[:MEMOIRE]
    )
    echange = [{"role": t.role, "content": t.text} for t in reversed(recents)]

    prompt = prompts.assistant_prompt(
        etat=etat_pour_le_modele(user, today=today),
        catalogue=catalogue_pour_le_modele(),
        echange=echange,
        demande=texte,
    )

    try:
        reponse = get_provider().structured(
            task=Task.ASSISTANT,
            system=prompts.SYSTEM_ASSISTANT,
            prompt=prompt,
            schema=prompts.schema_assistant(catalogue.CLES),
        )
    except LLMUnavailable as error:
        raise AssistantIndisponible(str(error)) from error

    if reponse.refused:
        raise AssistantIndisponible("le modèle a décliné la demande")

    payload = reponse.content if isinstance(reponse.content, dict) else {}
    try:
        valide = gate(Task.ASSISTANT, payload, cles_connues=catalogue.CLES)
    except QualityGateFailed as error:
        logger.warning("assistant refusé par la porte : %s", error.reason)
        raise AssistantIndisponible(f"réponse refusée : {error.reason}") from error

    # La réponse et ses actions, elles, sont solidaires : un tour affiché sans
    # ses cartes se lirait comme un assistant qui parle sans rien proposer.
    with transaction.atomic():
        tour = ConversationTurn.objects.create(
            conversation=fil,
            role=ConversationTurn.ASSISTANT,
            text=valide["reponse"],
            meta={
                "model": reponse.model,
                "tokens": reponse.usage.total,
            },
        )
        for proposee in valide["actions"]:
            _ranger(user, tour, proposee["action"], proposee["params"], today=today)

    return payload_fil(user)


def _ranger(user, tour: ConversationTurn, cle: str, params: dict, *, today: date) -> ProposedAction:
    """Valide la forme puis le fond, et range l'action — acceptée ou refusée.

    Une action refusée est **conservée**. La supprimer laisserait croire que
    l'assistant n'a rien tenté, alors qu'il a tenté quelque chose d'impossible :
    lire « baisser l'engagement à zéro — refusé : zéro n'est pas un engagement »
    apprend la règle, un silence n'apprend rien.
    """
    forme = catalogue.verifier_forme(cle, params)
    if not forme.ok:
        return ProposedAction.objects.create(
            turn=tour,
            key=cle,
            params=params if isinstance(params, dict) else {},
            summary=catalogue.resume(cle, params if isinstance(params, dict) else {}),
            state=ProposedAction.ECARTEE,
            detail=forme.raison,
        )

    try:
        plan = executeurs.resoudre(user, cle, forme.params, today=today)
    except executeurs.ActionRefusee as refus:
        return ProposedAction.objects.create(
            turn=tour,
            key=cle,
            params=forme.params,
            summary=catalogue.resume(cle, forme.params),
            state=ProposedAction.ECARTEE,
            detail=str(refus),
        )

    action = catalogue.PAR_CLE[cle]
    return ProposedAction.objects.create(
        turn=tour,
        key=cle,
        params=forme.params,
        summary=catalogue.resume(cle, forme.params),
        before=plan.avant,
        after=plan.apres,
        warning=plan.avertissement or ("Difficile à défaire." if action.destructive else ""),
        empreinte=plan.empreinte,
        state=ProposedAction.EN_ATTENTE,
    )


# --------------------------------------------------------------------------
# Appliquer
# --------------------------------------------------------------------------

@transaction.atomic
def appliquer(action: ProposedAction, *, user, today: date) -> ProposedAction:
    """Exécute une action proposée. Une seule fois, et sur l'état qu'elle a vu.

    Deux refus possibles, et ils disent des choses différentes :

    - **déjà traitée** : le bouton a été cliqué deux fois, ou depuis deux
      onglets. On ne rejoue pas — une fusion appliquée deux fois archiverait
      une routine de plus ;
    - **périmée** : l'état a bougé depuis l'aperçu. Le projet a été renommé, une
      étape ajoutée, la fenêtre changée. L'aperçu qu'on a lu ne décrit plus ce
      qui va se passer, donc appliquer serait écrire quelque chose que personne
      n'a validé.
    """
    if action.state != ProposedAction.EN_ATTENTE:
        raise ValueError(f"Action déjà {action.get_state_display().lower()}.")

    try:
        plan = executeurs.resoudre(user, action.key, action.params, today=today)
    except executeurs.ActionRefusee as refus:
        action.state = ProposedAction.PERIMEE
        action.detail = str(refus)
        action.save(update_fields=["state", "detail"])
        return action

    if action.empreinte and plan.empreinte != action.empreinte:
        action.state = ProposedAction.PERIMEE
        action.detail = (
            "Quelque chose a changé depuis cette proposition. Redemande-la : "
            "l'aperçu que tu as lu ne décrit plus ce qui se passerait."
        )
        action.save(update_fields=["state", "detail"])
        return action

    plan.appliquer()
    action.state = ProposedAction.APPLIQUEE
    action.applied_at = timezone.now()
    action.before, action.after = plan.avant, plan.apres
    action.save(update_fields=["state", "applied_at", "before", "after"])
    return action


def ecarter(action: ProposedAction) -> ProposedAction:
    """Range une proposition sans l'appliquer. Réversible : rien n'a été écrit."""
    if action.state == ProposedAction.EN_ATTENTE:
        action.state = ProposedAction.ECARTEE
        action.detail = "Écartée."
        action.save(update_fields=["state", "detail"])
    return action


# --------------------------------------------------------------------------
# Ce que l'écran affiche
# --------------------------------------------------------------------------

def payload_fil(user) -> dict:
    fil = fil_ouvert(user)
    tours = fil.turns.prefetch_related("actions").order_by("created_at", "id")

    return {
        "conversation_id": fil.id,
        "started_at": fil.started_at.isoformat(),
        "turns": [
            {
                "id": tour.id,
                "role": tour.role,
                "text": tour.text,
                "at": tour.created_at.isoformat(),
                "model": (tour.meta or {}).get("model", ""),
                "tokens": (tour.meta or {}).get("tokens", 0),
                "actions": [
                    {
                        "id": action.id,
                        "key": action.key,
                        "label": catalogue.PAR_CLE[action.key].label
                        if action.key in catalogue.PAR_CLE
                        else action.key,
                        "domain": catalogue.PAR_CLE[action.key].domaine
                        if action.key in catalogue.PAR_CLE
                        else "",
                        "summary": action.summary,
                        "params": action.params,
                        "before": action.before,
                        "after": action.after,
                        "warning": action.warning,
                        "state": action.state,
                        "detail": action.detail,
                    }
                    for action in tour.actions.all()
                ],
            }
            for tour in tours
        ],
    }
