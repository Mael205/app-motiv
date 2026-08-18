"""Génère la paire de clés VAPID des notifications Web Push.

    python manage.py vapid_keys

``settings.py`` renvoyait vers cette commande depuis le début sans qu'elle
existe : configurer les notifications demandait donc d'aller chercher soi-même
comment fabriquer une clé EC P-256 en base64url, ce qui est exactement le genre
de détail qui fait renoncer à une fonctionnalité par ailleurs terminée.

Les clés ne sont **pas écrites** dans `.env`. C'est délibéré : une commande qui
modifie un fichier de configuration à la place de quelqu'un le fait aussi le
jour où il en existait déjà une, et une clé privée écrasée coupe toutes les
notifications déjà abonnées sans rien dire. Elle affiche, on colle.
"""

from __future__ import annotations

import base64

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Génère une paire de clés VAPID pour les notifications Web Push."

    def handle(self, *args, **options):
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ec
        except ImportError as error:                  # pragma: no cover
            raise CommandError(
                "La bibliothèque « cryptography » manque. Elle arrive avec "
                "pywebpush :\n\n    pip install pywebpush\n"
            ) from error

        prive = ec.generate_private_key(ec.SECP256R1())
        public = prive.public_key()

        # Le format attendu par le navigateur : le point public non compressé
        # (65 octets), et le scalaire privé (32 octets), tous deux en base64url
        # sans remplissage. C'est ce que fait py_vapid ; le refaire ici évite
        # une dépendance de plus pour quatre lignes.
        octets_public = public.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        octets_prive = prive.private_numbers().private_value.to_bytes(32, "big")

        self.stdout.write(self.style.SUCCESS("Colle ces deux lignes dans coach-api/.env :\n"))
        self.stdout.write(f"VAPID_PUBLIC_KEY={_b64(octets_public)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={_b64(octets_prive)}")
        self.stdout.write(
            "\nEt une adresse de contact, exigée par la spécification Web Push :\n"
            "VAPID_SUBJECT=mailto:toi@exemple.fr\n"
        )
        self.stdout.write(
            self.style.WARNING(
                "Garde la clé privée. La changer invalide tous les abonnements "
                "déjà pris : les appareils devront se réabonner, sans être prévenus."
            )
        )


def _b64(donnees: bytes) -> str:
    return base64.urlsafe_b64encode(donnees).rstrip(b"=").decode("ascii")
