"""Modèle de données du coach (SPEC §10).

Le serveur est la source de vérité. Les états dérivés (streak, niveau, rang,
dégâts au boss) ne sont pas stockés en double : ils se recalculent depuis les
faits — sessions et journées — par la logique pure de ``forge/rules``.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import time, timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from forge.rules import gardes as rules_gardes
from forge.rules import loot as rules_loot
from forge.rules import phantom as rules_phantom
from forge.rules import relics as rules_relics
from forge.rules import routines as rules_routines
from forge.rules import signals as rules_signals
from forge.rules import slots as rules_slots
from forge.rules import verification as rules_verification
from forge.rules import years as rules_years


class Profile(models.Model):
    """Réglages de l'utilisateur. Un seul au départ, modélisé proprement."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    timezone_name = models.CharField(max_length=64, default="Europe/Paris")
    day_rollover_hour = models.PositiveSmallIntegerField(default=4)
    discord_webhook = models.URLField(blank=True, help_text="Webhook d'un salon perso, canal de redondance")
    buddy_channel = models.CharField(max_length=255, blank=True)
    public_base_url = models.URLField(
        blank=True,
        help_text=(
            "Adresse par laquelle un lien signé est joignable de l'extérieur (§11.7). "
            "Sans elle, le bilan part sans son bouton « vu » : mieux vaut pas de lien "
            "qu'un lien vers 127.0.0.1, qui ne mène nulle part chez l'ami."
        ),
    )
    guardian_minutes_before_end = models.PositiveSmallIntegerField(
        default=90, help_text="Le gardien se déclenche N minutes avant la fin de la fenêtre du soir"
    )
    morning_hour = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=8,
        help_text=(
            "Heure du rappel du matin, qui redit l'amorce laissée hier soir. "
            "Vide : pas de rappel. C'est le déclencheur le moins cher du système — "
            "l'idée travaille toute la journée au lieu d'être découverte à 21h."
        ),
    )
    buddy_disable_requested_at = models.DateTimeField(null=True, blank=True)
    shards = models.IntegerField(default=0)
    # Cosmétique équipé, un emplacement par type de carte (§12.6). Vide = défaut
    # du thème. Aucun de ces champs n'entre dans un calcul de règle.
    cosmetics = models.JSONField(default=dict, blank=True)
    coach_quota_enabled = models.BooleanField(
        default=False,
        help_text="Contrainte sur le temps passé à développer le coach. Désactivée tant que le projet n'est pas fini.",
    )

    def __str__(self) -> str:
        return f"Profil de {self.user}"

    def windows_by_weekday(self) -> dict[int, tuple[time, time]]:
        return {w.weekday: (w.start_time, w.end_time) for w in self.windows.all()}


class DayWindow(models.Model):
    """Fenêtre du soir, paramétrable par jour de semaine (SPEC §1)."""

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="windows")
    weekday = models.PositiveSmallIntegerField(help_text="0 = lundi")
    start_time = models.TimeField(default=time(18, 0))
    end_time = models.TimeField(default=time(23, 0))

    class Meta:
        unique_together = ("profile", "weekday")
        ordering = ("weekday",)


class Track(models.Model):
    """Atelier, Corps et Entretien : des pistes indépendantes qui ne se valident jamais l'une l'autre.

    La règle dure du §11.4, étendue à l'Entretien par le §11.9 : une routine
    cochée ne valide aucun streak, et aucune session ne coche de routine.
    """

    ATELIER = "atelier"
    CORPS = "corps"
    ENTRETIEN = "entretien"
    KINDS = [(ATELIER, "Atelier"), (CORPS, "Corps"), (ENTRETIEN, "Entretien")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tracks")
    kind = models.CharField(max_length=16, choices=KINDS)

    class Meta:
        unique_together = ("user", "kind")

    def __str__(self) -> str:
        return self.get_kind_display()


class Project(models.Model):
    ACTIVE, FRIDGE, ARCHIVED = "active", "fridge", "archived"
    STATUSES = [(ACTIVE, "Actif"), (FRIDGE, "Frigo"), (ARCHIVED, "Archivé")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    track = models.ForeignKey(Track, on_delete=models.PROTECT, related_name="projects")
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=STATUSES, default=ACTIVE)
    slot = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1 à 3, ou vide")
    color = models.CharField(max_length=7, default="#E8A33D")
    emblem = models.CharField(max_length=8, default="◆", help_text="Glyphe affiché sur la jauge")
    branch = models.CharField(max_length=32, blank=True, help_text="Branche de l'arbre de compétences")
    domain = models.CharField(
        max_length=16,
        choices=[(d, rules_slots.DOMAIN_LABELS[d]) for d in rules_slots.DOMAINS],
        default=rules_slots.CODE,
        help_text="Deux slots au maximum par domaine (SPEC §4.3)",
    )
    verification = models.CharField(
        max_length=16,
        choices=[(k, rules_verification.LABELS[k]) for k in rules_verification.KINDS],
        default=rules_verification.MANUELLE,
        help_text="Comment ce projet prouve qu'on a travaillé dessus (SPEC §6)",
    )
    is_coach_project = models.BooleanField(default=False)
    weekly_commitment = models.PositiveSmallIntegerField(default=3)
    # Ce que le projet vise, et ce qui le borne. Écrits une fois à la création,
    # relus à chaque fois qu'on se demande pourquoi on fait ça. L'objectif est
    # la condition de fin — « compromettre une machine Easy en moins de 3 h » —,
    # pas un thème ; le cadre porte ce qui interdit ou contraint : légalité,
    # budget, matériel. Le second existe parce qu'un parcours qui ignore sa
    # contrainte se découvre au pire moment, à mi-chemin.
    objective = models.TextField(blank=True, help_text="La condition de fin du projet (SPEC §4.5)")
    frame = models.TextField(blank=True, help_text="Ce qui borne le projet : légalité, budget, matériel")
    created_at = models.DateTimeField(default=timezone.now)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("slot", "name")

    def __str__(self) -> str:
        return self.name

    @property
    def current_step(self) -> "RoadmapStep | None":
        """L'étape sur laquelle on peut agir ce soir : celle en cours, sinon la suivante.

        L'ordre est explicite parce que l'implicite était faux. ``-state`` triait
        des chaînes, et en ordre décroissant « todo » passe devant « doing » :
        une étape déjà commencée était donc systématiquement doublée par la
        première étape non touchée. Le défaut ne se voyait pas — les deux
        libellés sont plausibles le soir venu — mais il faisait perdre le
        travail entamé une fois sur deux, et il n'était couvert par aucun test.
        """
        return (
            self.steps.filter(state__in=[RoadmapStep.DOING, RoadmapStep.TODO])
            .order_by(
                models.Case(
                    models.When(state=RoadmapStep.DOING, then=0),
                    default=1,
                    output_field=models.IntegerField(),
                ),
                "order",
            )
            .first()
        )

    @property
    def completion(self) -> float:
        total = self.steps.count()
        if not total:
            return 0.0
        return round(self.steps.filter(state=RoadmapStep.DONE).count() / total, 3)


class RoadmapStep(models.Model):
    TODO, DOING, DONE = "todo", "doing", "done"
    STATES = [(TODO, "À faire"), (DOING, "En cours"), (DONE, "Fait")]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="steps")
    # De quel bloc du parcours cette étape est le détail. Nul pour les projets
    # sans parcours — une roadmap collée à la main n'en a pas — et c'est un cas
    # normal, pas une donnée manquante.
    bloc = models.ForeignKey(
        "ProjectBloc", on_delete=models.SET_NULL, null=True, blank=True, related_name="steps"
    )
    order = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=255)
    state = models.CharField(max_length=8, choices=STATES, default=TODO)
    estimated_sessions = models.PositiveSmallIntegerField(default=1)
    done_at = models.DateTimeField(null=True, blank=True)
    # Quand on a commencé à travailler dessus. Posé à la première session sur le
    # projet pendant que l'étape est courante, jamais par un geste explicite —
    # le §13.5 veut détecter une étape figée depuis trois semaines, et une date
    # que l'utilisateur devrait déclarer ne serait jamais déclarée.
    doing_since = models.DateTimeField(null=True, blank=True)
    # Les minutes déjà passées dessus. Sans ce compteur, une étape de cinquante
    # minutes entamée sur un créneau de vingt-cinq serait à refaire en entier le
    # lendemain : le travail de la veille existait dans l'XP mais pas dans la
    # roadmap, et personne n'accepte deux fois de suite de n'en faire que la
    # moitié. C'est le compteur qui permet de couper une étape en deux soirées.
    minutes_done = models.PositiveIntegerField(default=0)

    # Ce qui rend l'étape exécutable sans réfléchir (SPEC §4.5). Facultatifs,
    # parce qu'ils n'ont pas toujours de sens — « appeler le plombier » n'a ni
    # ressource ni charge. Le critère de sortie est le plus important des cinq :
    # sans lui, on ne sait pas quand l'étape est finie, et une étape sans fin
    # connue se traîne jusqu'à ce que le projet meure.
    resource = models.CharField(max_length=255, blank=True, help_text="Le support précis : cours, dépôt, chapitre")
    url = models.URLField(blank=True, max_length=500)
    scope = models.CharField(max_length=255, blank=True, help_text="Ce que l'étape couvre, et ce qu'elle laisse")
    load = models.CharField(max_length=64, blank=True, help_text="La charge estimée, en toutes lettres : « 6–8 h »")
    exit_criterion = models.CharField(max_length=500, blank=True, help_text="À quoi on sait que c'est fini")

    class Meta:
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.label

    @property
    def needs_split(self) -> bool:
        """Plus de 3 sessions estimées : l'étape est trop grosse (SPEC §4.5)."""
        return self.estimated_sessions > 3

    @property
    def minutes_estimees(self) -> int:
        """L'estimation, en minutes. Une session vaut vingt-cinq minutes (§4.1)."""
        return max(1, self.estimated_sessions) * 25

    @property
    def minutes_restantes(self) -> int:
        """Ce qu'il reste à faire d'après l'estimation. Zéro = à clore."""
        return max(0, self.minutes_estimees - self.minutes_done)

    @property
    def avancement(self) -> float:
        """De 0 à 1. Sert à l'écran, jamais à décider qu'une étape est finie —
        c'est le critère de sortie qui tranche, pas le chronomètre (§6)."""
        return min(1.0, self.minutes_done / self.minutes_estimees)


class ProjectBloc(models.Model):
    """Un bloc du parcours : l'échelle des mois, pas celle de la soirée (SPEC §4.5).

    Le parcours existe parce qu'une roadmap d'étapes de 25 minutes ne peut pas
    porter un objectif à deux ans sans faire trois cents lignes. Le bloc dit où
    l'on va ; les étapes disent quoi faire ce soir.

    Il n'a **pas d'état**, et c'est délibéré : rien dans le produit ne coche un
    bloc, donc un champ « terminé » serait un champ que personne n'écrit — pire
    qu'absent, parce qu'il se lirait comme une information. L'avancement se lit
    sur les étapes, qui sont les seules choses qu'on termine.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="parcours")
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=255)
    outcome = models.CharField(max_length=500, blank=True, help_text="Ce qu'on sait faire à la sortie du bloc")
    resource = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True, max_length=500)
    load = models.CharField(max_length=64, blank=True)
    # Le prix, écrit même quand il est nul. Une ressource payante découverte à
    # mi-parcours arrête le parcours ; « gratuit » écrit noir sur blanc est une
    # information, pas du remplissage.
    cost = models.CharField(max_length=64, blank=True)
    optional = models.BooleanField(default=False)
    exit_criterion = models.CharField(max_length=500, blank=True)
    # Quand le bloc a été refermé et le suivant ouvert. Sans cette date, rien ne
    # savait où l'on en était du parcours : l'entretien n'explose en étapes que
    # le bloc courant, la roadmap se vidait au bout de quelques semaines, et
    # treize blocs restaient à l'état de titres que personne ne pouvait
    # transformer en soirées.
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.name

    @property
    def done(self) -> bool:
        return self.done_at is not None


class DiscardedResource(models.Model):
    """Une ressource écartée, et la raison (SPEC §4.5).

    Sur un sujet documenté il existe dix ressources concurrentes. Sans la raison
    écrite, on refait l'arbitrage à chaque fois qu'on en croise une — sans les
    éléments qui avaient servi à trancher. C'est la seule chose du document qui
    ne sert à rien tant qu'on ne la relit pas, et qui fait gagner une soirée le
    jour où on la relit.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="ecartees")
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=255)
    reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.name


class TimeSlot(models.Model):
    """Rendez-vous hebdomadaire fixe. « Mardi 20h30 » se tient, « ce soir » se rate."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="timeslots")
    weekday = models.PositiveSmallIntegerField(help_text="0 = lundi")
    start_time = models.TimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=25)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("weekday", "start_time")


class Commitment(models.Model):
    """Engagement hebdo historisé — sinon « tenus vs pris » est incalculable."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="commitments")
    week_start = models.DateField()
    planned_sessions = models.PositiveSmallIntegerField(default=3)
    done_sessions = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ("project", "week_start")
        ordering = ("-week_start",)

    @property
    def kept(self) -> bool:
        return self.done_sessions >= self.planned_sessions


class Season(models.Model):
    RUNNING, CLOSED, PAUSED = "running", "closed", "paused"
    STATUSES = [(RUNNING, "En cours"), (CLOSED, "Close"), (PAUSED, "Pause")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seasons")
    index = models.PositiveIntegerField()
    key = models.CharField(max_length=32)
    name = models.CharField(max_length=64)
    accent = models.CharField(max_length=7)
    baseline = models.CharField(max_length=255, blank=True)
    modifier_key = models.CharField(max_length=32, blank=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    stake_shards = models.PositiveIntegerField(default=0)
    # Part de la mise déjà partie en cours de saison (§14, palier 2). Stockée
    # plutôt que recalculée à la lecture parce que c'est le seul prélèvement
    # irréversible du système : le solde d'Éclats a déjà bougé, et une valeur
    # qu'on recalculerait à chaque appel finirait par le prélever deux fois.
    stake_forfeited = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUSES, default=RUNNING)
    # Le jour où elle a réellement été close, qui n'est pas ``ends_on`` quand le
    # boss est tombé en avance (§12.4). Sans lui, impossible de savoir quels
    # jours appartiennent au **mode extra** — ceux d'après la victoire, dont le
    # travail est mis de côté pour la saison suivante.
    closed_on = models.DateField(null=True, blank=True)
    # La trame du §12.2 : quelle voie cette saison a suivie, et si elle a été
    # tenue. Les deux sont **stockées** et non recalculées, contrairement au
    # reste du produit : la voie de la saison suivante descend de ce résultat,
    # et un barème qui changerait un jour réécrirait rétroactivement l'histoire
    # qu'on a traversée. Ce qui a été raconté a été raconté.
    voie = models.CharField(max_length=16, blank=True)
    reussie = models.BooleanField(null=True, blank=True)
    title_awarded = models.CharField(max_length=120, blank=True)
    # Contre quoi on court cette saison (§12.7). Choisi à l'ouverture, figé
    # ensuite : pouvoir changer d'adversaire en cours de route reviendrait à
    # renégocier l'objectif, ce que le fantôme existe précisément pour empêcher.
    phantom_choice = models.CharField(
        max_length=16,
        choices=[(c, rules_phantom.CHOIX_LABELS[c]) for c in rules_phantom.CHOIX],
        default=rules_phantom.MEILLEURE,
    )
    final_score = models.PositiveIntegerField(default=0)
    # Le contrat de saison (ajout du 17 août 2026). Signé à l'ouverture, figé
    # ensuite : baisser un engagement en cours de semaine reste possible, mais
    # le contrat garde ce qui a été signé. Sans ça, la clôture se comparerait à
    # une cible déplacée en route, et la comparaison ne vaudrait rien.
    contract_sessions_per_week = models.PositiveSmallIntegerField(default=0)
    contract_projects = models.JSONField(default=list, blank=True)
    contract_signed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "index")
        ordering = ("-index",)

    def __str__(self) -> str:
        return f"Saison {self.index} — {self.name}"

    def day_index(self, day) -> int:
        return (day - self.starts_on).days

    def days_left(self, day) -> int:
        return max(0, (self.ends_on - day).days)

    @property
    def signed(self) -> bool:
        return self.contract_signed_at is not None


class Ascendance(models.Model):
    """Une année accomplie : douze saisons closes, et la voie choisie ensuite.

    L'XP et le niveau repartent de zéro à ce moment-là — non pas parce qu'ils
    seraient mérités à moitié, mais parce qu'ils cessent de vouloir dire quelque
    chose : entre le niveau 41 et le 42, il n'y a plus d'information.

    **Rien n'est effacé.** Aucune session n'est touchée : c'est l'horizon du
    calcul qui se déplace, l'XP courante se comptant depuis ``closed_on``. La
    trace longue continue de porter le cumul de toujours, et le §17 est tenu —
    il interdit de faire disparaître du travail réel, pas de changer d'échelle.

    Le bilan de l'année est **figé ici**, à la clôture. Recalculé plus tard il
    changerait : une session corrigée, une saison rejouée, et l'année deux ne
    raconterait plus ce qu'on a lu le jour de l'ascendance.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ascendances"
    )
    year_index = models.PositiveSmallIntegerField(help_text="1 pour la première année")
    closed_on = models.DateField(help_text="Journée du coach où l'année a été close")
    closed_at = models.DateTimeField(default=timezone.now)
    voie = models.CharField(
        max_length=16,
        blank=True,
        choices=[(v.cle, v.label) for v in rules_years.CATALOGUE],
        help_text="Choisie après la clôture. Vide tant que le choix n'est pas fait.",
    )
    title_awarded = models.CharField(max_length=120, blank=True)

    # Le bilan figé de l'année.
    seasons_closed = models.PositiveSmallIntegerField(default=0)
    bosses_killed = models.PositiveSmallIntegerField(default=0)
    minutes = models.PositiveIntegerField(default=0)
    xp_at_reset = models.PositiveIntegerField(default=0)
    level_at_reset = models.PositiveSmallIntegerField(default=1)
    rank_at_reset = models.CharField(max_length=2, default="F")
    # Les slots ouverts au moment de l'ascendance. Ils deviennent permanents :
    # le rang repart de F, et le §4.3 interdit de reprendre un slot puisque
    # « les projets ne sont pas supprimés ». Sans ce champ, une ascendance
    # gèlerait deux projets en cours du jour au lendemain.
    slots_engraved = models.PositiveSmallIntegerField(default=3)

    class Meta:
        unique_together = ("user", "year_index")
        ordering = ("-year_index",)

    def __str__(self) -> str:
        return f"An {self.year_index} — {self.get_voie_display() or 'voie à choisir'}"

    @property
    def choisie(self) -> bool:
        return bool(self.voie)


class SeasonBoss(models.Model):
    season = models.OneToOneField(Season, on_delete=models.CASCADE, related_name="boss")
    key = models.CharField(max_length=32)
    name = models.CharField(max_length=64)
    max_hp = models.PositiveIntegerField()
    damage_taken = models.PositiveIntegerField(default=0)
    regen = models.PositiveIntegerField(default=0, help_text="Vie récupérée lors des jours ratés")

    @property
    def current_hp(self) -> int:
        # La régénération ne rend que de la vie réellement retirée. Sans ce
        # plafond, rater un jour avant d'avoir touché le boss le ferait monter
        # au-dessus de son maximum : la barre dépasserait 100 % et le ratio de
        # clôture du §12.4 passerait au-dessus de 1.
        return max(0, self.max_hp - self.damage_taken + min(self.regen, self.damage_taken))

    @property
    def ratio(self) -> float:
        return round(self.current_hp / max(1, self.max_hp), 4)

    @property
    def is_dead(self) -> bool:
        return self.current_hp == 0


class Session(models.Model):
    NORMAL, DEGRADED = "normal", "degraded"
    MODES = [(NORMAL, "Normale"), (DEGRADED, "Dégradée")]
    RUNNING, DONE, ABANDONED = "running", "done", "abandoned"
    STATUSES = [(RUNNING, "En cours"), (DONE, "Terminée"), (ABANDONED, "Abandonnée")]
    SERVER, UNVERIFIED = "server", "unverified"
    VERIFICATIONS = [(SERVER, "Horodatée serveur"), (UNVERIFIED, "Non vérifiée")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="sessions")
    season = models.ForeignKey(Season, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    coach_day = models.DateField(db_index=True, help_text="Journée du coach, bascule à 4h")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    # L'objectif de la séance, annoncé au démarrage. Il peut monter en cours de
    # route — c'est le « +15 min » du §4.1 — mais jamais descendre : renégocier
    # à la baisse une promesse qu'on est en train de tenir la viderait de son
    # sens, et le bouton « Terminer maintenant » existe déjà pour ça.
    planned_minutes = models.PositiveSmallIntegerField(default=25)
    extensions = models.PositiveSmallIntegerField(
        default=0, help_text="Combien de fois la séance a été prolongée"
    )
    actual_minutes = models.PositiveSmallIntegerField(default=0)
    mode = models.CharField(max_length=16, choices=MODES, default=NORMAL)
    status = models.CharField(max_length=16, choices=STATUSES, default=RUNNING)
    rank_in_day = models.PositiveSmallIntegerField(default=1)
    xp_awarded = models.IntegerField(default=0)
    xp_breakdown = models.JSONField(default=dict, blank=True)
    # Le plan de la soirée, figé au démarrage : les étapes que ce créneau devait
    # couvrir, et pour combien de minutes chacune. La clôture s'en sert pour
    # créditer le temps réellement passé sur les bonnes étapes. Le recalculer à
    # la clôture donnerait un autre plan — la roadmap a pu changer entre-temps —
    # et créditerait du travail sur une étape qu'on n'a jamais ouverte.
    plan = models.JSONField(default=list, blank=True)
    focus_quality = models.PositiveSmallIntegerField(null=True, blank=True)
    energy_level = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1 à 3")
    # La difficulté ressentie, déclarée au debrief en un tap. Facultative, et
    # elle le reste : un champ obligatoire de plus à la clôture ferait renoncer
    # à clôturer. Trois sessions d'affilée « trop facile » sont le seul signal
    # du système qui dise qu'on a cessé d'apprendre — invisible partout
    # ailleurs, et qui ressemble même à une bonne série (§ capacité).
    difficulty = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="1 trop facile, 2 juste, 3 trop dur"
    )
    verification = models.CharField(max_length=16, choices=VERIFICATIONS, default=SERVER)
    client_uuid = models.UUIDField(unique=True, null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"{self.project} — {self.actual_minutes} min le {self.coach_day}"


class JournalEntry(models.Model):
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name="journal")
    raw_note = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True)
    blockers = models.JSONField(default=list, blank=True)
    next_action = models.CharField(
        max_length=255, blank=True, help_text="L'amorce : première action de la prochaine session"
    )
    source = models.CharField(max_length=16, default="manuel")
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)


class DayStatus(models.Model):
    """État résolu d'une journée, par piste. Trois états, pas deux (SPEC §4.2)."""

    VALIDEE, RATEE, NEUTRE = "validee", "ratee", "neutre"
    STATES = [(VALIDEE, "Validée"), (RATEE, "Ratée"), (NEUTRE, "Neutre")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="day_statuses")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="day_statuses")
    date = models.DateField(db_index=True)
    state = models.CharField(max_length=8, choices=STATES)
    reason = models.CharField(max_length=120, blank=True)

    class Meta:
        unique_together = ("user", "track", "date")
        ordering = ("date",)


class DayOff(models.Model):
    """Jour off déclaré au moins la veille. Neutre : ne casse rien, ne construit rien."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="days_off")
    date = models.DateField()
    declared_at = models.DateTimeField(default=timezone.now)
    season = models.ForeignKey(Season, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ("user", "date")


class FridgeIdea(models.Model):
    """Le frigo : capture illimitée, 5 secondes, pour ne pas démarrer un 4ᵉ projet."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fridge")
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(default=timezone.now)
    promoted_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=16, default="app")

    class Meta:
        ordering = ("-created_at",)


class Preuve(models.Model):
    """Une capacité constatée : datée, binaire, vérifiable par quelqu'un d'autre.

    Le troisième axe du système, à côté du volume (XP) et de la fiabilité
    (rang). Il existe parce qu'aucun des deux autres ne dit qu'on est devenu
    meilleur : quarante heures de mauvaise pratique donnent le même titre
    d'arbre que quarante heures de bonne.

    Le critère vient presque toujours du **critère de sortie** d'un bloc de
    parcours, écrit à la création du projet (§4.5) — donc décidé à froid,
    des mois avant d'être atteint, ce qui est la seule façon de ne pas se noter
    soi-même après coup.

    Ne se retire jamais (§17). Une capacité constatée reste constatée, même si
    elle rouille : le contraire demanderait au système de juger un niveau, ce
    qu'il ne sait pas faire.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preuves")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="preuves")
    # Le bloc dont elle vient, quand elle vient d'un bloc. Vide pour une preuve
    # déclarée à la main — un examen passé, un contrat signé, une scène jouée.
    bloc = models.ForeignKey(
        "ProjectBloc", on_delete=models.SET_NULL, null=True, blank=True, related_name="preuves"
    )
    critere = models.CharField(max_length=500, help_text="Ce qui a été constaté, en toutes lettres")
    obtained_on = models.DateField(help_text="Journée du coach où elle a été constatée")
    shards_awarded = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-obtained_on", "-id")

    def __str__(self) -> str:
        return self.critere


class Ponctuel(models.Model):
    """Une chose à faire une fois, qui n'est ni un projet ni une routine.

    « Commander la carte mère », « appeler le dentiste ». Ça ne se répète pas,
    donc ce n'est pas une routine ; ça ne se découpe pas en étapes, donc ce
    n'est pas un projet ; et ça n'a rien à faire au frigo, qui garde des *idées
    de projet* et non des courses.

    **Ce que ce modèle ne fait pas, et pourquoi.** Le §0 dit que le coach n'est
    pas une todo-list, et le §11.1 interdit une liste à arbitrer avant de
    démarrer. Les deux restent vrais ici : un ponctuel ne rapporte **ni XP, ni
    Éclats, ni coche**, il n'entre dans aucun streak, et il **n'apparaît jamais
    sur l'écran du soir**. C'est ce qui l'empêche de devenir la chose qu'on fait
    à la place d'une session — trois courses cochées ressemblent à une soirée
    productive, et c'est précisément le mode de défaillance que tout le reste du
    système combat.

    Il existe pour la raison inverse : une course qu'on garde en tête occupe la
    place d'une session. L'écrire quelque part la sort de la tête sans lui
    donner de valeur.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ponctuels")
    label = models.CharField(max_length=255)
    # L'échéance est facultative, et c'est important : la plupart des courses
    # n'en ont pas. Une date obligatoire ferait inventer des dates, et une date
    # inventée dépassée est une fausse alerte — la seule chose qui apprend à
    # ignorer les alertes.
    due_on = models.DateField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=16, default="app")

    class Meta:
        # Les datées d'abord, dans l'ordre où elles tombent ; les autres à la
        # suite, la plus ancienne en tête. `F` explicite parce que le tri par
        # défaut de SQLite met les NULL en premier, ce qui enterrerait
        # justement ce qui presse.
        ordering = (models.F("due_on").asc(nulls_last=True), "created_at")

    def __str__(self) -> str:
        return self.label

    @property
    def done(self) -> bool:
        return self.done_at is not None


class Quest(models.Model):
    PLANCHER, BONUS, HEBDO = "plancher", "bonus", "hebdo"
    KINDS = [(PLANCHER, "Plancher"), (BONUS, "Bonus"), (HEBDO, "Hebdomadaire")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quests")
    kind = models.CharField(max_length=16, choices=KINDS)
    date = models.DateField(db_index=True)
    label = models.CharField(max_length=255)
    target = models.PositiveIntegerField(default=1)
    progress = models.PositiveIntegerField(default=0)
    reward_xp = models.PositiveIntegerField(default=0)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("kind", "id")

    @property
    def done(self) -> bool:
        return self.progress >= self.target


class Routine(models.Model):
    """Une routine courte de la piste Entretien (SPEC §11.9).

    Le rythme (``weekdays``) et le seuil (``weekly_target``) sont deux réglages
    distincts : c'est l'écart entre les deux qui absorbe les oublis, à la place
    du bouclier du §4.2.
    """

    ANCHORS = [
        (rules_routines.REVEIL, "Au réveil"),
        (rules_routines.APRES_DOUCHE, "Après la douche"),
        (rules_routines.FIN_DE_SESSION, "En fin de session"),
        (rules_routines.AVANT_COUCHER, "Avant le coucher"),
        (rules_routines.LIBRE, "Dans la journée"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="routines")
    track = models.ForeignKey(Track, on_delete=models.PROTECT, related_name="routines")
    name = models.CharField(max_length=120)
    anchor = models.CharField(max_length=24, choices=ANCHORS, default=rules_routines.LIBRE)
    weekdays = models.JSONField(
        default=list, blank=True, help_text="Jours où elle est proposée, 0 = lundi. Vide = tous les jours."
    )
    weekly_target = models.PositiveSmallIntegerField(
        default=6, help_text="Nombre de fois par semaine qui rend la semaine tenue"
    )
    reward_shards = models.PositiveSmallIntegerField(default=rules_routines.SHARDS_PER_CHECK)
    # La fenêtre horaire, facultative (§11.9 étendu). Vide pour presque tout :
    # le §11.9 ancre les routines sur un geste et pas sur une horloge, et il a
    # raison — « après la douche » arrive au bon moment sans réveil. Deux
    # habitudes échappent à la règle parce que l'heure *est* l'habitude : se
    # lever tôt, ne pas se coucher tard. Sans borne, elles n'ont aucun sens :
    # une coche « debout » posée à 14h compterait pareil.
    deadline = models.TimeField(
        null=True, blank=True, help_text="Heure limite, heure locale. Vide : la routine n'en a pas."
    )
    direction = models.CharField(
        max_length=8,
        choices=[(rules_routines.AVANT, "Avant l'heure"), (rules_routines.APRES, "Après l'heure")],
        default=rules_routines.AVANT,
    )
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.name

    def to_rule(self) -> rules_routines.Routine:
        """Projection vers la logique pure — aucune règle ne vit dans le modèle."""
        return rules_routines.Routine(
            key=str(self.pk),
            name=self.name,
            weekly_target=self.weekly_target,
            weekdays=tuple(self.weekdays or ()),
            anchor=self.anchor,
            deadline=self.deadline,
            direction=self.direction,
        )


class RoutineCheck(models.Model):
    """Une routine cochée un jour donné. Une seule coche par journée du coach."""

    APP, TELEGRAM, AGENT = "app", "telegram", "agent"
    SOURCES = [(APP, "App"), (TELEGRAM, "Telegram"), (AGENT, "Agent")]

    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name="checks")
    day = models.DateField(db_index=True, help_text="Journée du coach, bascule à 4h")
    checked_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=16, choices=SOURCES, default=APP)
    shards_awarded = models.PositiveSmallIntegerField(default=0)
    # Hors fenêtre : la coche est gardée, elle ne compte pas pour la semaine et
    # ne paie rien. Garder le fait plutôt que refuser le geste est la même
    # logique qu'ailleurs — le §17 interdit d'effacer ce qui a eu lieu, et une
    # coche refusée ferait croire à un bug. Vrai par défaut : toutes les
    # routines sans fenêtre sont à l'heure par construction.
    on_time = models.BooleanField(default=True)

    class Meta:
        unique_together = ("routine", "day")
        ordering = ("-day", "routine_id")

    def __str__(self) -> str:
        return f"{self.routine} — {self.day}"


class Garde(models.Model):
    """Un comportement à réduire, mesuré par un budget hebdomadaire (SPEC §11.10).

    Le budget ne descend jamais à zéro : viser « plus jamais » transforme la
    première fois en abandon complet. La contrainte est portée par la base, pas
    seulement par le formulaire.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gardes")
    name = models.CharField(max_length=120)
    weekly_budget = models.PositiveSmallIntegerField(
        default=2,
        validators=[
            MinValueValidator(rules_gardes.MIN_BUDGET),
            MaxValueValidator(rules_gardes.MAX_BUDGET),
        ],
        help_text="Jours tolérés par semaine. Jamais zéro (SPEC §11.10).",
    )
    auto_category = models.CharField(
        max_length=24,
        blank=True,
        choices=[(c, c) for c in rules_signals.CATEGORIES],
        help_text="Catégorie de sonde qui marque cette garde. Vide = déclaration à la main seulement.",
    )
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(weekly_budget__gte=rules_gardes.MIN_BUDGET),
                name="garde_budget_jamais_zero",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def to_rule(self) -> rules_gardes.Garde:
        return rules_gardes.Garde(
            key=str(self.pk),
            name=self.name,
            weekly_budget=self.weekly_budget,
        )


class GardeDay(models.Model):
    """Une journée déclarée pour une garde. Non déclarée = ni tenue ni marquée."""

    MAIN, SONDE = "main", "sonde"
    ORIGINS = [(MAIN, "Déclaré à la main"), (SONDE, "Marqué par une sonde")]

    garde = models.ForeignKey(Garde, on_delete=models.CASCADE, related_name="days")
    day = models.DateField(db_index=True, help_text="Journée du coach, bascule à 4h")
    occurred = models.BooleanField(default=False, help_text="Le comportement a eu lieu ce jour-là")
    origin = models.CharField(max_length=8, choices=ORIGINS, default=MAIN)
    declared_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("garde", "day")
        ordering = ("-day", "garde_id")

    def __str__(self) -> str:
        return f"{self.garde} — {self.day} — {'marqué' if self.occurred else 'tenu'}"


class ProbeToken(models.Model):
    """Jeton d'une sonde (SPEC §8, §9).

    Une sonde n'a pas besoin des droits de l'utilisateur : elle poste des
    signaux, rien d'autre. Lui donner un JWT complet reviendrait à donner à une
    extension navigateur le droit de supprimer des projets. Ce jeton-ci ne
    déverrouille que ``/api/signals``.

    Seule l'empreinte est stockée. Le jeton en clair est montré une fois, à la
    création, et n'existe ensuite que dans la config locale de la sonde.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="probe_tokens")
    name = models.CharField(max_length=64)
    kind = models.CharField(max_length=8, choices=[(s, s) for s in rules_signals.SOURCES])
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        etat = "révoqué" if self.revoked_at else "actif"
        return f"{self.name} ({self.kind}, {etat})"

    @property
    def active(self) -> bool:
        return self.revoked_at is None

    @staticmethod
    def hash_of(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def issue(cls, user, *, name: str, kind: str) -> tuple["ProbeToken", str]:
        """Crée un jeton et rend le secret en clair — la seule et unique fois."""
        raw = secrets.token_urlsafe(32)
        token = cls.objects.create(user=user, name=name, kind=kind, token_hash=cls.hash_of(raw))
        return token, raw


class Hiatus(models.Model):
    """Le mode veille : une pause déclarée qui n'est pas un abandon (§11.5 étendu).

    Les jours off couvrent deux jours par semaine. Rien ne couvrait des vacances,
    une grippe ou une semaine de partiels — et un système qui n'a pas de pause
    n'en offre qu'une : la désinstallation.

    Pendant la veille, tout est **neutre** au sens du §4.2 : rien ne casse, rien
    ne se construit, aucun déclencheur ne part, la saison est gelée. On en sort
    quand on veut : une pause dont on ne peut pas sortir est une raison de plus
    de ne pas la prendre.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hiatuses"
    )
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.CharField(max_length=120, blank=True)
    declared_at = models.DateTimeField(default=timezone.now)
    ended_early_at = models.DateTimeField(null=True, blank=True)
    # Jours déjà rendus à la saison. Stocké pour que la reprise soit idempotente :
    # sans ça, deux lectures de l'accueil rallongeraient la saison deux fois.
    days_given_back = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("-starts_on",)

    def __str__(self) -> str:
        return f"Veille du {self.starts_on} au {self.ends_on}"

    def covers(self, day) -> bool:
        return self.starts_on <= day <= self.ends_on

    @property
    def days(self) -> int:
        return (self.ends_on - self.starts_on).days + 1


class ProjectHold(models.Model):
    """Un projet bloqué par un tiers ou du matériel (ajout du 17 août 2026).

    Une réponse qu'on attend, une pièce qui n'arrive pas, un accès qu'on ne t'a
    pas donné. Sans rien pour le dire, le système lisait ça comme un abandon :
    au dixième jour la détection du §13.5 proposait le frigo, et l'engagement
    manqué faisait tomber la semaine — donc le rang, qui mesure la fiabilité.
    Être sanctionné pour l'inaction de quelqu'un d'autre est la meilleure façon
    de perdre confiance en un système de discipline.

    L'attente **ne libère pas le slot**, et c'est ce qui la distingue du frigo.
    Le projet reste à sa place et la reprend intacte au retour.

    Historisée comme la veille plutôt que rangée dans un champ du projet : le
    rang se recalcule sur des semaines passées (§4.4), et une attente qu'on ne
    connaîtrait qu'au présent ne pourrait pas lever la semaine où elle a eu lieu.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="holds")
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.CharField(max_length=200)
    declared_at = models.DateTimeField(default=timezone.now)
    # La sortie anticipée est une **journée du coach**, pas un horodatage. Un
    # instant serré contre la bascule de 4h se rangerait du mauvais côté d'une
    # journée, et l'attente s'arrêterait un jour trop tôt ou trop tard.
    ended_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ("-starts_on",)

    def __str__(self) -> str:
        return f"{self.project.name} en attente jusqu'au {self.ends_on}"

    @property
    def effective_end(self):
        """La fin réelle : la sortie anticipée l'emporte sur la date annoncée.

        Le jour de la sortie n'est **pas** couvert, contrairement à la veille du
        §11.5. La différence tient à ce que chacune protège : la veille rend des
        journées neutres déjà entamées, alors qu'une attente n'a qu'un effet —
        empêcher le projet d'être proposé. Sortir à 19h pour découvrir que le
        projet reste absent de la soirée viderait la sortie de son sens.
        """
        if self.ended_on is None:
            return self.ends_on
        return min(self.ends_on, self.ended_on - timedelta(days=1))

    def covers(self, day) -> bool:
        return self.starts_on <= day <= self.effective_end


class WeeklyReview(models.Model):
    """La revue du dimanche (SPEC §5.3, §13.3).

    Le seul moment de la semaine où l'app pose des questions — et elle arrive
    avec les constats déjà faits, jamais avec une page blanche (§0.9).

    Les réponses sont stockées avec leur question : une réponse seule ne se
    relit pas, et c'est la relecture qui fait la valeur d'une revue au bout de
    quatre semaines.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="weekly_reviews"
    )
    week_start = models.DateField()
    # [{"fait": …, "question": …, "reponse": …}]. Un seul champ plutôt qu'une
    # table par question : rien ne les interroge séparément, et une revue se lit
    # toujours entière.
    questions = models.JSONField(default=list, blank=True)
    # {"a_marche": …, "n_a_pas_marche": …, "seule_chose": …, "dialogue": bool}
    report = models.JSONField(default=dict, blank=True)
    # [{"projet": …, "actuel": n, "propose": n, "raison": …}]
    contract = models.JSONField(default=list, blank=True)
    contract_applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-week_start",)
        unique_together = ("user", "week_start")

    def __str__(self) -> str:
        return f"Revue du {self.week_start}"

    @property
    def answered(self) -> int:
        return sum(1 for q in self.questions if (q.get("reponse") or "").strip())


class WeeklyReport(models.Model):
    """Le bilan envoyé à un ami, une fois par semaine (SPEC §4.7).

    Le seul point d'appui **externe** du produit. Le §0.1 dit que la contrainte
    interne n'existe pas chez cet utilisateur : tout le reste — streak, boss,
    sanctions — est un cadre qu'il s'impose et peut donc se lever. Celui-ci
    engage quelqu'un d'autre, et c'est pour ça qu'il est le seul mécanisme
    volontairement difficile à désarmer.

    Ce qui est stocké est **ce qui a été envoyé**, mot pour mot. Un bilan
    recalculé à l'affichage ne dirait pas ce que l'ami a lu, et la question qui
    compte au bout de trois semaines sans lecture est justement : qu'a-t-il vu ?
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="weekly_reports"
    )
    week_start = models.DateField(help_text="Lundi de la semaine couverte")
    body = models.TextField()
    channel = models.CharField(max_length=32, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-week_start",)
        # Un bilan par semaine. L'unicité est la règle du §4.7, pas une
        # précaution : deux envois le même dimanche feraient du destinataire un
        # spectateur qu'on sature, et un ami saturé cesse de lire.
        unique_together = ("user", "week_start")

    def __str__(self) -> str:
        return f"Bilan du {self.week_start} ({'lu' if self.read_at else 'non lu'})"


class ActionLink(models.Model):
    """Un lien signé qui fait **une** chose, sans compte ni application.

    Le canal entrant du produit. Le §11.7 le confiait à un bot Telegram, remplacé
    depuis par le Web Push et un webhook Discord — parfait pour ce qui sort, muet
    pour ce qui rentre. Or trois mécaniques ont besoin qu'on réponde : l'accusé
    de lecture du bilan de l'ami (§4.7), les questions de la revue du dimanche
    (§5.3), et la capture d'une idée au frigo sans ouvrir l'app (§11.7).

    Un lien n'a ni compte à créer, ni application à installer, ni jeton à coller
    dans un réglage — ce qui compte surtout pour l'ami du §4.7, qui n'a aucune
    raison de s'inscrire quelque part pour cliquer une fois par semaine.

    **Ce qu'un lien ne donne jamais**, même volé : la lecture de l'historique, le
    moindre projet, la moindre garde. Il porte son geste et son contexte, et il
    ne déverrouille rien d'autre — la même règle que le ``ProbeToken`` du §8, et
    pour la même raison : un secret qui voyage dans une notification finit par
    fuir.
    """

    FRIGO, VU, REPONSE = "frigo", "vu", "reponse"
    # Les deux gestes des boutons d'une notification Web Push (§11.7). Ils sont
    # des liens et non des routes authentifiées pour une raison précise : un
    # service worker ne connaît pas le jeton de l'app — il ne partage ni son
    # stockage local ni sa session — et lui en confier un serait sortir un
    # secret de longue durée de l'endroit qui le garde. Un lien signé porte un
    # seul geste, expire dans la soirée, et ne lit rien.
    DEMARRER, REPORTER = "demarrer", "reporter"
    KINDS = [
        (FRIGO, "Jeter une idée au frigo"),
        (VU, "Accuser réception d'un bilan"),
        (REPONSE, "Répondre à une question"),
        (DEMARRER, "Démarrer la séance proposée"),
        (REPORTER, "Reporter le gardien"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="action_links"
    )
    kind = models.CharField(max_length=8, choices=KINDS)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    # Ce que la page a besoin de savoir pour se dessiner : la question posée, le
    # titre du bilan. Jamais de donnée qu'un lien volé ne devrait pas montrer.
    context = models.JSONField(default=dict, blank=True)
    answer = models.TextField(blank=True)
    max_uses = models.PositiveSmallIntegerField(default=1)
    uses = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.uses}/{self.max_uses})"

    @staticmethod
    def hash_of(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def issue(
        cls,
        user,
        *,
        kind: str,
        context: dict | None = None,
        max_uses: int = 1,
        ttl_days: int | None = 30,
    ) -> tuple["ActionLink", str]:
        """Crée le lien et rend le secret en clair — la seule et unique fois."""
        raw = secrets.token_urlsafe(24)
        lien = cls.objects.create(
            user=user,
            kind=kind,
            token_hash=cls.hash_of(raw),
            context=context or {},
            max_uses=max_uses,
            expires_at=timezone.now() + timedelta(days=ttl_days) if ttl_days else None,
        )
        return lien, raw

    @property
    def expired(self) -> bool:
        return bool(self.expires_at and timezone.now() >= self.expires_at)

    @property
    def spent(self) -> bool:
        return self.uses >= self.max_uses

    @property
    def usable(self) -> bool:
        return not self.expired and not self.spent


class Conversation(models.Model):
    """Le fil de discussion avec l'assistant (§5 étendu).

    Un seul fil ouvert à la fois par utilisateur. Ce n'est pas une limite
    technique : plusieurs fils demanderaient de choisir lequel reprendre, ce
    qui est exactement l'espace à remplir que le §0.9 interdit. On reprend là
    où on s'était arrêté, ou on repart de zéro — deux états, pas une liste.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    started_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self) -> str:
        return f"Conversation du {self.started_at:%d/%m %H:%M}"


class ConversationTurn(models.Model):
    """Un tour de parole. Le contexte du modèle se relit d'ici, pas d'un cache."""

    UTILISATEUR, ASSISTANT = "user", "assistant"
    ROLES = [(UTILISATEUR, "Toi"), (ASSISTANT, "L'assistant")]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="turns"
    )
    role = models.CharField(max_length=12, choices=ROLES)
    text = models.TextField(blank=True)
    # Ce qui a servi à répondre : modèle, coût, motif de refus de la porte. Le
    # §5.6 veut que le coût soit affiché et jamais caché.
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("created_at", "id")


class ProposedAction(models.Model):
    """Une action proposée par l'assistant, en attente d'un geste.

    Elle porte son **aperçu** — l'avant et l'après, calculés au moment de la
    proposition — et le point de contrôle de l'état sur lequel elle a été
    calculée. Une proposition appliquée trois jours plus tard, sur un projet
    qui a changé entre-temps, ferait une écriture que personne n'a validée :
    ``empreinte`` la fait refuser plutôt que l'appliquer à l'aveugle.
    """

    EN_ATTENTE, APPLIQUEE, ECARTEE, PERIMEE = "attente", "appliquee", "ecartee", "perimee"
    ETATS = [
        (EN_ATTENTE, "En attente"),
        (APPLIQUEE, "Appliquée"),
        (ECARTEE, "Écartée"),
        (PERIMEE, "Périmée"),
    ]

    turn = models.ForeignKey(
        ConversationTurn, on_delete=models.CASCADE, related_name="actions"
    )
    key = models.CharField(max_length=48)
    params = models.JSONField(default=dict, blank=True)
    summary = models.CharField(max_length=255)
    before = models.TextField(blank=True)
    after = models.TextField(blank=True)
    warning = models.CharField(max_length=255, blank=True)
    empreinte = models.CharField(max_length=64, blank=True)
    state = models.CharField(max_length=16, choices=ETATS, default=EN_ATTENTE)
    detail = models.CharField(max_length=255, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.key} ({self.get_state_display()})"


class Signal(models.Model):
    """Une observation d'une sonde (SPEC §8, §9, §11.10).

    Append-only. **Aucun contenu** : ni URL, ni titre de page, ni chemin. Une
    catégorie et une durée, c'est tout ce que le modèle sait représenter — et
    c'est volontaire, un champ libre finirait par recevoir une adresse.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="signals")
    source = models.CharField(max_length=8, choices=[(s, s) for s in rules_signals.SOURCES])
    category = models.CharField(max_length=24, choices=[(c, c) for c in rules_signals.CATEGORIES])
    minutes = models.PositiveIntegerField(default=0)
    day = models.DateField(db_index=True, help_text="Journée du coach, bascule à 4h")
    started_at = models.DateTimeField(
        null=True, blank=True, help_text="Début de la fenêtre observée, si la sonde sait la donner"
    )
    ended_at = models.DateTimeField(null=True, blank=True)
    seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-day", "category")
        indexes = [models.Index(fields=["user", "day", "category"])]

    def __str__(self) -> str:
        return f"{self.category} · {self.minutes} min · {self.source}"

    def to_rule(self) -> rules_signals.Signal:
        return rules_signals.Signal(
            source=self.source,
            category=self.category,
            minutes=self.minutes,
            day=self.day,
            started_at=self.started_at,
            ended_at=self.ended_at,
        )


class ProjectRepo(models.Model):
    """Un dépôt git déclaré pour un projet (SPEC §8.3).

    Sert à pré-remplir le debrief et à mesurer le travail réel : ce qui a été
    commité pendant la session est la preuve la moins falsifiable qui existe,
    et elle ne coûte aucune saisie.
    """

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="repos")
    path = models.CharField(max_length=500, help_text="Chemin local du dépôt")
    remote = models.CharField(max_length=255, blank=True)
    last_scanned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("project", "path")

    def __str__(self) -> str:
        return f"{self.project} → {self.path}"


class Achievement(models.Model):
    """Hauts faits — vocabulaire Dofus assumé."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements")
    key = models.CharField(max_length=48)
    label = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    unlocked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "key")
        ordering = ("-unlocked_at",)


class RelaxWindow(models.Model):
    """Sas de détente : une seule utilisation par soir, révoqué le lendemain d'un jour raté."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="relax_windows")
    coach_day = models.DateField()
    started_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()

    class Meta:
        unique_together = ("user", "coach_day")


class Device(models.Model):
    """Un appareil appairé. Porte l'abonnement Web Push quand il y en a un."""

    PC, PHONE = "pc", "phone"
    KINDS = [(PC, "PC"), (PHONE, "Téléphone")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    kind = models.CharField(max_length=8, choices=KINDS, default=PHONE)
    name = models.CharField(max_length=64)
    push_subscription = models.JSONField(null=True, blank=True)
    paired_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_kind_display()})"


class NotificationLog(models.Model):
    """Ce qui a été envoyé, et par quel canal. Sert à prouver qu'un gardien
    a bien été déclenché — et à ne jamais le déclencher deux fois."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=32)
    coach_day = models.DateField(db_index=True)
    title = models.CharField(max_length=140)
    body = models.TextField()
    channels = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)
        # Un gardien par soir, un rappel par créneau : l'unicité est une règle
        # métier, pas une précaution technique.
        unique_together = ("user", "kind", "coach_day")


class Rappel(models.Model):
    """Une notification différée : le « reporter de 15 min » du §11.7.

    **Pourquoi un modèle et pas un minuteur.** Le report est demandé depuis une
    notification système, c'est-à-dire depuis un service worker qui sera
    endormi bien avant l'échéance — Android suspend le sien en quelques
    secondes. Le seul endroit capable de tenir quinze minutes est celui qui
    tourne déjà chaque minute : l'ordonnanceur du serveur.

    Un rappel **périmé ne part pas**. Si le serveur était éteint à l'heure dite,
    le faire partir une heure plus tard réveillerait quelqu'un pour une soirée
    qui est finie — et une notification qui arrive à contretemps est celle qui
    apprend à toutes les ignorer.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rappels")
    kind = models.CharField(max_length=32)
    due_at = models.DateTimeField(db_index=True)
    title = models.CharField(max_length=140)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("due_at",)

    def __str__(self) -> str:
        return f"{self.kind} à {self.due_at:%H:%M}"


class AgentEvent(models.Model):
    """Journal append-only, non éditable depuis l'interface."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_events")
    type = models.CharField(max_length=48)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class ProjectInterview(models.Model):
    """L'entretien qui produit une roadmap (SPEC §4.5, §5.6).

    **Le serveur porte la conversation, pas le modèle.** Chaque tour renvoie
    l'échange complet au fournisseur, plutôt que de s'appuyer sur une session
    ouverte de son côté. C'est un peu plus de jetons et beaucoup moins de
    surprises : l'entretien survit à un redémarrage, se reprend depuis le
    téléphone, se relit, et se teste sans réseau.

    Rien n'est écrit dans ``Project`` avant que l'utilisateur ait vu le markdown
    et confirmé. Un modèle qui aurait mal compris produit alors un brouillon
    qu'on jette, pas un projet à supprimer.
    """

    EN_COURS, PROPOSE, IMPORTE, ABANDONNE = "en_cours", "propose", "importe", "abandonne"
    STATUSES = [
        (EN_COURS, "Entretien en cours"),
        (PROPOSE, "Roadmap proposée"),
        (IMPORTE, "Projet créé"),
        (ABANDONNE, "Abandonné"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interviews"
    )
    status = models.CharField(max_length=16, choices=STATUSES, default=EN_COURS)
    # [{"role": "assistant"|"user", "content": "…"}] — l'échange tel qu'affiché.
    messages = models.JSONField(default=list, blank=True)
    markdown = models.TextField(blank=True, help_text="La roadmap proposée, pas encore importée")
    project = models.ForeignKey(
        "Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="interviews"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Entretien {self.id} ({self.get_status_display()})"

    @property
    def questions_posees(self) -> int:
        return sum(1 for m in self.messages if m.get("role") == "assistant")


class LootCard(models.Model):
    """Une carte obtenue (SPEC §12.6).

    Une ligne par clé de carte et par utilisateur : les doublons ne créent pas
    de nouvelles lignes, ils incrémentent ``copies`` et se convertissent en
    Éclats. Sans ça, l'inventaire d'une année serait une liste de trois cents
    entrées où l'on ne verrait plus ce qu'on possède.

    ``equipped`` est géré par emplacement, pas par carte : deux thèmes ne
    peuvent pas être équipés en même temps, et c'est ``services`` qui l'applique.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cards")
    key = models.CharField(max_length=32)
    rarity = models.CharField(max_length=16)
    kind = models.CharField(max_length=16)
    copies = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField(default=False)
    obtained_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=16, blank=True, help_text="niveau, semaine, saison")

    class Meta:
        ordering = ("-obtained_at",)
        unique_together = ("user", "key")

    def __str__(self) -> str:
        return f"{self.key} ({self.rarity})"

    @property
    def card(self):
        return rules_loot.PAR_CLE.get(self.key)


class OwnedRelic(models.Model):
    """Une relique débloquée par un haut fait (SPEC §12.8).

    Séparée de ``LootCard`` **exprès**, et pas par commodité de schéma : une
    relique donne un bonus, une carte n'en donne jamais. Les mélanger dans une
    même table rendrait possible, un jour, d'accorder un bonus à un tirage — ce
    que le §17 interdit. Deux tables, deux origines, aucune passerelle.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="relics")
    key = models.CharField(max_length=32)
    equipped = models.BooleanField(default=False)
    obtained_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-obtained_at",)
        unique_together = ("user", "key")

    def __str__(self) -> str:
        return self.key

    @property
    def relic(self):
        return rules_relics.PAR_CLE.get(self.key)


class LootDraw(models.Model):
    """Le journal des tirages, qui porte aussi les compteurs de pitié.

    Le compteur ne vit pas sur le profil : il se **recalcule** depuis ce
    journal. Un compteur stocké et un journal peuvent diverger, et le jour où
    ils divergent c'est la pitié qui se dérègle — donc la sensation que le
    système triche, qui est exactement ce que la pitié devait éviter.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="draws")
    key = models.CharField(max_length=32)
    rarity = models.CharField(max_length=16)
    duplicate = models.BooleanField(default=False)
    shards = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ("-created_at",)
