"""Le canal entrant : ce qu'un lien signé permet de faire (SPEC §11.7, §4.7, §5.3).

Tout ce qui sort du coach a un canal — Web Push, Discord, notification Windows.
Rien n'y rentre. Un webhook ne reçoit pas, et le bot Telegram qui devait servir
de porte d'entrée a été remplacé par des canaux qui ne parlent que dans un sens.

Trois mécaniques écrites dans la spec s'en trouvaient bloquées : l'accusé de
lecture du bilan de l'ami (§4.7), les questions de la revue du dimanche (§5.3),
et la capture d'une idée sans ouvrir l'app (§11.7). Un lien les débloque toutes
les trois, sans compte à créer et sans application à installer.

**Trois règles tenues ici, et pas ailleurs :**

1. *Un lien fait une chose.* Le geste est décidé à l'émission, pas par celui qui
   clique. Il n'y a donc aucun paramètre à valider qui pourrait en changer.
2. *Un lien ne lit rien.* La page qu'il ouvre montre ce que le lien porte, et
   jamais ce qu'il y a en base. Un lien de bilan ne dit pas l'état du streak, un
   lien de frigo ne liste pas les idées déjà jetées — un lien qui fuit ne doit
   rien apprendre à personne.
3. *Cliquer deux fois ne casse rien.* Une messagerie qui pré-charge les liens,
   un ami qui rafraîchit : le second passage doit dire « déjà fait », pas
   « erreur ».
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import ActionLink, FridgeIdea

# Combien de temps un lien reste valable, selon ce qu'il sert à faire. La durée
# n'est pas cosmétique : un lien de bilan qui traîne un an dans une boîte
# Discord est un secret qui traîne un an.
TTL_JOURS = {
    ActionLink.VU: 30,
    ActionLink.REPONSE: 14,
    ActionLink.FRIGO: 365,        # celui-là est un raccourci, on le garde
}

# Un frigo se remplit plusieurs fois avec le même lien : c'est un marque-page,
# pas un ticket. Les deux autres se consomment.
USAGES = {ActionLink.FRIGO: 500, ActionLink.VU: 1, ActionLink.REPONSE: 1}

MAX_TEXTE = 2000


def emettre(user, *, kind: str, context: dict | None = None) -> tuple[ActionLink, str]:
    """Crée un lien de ce type, avec la durée et le nombre d'usages qui vont avec."""
    return ActionLink.issue(
        user,
        kind=kind,
        context=context,
        max_uses=USAGES.get(kind, 1),
        ttl_days=TTL_JOURS.get(kind, 30),
    )


def resoudre(token: str) -> ActionLink | None:
    """Le lien correspondant au secret, ou ``None``.

    Aucune distinction entre « inconnu » et « expiré » n'est faite ici : c'est
    l'appelant qui décide quoi en dire, et la page dit la même chose dans les
    deux cas.
    """
    if not token:
        return None
    return ActionLink.objects.filter(token_hash=ActionLink.hash_of(token)).first()


def presenter(lien: ActionLink) -> dict:
    """Ce que la page affiche. Uniquement ce que le lien porte lui-même."""
    return {
        "kind": lien.kind,
        "titre": _titre(lien),
        "question": lien.context.get("question", ""),
        "fait": lien.spent,
        "expire": lien.expired,
        "utilisable": lien.usable,
    }


def _titre(lien: ActionLink) -> str:
    if lien.kind == ActionLink.VU:
        return lien.context.get("titre") or "Bilan de la semaine"
    if lien.kind == ActionLink.REPONSE:
        return "Une question"
    return "Au frigo"


@transaction.atomic
def consommer(lien: ActionLink, *, texte: str = "") -> dict:
    """Applique le geste du lien. Rend ce que la page doit dire ensuite.

    Verrouille la ligne : deux clics simultanés — le pré-chargement d'une
    messagerie et l'ami qui clique — ne doivent pas compter deux usages ni créer
    deux idées.
    """
    lien = ActionLink.objects.select_for_update().get(pk=lien.pk)

    if lien.expired:
        return {"ok": False, "message": "Ce lien a expiré."}
    if lien.spent:
        return {"ok": True, "message": _deja(lien)}

    texte = (texte or "").strip()[:MAX_TEXTE]

    if lien.kind == ActionLink.FRIGO:
        if not texte:
            return {"ok": False, "message": "Écris quelque chose."}
        FridgeIdea.objects.create(user=lien.user, text=texte, source="lien")
        # Le frigo garde son lien utilisable : c'est un raccourci qu'on épingle.
        lien.uses += 1
        lien.last_used_at = timezone.now()
        lien.save(update_fields=["uses", "last_used_at"])
        return {"ok": True, "message": "Au frigo. Tu le retrouveras dimanche."}

    if lien.kind == ActionLink.REPONSE:
        if not texte:
            return {"ok": False, "message": "Écris quelque chose."}
        lien.answer = texte

    lien.uses = lien.max_uses
    lien.last_used_at = timezone.now()
    lien.save(update_fields=["answer", "uses", "last_used_at"])

    if lien.kind == ActionLink.VU:
        _marquer_lu(lien)
        return {"ok": True, "message": "Merci. C'est noté comme lu."}

    return {"ok": True, "message": "Reçu."}


def _deja(lien: ActionLink) -> str:
    if lien.kind == ActionLink.VU:
        return "Déjà marqué comme lu."
    return "Déjà envoyé."


def _marquer_lu(lien: ActionLink) -> None:
    """Note la lecture sur le bilan visé, s'il y en a un.

    Le lien ne sait rien du bilan au-delà de son identifiant, et ne peut rien en
    lire : il pose une date, c'est tout. C'est ce qui permet de l'envoyer à
    quelqu'un d'autre sans lui ouvrir quoi que ce soit (§4.7).
    """
    identifiant = lien.context.get("bilan_id")
    if not identifiant:
        return

    from .models import WeeklyReport

    WeeklyReport.objects.filter(pk=identifiant, read_at__isnull=True).update(
        read_at=timezone.now()
    )
