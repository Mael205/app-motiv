"""Les pages servies par le serveur lui-même.

Il n'y en a qu'une, et elle est là pour une raison précise : la page d'un lien
signé (§11.7) doit s'ouvrir **sans compte, sans application installée et sans
JavaScript de l'app**. L'ami du §4.7 reçoit un lien dans un message et clique ;
lui faire charger la PWA, se connecter et attendre un rendu React pour appuyer
sur un bouton « vu » serait le meilleur moyen qu'il ne le fasse jamais.

D'où une page autonome, un formulaire, une redirection. Elle fonctionne sur un
téléphone en 3G, dans le navigateur intégré d'une messagerie, et sans le
serveur de développement du front.
"""

from __future__ import annotations

from django.shortcuts import render

from . import links


def action_link_page(request, token: str):
    """La page d'un lien : une phrase, un champ s'il en faut un, un bouton."""
    lien = links.resoudre(token)
    if lien is None:
        return render(request, "forge/lien.html", {"introuvable": True}, status=404)

    if request.method == "POST":
        resultat = links.consommer(lien, texte=request.POST.get("texte", ""))
        return render(
            request,
            "forge/lien.html",
            {"vue": links.presenter(lien), "resultat": resultat},
            status=200 if resultat["ok"] else 400,
        )

    return render(request, "forge/lien.html", {"vue": links.presenter(lien)})
