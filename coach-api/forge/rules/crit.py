"""Le coup critique (SPEC §12, ajout du 17 août 2026).

Une session sur dix rapporte le double d'XP. C'est la seule récompense
**variable** du système, et elle est posée là pour une raison précise : tout le
reste est calculable à l'avance. Une soirée de 25 minutes vaut exactement le
même nombre de points que la précédente, et un barème entièrement prévisible
finit par ne plus rien signaler du tout — c'est le diagnostic du §0.2 appliqué
à la récompense elle-même.

Trois garde-fous, et chacun répond à une façon connue de faire d'un critique un
problème.

**Il ne double que l'XP.** Ni les minutes, ni les dégâts au boss, ni les
compteurs de la trace. Les minutes mesurent le travail et servent de base à la
comparaison au fantôme (§12.7) ; les doubler ferait gagner une course sur un
tirage. L'XP, elle, ne mesure rien d'autre qu'elle-même : elle porte déjà des
multiplicateurs de streak, de momentum et de modificateur, et un de plus ne
change pas sa nature.

**Il ne s'applique qu'à du travail réellement payé.** Une session au-delà du
plafond de régime rapporte zéro (§0.2) ; annoncer un critique sur zéro serait
un mensonge, et un mensonge qui se voit — le double de rien est rien. On ne
tire donc pas du tout dans ce cas.

**Il a une pitié, et pas de mémoire courte.** À probabilité fixe, vingt sessions
sans critique sont banales et se lisent comme un truquage. Au vingtième tirage
sec, il tombe. Le compteur se recalcule depuis les sessions déjà closes, jamais
depuis un champ incrémenté : un compteur qui dérive dérègle la pitié, donc
produit exactement la sensation de triche qu'elle devait empêcher.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

CHANCE = 0.10
MULTIPLIER = 2
PITY = 20                 # sessions payées d'affilée sans critique

LABEL = "Coup critique"
LINE = "Coup critique — XP doublée."
LINE_PITY = "Coup critique — vingt sessions qu'il se faisait attendre."


@dataclass(frozen=True)
class Crit:
    """Le résultat du tirage, prêt à graver dans le détail de la session."""

    hit: bool
    multiplier: int
    forced: bool
    xp_before: int
    xp_after: int

    @property
    def bonus(self) -> int:
        return self.xp_after - self.xp_before

    @property
    def line(self) -> str:
        if not self.hit:
            return ""
        return LINE_PITY if self.forced else LINE


def roll(
    *,
    xp: int,
    draws_since_crit: int,
    rng: random.Random | None = None,
) -> Crit:
    """Tire le critique d'une session close.

    ``draws_since_crit`` compte les sessions **payées** depuis le dernier
    critique. Les sessions à zéro XP n'y entrent pas : elles n'ont pas tiré,
    donc elles ne rapprochent pas de la pitié.
    """
    if xp <= 0:
        return Crit(hit=False, multiplier=1, forced=False, xp_before=xp, xp_after=xp)

    forced = draws_since_crit >= PITY
    hit = forced or (rng or random).random() < CHANCE

    return Crit(
        hit=hit,
        multiplier=MULTIPLIER if hit else 1,
        forced=forced,
        xp_before=xp,
        xp_after=xp * MULTIPLIER if hit else xp,
    )
