"""L'horloge du coach.

    python manage.py tick            # une passe
    python manage.py tick --loop     # boucle chaque minute, pour le dev

En production, un cron externe appelle cette commande chaque minute — ce qui
sert aussi de ping et empêche le free tier de s'endormir avant le gardien du
soir, qui est le mécanisme le plus important à ne jamais rater.
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from forge import triggers


class Command(BaseCommand):
    help = "Évalue les déclencheurs : rappels de créneau, gardien du soir, fin de sas."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Boucle chaque minute.")

    def handle(self, *args, **options):
        while True:
            fired = triggers.run_all(timezone.now())
            for event in fired:
                self.stdout.write(self.style.SUCCESS(f"déclenché : {event}"))
            if not options["loop"]:
                if not fired:
                    self.stdout.write("rien à déclencher pour l'instant.")
                return
            time.sleep(60)
