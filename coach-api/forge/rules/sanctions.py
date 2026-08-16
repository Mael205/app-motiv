"""Le prix du décrochage (SPEC §14).

Le streak et les boucliers empêchent l'effondrement, mais rater un jour ne
coûtait presque rien, et un système sans coût n'est pas un cadre. Ce module dit
ce qui s'éteint, et rien d'autre : il ne calcule pas le streak — il le lit.

**Les quatre invariants, qui décident de toute la forme du module :**

1. *Réparable en dix minutes.* Toute sanction de palier 1 s'annule par une
   seule session dégradée. C'est pourquoi presque tout ici est conditionné à
   ``validated_today`` : la réparation est immédiate, pas datée du lendemain.
2. *Jamais rétroactive.* Rien ne retire d'XP, d'heures, d'étapes ni de rang. La
   seule chose qui parte pour de bon est une part de la mise (§12.6), et c'est
   assumé comme le seul coût irréversible du produit.
3. *Jamais morale.* ``lines()`` rend des constats chiffrés. Un test tient cette
   promesse, parce qu'elle se perd au premier message écrit à la va-vite.
4. *Jamais sociale.* Rien ici ne sort de l'app.

Le palier 3 est le point où le registre change : au-delà de trois jours, punir
davantage serait le meilleur moyen de faire désinstaller. Rien ne s'ajoute, et
l'accueil devient une rampe de retour.
"""

from __future__ import annotations

from dataclasses import dataclass

# Paliers, tels que le §14 les nomme.
TERNE = 1           # un jour raté : l'interface s'éteint, la vitrine ferme
CASSE = 2           # deux jours d'affilée : dette, sursis, mise entamée
DECROCHAGE = 3      # trois jours et plus : plus rien ne s'ajoute

# Trois journées validées d'affilée rendent le titre. Le même nombre que le
# palier de décrochage, et ce n'est pas un hasard : ce qu'il a fallu pour
# perdre le titre est ce qu'il faut pour le reprendre.
TITLE_REPRIEVE_DAYS = 3

# Part de la mise qui part au premier streak cassé de la saison (§12.6).
STAKE_FORFEIT_RATIO = 0.25

# Au-delà, l'app propose de clore la saison en avance. La porte de sortie est
# offerte avant qu'elle soit inventée sous forme de désinstallation.
SEASON_EXIT_AFTER_DAYS = 5


@dataclass(frozen=True)
class Sanctions:
    """Ce qui est éteint en ce moment. Un état de fait, jamais un verdict."""

    level: int
    showcase_locked: bool = False
    relax_revoked: bool = False
    slots_frozen: bool = False
    early_block: bool = False
    title_reprieve: bool = False
    comeback: bool = False
    season_exit_offered: bool = False
    debt_minutes: int = 0
    day_validated: bool = False

    @property
    def active(self) -> bool:
        return self.level > 0 or self.title_reprieve or self.debt_minutes > 0


def evaluate(
    *,
    missed_run: int,
    current_streak: int,
    broken_once: bool,
    validated_today: bool,
    debt_minutes: int = 0,
) -> Sanctions:
    """Traduit un état de streak en sanctions actives.

    ``missed_run`` est le nombre de jours ratés d'affilée, **non plafonné** :
    les paliers s'arrêtent à 3, mais la porte de sortie du §14 s'ouvre au
    cinquième jour et ne saurait donc pas se lire sur un compteur écrêté.

    Il se lit sur les jours **révolus** : la journée en cours n'est jamais
    ratée tant qu'elle n'est pas finie. ``validated_today`` est donc la
    réparation, pas une exception.

    Deux sanctions ne s'éteignent pas avec la session du jour, et c'est
    délibéré :

    * la **dette** *est* le seuil de la journée en cours — l'annuler dès la
      première minute reviendrait à ne pas l'avoir ;
    * le **sursis du titre** demande trois journées d'affilée, parce qu'un
      titre repris en une soirée n'aurait pas été en sursis.
    """
    level = min(max(0, missed_run), DECROCHAGE)
    en_cours = level > 0 and not validated_today

    return Sanctions(
        level=level,
        # Palier 1 — tout est éteint, rien n'est cassé.
        showcase_locked=en_cours and level >= TERNE,
        relax_revoked=en_cours and level >= TERNE,
        # Palier 2 — les droits gagnés se gèlent, ils ne se reprennent pas.
        slots_frozen=en_cours and level >= CASSE,
        early_block=en_cours and level >= CASSE,
        debt_minutes=max(0, debt_minutes),
        title_reprieve=broken_once and current_streak < TITLE_REPRIEVE_DAYS,
        # Palier 3 — le registre change : plus aucune sanction, une rampe.
        comeback=en_cours and level >= DECROCHAGE,
        season_exit_offered=en_cours and missed_run > SEASON_EXIT_AFTER_DAYS,
        day_validated=validated_today,
    )


def stake_forfeit(stake: int, breaks: int) -> int:
    """Part de la mise engagée qui ne revient pas, après ``breaks`` cassures.

    Chaque cassure entame un quart de la mise **d'origine**, jamais un quart du
    reste : sur un solde qui fond, les cassures suivantes coûteraient de moins
    en moins, et une sanction qui s'adoucit à mesure qu'on décroche fait
    exactement l'inverse de ce qu'on lui demande. Le total est plafonné à la
    mise — on ne peut pas devoir plus qu'on n'a engagé.
    """
    if stake <= 0 or breaks <= 0:
        return 0
    return min(stake, breaks * round(stake * STAKE_FORFEIT_RATIO))


def lines(
    sanctions: Sanctions,
    *,
    boss_regen_minutes: int = 0,
    shards_forfeited: int = 0,
    frozen_slots: int = 0,
) -> list[str]:
    """Ce qui s'affiche. Des faits chiffrés, dans l'unité qui compte.

    Le §14 exige que le coût du boss soit dit *"Le boss a récupéré 45 min de
    vie"* et pas en points : une saison se vit en minutes, et un chiffre qu'on
    ne sait pas convertir n'est pas une sanction, c'est une décoration.
    """
    dits: list[str] = []

    if sanctions.comeback:
        # Palier 3 : on ne récite pas ce qui est éteint. Le §14 l'interdit
        # explicitement — un bilan de ce qui a été perdu est ce qui fait fermer
        # l'app pour de bon.
        return dits

    if sanctions.showcase_locked:
        dits.append("Vitrine fermée jusqu'à la prochaine session.")
    if boss_regen_minutes:
        dits.append(f"Le boss a récupéré {boss_regen_minutes} min de vie.")
    if sanctions.relax_revoked:
        dits.append("Sas de détente indisponible ce soir.")
    if sanctions.debt_minutes and not sanctions.day_validated:
        # La dette est un objectif pour ce soir, pas un solde à traîner. La
        # rappeler à quelqu'un qui vient de poser sa session en ferait une
        # remarque, et le §14 n'en veut aucune.
        dits.append(f"Dette de {sanctions.debt_minutes} min sur la journée.")
    if sanctions.slots_frozen and frozen_slots:
        dits.append(
            f"{frozen_slots} slot{'s' if frozen_slots > 1 else ''} gelé"
            f"{'s' if frozen_slots > 1 else ''} jusqu'à la reprise."
        )
    if shards_forfeited and sanctions.level >= CASSE:
        # Seulement le soir où la cassure a lieu. Le prélèvement est définitif,
        # donc il n'est jamais « éteint » : le répéter chaque soir jusqu'à la fin
        # de la saison en ferait un reproche permanent pour un fait déjà réglé.
        # Le compte définitif vit sur la mise de la saison, qui l'affiche en
        # moins, et dans le bilan de clôture.
        dits.append(f"Mise entamée : {shards_forfeited} Éclats en moins.")
    if sanctions.title_reprieve:
        dits.append(
            f"Titre en sursis. {TITLE_REPRIEVE_DAYS} journées validées d'affilée le rendent."
        )

    return dits
