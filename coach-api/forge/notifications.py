"""Envoi des notifications.

Trois canaux, choisis pour qu'aucun ne demande d'installer une application de
plus :

- ``webpush``  : de vraies notifications système sur PC et Android, via le
  service worker de la PWA installée. C'est le canal principal.
- ``discord``  : un webhook sur un salon perso. Redondance fiable quand Android
  met le service worker en veille, et canal du bilan hebdo à l'ami.
- ``console``  : le repli de développement, qui écrit dans les logs.

Le contrat est le même pour tous : ``send(user, message)``. Ajouter un canal
(ntfy, e-mail, notification native de l'agent) revient à écrire une classe de
quinze lignes et à l'inscrire dans ``CHANNELS``.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Notification:
    """Ce qu'on envoie. Le ton du coach s'arrête au contenu, pas au transport."""

    title: str
    body: str
    kind: str = "info"          # gardien | creneau | sanction | bilan | info
    action_label: str = ""
    action_url: str = ""
    # Les boutons d'une notification Web Push (§11.7). Chaque entrée est
    # ``{"action", "title", "post"}`` : le service worker appelle ``post`` et
    # n'a rien à décider. C'est la condition pour qu'un bouton de notification
    # soit fiable — le worker peut être réveillé sans l'app, sans jeton, et sans
    # réseau stable ; tout ce qui demanderait un état local échouerait un soir
    # sur deux, c'est-à-dire toujours au mauvais moment.
    actions: tuple[dict, ...] = ()

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "body": self.body,
            "kind": self.kind,
            "action_label": self.action_label,
            "action_url": self.action_url,
            "actions": list(self.actions),
        }


class Channel:
    name = "abstrait"

    def available(self, profile) -> bool:
        raise NotImplementedError

    def send(self, profile, notification: Notification) -> bool:
        raise NotImplementedError


class ConsoleChannel(Channel):
    """Repli de développement : rien ne se perd, tout finit dans les logs."""

    name = "console"

    def available(self, profile) -> bool:
        return True

    def send(self, profile, notification: Notification) -> bool:
        logger.info("[coach] %s — %s", notification.title, notification.body)
        return True


class DiscordChannel(Channel):
    """Webhook Discord. Aucune application supplémentaire, aucun compte à créer."""

    name = "discord"

    def available(self, profile) -> bool:
        return bool(profile.discord_webhook)

    def send(self, profile, notification: Notification) -> bool:
        colors = {
            "gardien": 0xE8A33D,
            "creneau": 0x4FC4B4,
            "sanction": 0xDE5F7E,
            "bilan": 0x8A6FB0,
        }
        payload = {
            "embeds": [
                {
                    "title": notification.title,
                    "description": notification.body,
                    "color": colors.get(notification.kind, 0x9A8CAE),
                }
            ]
        }
        request = urllib.request.Request(
            profile.discord_webhook,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                return 200 <= response.status < 300
        except Exception as exc:                      # réseau, webhook révoqué…
            logger.warning("Discord injoignable : %s", exc)
            return False


class WebPushChannel(Channel):
    """Web Push vers la PWA installée — de vraies notifications système.

    L'envoi réel demande les clés VAPID et la bibliothèque `pywebpush` ; tant
    qu'elles ne sont pas configurées, le canal se déclare indisponible plutôt
    que d'échouer silencieusement.
    """

    name = "webpush"

    def available(self, profile) -> bool:
        from django.conf import settings

        return bool(settings.COACH.get("VAPID_PRIVATE_KEY")) and profile.user.devices.filter(
            push_subscription__isnull=False
        ).exists()

    def send(self, profile, notification: Notification) -> bool:
        from django.conf import settings

        try:
            from pywebpush import webpush
        except ImportError:
            logger.warning("pywebpush absent : canal Web Push inactif.")
            return False

        sent = False
        for device in profile.user.devices.exclude(push_subscription=None):
            try:
                webpush(
                    subscription_info=device.push_subscription,
                    data=json.dumps(notification.as_dict()),
                    vapid_private_key=settings.COACH["VAPID_PRIVATE_KEY"],
                    vapid_claims={"sub": settings.COACH["VAPID_SUBJECT"]},
                )
                sent = True
            except Exception as exc:
                logger.warning("Push refusé pour %s : %s", device.name, exc)
        return sent


CHANNELS: tuple[Channel, ...] = (WebPushChannel(), DiscordChannel(), ConsoleChannel())


def notify(user, notification: Notification) -> list[str]:
    """Envoie sur tous les canaux disponibles et rend ceux qui ont abouti.

    La redondance est volontaire : un gardien du soir qui n'arrive pas est un
    gardien qui n'existe pas, et Android endort les service workers sans
    prévenir.
    """
    profile = user.profile
    delivered: list[str] = []

    for channel in CHANNELS:
        if not channel.available(profile):
            continue
        if channel.send(profile, notification):
            delivered.append(channel.name)
            # La console est un repli : inutile de doubler un envoi réussi.
            if channel.name != "console":
                continue

    from .models import AgentEvent

    AgentEvent.objects.create(
        user=user,
        type="notification",
        payload={"notification": notification.as_dict(), "delivered": delivered},
    )
    return delivered
