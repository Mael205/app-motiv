"""Le blocage par le résolveur — le seul qui atteigne le téléphone (SPEC §8.5).

*(Écrit le 16 septembre 2026, et **désactivé par défaut**.)*

Le fichier hosts ne ferme que la machine où il vit, et l'extension que le
navigateur où elle est installée. Le téléphone est donc resté ouvert pendant
qu'un couvre-feu fermait le PC — c'est-à-dire que le couvre-feu ne fermait rien
du tout : il déplaçait l'écran.

AdGuard Home est déjà là comme **sonde** (``adguard.py``). Il voit tous les
appareils du réseau, il est auto-hébergé, et il sait refuser une résolution.
C'est le même point de passage, utilisé dans l'autre sens.

**Ce que ce module écrit, et rien d'autre.** Les règles du coach vivent entre
deux marqueurs dans les *règles utilisateur* d'AdGuard. Tout ce qui est hors des
marqueurs appartient à l'utilisateur et est réécrit tel quel — même principe
qu'au fichier hosts, et pour la même raison : un outil qui écrase la
configuration d'à côté finit par casser quelque chose que personne ne relie à
lui.

**Trois limites, dites d'avance :**

- **en 4G, le téléphone ne passe plus par AdGuard.** Ce blocage couvre le
  Wi-Fi, donc la maison. C'est là que se passent les soirées qu'il vise ;
- **il ne remplace pas le fichier hosts**, il s'y ajoute. Le PC reste fermé même
  si le résolveur tombe ;
- **il se lève avec le reste.** La porte de sortie du §8.5 et le sas du §4.6
  désarment le serveur, donc ce module reçoit « rien à fermer » et retire ses
  règles. Un blocage réseau qu'on ne peut pas lever depuis l'app serait le
  premier à être contourné par un changement de DNS.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from adguard import ProbeError, _login

MARQUEUR_DEBUT = "! --- coach : blocage (SPEC §8.5) ---"
MARQUEUR_FIN = "! --- coach : fin ---"

# Les mêmes catégories qu'au fichier hosts, et pour les mêmes raisons : le
# scroll passif et les réseaux, jamais les jeux ni le travail (§17).
CATEGORIES_FERMEES = ("scroll_passif", "reseaux")

# Ce que le couvre-feu ajoute, comme dans ``blocage.py``.
DOMAINES_DE_NUIT = ("youtube.com", "youtu.be")


def regles(domaines: list[str]) -> list[str]:
    """Les règles AdGuard pour ces domaines, sous-domaines compris.

    ``||domaine^`` est la forme qui ferme le domaine **et** ce qui est dessous,
    sans toucher aux domaines qui finissent par la même chaîne : ``||x.com^``
    ne ferme pas ``notx.com``.
    """
    return [f"||{domaine}^" for domaine in domaines]


def sans_le_bloc(lignes: list[str]) -> list[str]:
    """Les règles de l'utilisateur, sans celles du coach. Sans effet s'il n'y en a pas."""
    sortie, dedans = [], False
    for ligne in lignes:
        if ligne.strip() == MARQUEUR_DEBUT:
            dedans = True
            continue
        if ligne.strip() == MARQUEUR_FIN:
            dedans = False
            continue
        if not dedans:
            sortie.append(ligne)
    return sortie


def avec_le_bloc(lignes: list[str], regles_du_coach: list[str]) -> list[str]:
    """Les règles de l'utilisateur, avec celles du coach. Idempotent."""
    base = sans_le_bloc(lignes)
    if not regles_du_coach:
        return base
    return [*base, MARQUEUR_DEBUT, *regles_du_coach, MARQUEUR_FIN]


def domaines_pour(niveau: str, categories: dict[str, list[str]]) -> list[str]:
    """Ce qu'il faut fermer pour ce niveau. Vide quand il n'y a rien à fermer.

    Un chemin n'est pas un domaine : ``youtube.com/shorts`` est écarté, comme au
    fichier hosts — l'écrire sans son chemin fermerait YouTube en entier, ce que
    le §9.1 interdit avant le couvre-feu.
    """
    if not niveau:
        return []

    domaines: list[str] = []
    for categorie in CATEGORIES_FERMEES:
        for fragment in categories.get(categorie, []):
            nom = fragment.strip().lower()
            if "/" in nom or nom.endswith(".exe") or "." not in nom:
                continue
            if nom not in domaines:
                domaines.append(nom)

    if niveau == "nuit":
        domaines += [d for d in DOMAINES_DE_NUIT if d not in domaines]
    return domaines


def _post(base: str, chemin: str, cookie: str, corps: dict) -> None:
    requete = urllib.request.Request(
        f"{base}{chemin}",
        data=json.dumps(corps).encode("utf-8"),
        headers={"Cookie": cookie, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(requete, timeout=10).close()
    except urllib.error.HTTPError as error:
        raise ProbeError(f"AdGuard a répondu {error.code} à l'écriture des règles") from error
    except (urllib.error.URLError, OSError) as error:
        raise ProbeError("AdGuard injoignable — le service tourne-t-il ?") from error


def appliquer(
    base_url: str,
    username: str,
    password: str,
    *,
    niveau: str,
    categories: dict[str, list[str]],
) -> list[str]:
    """Aligne les règles d'AdGuard sur le niveau demandé. Rend ce qui est fermé.

    ``niveau`` vient du serveur : vide, « projet » ou « nuit ». Comme partout
    ailleurs, l'agent ne décide de rien — il applique, et le résolveur ne sait
    même pas pourquoi.
    """
    base = base_url.rstrip("/")
    cookie = _login(base, username, password)

    from adguard import _get

    etat = _get(f"{base}/control/filtering/status", cookie)
    actuelles = list(etat.get("user_rules") or [])

    fermes = domaines_pour(niveau, categories)
    voulues = avec_le_bloc(actuelles, regles(fermes))

    # N'écrire que si ça change : AdGuard recharge ses filtres à chaque
    # écriture, et le faire toutes les dix minutes pour rien coûte une coupure
    # de résolution à tout le réseau.
    if voulues != actuelles:
        _post(base, "/control/filtering/set_rules", cookie, {"rules": voulues})
    return fermes
