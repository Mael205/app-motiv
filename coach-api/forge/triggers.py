"""Les déclencheurs.

Le diagnostic est explicite (SPEC §11.2) : « j'oublie de le faire » n'est pas un
problème de mémoire, c'est une absence de déclencheur. Ce module contient donc
tout ce qui fait que l'app se manifeste sans qu'on l'ouvre.

1. Le rappel de créneau, 10 minutes **avant** un rendez-vous fixe.
2. Le gardien de créneau, 20 minutes **après**, quand rien n'a démarré. C'est
   lui qui donne un poids à l'heure annoncée : depuis qu'une séance compte à
   n'importe quelle heure, un rendez-vous que personne ne constate n'est plus un
   rendez-vous, c'est une préférence.
3. Le gardien du soir, quand la fenêtre se referme sans session validée. Lui
   seul porte l'enjeu de la journée — plancher, boucliers, streak.
4. La fin du sas de détente.
5. Les rappels différés (le « reporter de 15 min » du §11.7), le rappel du
   matin, la coche automatique des habitudes horaires, le bilan de la nuit et
   celui du dimanche.

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

from .models import (
    NotificationLog,
    Profile,
    Rappel,
    RelaxWindow,
    Routine,
    RoutineCheck,
    Session,
    Track,
)
from .notifications import Notification, notify
from .rules.calendar import coach_day, evening_window
from .rules import sommeil as sommeil_rules
from . import services
from .services import DEGRADED_MINUTES, propose, streak_state

GUARDIAN = "gardien"
GUARDIAN_SLOT = "gardien_creneau"
SLOT_REMINDER = "creneau"
RELAX_OVER = "sas_fini"
BILAN = "bilan"
DAILY = "bilan_du_jour"
BILAN_NON_LU = "bilan_non_lu"
MATIN = "matin"
REVUE = "revue"
RAPPEL = "rappel"

# Au-delà, un rappel différé ne part plus. Le serveur peut avoir été éteint à
# l'échéance ; faire arriver une heure plus tard un gardien reporté d'un quart
# d'heure réveillerait quelqu'un pour une soirée déjà finie, et une notification
# à contretemps est celle qui apprend à ignorer toutes les autres.
RETARD_TOLERE_MINUTES = 20

# Combien de temps après un créneau annoncé le gardien constate qu'il est passé.
# Vingt minutes : assez pour finir ce qu'on faisait et s'installer, trop peu
# pour que la soirée ait basculé ailleurs.
RETARD_CRENEAU_MINUTES = 20

# Dimanche 20h. Assez tôt pour que la semaine décrite soit encore la semaine
# qu'on a en tête, assez tard pour que le dimanche compte dedans.
HEURE_BILAN = 20


def run_all(now: datetime | None = None) -> list[dict]:
    """Point d'entrée unique, appelé chaque minute par l'ordonnanceur."""
    now = now or timezone.now()
    fired: list[dict] = []

    for profile in Profile.objects.select_related("user").all():
        today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)
        # La reprise ne dépend d'aucun geste : quelqu'un qui rentre après trois
        # semaines n'a pas à cliquer sur « je suis rentré ».
        services.synchroniser_veille(profile.user, today=today)
        if services.veille_en_cours(profile.user, today=today):
            # Le silence complet est la moitié de ce que la veille promet.
            continue

        fired += check_rappels(profile, now)
        fired += check_habitudes(profile, now)
        fired += check_morning(profile, now)
        fired += check_slot_reminder(profile, now)
        fired += check_slot_guardian(profile, now)
        fired += check_relax_end(profile, now)
        fired += check_guardian(profile, now)
        fired += check_daily_report(profile, now)
        fired += check_weekly_report(profile, now)

    return fired


# --------------------------------------------------------------------------
# 0 ter. Les rappels différés (le « reporter de 15 min » du §11.7)
# --------------------------------------------------------------------------

def check_rappels(profile: Profile, now: datetime) -> list[dict]:
    """Envoie les rappels arrivés à échéance, et périme les autres.

    Le report est demandé depuis un bouton de notification, donc depuis un
    service worker qui dort bien avant l'échéance. Le seul endroit capable de
    tenir un quart d'heure est celui qui tourne déjà chaque minute.

    Deux garde-fous, et le second compte autant que le premier : un rappel ne
    part qu'une fois, et **ne part plus s'il est en retard**. Un rappel périmé
    est marqué comme traité plutôt que laissé en attente — sinon il ressortirait
    au prochain démarrage du serveur, c'est-à-dire au pire moment possible.
    """
    fired: list[dict] = []
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)
    limite = now - timedelta(minutes=RETARD_TOLERE_MINUTES)

    for rappel in Rappel.objects.filter(user=profile.user, sent_at=None, due_at__lte=now):
        if rappel.due_at < limite:
            rappel.sent_at = now                    # périmé : classé, jamais envoyé
            rappel.save(update_fields=["sent_at"])
            continue

        # Le jour est peut-être déjà validé depuis le report : le gardien n'a
        # alors plus rien à dire, et le §17 interdit de relancer quelqu'un qui a
        # fait ce qu'il fallait.
        if rappel.kind == "gardien_reporte" and _minutes_today(profile.user, today) >= DEGRADED_MINUTES:
            rappel.sent_at = now
            rappel.save(update_fields=["sent_at"])
            continue

        notify(
            profile.user,
            Notification(title=rappel.title, body=rappel.body, kind="gardien"),
        )
        rappel.sent_at = now
        rappel.save(update_fields=["sent_at"])
        fired.append({"kind": RAPPEL, "rappel": rappel.kind})

    return fired


# --------------------------------------------------------------------------
# 0 bis. Les habitudes horaires que les sondes ont déjà prouvées
# --------------------------------------------------------------------------

def check_habitudes(profile: Profile, now: datetime) -> list[dict]:
    """Coche « debout » et « au lit » quand les sondes l'ont déjà démontré.

    **Pourquoi automatiser celle-là et pas les autres.** Une routine se coche
    parce qu'on l'a faite, et personne d'autre ne peut le savoir : aucune sonde
    ne voit un étirement. Le lever et le coucher sont différents — ils laissent
    une trace mesurable, et cette trace est *meilleure* que le tap. On peut
    cocher « debout » et se recoucher ; on ne peut pas produire une activité à
    7h05 en dormant.

    Trois bornes, et elles ne se négocient pas :

    * **preuve positive seulement.** Aucun silence ne coche quoi que ce soit.
      Une journée sans sonde reste une journée à cocher à la main ;
    * **jamais de décoche, jamais d'échec.** Le §6 interdit qu'une sonde
      invalide quoi que ce soit. Ce déclencheur ne sait qu'ajouter ;
    * **le coucher attend la journée close.** Avant la bascule de 4h, l'absence
      d'activité après 23h30 ne prouve rien : il est 22h. La veille est donc
      repassée une fois, le lendemain.

    Ça ne touche pas au §11.10 — « aucune sonde ne peut déclarer une journée
    tenue ». Une journée tenue est un fait de la piste Atelier, et rien ici n'en
    approche : une routine cochée ne valide aucun streak (§11.4), et c'est
    précisément ce qui rend cette automatisation sans danger.
    """
    fired: list[dict] = []
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)

    horaires = Routine.objects.filter(user=profile.user, active=True, deadline__isnull=False)
    for routine in horaires:
        regle = routine.to_rule()
        # Aujourd'hui pour le lever, hier pour le coucher : la journée d'hier
        # est close, donc son silence du soir veut enfin dire quelque chose.
        for jour, finie in ((today, False), (today - timedelta(days=1), True)):
            if not regle.is_due(jour):
                continue
            if RoutineCheck.objects.filter(routine=routine, day=jour).exists():
                continue

            premiere, derniere = services._bornes_d_activite(profile.user, jour)
            preuve = sommeil_rules.coche_automatique(
                routine.deadline,
                routine.direction,
                routine.anchor,
                premiere_activite=premiere,
                derniere_activite=derniere,
                journee_finie=finie,
                rollover_hour=profile.day_rollover_hour,
            )
            if preuve is None:
                continue

            # Créditée à l'heure du fait, jamais à celle du traitement : un
            # déclencheur qui tourne à 14h et crédite « debout » à 14h
            # enregistrerait une coche hors fenêtre pour une preuve qui, elle,
            # était dedans.
            services.check_routine(
                routine, day=jour, source=RoutineCheck.AGENT, at=preuve
            )
            fired.append(
                {
                    "kind": "habitude_auto",
                    "user": profile.user.username,
                    "routine": routine.name,
                    "day": jour.isoformat(),
                    "preuve": preuve.isoformat(timespec="minutes"),
                }
            )

    return fired


# --------------------------------------------------------------------------
# 0. Le rappel du matin
# --------------------------------------------------------------------------

def check_morning(profile: Profile, now: datetime) -> list[dict]:
    """Redit au réveil l'amorce laissée hier soir (§11.3).

    L'amorce existe déjà, et elle n'est lue qu'au moment de démarrer —
    c'est-à-dire le soir, quand il est trop tard pour y penser. La sortir le
    matin fait travailler l'idée toute la journée : à 21h, ce n'est plus une
    décision à prendre mais une chose déjà en tête.

    Silencieux s'il n'y a rien de précis à dire. « Bonne journée » n'est pas une
    notification, c'est du bruit — et le bruit apprend à ignorer les vraies.
    """
    if profile.morning_hour is None:
        return []

    local = now.astimezone(_zone(profile))
    if local.hour != profile.morning_hour or local.minute >= 5:
        return []

    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)
    proposal = propose(profile.user, today=today)
    if not proposal:
        return []

    amorce = proposal["amorce"] or (proposal["step"]["label"] if proposal["step"] else "")
    if not amorce:
        return []

    sent = _deliver(
        profile.user,
        MATIN,
        today,
        Notification(
            title="Ce soir",
            body=f"{amorce}\n{proposal['project']['name']} · {proposal['minutes']} min.",
            kind="info",
        ),
    )
    return [{"kind": MATIN}] if sent else []


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
# 1 bis. Le gardien du créneau : l'heure annoncée est passée
# --------------------------------------------------------------------------

def check_slot_guardian(profile: Profile, now: datetime) -> list[dict]:
    """Constate qu'un rendez-vous fixe est passé sans que rien n'ait démarré.

    **Pourquoi il existe** (tranché le 20 août 2026). Depuis qu'une séance
    compte à n'importe quelle heure, l'heure annoncée ne pesait plus rien : la
    manquer ne se disait qu'au bilan du lendemain matin, ou à la revue du
    dimanche — six jours plus tard. Le §11.2 est pourtant explicite : « mardi
    20h30 se tient, "ce soir" se rate », et un rendez-vous dont personne ne
    constate le passage n'est pas un rendez-vous, c'est une préférence.

    **Ce qu'il n'est pas.** Il ne sanctionne rien, ne touche ni au streak ni au
    rang, et ne parle pas de boucliers — c'est le gardien du soir qui porte
    l'enjeu de la journée, une fois, en fin de fenêtre. Celui-ci ne dit qu'une
    chose : l'heure que tu as fixée est passée, voilà la tâche, voilà deux
    boutons. Le §17 interdit d'ajouter une punition ; constater n'en est pas
    une, et se taire n'aurait pas aidé.

    Silencieux si une séance tourne — on est dessus —, si le projet a déjà eu
    sa séance dans la journée, et si le rappel du créneau n'a pas eu lieu.
    """
    user = profile.user
    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)
    local = now.astimezone(_zone(profile))

    if Session.objects.filter(user=user, status=Session.RUNNING).exists():
        return []

    from .models import TimeSlot

    fired: list[dict] = []
    for slot in TimeSlot.objects.filter(
        project__user=user, project__status="active", active=True, weekday=today.weekday()
    ).select_related("project"):
        rendez_vous = local.replace(
            hour=slot.start_time.hour, minute=slot.start_time.minute, second=0, microsecond=0
        )
        retard = (local - rendez_vous).total_seconds() / 60
        if not (RETARD_CRENEAU_MINUTES <= retard < RETARD_CRENEAU_MINUTES + 5):
            continue

        # Une séance sur ce projet aujourd'hui suffit : le rendez-vous a été
        # honoré, même décalé. Le constater quand même serait du reproche.
        if Session.objects.filter(
            user=user, project=slot.project, coach_day=today, status=Session.DONE
        ).exists():
            continue

        proposal = propose(user, today=today)
        corps = f"{slot.start_time.strftime('%Hh%M')} est passé, rien de lancé."
        if proposal and proposal["project"]["id"] == slot.project_id:
            from .coaching import tache_du_gardien

            tache = tache_du_gardien(proposal, minutes_restantes=slot.duration_minutes)
            if tache["texte"]:
                corps += "\n" + f"{DEGRADED_MINUTES} min : {tache['texte']}"
        else:
            corps += "\n" + f"{slot.duration_minutes} min prévues sur {slot.project.name}."

        boutons = _boutons_du_gardien(
            user,
            slot.project_id,
            titre=f"{slot.project.name}, toujours rien",
            corps=corps,
        )
        sent = _deliver(
            user,
            f"{GUARDIAN_SLOT}:{slot.id}",
            today,
            Notification(
                title=slot.project.name,
                body=corps,
                kind="creneau",
                actions=tuple(bouton for bouton, _ in boutons),
            ),
        )
        if not sent:
            from .models import ActionLink

            ActionLink.objects.filter(pk__in=[lien.pk for _, lien in boutons]).delete()
            continue

        fired.append({"kind": GUARDIAN_SLOT, "project": slot.project.name})

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

    # Les deux boutons du §11.7. Ils existent pour une raison mesurée par le
    # §0.9 : ouvrir l'app est déjà une décision, et le soir où le gardien tombe
    # est précisément le soir où l'on n'en prend pas. Un bouton qui démarre dix
    # minutes fait passer le coût de « ouvrir, lire, choisir, démarrer » à un
    # appui — et « reporter » est la seule réponse honnête à « pas maintenant »,
    # celle qui évite de balayer la notification et donc de la perdre.
    boutons = _boutons_du_gardien(
        user,
        proposal["project"]["id"] if proposal else None,
        titre="Toujours rien de posé",
        corps=body,
    )

    sent = _deliver(
        user,
        GUARDIAN,
        today,
        Notification(
            title="Rien de posé ce soir",
            body=body,
            kind="gardien",
            actions=tuple(bouton for bouton, _ in boutons),
        ),
    )
    if not sent:
        # Rien n'est parti : les liens émis ne serviraient à personne et
        # resteraient des secrets utilisables pour rien. Même règle qu'au §4.7.
        from .models import ActionLink

        ActionLink.objects.filter(pk__in=[lien.pk for _, lien in boutons]).delete()
    return [{"kind": GUARDIAN, "delivered": sent}] if sent else []


def _boutons_du_gardien(
    user, project_id: int | None, *, titre: str, corps: str
) -> list[tuple[dict, object]]:
    """Émet les liens des boutons et rend ``(bouton, lien)`` pour chacun.

    Le lien **est** le droit d'agir : le service worker n'a pas de jeton, et lui
    en donner un reviendrait à sortir un secret de longue durée de l'endroit qui
    le garde pour le poser dans un contexte qui survit à la déconnexion. Ceux-ci
    expirent avec la journée et ne font qu'une chose (§11.7).
    """
    from .models import ActionLink
    from . import links

    boutons: list[tuple[dict, object]] = []

    if project_id:
        lien, secret = links.emettre(
            user,
            kind=ActionLink.DEMARRER,
            context={"project_id": project_id, "minutes": DEGRADED_MINUTES},
        )
        boutons.append(
            (
                {
                    "action": "demarrer",
                    "title": f"Démarrer {DEGRADED_MINUTES} min",
                    "post": f"/api/links/{secret}",
                },
                lien,
            )
        )

    lien, secret = links.emettre(
        user,
        kind=ActionLink.REPORTER,
        context={"titre": titre, "corps": corps},
    )
    boutons.append(
        (
            {
                "action": "reporter",
                "title": f"Reporter {links.REPORT_MINUTES} min",
                "post": f"/api/links/{secret}",
            },
            lien,
        )
    )
    return boutons


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
    revue = review.ouvrir(profile.user, now=now)
    fired = _poser_une_question(profile, revue, now=now)

    rapport = weekly.envoyer(profile.user, now=now)
    if rapport is None:
        return fired

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

    return fired + [{"kind": BILAN, "sent": bool(rapport.sent_at)}]


def _poser_une_question(profile: Profile, revue, *, now: datetime) -> list[dict]:
    """Envoie **une** question de la revue, avec son lien signé (§5.3, §11.7).

    C'est le dernier morceau du canal entrant : le type ``reponse`` existait, la
    page savait l'afficher, et personne ne l'émettait jamais. La revue restait
    donc une chose à ouvrir dans l'app un dimanche soir — c'est-à-dire, en
    pratique, une chose qu'on n'ouvre pas.

    **Sans adresse publique, rien ne part.** Un lien vers ``127.0.0.1`` ne mène
    nulle part depuis un téléphone, et une notification qui pose une question
    sans donner le moyen d'y répondre est pire que le silence : elle ajoute une
    chose à faire plus tard. La même règle que le bilan de l'ami (§4.7).
    """
    base = (profile.public_base_url or "").rstrip("/")
    if not base:
        return []

    from . import review

    emis = review.lien_de_question(revue)
    if emis is None:
        return []

    secret, question = emis
    lignes = [question.get("fait", ""), question.get("question", ""), "", f"{base}/l/{secret}"]
    corps = "\n".join(ligne for ligne in lignes if ligne is not None)

    today = coach_day(now, profile.timezone_name, profile.day_rollover_hour)
    sent = _deliver(
        profile.user,
        REVUE,
        today,
        Notification(
            title="Revue de la semaine",
            body=corps.strip(),
            kind="bilan",
            action_label="Répondre",
            action_url=f"{base}/l/{secret}",
        ),
    )
    return [{"kind": REVUE, "delivered": sent}] if sent else []


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
