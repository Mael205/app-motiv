"""Les quêtes du jour et de la semaine (SPEC §4.4).

Trois lignes, jamais plus : une **quête plancher** — celle qui valide la journée
et qui est déjà l'objectif du soir —, une **quête bonus** contextuelle, et une
**quête hebdomadaire** posée le dimanche.

Deux décisions structurent tout le reste.

**Elles paient en Éclats, jamais en XP.** L'XP mesure le travail réel : une
minute travaillée vaut une minute, et rien d'autre n'en produit. Une quête qui
donnerait de l'XP ferait payer deux fois la même session, et le §4.4 est
explicite — aucune récompense ne donne d'XP sans travail réel. Les Éclats sont
la monnaie du cosmétique : elles peuvent récompenser un comportement sans
déformer la mesure. C'est déjà la règle des routines du §11.9.

**Elles sont contextuelles, pas aléatoires.** La quête bonus est choisie parmi
des candidates dont la condition est *actuellement vraie* — proposer « termine
une étape » à quelqu'un dont l'étape courante en est à sa première session est
une quête décorative, et une quête décorative apprend à ignorer les quêtes. Le
tirage est ensuite figé par la date : rafraîchir l'accueil ne rebat pas les
cartes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

PLANCHER, BONUS, HEBDO = "plancher", "bonus", "hebdo"

# Les Éclats d'une quête, calibrés sur les routines : quelques-uns par geste, un
# peu plus pour la semaine. Assez pour être noté, trop peu pour valoir une
# soirée de travail — sinon on optimise la quête au lieu du projet.
ECLATS_BONUS = 15
ECLATS_HEBDO = 60


@dataclass(frozen=True)
class Quete:
    kind: str
    code: str
    label: str
    target: int
    reward_shards: int


@dataclass(frozen=True)
class Contexte:
    """Les faits du jour, tels que le serveur les connaît déjà."""

    plancher_minutes: int
    avant_vingt_heures: bool          # la fenêtre du soir commence-t-elle avant 20h
    etape_presque_finie: bool         # une étape en cours depuis au moins une session
    projet_en_retard: str             # le projet le plus en retard sur son engagement, ou ""
    routines_du_jour: int
    corps_actif: bool
    engagements_pris: int
    jours_valides_semaine: int


def du_jour(contexte: Contexte, *, jour: date) -> list[Quete]:
    """La quête plancher et, si une candidate est vraie, la quête bonus."""
    quetes = [
        Quete(
            kind=PLANCHER,
            code="plancher",
            label=f"Une session de {contexte.plancher_minutes} minutes",
            target=1,
            # Zéro : la quête plancher est déjà payée par la session elle-même.
            # La doubler reviendrait à récompenser le fait de lire l'objectif.
            reward_shards=0,
        )
    ]

    bonus = _bonus(contexte, jour=jour)
    if bonus:
        quetes.append(bonus)
    return quetes


def _bonus(contexte: Contexte, *, jour: date) -> Quete | None:
    candidates: list[Quete] = []

    if contexte.avant_vingt_heures:
        candidates.append(
            Quete(BONUS, "avant_20h", "Démarrer une session avant 20h", 1, ECLATS_BONUS)
        )
    if contexte.etape_presque_finie:
        candidates.append(
            Quete(BONUS, "etape", "Terminer une étape de roadmap", 1, ECLATS_BONUS)
        )
    if contexte.projet_en_retard:
        candidates.append(
            Quete(
                BONUS,
                "retard",
                f"Une session sur {contexte.projet_en_retard}",
                1,
                ECLATS_BONUS,
            )
        )
    if contexte.routines_du_jour:
        candidates.append(
            Quete(
                BONUS,
                "routines",
                f"Cocher les {contexte.routines_du_jour} routines du jour",
                contexte.routines_du_jour,
                ECLATS_BONUS,
            )
        )
    if contexte.corps_actif:
        candidates.append(Quete(BONUS, "corps", "Une séance sur la piste Corps", 1, ECLATS_BONUS))

    if not candidates:
        return None

    # Figé par la date : rafraîchir l'accueil ne rebat pas les cartes, et la
    # quête du soir reste la même qu'à 18h.
    return candidates[jour.toordinal() % len(candidates)]


def de_la_semaine(contexte: Contexte, *, jour: date) -> Quete | None:
    """La quête hebdomadaire, posée le dimanche pour la semaine qui vient (§4.4).

    Plus ambitieuse, mais toujours adossée à ce qui est déjà promis : tenir ses
    engagements, ou valider cinq jours. Une quête hebdo qui demanderait autre
    chose que le contrat mettrait deux objectifs en concurrence, et c'est le
    contrat qui perdrait.
    """
    if contexte.engagements_pris:
        return Quete(
            HEBDO,
            "engagements",
            f"Tenir tes {contexte.engagements_pris} engagements de la semaine",
            contexte.engagements_pris,
            ECLATS_HEBDO,
        )
    return Quete(HEBDO, "cinq_jours", "Valider cinq journées cette semaine", 5, ECLATS_HEBDO)
