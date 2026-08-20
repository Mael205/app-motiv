"""L'export complet des données (SPEC §16, jalon J6).

**Pourquoi ça existe.** Tout ce que le produit mesure vit dans un fichier
SQLite sur une machine. Le 19 août 2026, une commande de démonstration a effacé
un projet de cent vingt étapes qui n'avait aucune sauvegarde, et il n'était pas
récupérable — c'est écrit dans ``docs/a-faire.md`` et ça ne se répare pas. Un
export ne remplace pas une sauvegarde de la base, mais il rend le travail
**relisible ailleurs** : un fichier JSON qu'on garde, qu'on ouvre dans dix ans,
et qui ne dépend ni de Django ni du schéma du moment.

**Ce qu'il contient : tout ce qui a été fait.** Sessions, notes, amorces,
étapes, routines, saisons, cartes, hauts faits. Ce qu'il ne contient pas : les
secrets. Aucun jeton de sonde, aucun lien signé, aucun abonnement Web Push,
aucun webhook. Un export se copie sur une clé USB et s'envoie par message ; s'il
portait des secrets, il serait une fuite à retardement — et ceux-ci se
régénèrent en une commande, contrairement au travail.

Format : du JSON plat, des dates ISO, des noms en clair plutôt que des
identifiants. Un export qu'il faut réimporter pour lire n'est pas un export.
"""

from __future__ import annotations

from datetime import date, datetime

from .models import (
    Achievement,
    FridgeIdea,
    JournalEntry,
    LootCard,
    Ponctuel,
    Preuve,
    Project,
    RoadmapStep,
    Routine,
    RoutineCheck,
    Season,
    Session,
    WeeklyReport,
    WeeklyReview,
)

VERSION = 1


def tout(user) -> dict:
    """L'intégralité de ce que le coach sait de quelqu'un, sans les secrets."""
    return {
        "version": VERSION,
        "exporte_le": _iso(datetime.now()),
        "utilisateur": user.username,
        "avertissement": (
            "Ce fichier contient du travail, pas des secrets : ni jeton de sonde, "
            "ni lien signé, ni abonnement de notification."
        ),
        "projets": _projets(user),
        "sessions": _sessions(user),
        "routines": _routines(user),
        "ponctuels": [
            {
                "intitule": p.label,
                "echeance": _iso(p.due_on),
                "fait_le": _iso(p.done_at),
                "cree_le": _iso(p.created_at),
            }
            for p in Ponctuel.objects.filter(user=user)
        ],
        "frigo": [
            {"texte": i.text, "cree_le": _iso(i.created_at), "source": i.source}
            for i in FridgeIdea.objects.filter(user=user)
        ],
        "saisons": _saisons(user),
        "revues": _revues(user),
        "bilans_hebdomadaires": [
            {
                "semaine": _iso(r.week_start),
                "texte": r.body,
                "envoye_le": _iso(r.sent_at),
                "lu_le": _iso(r.read_at),
            }
            for r in WeeklyReport.objects.filter(user=user)
        ],
        "hauts_faits": [
            {"cle": a.key, "obtenu_le": _iso(a.unlocked_at)}
            for a in Achievement.objects.filter(user=user)
        ],
        "cartes": [
            {"cle": c.key, "rarete": c.rarity, "emplacement": c.kind, "exemplaires": c.copies}
            for c in LootCard.objects.filter(user=user)
        ],
        "preuves": [
            {
                "projet": p.project.name,
                "critere": p.critere,
                "jour": _iso(p.obtained_on),
            }
            for p in Preuve.objects.filter(project__user=user).select_related("project")
        ],
    }


def _projets(user) -> list[dict]:
    projets = Project.objects.filter(user=user).select_related("track").prefetch_related("steps")
    return [
        {
            "nom": p.name,
            "piste": p.track.kind,
            "statut": p.status,
            "slot": p.slot,
            "domaine": p.domain,
            "branche": p.branch,
            "objectif": p.objective,
            "cadre": p.frame,
            "verification": p.verification,
            "engagement_hebdomadaire": p.weekly_commitment,
            "cree_le": _iso(p.created_at),
            "etapes": [
                {
                    "ordre": e.order,
                    "intitule": e.label,
                    "etat": e.state,
                    "critere_de_sortie": e.exit_criterion,
                    "ressource": e.resource,
                    "commencee_le": _iso(e.doing_since),
                    "finie_le": _iso(e.done_at),
                }
                for e in p.steps.all()
            ],
        }
        for p in projets
    ]


def _sessions(user) -> list[dict]:
    entrees = {
        e.session_id: e
        for e in JournalEntry.objects.filter(session__user=user)
    }
    lignes = []
    for s in Session.objects.filter(user=user).select_related("project").order_by("started_at"):
        entree = entrees.get(s.id)
        lignes.append(
            {
                "jour": _iso(s.coach_day),
                "projet": s.project.name,
                "debut": _iso(s.started_at),
                "fin": _iso(s.ended_at),
                "minutes": s.actual_minutes,
                "objectif": s.planned_minutes,
                "prolongations": s.extensions,
                "statut": s.status,
                "mode": s.mode,
                "xp": s.xp_awarded,
                "difficulte": s.difficulty,
                # La note et l'amorce sont le seul contenu écrit à la main de
                # tout l'export. C'est aussi la seule chose qu'aucun calcul ne
                # peut reconstituer : elles passent avant les chiffres.
                "note": entree.raw_note if entree else "",
                "amorce": entree.next_action if entree else "",
            }
        )
    return lignes


def _routines(user) -> list[dict]:
    return [
        {
            "nom": r.name,
            "ancre": r.anchor,
            "heure_limite": _iso(r.deadline),
            "sens": r.direction,
            "objectif_hebdomadaire": r.weekly_target,
            "active": r.active,
            "coches": [
                {"jour": _iso(c.day), "source": c.source, "a_l_heure": c.on_time}
                for c in RoutineCheck.objects.filter(routine=r).order_by("day")
            ],
        }
        for r in Routine.objects.filter(user=user)
    ]


def _saisons(user) -> list[dict]:
    lignes = []
    for s in Season.objects.filter(user=user).order_by("index"):
        boss = getattr(s, "boss", None)
        lignes.append(
            {
                "index": s.index,
                "nom": s.name,
                "debut": _iso(s.starts_on),
                "fin": _iso(s.ends_on),
                "statut": s.status,
                "modificateur": s.modifier_key,
                "score_final": s.final_score,
                "titre_decerne": s.title_awarded,
                "mise": s.stake_shards,
                "mise_perdue": s.stake_forfeited,
                "boss": (
                    {"nom": boss.name, "vie": boss.max_hp, "degats_subis": boss.damage_taken}
                    if boss
                    else None
                ),
            }
        )
    return lignes


def _revues(user) -> list[dict]:
    return [
        {
            "semaine": _iso(r.week_start),
            "questions": r.questions,
            "compte_rendu": r.report,
            "contrat": r.contract,
            "close_le": _iso(r.closed_at),
        }
        for r in WeeklyReview.objects.filter(user=user).order_by("week_start")
    ]


def _iso(valeur) -> str | None:
    """Dates, heures et instants sortent tous en ISO. ``None`` reste ``None``.

    Un export où l'absence de date serait une chaîne vide obligerait le lecteur
    à deviner la différence entre « pas encore fait » et « fait à une date
    inconnue ». `null` le dit sans ambiguïté, dans tous les langages.
    """
    if valeur is None:
        return None
    if isinstance(valeur, (datetime, date)):
        return valeur.isoformat()
    return valeur.isoformat() if hasattr(valeur, "isoformat") else str(valeur)
