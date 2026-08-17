"""Le blocage des domaines pleins (SPEC §8.5).

L'extension ferme YouTube, qui demande de distinguer une page d'une autre. Ici
on ferme des **domaines entiers** — TikTok, X, Instagram, Reddit —, et pour ça
le fichier hosts suffit : il couvre tous les navigateurs, tous les profils, la
navigation privée, et les applications de bureau qui parlent aux mêmes serveurs.

Le fichier hosts demande les droits administrateur, et le §8 interdit que
l'agent les ait : il lit ActivityWatch, il parle au serveur, il lance des
programmes d'une liste blanche — lui donner l'élévation en plus ferait de la
moindre faille une machine ouverte.

D'où la coupure en deux, telle que le §8.5 la décrit :

- **le service** (``python blocage.py --service``, lancé élevé) n'accepte que
  deux ordres, ``block`` et ``unblock``, sur un tube local. Il ne prend aucune
  liste de domaines de l'extérieur : elle est lue ici, sur cette machine, dans
  ``categories.toml``. Un tube compromis ne peut donc pas faire fermer un
  domaine arbitraire — il ne peut que rejouer l'un des deux ordres ;
- **l'agent** tourne en utilisateur normal et se contente d'envoyer l'ordre.

La porte de sortie du §8.5 : ``python blocage.py --lever``. Soixante secondes
d'attente, puis deux heures de répit. « La friction suffit, l'emprisonnement
non. »
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

MARQUEUR_DEBUT = "# --- coach : blocage du scroll passif (SPEC §8.5) ---"
MARQUEUR_FIN = "# --- coach : fin du blocage ---"

TUBE = r"\\.\pipe\coach-blocage"
ORDRES = ("block", "unblock")

HOSTS = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
PAUSE_PATH = Path(__file__).with_name("pause.local")

# Voir l'extension : deux heures couvrent une soirée, et demain repart armé.
PAUSE = timedelta(hours=2)
ATTENTE_SECONDES = 60

# Les catégories qui se ferment, et elles seules. Le §8.5 nomme les domaines
# pleins — TikTok, X, Instagram, Reddit — et s'arrête là.
#
# « travail_hors_projet » n'y est pas : fermer Outlook un soir de semaine
# reviendrait à bloquer du travail, ce que le §17 refuse pour les jeux et qui
# vaut ici pour la même raison.
#
# « adulte » n'y est pas non plus, et c'est délibéré. C'est une **garde** au
# sens du §11.10, qui se tient avec un budget hebdomadaire et jamais avec un
# objectif à zéro. L'y mettre changerait la mécanique, et écrirait en clair dans
# un fichier lisible par n'importe qui sur la machine une liste que le §11.10
# refuse de faire sortir où que ce soit — y compris dans une notification.
CATEGORIES_FERMEES = ("scroll_passif", "reseaux")


# --------------------------------------------------------------------------
# La liste, et le fichier
# --------------------------------------------------------------------------

def domaines_a_fermer(categories: dict[str, list[str]]) -> list[str]:
    """Les domaines des catégories fermées, et **seulement** ceux-là.

    Un fichier hosts ne connaît que des noms d'hôtes : il ne sait pas fermer un
    chemin. ``youtube.com/shorts`` est donc écarté ici, et c'est heureux —
    l'écrire sans son chemin fermerait YouTube en entier, ce que le §9.1
    interdit explicitement. Les noms d'exécutables le sont aussi : ``steam.exe``
    n'est pas un domaine.
    """
    domaines: list[str] = []
    for categorie in CATEGORIES_FERMEES:
        for fragment in categories.get(categorie, []):
            nom = fragment.strip().lower()
            if "/" in nom or nom.endswith(".exe") or "." not in nom:
                continue
            if nom not in domaines:
                domaines.append(nom)
    return domaines


def retirer(contenu: str) -> str:
    """Le fichier sans le bloc du coach. Sans effet s'il n'y en a pas.

    Tout se joue sur les marqueurs : ce qui est entre eux nous appartient, le
    reste ne nous regarde pas. Un blocage qui réécrirait le fichier entier
    effacerait les lignes que l'utilisateur y a mises lui-même, et personne ne
    s'en apercevrait avant que quelque chose d'autre casse.
    """
    lignes = contenu.splitlines()
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

    texte = "\n".join(sortie).rstrip("\n")
    return texte + "\n" if texte else ""


def rendre(contenu: str, domaines: list[str]) -> str:
    """Le fichier avec le bloc du coach, remplaçant celui qui s'y trouvait.

    Idempotent : appliquer deux fois le même blocage rend le même fichier.
    """
    base = retirer(contenu)
    if not domaines:
        return base

    lignes = [MARQUEUR_DEBUT]
    for domaine in domaines:
        lignes.append(f"0.0.0.0 {domaine}")
        if not domaine.startswith("www."):
            lignes.append(f"0.0.0.0 www.{domaine}")
    lignes.append(MARQUEUR_FIN)

    return base + "\n".join(lignes) + "\n"


def appliquer_au_fichier(domaines: list[str], *, bloquer: bool) -> bool:
    """Écrit le fichier hosts. Rend ``False`` si les droits manquent.

    N'écrit pas si le contenu ne change pas : le fichier hosts est surveillé par
    les antivirus, et le réécrire toutes les dix minutes pour rien finit par
    ressembler à ce contre quoi ils existent.
    """
    try:
        contenu = HOSTS.read_text(encoding="utf-8", errors="replace")
    except OSError as erreur:
        print(f"Fichier hosts illisible : {erreur}", file=sys.stderr)
        return False

    voulu = rendre(contenu, domaines) if bloquer else retirer(contenu)
    if voulu == contenu:
        return True

    try:
        HOSTS.write_text(voulu, encoding="utf-8")
    except PermissionError:
        print(
            "Droits insuffisants sur le fichier hosts. Le service doit tourner élevé "
            "(voir README) ; l'agent, lui, ne doit surtout pas l'être.",
            file=sys.stderr,
        )
        return False
    except OSError as erreur:
        print(f"Écriture impossible : {erreur}", file=sys.stderr)
        return False

    # Sans purge, Windows garde la résolution précédente en cache et le blocage
    # ne prend qu'au bout de plusieurs minutes — donc trop tard pour le soir où
    # il sert.
    subprocess.run(
        ["ipconfig", "/flushdns"], capture_output=True, timeout=15, check=False
    )
    return True


# --------------------------------------------------------------------------
# Le tube local
# --------------------------------------------------------------------------

def envoyer(ordre: str) -> bool:
    """Envoie un ordre au service. Rend ``False`` s'il n'écoute pas.

    Un service absent n'est pas une erreur : c'est l'état de la machine tant
    qu'il n'a pas été installé, et l'agent doit continuer sans lui.
    """
    if ordre not in ORDRES:
        raise ValueError(f"ordre inconnu : {ordre!r}")

    try:
        with open(TUBE, "w", encoding="ascii") as tube:
            tube.write(ordre)
    except OSError:
        return False
    return True


def servir() -> int:
    """La boucle du service. À lancer élevé, et à ne jamais faire faire à l'agent.

    Le tube est en mode message et refuse les clients distants. Il n'accepte que
    deux mots ; tout le reste est ignoré sans être exécuté ni journalisé
    ailleurs qu'à l'écran. C'est ce qui rend le compromis acceptable : la
    surface d'attaque d'un service élevé se mesure à ce qu'il accepte, et celui-
    ci accepte deux chaînes de cinq et sept lettres.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    PIPE_ACCESS_DUPLEX = 0x00000003
    PIPE_TYPE_MESSAGE = 0x00000004
    PIPE_READMODE_MESSAGE = 0x00000002
    PIPE_WAIT = 0x00000000
    PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    categories = _categories()
    domaines = domaines_a_fermer(categories)
    print(f"Service de blocage : {len(domaines)} domaine(s) sous la main, tube {TUBE}.")

    while True:
        tube = kernel32.CreateNamedPipeW(
            TUBE,
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
            1,          # une seule instance : il n'y a qu'un agent
            256,
            256,
            0,
            None,
        )
        if tube == INVALID_HANDLE_VALUE:
            print(f"Tube impossible à créer (erreur {ctypes.get_last_error()}).", file=sys.stderr)
            return 1

        if not kernel32.ConnectNamedPipe(tube, None) and ctypes.get_last_error() != 535:
            kernel32.CloseHandle(tube)      # 535 = le client était déjà là
            continue

        tampon = ctypes.create_string_buffer(256)
        lus = wintypes.DWORD(0)
        ok = kernel32.ReadFile(tube, tampon, 256, ctypes.byref(lus), None)
        kernel32.DisconnectNamedPipe(tube)
        kernel32.CloseHandle(tube)

        if not ok:
            continue

        ordre = tampon.raw[: lus.value].decode("ascii", errors="replace").strip()
        if ordre not in ORDRES:
            print(f"Ordre refusé : {ordre!r}")
            continue

        applique = appliquer_au_fichier(domaines, bloquer=ordre == "block")
        print(f"{ordre} : {'appliqué' if applique else 'échoué'}.")


# --------------------------------------------------------------------------
# La pause, et le pilotage depuis l'agent
# --------------------------------------------------------------------------

def en_pause(*, maintenant: datetime | None = None) -> bool:
    """Vrai tant que la levée manuelle court."""
    maintenant = maintenant or datetime.now(timezone.utc)
    try:
        jusqua = datetime.fromisoformat(PAUSE_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return maintenant < jusqua


def lever() -> int:
    """Les deux clics et les soixante secondes du §8.5.

    L'attente est le mécanisme, pas un délai technique : elle laisse passer
    l'impulsion. Ce qui est interdit, c'est de la rendre impossible à purger —
    un blocage qu'on ne peut pas lever se contourne par le navigateur d'à côté,
    et l'outil finit désinstallé le jour où il gêne pour de bon.
    """
    print(f"Levée du blocage dans {ATTENTE_SECONDES} secondes. Ctrl+C pour annuler.")
    try:
        for restant in range(ATTENTE_SECONDES, 0, -1):
            print(f"  {restant:>2} s…", end="\r", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nAnnulé. Le blocage reste en place.")
        return 1

    jusqua = datetime.now(timezone.utc) + PAUSE
    PAUSE_PATH.write_text(jusqua.isoformat(), encoding="utf-8")
    envoyer("unblock")
    print(f"\nLevé jusqu'à {jusqua.astimezone().strftime('%Hh%M')}.")
    return 0


def synchroniser(etat: dict) -> str | None:
    """Aligne le fichier hosts sur l'état du serveur. Rend l'ordre envoyé.

    Appelée à chaque cycle de l'agent. Rend ``None`` quand il n'y a rien à
    faire — service absent, ou état illisible.
    """
    bloc = (etat or {}).get("block_scroll") or {}
    if "armed" not in bloc:
        return None

    arme = bool(bloc["armed"]) and not en_pause()
    ordre = "block" if arme else "unblock"
    return ordre if envoyer(ordre) else None


def _categories() -> dict[str, list[str]]:
    """La table locale, base et surcouche. Dupliquée de l'agent à dessein.

    Le service tourne élevé : lui faire importer ``agent.py`` — donc ses
    dépendances, ses profils de lancement et son client HTTP — étendrait la
    surface élevée à tout ce que l'agent sait faire. Vingt lignes de lecture de
    TOML sont moins chères que ça.
    """
    fusion: dict[str, list[str]] = {}
    for nom in ("categories.toml", "categories.local.toml"):
        chemin = Path(__file__).with_name(nom)
        if not chemin.exists():
            continue
        with chemin.open("rb") as handle:
            table = tomllib.load(handle).get("categories", {})
        for categorie, fragments in table.items():
            connus = fusion.setdefault(categorie, [])
            connus.extend(f for f in fragments if f not in connus)
    return fusion


def main() -> int:
    parser = argparse.ArgumentParser(description="Blocage des domaines pleins (SPEC §8.5).")
    groupe = parser.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--service", action="store_true", help="La boucle élevée. Écoute le tube.")
    groupe.add_argument("--lever", action="store_true", help="Deux clics, soixante secondes.")
    groupe.add_argument("--liste", action="store_true", help="Montre les domaines qui seraient fermés.")
    args = parser.parse_args()

    if args.liste:
        for domaine in domaines_a_fermer(_categories()):
            print(domaine)
        return 0
    if args.lever:
        return lever()
    return servir()


if __name__ == "__main__":
    raise SystemExit(main())
