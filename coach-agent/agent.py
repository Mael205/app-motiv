"""coach-agent — la sonde PC (SPEC §8).

Elle lit ce qui se passe sur la machine et poste des **catégories et des
durées** au serveur. Jamais un titre de fenêtre, jamais une URL, jamais une
capture : le §17 interdit la capture d'écran et le keylogging, le §11.10 ajoute
l'interdiction de faire sortir l'adresse exacte d'où que ce soit.

Deux sources, toutes deux en lecture seule :

1. **ActivityWatch** (`localhost:5600`), s'il est installé. L'agent
   n'implémente pas son propre suivi de fenêtre — ActivityWatch gère déjà
   l'inactivité clavier/souris, le multi-écran et la veille, et il le fait
   mieux qu'un script de 200 lignes ne le ferait (SPEC §8.4). Absent, l'agent
   le signale et continue : la mesure d'activité est simplement absente.
2. **git**, sur les dépôts déclarés des projets, pour la preuve de travail.
3. **AdGuard Home**, s'il est configuré : le seul point qui voit *tous* les
   appareils du réseau, téléphone compris. Auto-hébergé, donc les domaines ne
   sortent pas de chez toi (voir ``adguard.py``).

La catégorisation se fait **ici**, avec `categories.toml`, avant tout envoi.
Le serveur reçoit « reseaux : 14 minutes » et n'apprend jamais lequel.

Usage :

    python agent.py --once            # un cycle, pour vérifier que ça marche
    python agent.py                   # boucle, toutes les 10 minutes
"""

from __future__ import annotations

import argparse
import sys
import time
import tomllib
import urllib.error
import urllib.request
import adguard
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.local.toml")
CATEGORIES_PATH = Path(__file__).with_name("categories.toml")
ACTIVITYWATCH = "http://localhost:5600"
DEFAULT_INTERVAL_SECONDS = 600
AUTRE = "autre"


def load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


class Categoriser:
    """Traduit un nom d'application ou de domaine en catégorie, localement."""

    def __init__(self, mapping: dict[str, list[str]]):
        self.mapping = {
            category: [fragment.lower() for fragment in fragments]
            for category, fragments in mapping.items()
        }

    def of(self, label: str) -> str:
        needle = (label or "").lower()
        for category, fragments in self.mapping.items():
            if any(fragment in needle for fragment in fragments):
                return category
        return AUTRE


def activitywatch_events(since: datetime) -> list[tuple[str, float]]:
    """Événements de fenêtre depuis ActivityWatch. Rend ``(étiquette, secondes)``.

    Ne lève jamais : si ActivityWatch n'est pas lancé, on rend une liste vide et
    l'appelant le signale. Une sonde absente n'est pas une erreur, c'est une
    absence de mesure — et le §11.10 interdit d'en conclure quoi que ce soit.
    """
    import json

    try:
        with urllib.request.urlopen(f"{ACTIVITYWATCH}/api/0/buckets", timeout=3) as response:
            buckets = json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        return []

    out: list[tuple[str, float]] = []
    for name, bucket in buckets.items():
        kind = bucket.get("type", "")
        if "window" not in kind and "web" not in kind:
            continue
        url = (
            f"{ACTIVITYWATCH}/api/0/buckets/{name}/events"
            f"?start={since.isoformat()}&limit=2000"
        )
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                events = json.load(response)
        except (urllib.error.URLError, OSError, ValueError):
            continue

        for event in events:
            data = event.get("data", {})
            # On lit l'application et le domaine, jamais le titre de la fenêtre.
            label = data.get("app") or data.get("url") or ""
            out.append((label, float(event.get("duration", 0))))
    return out


def aggregate(events: list[tuple[str, float]], categoriser: Categoriser) -> dict[str, int]:
    """Minutes par catégorie. C'est tout ce qui quittera cette machine."""
    totals: dict[str, float] = defaultdict(float)
    for label, seconds in events:
        totals[categoriser.of(label)] += seconds
    return {
        category: int(seconds // 60)
        for category, seconds in totals.items()
        if seconds >= 60 and category != AUTRE
    }


def post_entries(base_url: str, token: str, entries: list[dict]) -> dict:
    """Envoie des entrées déjà formées, chacune avec sa propre fenêtre."""
    import json

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/signals",
        data=json.dumps({"source": "agent", "entries": entries}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Probe-Token": token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def poll_adguard(config: dict, categoriser: Categoriser, *, since: datetime, verbose: bool) -> None:
    """Lit le résolveur, catégorise **ici**, n'envoie que des catégories."""
    section = config.get("adguard") or {}
    if not section.get("url"):
        return

    queries = adguard.fetch_queries(
        section["url"],
        section.get("username", ""),
        section.get("password", ""),
        since=since,
    )
    if queries is None:
        print("AdGuard Home injoignable — aucune mesure réseau. Rien n'en est déduit.")
        return

    # La traduction domaine → catégorie se fait sur cette machine, et le domaine
    # ne va pas plus loin (SPEC §11.10).
    events = [
        (moment, categoriser.of(domain))
        for moment, domain in queries
        if categoriser.of(domain) != AUTRE
    ]
    if not events:
        if verbose:
            print("  AdGuard : rien de catégorisé sur cette fenêtre.")
        return

    entries = adguard.to_entries(adguard.bursts(events))
    if verbose:
        for entry in entries:
            print(f"  AdGuard : {entry['category']} — {entry['minutes']} min")

    try:
        result = post_entries(config["api_url"], config["token"], entries)
    except (urllib.error.URLError, OSError, KeyError) as error:
        print(f"Envoi AdGuard impossible ({error}).")
        return

    for mark in result.get("marked", []):
        print(f"  garde marquée : {mark['garde']} ({mark['minutes']} min)")


def post_signals(
    base_url: str, token: str, entries: dict[str, int], *, since: datetime, until: datetime
) -> dict:
    """Envoie les totaux **avec la fenêtre observée**.

    Sans elle, le serveur ne pourrait pas rattacher ce temps à une session : il
    saurait « 20 minutes dans la journée » sans savoir lesquelles (SPEC §6).
    """
    import json

    payload = {
        "source": "agent",
        "entries": [
            {
                "category": c,
                "minutes": m,
                "started_at": since.isoformat(),
                "ended_at": until.isoformat(),
            }
            for c, m in entries.items()
        ],
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/signals",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Probe-Token": token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def cycle(config: dict, categoriser: Categoriser, *, window_minutes: int, verbose: bool) -> None:
    until = datetime.now(timezone.utc)
    since = until - timedelta(minutes=window_minutes)

    poll_adguard(config, categoriser, since=since, verbose=verbose)

    events = activitywatch_events(since)

    if not events:
        print(
            "ActivityWatch injoignable sur localhost:5600 — aucune mesure d'activité "
            "sur cette fenêtre. Rien n'en est déduit."
        )
        return

    entries = aggregate(events, categoriser)
    if verbose:
        for category, minutes in sorted(entries.items()):
            print(f"  {category:>20} : {minutes} min")

    if not entries:
        print("Rien de catégorisé sur cette fenêtre.")
        return

    try:
        result = post_signals(
            config["api_url"], config["token"], entries, since=since, until=until
        )
    except (urllib.error.URLError, OSError, KeyError) as error:
        print(f"Envoi impossible ({error}). Les signaux de cette fenêtre sont perdus.")
        return

    marked = result.get("marked", [])
    print(f"{result.get('stored', 0)} signaux envoyés.")
    for mark in marked:
        print(f"  garde marquée : {mark['garde']} ({mark['minutes']} min)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sonde PC du coach (SPEC §8).")
    parser.add_argument("--once", action="store_true", help="Un seul cycle puis on sort.")
    parser.add_argument("--window", type=int, default=10, help="Fenêtre lue, en minutes.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    config = load_toml(CONFIG_PATH)
    if not config.get("api_url") or not config.get("token"):
        print(
            "Il manque config.local.toml. Crée-le à côté de agent.py :\n\n"
            '    api_url = "http://127.0.0.1:8000"\n'
            '    token   = "<jeton de sonde>"\n\n'
            "Ce fichier est ignoré par git et n'est jamais modifiable via l'API (SPEC §8).",
            file=sys.stderr,
        )
        return 1

    categoriser = Categoriser(load_toml(CATEGORIES_PATH).get("categories", {}))
    interval = int(config.get("interval_seconds", DEFAULT_INTERVAL_SECONDS))

    while True:
        cycle(config, categoriser, window_minutes=args.window, verbose=not args.quiet)
        if args.once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
