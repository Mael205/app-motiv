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
    created_at = models.DateTimeField(default=timezone.now)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("slot", "name")

    def __str__(self) -> str:
        return self.name

    @property
    def current_step(self) -> "RoadmapStep | None":
        return (
            self.steps.filter(state__in=[RoadmapStep.DOING, RoadmapStep.TODO])
            .order_by("-state", "order")
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
    order = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=255)
    state = models.CharField(max_length=8, choices=STATES, default=TODO)
    estimated_sessions = models.PositiveSmallIntegerField(default=1)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.label

    @property
    def needs_split(self) -> bool:
        """Plus de 3 sessions estimées : l'étape est trop grosse (SPEC §4.5)."""
        return self.estimated_sessions > 3


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

    class Meta:
        unique_together = ("user", "index")
        ordering = ("-index",)

    def __str__(self) -> str:
        return f"Saison {self.index} — {self.name}"

    def day_index(self, day) -> int:
        return (day - self.starts_on).days

    def days_left(self, day) -> int:
        return max(0, (self.ends_on - day).days)


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
    planned_minutes = models.PositiveSmallIntegerField(default=25)
    actual_minutes = models.PositiveSmallIntegerField(default=0)
    mode = models.CharField(max_length=16, choices=MODES, default=NORMAL)
    status = models.CharField(max_length=16, choices=STATUSES, default=RUNNING)
    rank_in_day = models.PositiveSmallIntegerField(default=1)
    xp_awarded = models.IntegerField(default=0)
    xp_breakdown = models.JSONField(default=dict, blank=True)
    focus_quality = models.PositiveSmallIntegerField(null=True, blank=True)
    energy_level = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1 à 3")
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
    KINDS = [
        (FRIGO, "Jeter une idée au frigo"),
        (VU, "Accuser réception d'un bilan"),
        (REPONSE, "Répondre à une question"),
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
