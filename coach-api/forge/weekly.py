"""Le bilan hebdomadaire envoyé à un ami (SPEC §4.7).

Le §0.1 est le point de départ du produit : la contrainte interne n'existe pas,
tout ce qui a tenu jusqu'ici venait de l'extérieur. Le streak, le boss, les
sanctions du §14 sont des cadres qu'on s'impose — donc des cadres qu'on peut se
lever un soir de fatigue. Ce bilan-ci engage **quelqu'un d'autre**, et c'est la
seule chose du système qui ne se négocie pas avec soi-même.

D'où trois règles qui ne sont pas des détails :

**Ce qui n'y figure pas.** Ni qualité de session, ni temps d'écran, ni fuite de
temps, ni garde. Ces signaux sont bruités ; les envoyer à un tiers transforme du
bruit en jugement social, et donnerait une excellente raison de couper le bilan.
Le §4.7 et le §11.10 les excluent nommément, et ``_INTERDITS`` le vérifie sur le
texte produit — un prompt qui dérive ne doit pas pouvoir les faire sortir.

**Le désarmement coûte 24 heures.** Le §4.7 en fait le seul mécanisme
volontairement difficile à désactiver du produit. Pas impossible : difficile. La
demande est enregistrée, et elle ne prend effet que le lendemain — le temps que
le soir où l'on veut couper soit passé.

**L'accusé de lecture.** Un contrôleur qui ne regarde pas ne contrôle rien. Le
bilan part avec un lien signé (§11.7) qui ne fait qu'une chose, marquer lu, et
trois semaines sans lecture sont signalées à l'utilisateur.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Sum
from django.utils import timezone

from . import links, services
from .llm import LLMUnavailable, QualityGateFailed, Task, gate, get_provider
from .llm import prompts
from .models import (
    ActionLink,
    Commitment,
    Profile,
    Project,
    RoadmapStep,
    Session,
    Track,
    WeeklyReport,
)
from .rules.calendar import week_start

logger = logging.getLogger(__name__)

# Le délai du §4.7. Vingt-quatre heures, et pas « à la prochaine ouverture » :
# ce qui doit passer, c'est une soirée entière.
DELAI_DESARMEMENT = timedelta(hours=24)

# Au-delà, le destinataire ne contrôle plus rien et il faut le dire.
SEUIL_NON_LUS = 3

# Mots qui trahissent une donnée que le §4.7 interdit d'envoyer à un tiers. La
# liste vise le vocabulaire, pas les chiffres : un modèle qui parlerait de
# « scroll » ou de « temps d'écran » aurait déjà franchi la ligne.
_INTERDITS = (
    "scroll",
    "temps d'écran",
    "temps d ecran",
    "youtube",
    "tiktok",
    "instagram",
    "reddit",
    "garde",
    "qualité de session",
    "fuite",
)


# --------------------------------------------------------------------------
# Les faits
# --------------------------------------------------------------------------

def collecter(user, *, semaine: date) -> dict:
    """Les faits de la semaine, et rien d'autre.

    Une seule chose est vraie de toutes les lignes ci-dessous : elles décrivent
    du **travail fait**. Rien de ce qui n'a pas été fait n'y entre, et aucune
    mesure de sonde non plus.
    """
    fin = semaine + timedelta(days=6)
    sessions = Session.objects.filter(
        user=user, status=Session.DONE, coach_day__gte=semaine, coach_day__lte=fin
    )

    par_projet = {
        row["project__name"]: row
        for row in sessions.values("project__name").annotate(
            minutes=Sum("actual_minutes"), n=Count("id")
        )
    }

    etapes = list(
        RoadmapStep.objects.filter(
            project__user=user,
            state=RoadmapStep.DONE,
            done_at__date__gte=semaine,
            done_at__date__lte=fin,
        ).select_related("project")
    )

    engagements = list(
        Commitment.objects.filter(project__user=user, week_start=semaine).select_related("project")
    )

    atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
    etat = services.streak_state(user, atelier, today=fin)
    saison = services.current_season(user, today=fin)

    boss = None
    if saison and hasattr(saison, "boss"):
        b = saison.boss
        boss = {
            "nom": b.name,
            "restant": b.current_hp,
            "total": b.max_hp,
            "part": round(100 * (1 - b.ratio)),
        }

    return {
        "semaine": semaine,
        "streak": etat.current,
        "projets": [
            {
                "nom": nom,
                "minutes": row["minutes"] or 0,
                "sessions": row["n"],
            }
            for nom, row in sorted(par_projet.items())
        ],
        "etapes": [f"{e.project.name} — {e.label}" for e in etapes],
        "engagements": [
            {
                "nom": c.project.name,
                "pris": c.planned_sessions,
                "tenus": c.done_sessions,
                "ok": c.kept,
            }
            for c in engagements
        ],
        "boss": boss,
        "titre": saison.title_awarded if saison else "",
        "rang": services.rank_state(user, today=fin)["code"],
    }


# --------------------------------------------------------------------------
# Le texte
# --------------------------------------------------------------------------

def rediger(faits: dict, *, synthese: str = "") -> str:
    """Le bilan, en texte simple. Lisible dans un message, sans mise en forme.

    Écrit ici et pas par le modèle : le §4.7 énumère ce qui doit y figurer, et
    laisser un modèle composer la liste reviendrait à parier chaque dimanche sur
    le fait qu'il n'oubliera rien. Il n'écrit qu'une phrase, et elle est
    facultative.
    """
    debut = faits["semaine"]
    fin = debut + timedelta(days=6)
    lignes = [f"Semaine du {debut.strftime('%d/%m')} au {fin.strftime('%d/%m')}", ""]

    total = sum(p["minutes"] for p in faits["projets"])
    lignes.append(f"Série en cours : {faits['streak']} jour(s). Rang {faits['rang']}.")
    lignes.append(f"Temps travaillé : {_heures(total)} sur {len(faits['projets'])} projet(s).")

    for projet in faits["projets"]:
        lignes.append(f"  · {projet['nom']} — {_heures(projet['minutes'])}, {projet['sessions']} session(s)")

    if faits["engagements"]:
        tenus = sum(1 for e in faits["engagements"] if e["ok"])
        lignes.append("")
        lignes.append(f"Engagements tenus : {tenus} sur {len(faits['engagements'])}.")
        for e in faits["engagements"]:
            lignes.append(f"  · {e['nom']} — {e['tenus']}/{e['pris']}")

    if faits["etapes"]:
        lignes.append("")
        lignes.append(f"Étapes terminées ({len(faits['etapes'])}) :")
        lignes.extend(f"  · {etape}" for etape in faits["etapes"])

    if faits["boss"]:
        b = faits["boss"]
        lignes.append("")
        lignes.append(f"Boss de saison — {b['nom']} : {b['part']} % entamé.")

    if faits["titre"]:
        lignes.append(f"Titre courant : {faits['titre']}.")

    if synthese:
        lignes.append("")
        lignes.append(synthese)

    return "\n".join(lignes)


def _heures(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d}"


def synthese(faits: dict) -> str:
    """La phrase du §4.7, écrite par le modèle. Vide s'il manque ou dérape.

    Facultative par construction : le bilan part sans elle, et personne ne s'en
    aperçoit. C'est la même règle que partout ailleurs — le modèle améliore, il
    ne conditionne rien.
    """
    try:
        reponse = get_provider().structured(
            task=Task.BILAN,
            system=prompts.SYSTEM_BILAN,
            prompt=prompts.bilan_prompt(faits),
            schema=prompts.SCHEMA_BILAN,
        )
    except LLMUnavailable as erreur:
        logger.info("bilan sans IA : %s", erreur)
        return ""

    if reponse.refused:
        return ""

    payload = reponse.content if isinstance(reponse.content, dict) else {}
    try:
        return gate(Task.BILAN, payload)["phrase"]
    except QualityGateFailed as erreur:
        logger.warning("phrase de bilan refusée : %s", erreur.reason)
        return ""


def contient_un_interdit(texte: str) -> str:
    """Le mot interdit trouvé dans le texte, ou une chaîne vide.

    Dernier filet avant l'envoi. Ce qui est en jeu n'est pas une erreur de
    style : une fuite de temps envoyée à un tiers est du bruit transformé en
    jugement social, et le §4.7 dit ce qu'elle coûterait — une bonne raison de
    couper le bilan, donc la fin du seul point d'appui externe.
    """
    bas = texte.lower()
    return next((mot for mot in _INTERDITS if mot in bas), "")


# --------------------------------------------------------------------------
# L'envoi
# --------------------------------------------------------------------------

def envoyer(user, *, semaine: date | None = None, now: datetime | None = None) -> WeeklyReport | None:
    """Compose et envoie le bilan de la semaine écoulée. Rend ``None`` si rien à faire.

    Idempotent par l'unicité en base : deux passages le même dimanche n'envoient
    qu'un bilan.
    """
    now = now or timezone.now()
    profile: Profile = user.profile

    # La semaine décrite est celle **en cours**, pas la précédente : le bilan
    # part le dimanche soir, et ce dimanche-là en fait partie. Calculée dans le
    # fuseau de l'utilisateur, sinon un envoi à 20h à Paris tomberait la veille
    # en UTC un dimanche sur deux et décalerait le bilan d'une semaine entière.
    local = now.astimezone(ZoneInfo(profile.timezone_name))
    semaine = semaine or week_start(local.date())

    if not destinataire_actif(profile, now=now):
        return None
    if WeeklyReport.objects.filter(user=user, week_start=semaine).exists():
        return None

    faits = collecter(user, semaine=semaine)
    texte = rediger(faits, synthese=synthese(faits))

    interdit = contient_un_interdit(texte)
    if interdit:
        # On préfère un bilan sans la phrase à un bilan qui parle de ce que le
        # §4.7 exclut. Le texte déterministe, lui, ne peut pas dériver.
        logger.warning("phrase de bilan écartée : elle contenait « %s »", interdit)
        texte = rediger(faits)

    rapport = WeeklyReport.objects.create(user=user, week_start=semaine, body=texte)

    lien, secret = links.emettre(
        user,
        kind=ActionLink.VU,
        context={"titre": f"Bilan de la semaine du {semaine.strftime('%d/%m')}", "bilan_id": rapport.pk},
    )
    base = (profile.public_base_url or "").rstrip("/")
    message = texte + (f"\n\nLu ? {base}/l/{secret}" if base else "")

    canal = _poster(profile.buddy_channel, message)
    WeeklyReport.objects.filter(pk=rapport.pk).update(
        sent_at=timezone.now() if canal else None, channel=canal
    )
    rapport.refresh_from_db()

    if not canal:
        # Le lien émis ne sert à rien si rien n'est parti : le laisser vivant
        # laisserait traîner un secret utilisable pour rien.
        ActionLink.objects.filter(pk=lien.pk).delete()

    return rapport


def _poster(canal: str, message: str) -> str:
    """Poste sur le webhook du destinataire. Rend le canal utilisé, ou une chaîne vide.

    Un webhook Discord suffit et n'oblige personne à créer un compte : l'ami lit
    dans un salon qu'il a déjà. L'e-mail viendra si le besoin s'en fait sentir ;
    le §4.7 laisse le choix ouvert et ne demande pas les deux.
    """
    if not canal:
        return ""

    requete = urllib.request.Request(
        canal,
        data=json.dumps({"content": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            return "discord" if 200 <= reponse.status < 300 else ""
    except Exception as erreur:                      # réseau, webhook révoqué…
        logger.warning("bilan non envoyé : %s", erreur)
        return ""


# --------------------------------------------------------------------------
# Le désarmement, et le contrôleur qui ne regarde plus
# --------------------------------------------------------------------------

def destinataire_actif(profile: Profile, *, now: datetime | None = None) -> bool:
    """Vrai tant que le bilan doit partir."""
    now = now or timezone.now()
    if not profile.buddy_channel:
        return False
    demande = profile.buddy_disable_requested_at
    return not (demande and now >= demande + DELAI_DESARMEMENT)


def demander_desactivation(profile: Profile, *, now: datetime | None = None) -> datetime:
    """Enregistre la demande. Rend l'instant où elle prendra effet (§4.7).

    Le délai est le mécanisme. Couper le bilan est une décision qui se prend un
    soir précis — celui où il va dire quelque chose de désagréable — et
    vingt-quatre heures suffisent à ce que ce ne soit plus le même soir.
    """
    now = now or timezone.now()
    if not profile.buddy_disable_requested_at:
        profile.buddy_disable_requested_at = now
        profile.save(update_fields=["buddy_disable_requested_at"])
    return profile.buddy_disable_requested_at + DELAI_DESARMEMENT


def annuler_desactivation(profile: Profile) -> None:
    """Reprendre est immédiat. Seul l'arrêt coûte du temps."""
    if profile.buddy_disable_requested_at:
        profile.buddy_disable_requested_at = None
        profile.save(update_fields=["buddy_disable_requested_at"])


def remplacer_destinataire(profile: Profile, canal: str, *, now: datetime | None = None) -> str:
    """Change le destinataire du bilan. Immédiat, et c'est le sujet.

    Le §4.7 fait payer vingt-quatre heures pour **arrêter** le bilan, et c'est
    juste : couper le contrôle est une décision qu'on prend un soir précis —
    celui où il va dire quelque chose de désagréable — et le délai suffit à ce
    que ce ne soit plus le même soir.

    Remplacer n'est pas arrêter. Le bilan continue de partir, à quelqu'un
    d'autre. Faire payer le même prix aux deux gestes revient à décourager
    celui qui sauve le mécanisme : au bout de trois semaines sans lecture
    (§4.7), la bonne réponse est de changer de destinataire, et si elle coûte
    un jour d'attente, personne ne la prend — on désarme, ou on garde un
    contrôleur qui ne regarde plus, ce qui est pire que pas de contrôleur du
    tout puisqu'on se croit surveillé.

    **L'ancien destinataire est prévenu.** C'est ce qui empêche le
    remplacement d'être un désarmement déguisé : personne ne peut basculer
    vers un canal qu'il contrôle sans que le précédent l'apprenne. Le système
    ne peut pas vérifier qui est au bout du fil ; il peut rendre le geste
    visible, et c'est tout ce qui est honnête.

    Un canal vide est refusé : ça, c'est un arrêt, et l'arrêt a son chemin.
    """
    now = now or timezone.now()
    canal = (canal or "").strip()
    if not canal:
        raise ValueError(
            "Un destinataire vide, c'est un arrêt — et l'arrêt passe par les "
            "vingt-quatre heures du §4.7."
        )
    if canal == profile.buddy_channel:
        raise ValueError("C'est déjà le destinataire actuel.")

    ancien = profile.buddy_channel
    if ancien:
        _poster(
            ancien,
            "Ce bilan hebdomadaire part désormais à quelqu'un d'autre. "
            "Tu ne recevras plus les suivants.",
        )

    profile.buddy_channel = canal
    # Reprendre est immédiat (§4.7) : basculer vers un nouveau destinataire
    # annule une demande d'arrêt en cours, comme le ferait une annulation.
    profile.buddy_disable_requested_at = None
    profile.save(update_fields=["buddy_channel", "buddy_disable_requested_at"])
    return canal


def proposition_de_remplacement(user, *, seuil: int = SEUIL_NON_LUS) -> dict | None:
    """Ce qu'on propose quand le destinataire ne lit plus (§4.7).

    Le manque était là : les trois semaines sans lecture étaient signalées, et
    rien ne suivait. Un constat sans suite se lit deux fois puis s'ignore.
    """
    compte = non_lus(user, seuil=seuil)
    if compte < seuil:
        return None

    return {
        "non_lus": compte,
        "line": (
            f"{compte} bilans partis sans être ouverts. Un contrôleur qui ne "
            "regarde pas ne contrôle rien, et se croire surveillé alors qu'on "
            "ne l'est plus est pire que de savoir qu'on ne l'est pas."
        ),
        "action": "Changer de destinataire — immédiat, sans les 24 heures.",
    }


def non_lus(user, *, seuil: int = SEUIL_NON_LUS) -> int:
    """Combien de bilans consécutifs sont partis sans être lus.

    Zéro tant que le dernier envoyé a été lu. Au-delà du seuil, le §4.7 demande
    de le signaler et de proposer un autre destinataire : un contrôleur qui ne
    regarde pas ne contrôle rien, et se croire surveillé alors qu'on ne l'est
    plus est pire que de savoir qu'on ne l'est pas.
    """
    compte = 0
    for rapport in WeeklyReport.objects.filter(user=user, sent_at__isnull=False):
        if rapport.read_at:
            break
        compte += 1
    return compte
