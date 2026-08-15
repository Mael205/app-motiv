"""Émet et révoque les jetons de sonde (SPEC §8, §9).

    python manage.py probetoken --issue ext --name "Chrome portable"
    python manage.py probetoken --list
    python manage.py probetoken --revoke 3
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from forge.models import ProbeToken
from forge.rules import signals as signal_rules


class Command(BaseCommand):
    help = "Gère les jetons de sonde. Un jeton ne peut que poster des signaux."

    def add_arguments(self, parser):
        parser.add_argument("--issue", choices=signal_rules.SOURCES, help="Émet un jeton pour cette sonde.")
        parser.add_argument("--name", default="", help="Nom lisible du jeton.")
        parser.add_argument("--list", action="store_true")
        parser.add_argument("--revoke", type=int, help="Identifiant du jeton à révoquer.")
        parser.add_argument("--user", default="arthur")

    def handle(self, *args, **options):
        user = get_user_model().objects.get(username=options["user"])

        if options["issue"]:
            kind = options["issue"]
            token, raw = ProbeToken.issue(user, name=options["name"] or kind, kind=kind)
            self.stdout.write(self.style.SUCCESS(f"Jeton #{token.pk} émis pour « {token.name} »."))
            self.stdout.write("")
            self.stdout.write(f"    {raw}")
            self.stdout.write("")
            self.stdout.write(
                "Copie-le maintenant : seule son empreinte est stockée, il ne sera plus jamais affiché."
            )
            return

        if options["revoke"]:
            updated = ProbeToken.objects.filter(user=user, pk=options["revoke"], revoked_at=None).update(
                revoked_at=timezone.now()
            )
            self.stdout.write("Jeton révoqué." if updated else "Aucun jeton actif avec cet identifiant.")
            return

        for token in ProbeToken.objects.filter(user=user):
            etat = "révoqué" if not token.active else "actif"
            vu = token.last_used_at.strftime("%d/%m %H:%M") if token.last_used_at else "jamais utilisé"
            self.stdout.write(f"#{token.pk}  {token.kind:<7} {token.name:<24} {etat:<8} {vu}")
