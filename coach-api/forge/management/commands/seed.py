"""Seed de développement : les vrais projets du SPEC §0, une saison ouverte.

    python manage.py seed --reset
"""

from __future__ import annotations

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from forge import services
from forge.models import (
    DayWindow,
    Profile,
    Project,
    Quest,
    RoadmapStep,
    Season,
    TimeSlot,
    Track,
)
from forge.rules.calendar import coach_day

PROJETS = [
    {
        "name": "Prototype UE5 — 4v1 asymétrique",
        "color": "#E8A33D",
        "emblem": "⬢",
        "branch": "moteur_de_jeu",
        "slot": 1,
        "steps": [
            ("Boucle de déplacement du survivant", "done", 2),
            ("Détection de collision du monstre", "doing", 2),
            ("Prototype de la mécanique de capture", "todo", 3),
            ("Écran de fin de partie", "todo", 1),
        ],
        "timeslots": [(1, time(20, 30), 50), (4, time(20, 30), 50)],
    },
    {
        "name": "Outils Dofus 3 — rentabilité craft",
        "color": "#4FC4B4",
        "emblem": "◈",
        "branch": "backend",
        "slot": 2,
        "steps": [
            ("Scraper les prix de l'HDV", "done", 2),
            ("Modèle de coût de craft", "doing", 2),
            ("API de comparaison des recettes", "todo", 3),
            ("Interface de consultation", "todo", 2),
        ],
        "timeslots": [(2, time(20, 30), 25)],
    },
    {
        "name": "Bot Slay the Spire 2 — RL",
        "color": "#8A6FB0",
        "emblem": "✦",
        "branch": "data_rl",
        "slot": 3,
        "steps": [
            ("Wrapper d'état de partie en C#", "doing", 3),
            ("Encodage des observations", "todo", 2),
            ("Boucle d'entraînement PPO", "todo", 3),
        ],
        "timeslots": [(3, time(20, 30), 50)],
    },
    {
        "name": "Développement du coach",
        "color": "#DE5F7E",
        "emblem": "◆",
        "branch": "backend",
        "slot": None,
        "is_coach_project": True,
        "steps": [
            ("J0 — socle du monorepo", "doing", 2),
            ("J1 — noyau et déclencheurs", "todo", 3),
        ],
        "timeslots": [],
    },
]

FRIGO = [
    "Analyseur de logs Windows en Rust",
    "Extension navigateur pour couper les Shorts",
    "Simulateur de combat Dofus en ligne de commande",
]


class Command(BaseCommand):
    help = "Charge les projets réels, une saison ouverte et les quêtes du jour."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Vide les données métier avant de recharger.")
        parser.add_argument("--user", default="arthur")
        parser.add_argument("--password", default="coach")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=options["user"], defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            user.set_password(options["password"])
            user.save()
            self.stdout.write(f"Utilisateur créé : {options['user']} / {options['password']}")

        profile, _ = Profile.objects.get_or_create(user=user)
        for weekday in range(7):
            start, end = (time(18), time(23)) if weekday < 5 else (time(10), time(23))
            DayWindow.objects.update_or_create(
                profile=profile, weekday=weekday, defaults={"start_time": start, "end_time": end}
            )

        if options["reset"]:
            Project.objects.filter(user=user).delete()
            Season.objects.filter(user=user).delete()
            Quest.objects.filter(user=user).delete()
            self.stdout.write("Données métier vidées.")

        atelier, _ = Track.objects.get_or_create(user=user, kind=Track.ATELIER)
        Track.objects.get_or_create(user=user, kind=Track.CORPS)

        for spec in PROJETS:
            project, _ = Project.objects.update_or_create(
                user=user,
                name=spec["name"],
                defaults={
                    "track": atelier,
                    "color": spec["color"],
                    "emblem": spec["emblem"],
                    "branch": spec["branch"],
                    "slot": spec["slot"],
                    "is_coach_project": spec.get("is_coach_project", False),
                    "weekly_commitment": 3,
                },
            )
            project.steps.all().delete()
            for order, (label, state, estimate) in enumerate(spec["steps"]):
                RoadmapStep.objects.create(
                    project=project, order=order, label=label, state=state, estimated_sessions=estimate
                )
            project.timeslots.all().delete()
            for weekday, start, duration in spec["timeslots"]:
                TimeSlot.objects.create(
                    project=project, weekday=weekday, start_time=start, duration_minutes=duration
                )

        from forge.models import FridgeIdea

        for text in FRIGO:
            FridgeIdea.objects.get_or_create(user=user, text=text)

        today = coach_day(timezone.now(), profile.timezone_name, profile.day_rollover_hour)
        if not Season.objects.filter(user=user, status=Season.RUNNING).exists():
            season = services.open_season(user, starts_on=today - timedelta(days=3), stake=120)
            self.stdout.write(f"Saison ouverte : {season.name} — boss {season.boss.name} ({season.boss.max_hp} PV)")

        Quest.objects.filter(user=user, date=today).delete()
        Quest.objects.create(
            user=user, kind=Quest.PLANCHER, date=today, label="Une session de 25 minutes", target=1, reward_xp=0
        )
        Quest.objects.create(
            user=user,
            kind=Quest.BONUS,
            date=today,
            label="Démarrer avant 20h",
            target=1,
            reward_xp=15,
        )

        self.stdout.write(self.style.SUCCESS("Seed terminé."))
