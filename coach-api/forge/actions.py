"""Ce que fait chaque action du catalogue, et ce qu'elle affiche avant de le faire.

``rules/actions`` dit **quels** verbes existent et vérifie leur forme, sans
toucher à la base. Ce module-ci résout les noms en objets, vérifie le fond
contre les vraies règles, calcule l'aperçu avant/après, et exécute.

## Trois principes, et ils tiennent tout le fichier

**Chaque action passe par le service qui existe déjà.** Poser une attente
appelle ``services.declare_hold``, terminer une étape appelle
``services.complete_step``, changer un engagement passe par
``slot_rules.peut_changer_engagement``. Rien n'est réécrit ici. Une action qui
contournerait sa règle serait une porte dérobée dans le produit — et la seule
raison pour laquelle l'assistant est sûr, c'est qu'il ne peut rien faire qu'on
ne puisse déjà faire à la main.

**Un nom inconnu est une hallucination, pas une faute de frappe.** Le modèle
reçoit la liste exacte des projets, étapes et routines. S'il en nomme un autre,
la résolution refuse et le dit — avec les noms réels, pour que la reformulation
soit immédiate. On ne devine jamais « il voulait sûrement dire celui-là » :
appliquer une action au mauvais objet est le pire résultat possible, pire qu'un
refus.

**L'aperçu se calcule au moment de proposer, et l'état est empreint.** Une
proposition appliquée le lendemain, sur un projet renommé entre-temps,
produirait une écriture que personne n'a validée. L'empreinte fait refuser ces
cas-là plutôt que de les appliquer à l'aveugle.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from . import services
from .models import (
    DayOff,
    Project,
    RoadmapStep,
    Routine,
    RoutineCheck,
    TimeSlot,
    Track,
)
from .rules import routines as routine_rules
from .rules import slots as slot_rules
from .rules import verification as verification_rules
from .rules.calendar import week_start


class ActionRefusee(ValueError):
    """L'action ne peut pas être proposée, et la phrase dit pourquoi."""


@dataclass
class Plan:
    """Une action résolue : ce qu'elle changera, et de quoi l'exécuter."""

    avant: str
    apres: str
    appliquer: Callable[[], None]
    empreinte: str = ""
    avertissement: str = ""


RESOLVEURS: dict[str, Callable] = {}


def resolveur(cle: str):
    def enregistrer(fonction):
        RESOLVEURS[cle] = fonction
        return fonction
    return enregistrer


def resoudre(user, cle: str, params: dict, *, today: date) -> Plan:
    """Résout une action contre l'état réel. Lève ``ActionRefusee`` sinon."""
    fonction = RESOLVEURS.get(cle)
    if fonction is None:
        raise ActionRefusee(f"« {cle} » n'a pas d'exécution déclarée.")
    plan = fonction(user, params, today)
    if plan.empreinte == "":
        plan.empreinte = _empreinte_globale(user)
    return plan


# --------------------------------------------------------------------------
# Retrouver les objets par leur nom
# --------------------------------------------------------------------------

def _projet(user, nom: str) -> Project:
    """Le projet nommé, parmi les non archivés. Comparaison insensible à la casse.

    Insensible à la casse et aux espaces, mais **jamais approximative** : « bot
    smash » retrouve « Bot Smash », « le bot » ne retrouve rien. Une
    correspondance floue finirait par agir sur le mauvais projet un jour où
    deux noms se ressemblent, et ce jour-là personne ne comprendrait pourquoi.
    """
    cible = (nom or "").strip().casefold()
    projets = list(Project.objects.filter(user=user).exclude(status=Project.ARCHIVED))
    for projet in projets:
        if projet.name.strip().casefold() == cible:
            return projet
    connus = ", ".join(p.name for p in projets) or "aucun"
    raise ActionRefusee(f"Aucun projet nommé « {nom} ». Ceux qui existent : {connus}.")


def _etape(projet: Project, libelle: str, *, terminees: bool = False) -> RoadmapStep:
    cible = (libelle or "").strip().casefold()
    etapes = list(projet.steps.all())
    if not terminees:
        etapes = [e for e in etapes if e.state != RoadmapStep.DONE]
    for etape in etapes:
        if etape.label.strip().casefold() == cible:
            return etape
    connues = " · ".join(e.label for e in etapes) or "aucune"
    raise ActionRefusee(
        f"Aucune étape « {libelle} » sur {projet.name}. Celles qui restent : {connues}."
    )


def _routine(user, nom: str) -> Routine:
    cible = (nom or "").strip().casefold()
    routines = list(Routine.objects.filter(user=user, active=True))
    for routine in routines:
        if routine.name.strip().casefold() == cible:
            return routine
    connues = ", ".join(r.name for r in routines) or "aucune"
    raise ActionRefusee(f"Aucune routine nommée « {nom} ». Celles qui existent : {connues}.")


def _heure(texte: str) -> time:
    try:
        heures, minutes = str(texte).strip().split(":")
        return time(int(heures), int(minutes))
    except (AttributeError, TypeError, ValueError):
        raise ActionRefusee(f"« {texte} » n'est pas une heure. Format attendu : HH:MM.")


def _jour(texte: str) -> date:
    try:
        return date.fromisoformat(str(texte).strip())
    except (TypeError, ValueError):
        raise ActionRefusee(f"« {texte} » n'est pas une date. Format attendu : AAAA-MM-JJ.")


def _jours_semaine(brut, *, defaut: list[int] | None = None) -> list[int]:
    if brut is None:
        return list(defaut or [])
    jours = []
    for valeur in brut:
        try:
            jour = int(valeur)
        except (TypeError, ValueError):
            raise ActionRefusee("Les jours s'écrivent en nombres, 0 = lundi.")
        if not 0 <= jour <= 6:
            raise ActionRefusee("Un jour va de 0 (lundi) à 6 (dimanche).")
        jours.append(jour)
    return sorted(set(jours))


JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def dire_jours(jours: list[int]) -> str:
    return ", ".join(JOURS[j] for j in jours) if jours else "tous les jours"


# --------------------------------------------------------------------------
# Empreintes : ce sur quoi l'aperçu a été calculé
# --------------------------------------------------------------------------

def _hacher(donnees) -> str:
    brut = json.dumps(donnees, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()[:32]


def _empreinte_projet(projet: Project) -> str:
    return _hacher(
        {
            "nom": projet.name,
            "statut": projet.status,
            "slot": projet.slot,
            "couleur": projet.color,
            "embleme": projet.emblem,
            "branche": projet.branch,
            "verification": projet.verification,
            "engagement": projet.weekly_commitment,
            "etapes": [(e.label, e.state, e.order) for e in projet.steps.all()],
            "creneaux": [(t.weekday, str(t.start_time), t.duration_minutes) for t in projet.timeslots.all()],
        }
    )


def _empreinte_routines(user) -> str:
    return _hacher(
        [
            (r.id, r.name, r.anchor, list(r.weekdays or ()), r.weekly_target, r.order, r.active)
            for r in Routine.objects.filter(user=user).order_by("id")
        ]
    )


def _empreinte_globale(user) -> str:
    profil = user.profile
    return _hacher(
        {
            "fuseau": profil.timezone_name,
            "gardien": profil.guardian_minutes_before_end,
            "matin": profil.morning_hour,
            "fenetres": [
                (w.weekday, str(w.start_time), str(w.end_time))
                for w in profil.windows.all().order_by("weekday")
            ],
        }
    )


# --------------------------------------------------------------------------
# Projets
# --------------------------------------------------------------------------

@resolveur("projet.renommer")
def _projet_renommer(user, params, today):
    projet = _projet(user, params["projet"])
    nouveau = params["nom"].strip()
    if not nouveau:
        raise ActionRefusee("Un projet a besoin d'un nom.")
    if Project.objects.filter(user=user, name__iexact=nouveau).exclude(pk=projet.pk).exists():
        raise ActionRefusee(f"Un autre projet s'appelle déjà « {nouveau} ».")

    def appliquer():
        projet.name = nouveau
        projet.save(update_fields=["name"])

    return Plan(
        avant=projet.name,
        apres=nouveau,
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("projet.apparence")
def _projet_apparence(user, params, today):
    projet = _projet(user, params["projet"])
    couleur = params.get("couleur")
    embleme = params.get("embleme")
    if not couleur and not embleme:
        raise ActionRefusee("Rien à changer : donne une couleur ou un emblème.")
    if couleur and not (couleur.startswith("#") and len(couleur) == 7):
        raise ActionRefusee(f"« {couleur} » n'est pas une couleur hexadécimale (#RRGGBB).")
    if embleme and len(embleme) > 2:
        raise ActionRefusee("Un emblème est un seul glyphe.")

    def appliquer():
        if couleur:
            projet.color = couleur
        if embleme:
            projet.emblem = embleme
        projet.save(update_fields=["color", "emblem"])

    return Plan(
        avant=f"{projet.emblem} {projet.color}",
        apres=f"{embleme or projet.emblem} {couleur or projet.color}",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("projet.branche")
def _projet_branche(user, params, today):
    from .rules import skills as skill_rules

    projet = _projet(user, params["projet"])
    branche = params["branche"].strip()
    connues = {b.key for b in skill_rules.tree({})}
    if branche not in connues:
        raise ActionRefusee(
            f"« {branche} » n'est pas une branche. Celles qui existent : {', '.join(sorted(connues))}."
        )

    def appliquer():
        projet.branch = branche
        projet.save(update_fields=["branch"])

    return Plan(
        avant=projet.branch or "aucune branche",
        apres=branche,
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("projet.verification")
def _projet_verification(user, params, today):
    projet = _projet(user, params["projet"])
    mode = params["mode"].strip()
    if mode not in verification_rules.KINDS:
        raise ActionRefusee(
            f"« {mode} » n'est pas un mode de preuve. Ceux qui existent : "
            f"{', '.join(verification_rules.KINDS)}."
        )
    chemin = (params.get("chemin") or "").strip()
    if mode != verification_rules.MANUELLE and not chemin and not projet.repos.exists():
        raise ActionRefusee(
            f"Le mode « {mode} » a besoin d'un chemin de dépôt ou de dossier : "
            "sans lui, le projet serait déclaré non vérifié à chaque session."
        )

    def appliquer():
        projet.verification = mode
        projet.save(update_fields=["verification"])
        if chemin:
            projet.repos.get_or_create(path=chemin)

    return Plan(
        avant=verification_rules.LABELS.get(projet.verification, projet.verification),
        apres=verification_rules.LABELS.get(mode, mode) + (f" — {chemin}" if chemin else ""),
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("projet.engagement")
def _projet_engagement(user, params, today):
    projet = _projet(user, params["projet"])
    vise = params["sessions"]
    ok, motif = slot_rules.peut_changer_engagement(
        actuel=projet.weekly_commitment, vise=vise, weekday=today.weekday()
    )
    if not ok:
        raise ActionRefusee(motif)

    def appliquer():
        projet.weekly_commitment = vise
        projet.save(update_fields=["weekly_commitment"])

    return Plan(
        avant=f"{projet.weekly_commitment} sessions par semaine",
        apres=f"{vise} sessions par semaine",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("projet.frigo")
def _projet_frigo(user, params, today):
    projet = _projet(user, params["projet"])
    if projet.status == Project.FRIDGE:
        raise ActionRefusee(f"{projet.name} est déjà au frigo.")

    ok, motif = slot_rules.can_replace(
        weekday=today.weekday(),
        project_finished=projet.completion >= 1.0,
        has_sessions=projet.sessions.exists(),
    )
    if not ok:
        raise ActionRefusee(motif)

    def appliquer():
        projet.status = Project.FRIDGE
        projet.slot = None
        projet.save(update_fields=["status", "slot"])

    return Plan(
        avant=f"actif, slot {projet.slot}" if projet.slot else "actif",
        apres="au frigo, slot libéré",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
        avertissement="Le slot redevient libre. Le reprendre demandera un slot disponible.",
    )


@resolveur("projet.reprendre")
def _projet_reprendre(user, params, today):
    projet = _projet(user, params["projet"])
    if projet.status == Project.ACTIVE:
        raise ActionRefusee(f"{projet.name} est déjà actif.")

    slot = services.free_slot(user, projet.domain, today=today)
    if slot is None:
        raise ActionRefusee(
            slot_rules.refused_reason(
                services.taken_slots(user),
                projet.domain,
                total_slots=services.rank_state(user, today=today)["slots"],
            )
        )

    def appliquer():
        projet.status = Project.ACTIVE
        projet.slot = slot
        projet.save(update_fields=["status", "slot"])

    return Plan(
        avant="au frigo",
        apres=f"actif, slot {slot}",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("projet.attente")
def _projet_attente(user, params, today):
    from .rules import holds as hold_rules

    projet = _projet(user, params["projet"])
    fin = _jour(params["jusqu_a"])
    raison = params["raison"]

    verdict = hold_rules.verifier(debut=today, fin=fin, aujourdhui=today, raison=raison)
    if not verdict.ok:
        raise ActionRefusee(verdict.raison)
    if projet.id in services.projects_on_hold(user, day=today):
        raise ActionRefusee(f"{projet.name} est déjà en attente.")

    def appliquer():
        services.declare_hold(
            user, projet, starts_on=today, ends_on=fin, reason=raison, today=today
        )

    return Plan(
        avant="proposé le soir comme les autres",
        apres=hold_rules.message(projet.name, fin, raison),
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("projet.fin_attente")
def _projet_fin_attente(user, params, today):
    projet = _projet(user, params["projet"])
    if projet.id not in services.projects_on_hold(user, day=today):
        raise ActionRefusee(f"{projet.name} n'est pas en attente.")

    def appliquer():
        services.end_hold(user, projet, today=today)

    return Plan(
        avant="en attente, hors des propositions du soir",
        apres="proposable dès ce soir",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


# --------------------------------------------------------------------------
# Roadmap
# --------------------------------------------------------------------------

@resolveur("etape.ajouter")
def _etape_ajouter(user, params, today):
    projet = _projet(user, params["projet"])
    libelle = params["libelle"].strip()
    sessions = params.get("sessions") or 1
    if sessions > 3:
        raise ActionRefusee(
            f"{sessions} sessions estimées : le §4.5 traite une étape de plus de trois "
            "sessions comme trop grosse. Découpe-la en la proposant."
        )

    apres_libelle = params.get("apres")
    rang = None
    if apres_libelle:
        rang = _etape(projet, apres_libelle, terminees=True).order

    def appliquer():
        if rang is None:
            position = (projet.steps.count() or 0)
        else:
            position = rang + 1
            for suivante in projet.steps.filter(order__gte=position).order_by("-order"):
                suivante.order += 1
                suivante.save(update_fields=["order"])
        RoadmapStep.objects.create(
            project=projet, label=libelle, order=position, estimated_sessions=sessions
        )

    ouvertes = [e.label for e in projet.steps.exclude(state=RoadmapStep.DONE)]
    return Plan(
        avant=" · ".join(ouvertes) or "roadmap vide",
        apres=" · ".join([*ouvertes, libelle]),
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("etape.renommer")
def _etape_renommer(user, params, today):
    projet = _projet(user, params["projet"])
    etape = _etape(projet, params["etape"])
    libelle = params["libelle"].strip()

    def appliquer():
        etape.label = libelle
        etape.save(update_fields=["label"])

    return Plan(
        avant=etape.label,
        apres=libelle,
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("etape.decouper")
def _etape_decouper(user, params, today):
    projet = _projet(user, params["projet"])
    etape = _etape(projet, params["etape"])
    morceaux = [str(m).strip() for m in params["morceaux"] if str(m).strip()]
    if len(morceaux) < 2:
        raise ActionRefusee("Découper demande au moins deux morceaux.")

    def appliquer():
        base = etape.order
        for suivante in projet.steps.filter(order__gt=base).order_by("-order"):
            suivante.order += len(morceaux) - 1
            suivante.save(update_fields=["order"])
        etape.label = morceaux[0]
        etape.estimated_sessions = 1
        etape.save(update_fields=["label", "estimated_sessions"])
        for decalage, libelle in enumerate(morceaux[1:], start=1):
            RoadmapStep.objects.create(
                project=projet, label=libelle, order=base + decalage, estimated_sessions=1
            )

    return Plan(
        avant=f"{etape.label} ({etape.estimated_sessions} sessions)",
        apres=" · ".join(morceaux),
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
        avertissement="L'étape d'origine disparaît au profit du premier morceau.",
    )


@resolveur("etape.reordonner")
def _etape_reordonner(user, params, today):
    projet = _projet(user, params["projet"])
    ouvertes = list(projet.steps.exclude(state=RoadmapStep.DONE))
    demandes = [str(x).strip() for x in params["ordre"]]

    if len(demandes) != len(ouvertes):
        raise ActionRefusee(
            f"{projet.name} a {len(ouvertes)} étapes non terminées, l'ordre proposé en "
            f"donne {len(demandes)}. Réordonner demande la liste entière."
        )
    ordonnees = [_etape(projet, libelle) for libelle in demandes]
    if len({e.pk for e in ordonnees}) != len(ordonnees):
        raise ActionRefusee("Une étape apparaît deux fois dans l'ordre proposé.")

    base = min(e.order for e in ouvertes)

    def appliquer():
        for position, etape in enumerate(ordonnees):
            etape.order = base + position
            etape.save(update_fields=["order"])

    return Plan(
        avant=" · ".join(e.label for e in ouvertes),
        apres=" · ".join(e.label for e in ordonnees),
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("etape.terminer")
def _etape_terminer(user, params, today):
    projet = _projet(user, params["projet"])
    etape = _etape(projet, params["etape"])

    def appliquer():
        services.complete_step(user, etape, today=today)

    return Plan(
        avant=f"{etape.label} — en cours",
        apres=f"{etape.label} — faite, dégâts au boss et une carte",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("etape.supprimer")
def _etape_supprimer(user, params, today):
    projet = _projet(user, params["projet"])
    etape = _etape(projet, params["etape"])
    if etape.doing_since is not None:
        raise ActionRefusee(
            f"« {etape.label} » a déjà reçu du travail. Une étape commencée se "
            "termine ou se reformule, elle ne s'efface pas — sinon le temps passé "
            "dessus ne mène nulle part."
        )

    def appliquer():
        etape.delete()

    return Plan(
        avant=etape.label,
        apres="retirée de la roadmap",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
        avertissement="L'étape est supprimée, pas archivée.",
    )


# --------------------------------------------------------------------------
# Entretien
# --------------------------------------------------------------------------

def _piste_entretien(user) -> Track:
    piste, _ = Track.objects.get_or_create(user=user, kind=Track.ENTRETIEN)
    return piste


def _decrire_routine(routine: Routine) -> str:
    ancrage = routine_rules.ANCHOR_LABELS.get(routine.anchor, routine.anchor)
    return (
        f"{routine.name} — {ancrage}, {dire_jours(list(routine.weekdays or []))}, "
        f"{routine.weekly_target}×/semaine"
    )


@resolveur("routine.creer")
def _routine_creer(user, params, today):
    nom = params["nom"].strip()
    if Routine.objects.filter(user=user, active=True, name__iexact=nom).exists():
        raise ActionRefusee(f"Une routine « {nom} » existe déjà.")

    ancrage = params.get("ancrage") or routine_rules.LIBRE
    if ancrage not in routine_rules.ANCHOR_ORDER:
        raise ActionRefusee(
            f"« {ancrage} » n'est pas un ancrage. Ceux qui existent : "
            f"{', '.join(routine_rules.ANCHOR_ORDER)}."
        )
    jours = _jours_semaine(params.get("jours"), defaut=[])
    cible = params.get("cible") or 6
    if cible > routine_rules.DAYS_PER_WEEK:
        raise ActionRefusee("Une routine ne peut pas être visée plus de sept fois par semaine.")
    if jours and cible > len(jours):
        raise ActionRefusee(
            f"Visée {cible}×/semaine mais proposée seulement {len(jours)} jours : "
            "l'écart entre le rythme et le seuil est ce qui absorbe les oublis (§11.9), "
            "et là il est négatif."
        )

    def appliquer():
        Routine.objects.create(
            user=user,
            track=_piste_entretien(user),
            name=nom,
            anchor=ancrage,
            weekdays=jours,
            weekly_target=cible,
            order=Routine.objects.filter(user=user, active=True).count(),
        )

    return Plan(
        avant="n'existe pas",
        apres=f"{nom} — {routine_rules.ANCHOR_LABELS.get(ancrage, ancrage)}, "
              f"{dire_jours(jours)}, {cible}×/semaine",
        appliquer=appliquer,
        empreinte=_empreinte_routines(user),
    )


@resolveur("routine.renommer")
def _routine_renommer(user, params, today):
    routine = _routine(user, params["routine"])
    nom = params["nom"].strip()

    def appliquer():
        routine.name = nom
        routine.save(update_fields=["name"])

    return Plan(
        avant=routine.name,
        apres=nom,
        appliquer=appliquer,
        empreinte=_empreinte_routines(user),
    )


@resolveur("routine.regler")
def _routine_regler(user, params, today):
    routine = _routine(user, params["routine"])
    ancrage = params.get("ancrage") or routine.anchor
    if ancrage not in routine_rules.ANCHOR_ORDER:
        raise ActionRefusee(f"« {ancrage} » n'est pas un ancrage.")
    jours = _jours_semaine(params.get("jours"), defaut=list(routine.weekdays or []))
    cible = params.get("cible") or routine.weekly_target
    if jours and cible > len(jours):
        raise ActionRefusee(
            f"Visée {cible}×/semaine mais proposée seulement {len(jours)} jours : "
            "il ne resterait aucune marge pour un oubli (§11.9)."
        )

    def appliquer():
        routine.anchor = ancrage
        routine.weekdays = jours
        routine.weekly_target = cible
        routine.save(update_fields=["anchor", "weekdays", "weekly_target"])

    apres = Routine(name=routine.name, anchor=ancrage, weekdays=jours, weekly_target=cible)
    return Plan(
        avant=_decrire_routine(routine),
        apres=_decrire_routine(apres),
        appliquer=appliquer,
        empreinte=_empreinte_routines(user),
    )


@resolveur("routine.fusionner")
def _routine_fusionner(user, params, today):
    noms = [str(x).strip() for x in params["routines"]]
    if len(noms) < 2:
        raise ActionRefusee("Fusionner demande au moins deux routines.")

    routines = [_routine(user, nom) for nom in noms]
    if len({r.pk for r in routines}) != len(routines):
        raise ActionRefusee("La même routine est citée deux fois.")

    gardee = routines[0]
    absorbees = routines[1:]
    nom = params["nom"].strip()
    ancrage = params.get("ancrage") or gardee.anchor
    if ancrage not in routine_rules.ANCHOR_ORDER:
        raise ActionRefusee(f"« {ancrage} » n'est pas un ancrage.")

    # Les jours de la fusionnée sont l'**union** : une routine qui absorbe une
    # autre doit couvrir les deux, sinon la fusion supprime des jours en douce.
    jours = sorted({j for r in routines for j in (r.weekdays or [])})
    cible = params.get("cible") or max(r.weekly_target for r in routines)
    if jours and cible > len(jours):
        cible = len(jours)

    coches = RoutineCheck.objects.filter(routine__in=absorbees).count()

    def appliquer():
        gardee.name = nom
        gardee.anchor = ancrage
        gardee.weekdays = jours
        gardee.weekly_target = cible
        gardee.save(update_fields=["name", "anchor", "weekdays", "weekly_target"])
        for routine in absorbees:
            routine.active = False
            routine.archived_at = timezone.now()
            routine.save(update_fields=["active", "archived_at"])

    return Plan(
        avant=" | ".join(_decrire_routine(r) for r in routines),
        apres=_decrire_routine(
            Routine(name=nom, anchor=ancrage, weekdays=jours, weekly_target=cible)
        ),
        appliquer=appliquer,
        empreinte=_empreinte_routines(user),
        avertissement=(
            f"{len(absorbees)} routine(s) archivée(s). Leurs {coches} coches passées "
            "restent en base mais ne comptent plus dans la semaine."
        ),
    )


@resolveur("routine.archiver")
def _routine_archiver(user, params, today):
    routine = _routine(user, params["routine"])

    def appliquer():
        routine.active = False
        routine.archived_at = timezone.now()
        routine.save(update_fields=["active", "archived_at"])

    return Plan(
        avant=_decrire_routine(routine),
        apres="archivée, hors de la piste Entretien",
        appliquer=appliquer,
        empreinte=_empreinte_routines(user),
        avertissement="L'historique de coches est conservé, la routine ne l'est plus.",
    )


@resolveur("routine.reordonner")
def _routine_reordonner(user, params, today):
    actives = list(Routine.objects.filter(user=user, active=True))
    demandes = [str(x).strip() for x in params["ordre"]]
    if len(demandes) != len(actives):
        raise ActionRefusee(
            f"L'Entretien a {len(actives)} routines actives, l'ordre proposé en donne "
            f"{len(demandes)}. Réordonner demande la liste entière."
        )
    ordonnees = [_routine(user, nom) for nom in demandes]
    if len({r.pk for r in ordonnees}) != len(ordonnees):
        raise ActionRefusee("Une routine apparaît deux fois dans l'ordre proposé.")

    def appliquer():
        for position, routine in enumerate(ordonnees):
            routine.order = position
            routine.save(update_fields=["order"])

    return Plan(
        avant=" · ".join(r.name for r in actives),
        apres=" · ".join(r.name for r in ordonnees),
        appliquer=appliquer,
        empreinte=_empreinte_routines(user),
    )


# --------------------------------------------------------------------------
# Créneaux
# --------------------------------------------------------------------------

@resolveur("creneau.poser")
def _creneau_poser(user, params, today):
    projet = _projet(user, params["projet"])
    jour = _jours_semaine([params["jour"]])[0]
    heure = _heure(params["heure"])
    minutes = params.get("minutes") or 25

    conflit = TimeSlot.objects.filter(
        project__user=user, weekday=jour, active=True, start_time=heure
    ).first()
    if conflit:
        raise ActionRefusee(
            f"{conflit.project.name} occupe déjà {JOURS[jour]} à {heure:%H:%M}."
        )

    def appliquer():
        TimeSlot.objects.create(
            project=projet, weekday=jour, start_time=heure, duration_minutes=minutes
        )

    return Plan(
        avant=f"{projet.name} n'a pas de créneau le {JOURS[jour]}",
        apres=f"{JOURS[jour]} {heure:%H:%M} — {minutes} min",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("creneau.deplacer")
def _creneau_deplacer(user, params, today):
    projet = _projet(user, params["projet"])
    actuel = _jours_semaine([params["jour_actuel"]])[0]
    creneau = TimeSlot.objects.filter(project=projet, weekday=actuel, active=True).first()
    if creneau is None:
        raise ActionRefusee(f"{projet.name} n'a pas de créneau le {JOURS[actuel]}.")

    jour = _jours_semaine([params["jour"]])[0] if params.get("jour") is not None else actuel
    heure = _heure(params["heure"]) if params.get("heure") else creneau.start_time
    minutes = params.get("minutes") or creneau.duration_minutes

    def appliquer():
        creneau.weekday = jour
        creneau.start_time = heure
        creneau.duration_minutes = minutes
        creneau.save(update_fields=["weekday", "start_time", "duration_minutes"])

    return Plan(
        avant=f"{JOURS[actuel]} {creneau.start_time:%H:%M} — {creneau.duration_minutes} min",
        apres=f"{JOURS[jour]} {heure:%H:%M} — {minutes} min",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
    )


@resolveur("creneau.retirer")
def _creneau_retirer(user, params, today):
    projet = _projet(user, params["projet"])
    jour = _jours_semaine([params["jour"]])[0]
    creneau = TimeSlot.objects.filter(project=projet, weekday=jour, active=True).first()
    if creneau is None:
        raise ActionRefusee(f"{projet.name} n'a pas de créneau le {JOURS[jour]}.")

    def appliquer():
        creneau.delete()

    return Plan(
        avant=f"{JOURS[jour]} {creneau.start_time:%H:%M}",
        apres="plus de rendez-vous ce jour-là",
        appliquer=appliquer,
        empreinte=_empreinte_projet(projet),
        avertissement="« Mardi 20h30 » se tient, « ce soir » se rate : un créneau retiré "
                      "est un rendez-vous en moins, pas seulement une ligne en moins.",
    )


# --------------------------------------------------------------------------
# Saison et réglages
# --------------------------------------------------------------------------

@resolveur("saison.signer")
def _saison_signer(user, params, today):
    from .rules import contract as contract_rules

    saison = services.current_season(user, today=today)
    if saison is None:
        raise ActionRefusee("Aucune saison en cours à signer.")
    if saison.signed:
        raise ActionRefusee(
            f"Le contrat de {saison.name} est déjà signé — {saison.contract_sessions_per_week} "
            "sessions par semaine — et un contrat signé ne bouge plus."
        )

    sessions = params["sessions"]
    verdict = contract_rules.verifier(sessions)
    if not verdict.ok:
        raise ActionRefusee(verdict.raison)

    semaines = max(1, ((saison.ends_on - saison.starts_on).days + 1) // 7)
    projets = list(
        Project.objects.filter(user=user, status=Project.ACTIVE)
        .exclude(slot=None)
        .values_list("name", flat=True)
    )
    contrat = contract_rules.Contrat(
        sessions_par_semaine=sessions, projets=tuple(projets), semaines=semaines
    )

    def appliquer():
        saison.contract_sessions_per_week = sessions
        saison.contract_projects = projets
        saison.contract_signed_at = timezone.now()
        saison.save(
            update_fields=[
                "contract_sessions_per_week",
                "contract_projects",
                "contract_signed_at",
            ]
        )

    return Plan(
        avant=f"{saison.name} — non signée",
        apres=" ".join(contrat.lignes[:2]),
        appliquer=appliquer,
        empreinte=_hacher({"saison": saison.pk, "signe": saison.signed}),
        avertissement="Un contrat signé ne bouge plus jusqu'à la clôture.",
    )


@resolveur("jour_off.declarer")
def _jour_off(user, params, today):
    from django.conf import settings

    jour = _jour(params["jour"])
    if jour <= today:
        raise ActionRefusee(
            "Un jour off se déclare au moins la veille (§11.5). Aujourd'hui, c'est "
            "un jour raté normal — et le dire après coup en ferait une excuse."
        )
    if DayOff.objects.filter(user=user, date=jour).exists():
        raise ActionRefusee(f"Le {jour:%d/%m} est déjà un jour off.")

    semaine = week_start(jour)
    pris = DayOff.objects.filter(
        user=user, date__gte=semaine, date__lt=semaine + timedelta(days=7)
    ).count()
    plafond = settings.COACH["MAX_DAYS_OFF_PER_WEEK"]
    if pris >= plafond:
        raise ActionRefusee(
            f"Déjà {pris} jour(s) off cette semaine-là, plafond à {plafond}. "
            "Au-delà, ce n'est plus un jour off, c'est un rythme — et c'est la veille "
            "qui couvre ça."
        )

    def appliquer():
        DayOff.objects.create(user=user, date=jour)

    return Plan(
        avant=f"{jour:%A %d/%m} — jour normal",
        apres=f"{jour:%A %d/%m} — jour off, neutre",
        appliquer=appliquer,
        empreinte=_hacher(list(DayOff.objects.filter(user=user).values_list("date", flat=True))),
    )


@resolveur("veille.declarer")
def _veille_declarer(user, params, today):
    from .rules import hiatus as hiatus_rules

    debut = _jour(params["debut"])
    fin = _jour(params["fin"])
    verdict = hiatus_rules.verifier(debut=debut, fin=fin, aujourdhui=today)
    if not verdict.ok:
        raise ActionRefusee(verdict.raison)
    if services.veille_en_cours(user, today=today):
        raise ActionRefusee("Une veille est déjà en cours.")

    def appliquer():
        services.declarer_veille(
            user, debut=debut, fin=fin, today=today, raison=params.get("raison", "")
        )

    return Plan(
        avant="saison en cours, jours comptés",
        apres=hiatus_rules.message(debut, fin),
        appliquer=appliquer,
        empreinte=_hacher({"veille": bool(services.veille_en_cours(user, today=today))}),
    )


@resolveur("veille.terminer")
def _veille_terminer(user, params, today):
    if services.veille_en_cours(user, today=today) is None:
        raise ActionRefusee("Aucune veille en cours.")

    def appliquer():
        services.terminer_veille(user, today=today)

    return Plan(
        avant="en veille",
        apres="reprise dès aujourd'hui, saison rendue avec ses jours",
        appliquer=appliquer,
        empreinte=_hacher({"veille": True}),
    )


@resolveur("fenetre.regler")
def _fenetre_regler(user, params, today):
    debut = _heure(params["debut"])
    fin = _heure(params["fin"])
    if fin <= debut:
        raise ActionRefusee("La fin de la fenêtre est avant son début.")

    jours = _jours_semaine(params.get("jours"), defaut=list(range(7)))
    fenetres = list(user.profile.windows.filter(weekday__in=jours).order_by("weekday"))
    if not fenetres:
        raise ActionRefusee("Aucune fenêtre déclarée sur ces jours-là.")

    def appliquer():
        for fenetre in fenetres:
            fenetre.start_time = debut
            fenetre.end_time = fin
            fenetre.save(update_fields=["start_time", "end_time"])

    return Plan(
        avant=" · ".join(
            f"{JOURS[f.weekday][:3]} {f.start_time:%H:%M}–{f.end_time:%H:%M}" for f in fenetres
        ),
        apres=f"{dire_jours(jours)} : {debut:%H:%M}–{fin:%H:%M}",
        appliquer=appliquer,
        empreinte=_empreinte_globale(user),
    )


@resolveur("reglages.gardien")
def _reglages_gardien(user, params, today):
    minutes = params["minutes"]
    if not 5 <= minutes <= 240:
        raise ActionRefusee("Le gardien se place entre 5 et 240 minutes avant la fin.")

    profil = user.profile

    def appliquer():
        profil.guardian_minutes_before_end = minutes
        profil.save(update_fields=["guardian_minutes_before_end"])

    return Plan(
        avant=f"{profil.guardian_minutes_before_end} min avant la fin de la fenêtre",
        apres=f"{minutes} min avant la fin de la fenêtre",
        appliquer=appliquer,
        empreinte=_empreinte_globale(user),
    )


@resolveur("reglages.amorce_matin")
def _reglages_amorce(user, params, today):
    profil = user.profile
    brut = (params.get("heure") or "").strip()
    heure = _heure(brut).hour if brut else None

    def appliquer():
        profil.morning_hour = heure
        profil.save(update_fields=["morning_hour"])

    return Plan(
        avant=f"{profil.morning_hour}h" if profil.morning_hour is not None else "coupé",
        apres=f"{heure}h" if heure is not None else "coupé",
        appliquer=appliquer,
        empreinte=_empreinte_globale(user),
    )


@resolveur("reglages.fuseau")
def _reglages_fuseau(user, params, today):
    fuseau = params["fuseau"].strip()
    try:
        ZoneInfo(fuseau)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise ActionRefusee(f"« {fuseau} » n'est pas un fuseau connu.")

    profil = user.profile

    def appliquer():
        profil.timezone_name = fuseau
        profil.save(update_fields=["timezone_name"])

    return Plan(
        avant=profil.timezone_name,
        apres=fuseau,
        appliquer=appliquer,
        empreinte=_empreinte_globale(user),
        avertissement="La fenêtre du soir et la bascule de 4h suivent ce réglage.",
    )
