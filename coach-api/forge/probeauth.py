"""Authentification des sondes (SPEC §8, §9).

Une sonde poste des signaux et rien d'autre. Cette classe n'est branchée que sur
``/api/signals`` : un jeton de sonde volé — dans une extension navigateur, sur
un téléphone perdu — ne donne accès à aucun autre endpoint, et ne permet ni de
lire l'historique, ni de toucher aux projets.
"""

from __future__ import annotations

from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import ProbeToken

HEADER = "HTTP_X_PROBE_TOKEN"


class ProbeTokenAuthentication(authentication.BaseAuthentication):
    """Authentifie par l'en-tête ``X-Probe-Token``."""

    def authenticate(self, request):
        raw = request.META.get(HEADER)
        if not raw:
            return None

        token = ProbeToken.objects.filter(token_hash=ProbeToken.hash_of(raw)).first()
        if token is None:
            raise exceptions.AuthenticationFailed("Jeton de sonde inconnu.")
        if not token.active:
            raise exceptions.AuthenticationFailed("Jeton de sonde révoqué.")

        ProbeToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
        request.probe_token = token
        return (token.user, token)

    def authenticate_header(self, request) -> str:
        """Sans cet en-tête, DRF répondrait 403 à un jeton invalide.

        La nuance compte pour une sonde : 401 veut dire « ton jeton ne vaut
        rien, réémets-en un », 403 veut dire « tu n'as pas le droit ». Une sonde
        qui reçoit 403 réessaie indéfiniment avec un secret mort.
        """
        return "X-Probe-Token"
