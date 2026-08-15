"""Lecture d'un AdGuard Home auto-hébergé (SPEC §9, §11.10).

L'extension ne voit qu'un navigateur, l'agent ne voit que le PC, une recette
mobile ne voit que des applications. Un résolveur DNS voit **tous les appareils
du réseau**, y compris la navigation privée — c'est le seul moyen d'éteindre
l'angle mort du téléphone sans écrire d'application Android.

Auto-hébergé, et c'est le point : la journalisation reste chez toi. Un résolveur
tiers inverserait tout ce que ce système protège, en recevant chaque domaine que
tu résous sur chaque appareil. Ici, les domaines sont lus en local, traduits en
catégories par ``categories.toml``, et seules les catégories sortent.

**Une requête DNS est un événement, pas une durée.** Ce module ne prétend donc
pas mesurer un temps d'usage : il regroupe les requêtes d'une même catégorie en
*rafales* et rend l'amplitude de chaque rafale — l'écart entre la première et la
dernière requête. C'est une estimation d'activité, assumée comme telle.

Conséquence utile : une requête isolée produit une rafale d'une minute, sous le
seuil de marquage du serveur. Un tracker embarqué ou un préchargement de
navigateur ne marquera donc jamais une journée à lui seul.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta

MAX_GAP_MINUTES = 5
MIN_BURST_MINUTES = 1
PAGE_SIZE = 500
MAX_PAGES = 20


@dataclass(frozen=True)
class Burst:
    """Une rafale de requêtes d'une même catégorie."""

    category: str
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        span = (self.end - self.start).total_seconds() / 60
        return max(MIN_BURST_MINUTES, int(round(span)))


class ProbeError(Exception):
    """Une raison précise de ne pas avoir pu lire le résolveur.

    « Injoignable » et « identifiants refusés » demandent des gestes opposés :
    les confondre fait chercher un problème de réseau là où il faut corriger un
    mot de passe. Le message doit donc porter la distinction — sans jamais
    contenir l'identifiant lui-même.
    """


def _login(base: str, username: str, password: str) -> str:
    """Ouvre une session et rend le cookie.

    AdGuard n'accepte pas l'authentification Basic sur son API : il faut passer
    par ``/control/login`` et réutiliser le cookie de session. Un 401 renvoyé
    sans en-tête ``WWW-Authenticate`` est le signe de ce fonctionnement.
    """
    payload = json.dumps({"name": username, "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/control/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as error:
        if error.code in (400, 401, 403):
            raise ProbeError(
                "identifiants refusés par AdGuard — corrige [adguard] dans config.local.toml"
            ) from error
        raise ProbeError(f"AdGuard a répondu {error.code} à la connexion") from error
    except (urllib.error.URLError, OSError) as error:
        raise ProbeError("AdGuard injoignable — le service tourne-t-il ?") from error

    cookie = raw.split(";", 1)[0].strip() if raw else ""
    if not cookie:
        raise ProbeError("AdGuard n'a pas renvoyé de cookie de session")
    return cookie


def _get(url: str, cookie: str) -> dict:
    """Appel authentifié par le cookie de session."""
    request = urllib.request.Request(url, headers={"Cookie": cookie})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ProbeError("session AdGuard refusée ou expirée") from error
        raise ProbeError(f"AdGuard a répondu {error.code}") from error
    except (urllib.error.URLError, OSError) as error:
        raise ProbeError("AdGuard injoignable — le service tourne-t-il ?") from error
    except ValueError as error:
        raise ProbeError("réponse d'AdGuard illisible") from error


def _domain_of(entry: dict) -> str:
    """Le domaine interrogé. AdGuard a changé de nom de champ selon les versions."""
    question = entry.get("question") or {}
    return (question.get("name") or question.get("host") or "").rstrip(".").lower()


def fetch_queries(
    base_url: str, username: str, password: str, *, since: datetime
) -> list[tuple[datetime, str]]:
    """Requêtes DNS depuis ``since``, sous forme de ``(instant, domaine)``.

    Lève ``ProbeError`` si le résolveur n'a pas pu être lu. Une liste vide
    signifie « lu, et rien vu » — les deux ne permettent pas les mêmes
    conclusions (SPEC §11.10).
    """
    base = base_url.rstrip("/")
    cookie = _login(base, username, password)
    out: list[tuple[datetime, str]] = []
    older_than = ""

    for _ in range(MAX_PAGES):
        url = f"{base}/control/querylog?limit={PAGE_SIZE}"
        if older_than:
            url += f"&older_than={older_than}"

        try:
            payload = _get(url, cookie)
        except ProbeError:
            if out:
                break          # première page lue : on garde ce qu'on a
            raise

        entries = payload.get("data") or []
        if not entries:
            break

        fini = False
        for entry in entries:
            raw = entry.get("time")
            if not raw:
                continue
            try:
                moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if moment < since:
                fini = True
                break
            domain = _domain_of(entry)
            if domain:
                out.append((moment, domain))

        if fini:
            break
        older_than = payload.get("oldest") or ""
        if not older_than:
            break

    return out


def bursts(
    events: list[tuple[datetime, str]], *, max_gap_minutes: int = MAX_GAP_MINUTES
) -> list[Burst]:
    """Regroupe des ``(instant, catégorie)`` en rafales par catégorie.

    Deux requêtes séparées de plus de ``max_gap_minutes`` appartiennent à deux
    rafales : entre les deux, rien ne prouve qu'il se passait quoi que ce soit.
    """
    par_categorie: dict[str, list[datetime]] = {}
    for moment, category in events:
        par_categorie.setdefault(category, []).append(moment)

    gap = timedelta(minutes=max_gap_minutes)
    out: list[Burst] = []

    for category, moments in par_categorie.items():
        moments.sort()
        debut = precedent = moments[0]
        for moment in moments[1:]:
            if moment - precedent > gap:
                out.append(Burst(category=category, start=debut, end=precedent))
                debut = moment
            precedent = moment
        out.append(Burst(category=category, start=debut, end=precedent))

    out.sort(key=lambda b: b.start)
    return out


def to_entries(found: list[Burst]) -> list[dict]:
    """Traduit des rafales en entrées de signal, fenêtre comprise."""
    return [
        {
            "category": burst.category,
            "minutes": burst.minutes,
            "started_at": burst.start.isoformat(),
            "ended_at": burst.end.isoformat(),
        }
        for burst in found
    ]
