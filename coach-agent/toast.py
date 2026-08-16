"""Notifications Windows natives (SPEC §8.6).

Le §1 exige des notifications natives sur les deux surfaces : Web Push sur le
téléphone, natives sur Windows via l'agent. Le canal compte autant que le
contenu — le §0.1 dit que la contrainte interne n'existe pas, donc un rappel
qui n'apparaît que dans un onglet fermé ne rappelle rien.

L'implémentation passe par PowerShell et l'API de notification de Windows,
**sans dépendance à installer**. Les bibliothèques Python de toast tirent des
paquets supplémentaires pour le même résultat, et chaque dépendance est une
raison de plus pour que l'agent ne démarre pas un soir.

Une notification qui échoue n'est jamais fatale : l'agent continue. Perdre un
rappel est ennuyeux, arrêter la sonde à cause d'un rappel serait pire.
"""

from __future__ import annotations

import subprocess

# L'identifiant d'application doit exister dans le menu Démarrer, sinon Windows
# refuse silencieusement d'afficher le toast. Celui de PowerShell est présent
# sur toutes les installations.
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($env:COACH_TOAST_XML)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:COACH_TOAST_APPID).Show($toast)
"""


def _escape(texte: str) -> str:
    return (
        texte.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_xml(title: str, body: str) -> str:
    """Le XML du toast. Séparé de l'envoi pour être testable sans afficher."""
    return (
        "<toast><visual><binding template='ToastText02'>"
        f"<text id='1'>{_escape(title)}</text>"
        f"<text id='2'>{_escape(body)}</text>"
        "</binding></visual></toast>"
    )


def show(title: str, body: str, *, timeout: int = 15) -> bool:
    """Affiche une notification. Rend ``False`` en cas d'échec, sans lever.

    Le XML passe par l'environnement plutôt que par la ligne de commande : un
    titre contenant une apostrophe ou un guillemet casserait le script, et les
    messages du coach en contiennent tout le temps.
    """
    import os

    env = dict(os.environ)
    env["COACH_TOAST_XML"] = build_xml(title, body)
    env["COACH_TOAST_APPID"] = APP_ID

    try:
        resultat = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", SCRIPT],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return resultat.returncode == 0
