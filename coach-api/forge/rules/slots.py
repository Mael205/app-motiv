"""Attribution des slots actifs (SPEC §4.3).

Deux limites dures, pas une :

1. **Trois projets actifs au maximum.** Le cœur du dispositif anti-dispersion.
2. **Deux slots au maximum par domaine.** Trois projets de code dans les trois
   slots, c'est une seule vie déguisée en trois : les mêmes outils, la même
   posture, la même fatigue. La diversité n'est pas un confort, c'est ce qui
   permet à une soirée sans énergie de coder d'exister quand même.

La règle se vérifie au moment où un projet prend un slot. Elle ne déloge jamais
un projet déjà installé — une limite qui expulse rétroactivement serait une
sanction, et le §17 les interdit.
"""

from __future__ import annotations

from collections.abc import Iterable

MAX_ACTIVE = 3
MAX_PER_DOMAIN = 2

CODE = "code"
CORPS = "corps"
CREATIF = "creatif"
SAVOIR = "savoir"
PRATIQUE = "pratique"

DOMAINS = (CODE, CORPS, CREATIF, SAVOIR, PRATIQUE)

DOMAIN_LABELS = {
    CODE: "Code",
    CORPS: "Corps",
    CREATIF: "Créatif",
    SAVOIR: "Savoir",
    PRATIQUE: "Pratique",
}


def assign_slot(taken: Iterable[tuple[int, str]], domain: str) -> int | None:
    """Le slot qu'un projet de ce domaine peut prendre, ou rien.

    ``taken`` est la liste des ``(slot, domaine)`` déjà actifs. Rendre ``None``
    n'est pas une erreur : l'appelant envoie le projet au frigo.
    """
    taken = list(taken)
    used = {slot for slot, _ in taken}
    if len(used) >= MAX_ACTIVE:
        return None
    if sum(1 for _, d in taken if d == domain) >= MAX_PER_DOMAIN:
        return None
    return next((slot for slot in range(1, MAX_ACTIVE + 1) if slot not in used), None)


def refused_reason(taken: Iterable[tuple[int, str]], domain: str) -> str | None:
    """Pourquoi le projet n'a pas trouvé de slot. Factuel, sans reproche."""
    taken = list(taken)
    if len({slot for slot, _ in taken}) >= MAX_ACTIVE:
        return "Les trois slots sont pris. Le projet part au frigo, l'échange se fait le dimanche."
    same = sum(1 for _, d in taken if d == domain)
    if same >= MAX_PER_DOMAIN:
        label = DOMAIN_LABELS.get(domain, domain)
        return (
            f"Deux slots sont déjà en « {label} », et c'est le maximum. "
            "Le projet part au frigo : le troisième slot est réservé à un autre domaine."
        )
    return None


def saturated_domains(taken: Iterable[tuple[int, str]]) -> list[str]:
    """Domaines qui ont atteint leur plafond. Sert à expliquer avant de refuser."""
    counts: dict[str, int] = {}
    for _, domain in taken:
        counts[domain] = counts.get(domain, 0) + 1
    return sorted(d for d, n in counts.items() if n >= MAX_PER_DOMAIN)


def breaches_diversity(taken: Iterable[tuple[int, str]]) -> str | None:
    """Un domaine occupe-t-il déjà plus que son plafond ?

    Ne se produit que sur des données antérieures à la règle : elle s'affiche
    comme un constat, elle ne déloge personne.
    """
    counts: dict[str, int] = {}
    for _, domain in taken:
        counts[domain] = counts.get(domain, 0) + 1
    over = [d for d, n in counts.items() if n > MAX_PER_DOMAIN]
    return over[0] if over else None
